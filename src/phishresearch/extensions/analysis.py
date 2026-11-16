"""Exploratory extensions (D-40), computed on FIT/VAL only.

E1 baselines   Logistic Regression on all 37 features; one-feature rule "not HTTPS => phishing".
E2 ablation    v1 RF/LightGBM refit on FIT without F30 (is_https), same params and seeds.
E3 errors      slice error rates and fixed-rule FP/FN examples of the frozen ALL bundles.
E4 EDA         class-conditional feature differences per source (FIT).

Every model takes its f1_max threshold from SOURCE VAL; transfer is measured on TARGET VAL,
which no model of that direction has seen. TEST features/labels are never loaded here, and
records.parquet is read without its label column.
"""
from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from ..common import GateError, Paths, effective_threads, sha256_file, write_json
from ..features import FEATURE_IDS, FEATURE_NAMES
from ..freeze import verify_freeze
from ..models import MODELS, ModelBundle, fit_model, positive_scores
from ..prepare import load_dev
from ..statistics import compute_metrics, paired_cluster_bootstrap
from ..thresholds import choose_threshold

OTHER = {"A": "B", "B": "A"}
ABLATED = ("F30",)
NO_HTTPS = [f for f in FEATURE_IDS if f not in ABLATED]
EDA_FEATURES = ("F01", "F02", "F03", "F06", "F07", "F16", "F18", "F20", "F22", "F23", "F29", "F30", "F35", "F36")
# Pre-specified slices (D-40): name -> (feature, [(label, predicate)])
SLICES = {
    "https": ("F30", [("HTTPS", lambda v: v == 1), ("not HTTPS", lambda v: v == 0)]),
    "length": ("F01", [("<=40", lambda v: v <= 40), ("41-80", lambda v: (v > 40) & (v <= 80)), (">80", lambda v: v > 80)]),
    "subdomains": ("F23", [("0", lambda v: v == 0), ("1", lambda v: v == 1), (">=2", lambda v: v >= 2)]),
    "query": ("F29", [("no query", lambda v: v == 0), ("query", lambda v: v == 1)]),
}
N_EXAMPLES = 5


# ------------------------------------------------------------------ models
def fit_logreg(X: pd.DataFrame, y: np.ndarray):
    """Course baseline: log1p (all features are >= 0) -> standardise -> L2 logistic regression, C=1."""
    if (X.to_numpy() < 0).any():
        raise ValueError("log1p baseline expects non-negative features")
    m = make_pipeline(FunctionTransformer(np.log1p), StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))
    return m.fit(X.to_numpy(dtype=np.float64), y)


def https_rule_scores(X: pd.DataFrame) -> np.ndarray:
    """One-feature heuristic: score 1 when the URL is not HTTPS. Fixed threshold 0.5, nothing is fitted."""
    return 1.0 - X["F30"].to_numpy(dtype=np.float64)


def defang(url: str, max_len: int = 70) -> str:
    """Make a URL non-clickable for display; it is never opened or resolved (AGENTS.md rule 5)."""
    s = url.replace("https://", "hxxps://").replace("http://", "hxxp://").replace(".", "[.]")
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


# ------------------------------------------------------------------ analyses
def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Standardised mean difference (phishing - benign) with pooled SD; 0 when both are constant."""
    na, nb = len(a), len(b)
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    return float((a.mean() - b.mean()) / sp) if sp > 0 else 0.0


def eda(fit: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for f in EDA_FEATURES:
        row = {"feature": f, "name": FEATURE_NAMES[f]}
        for s, d in fit.items():
            ph, be = d.loc[d.label == 1, f].to_numpy(), d.loc[d.label == 0, f].to_numpy()
            row.update({f"{s}_benign_mean": float(be.mean()), f"{s}_phish_mean": float(ph.mean()),
                        f"{s}_benign_median": float(np.median(be)), f"{s}_phish_median": float(np.median(ph)),
                        f"{s}_d": cohens_d(ph, be)})
        rows.append(row)
    out = pd.DataFrame(rows)
    out["sign_agrees"] = np.sign(out["A_d"]) == np.sign(out["B_d"])
    out["abs_d_gap"] = (out["A_d"] - out["B_d"]).abs()
    return out


def slice_table(df: pd.DataFrame, y: np.ndarray, yhat: np.ndarray) -> pd.DataFrame:
    rows = []
    for sname, (feat, parts) in SLICES.items():
        v = df[feat].to_numpy()
        for lab, pred in parts:
            m = pred(v)
            yy, pp = y[m], yhat[m]
            neg, pos = int((yy == 0).sum()), int((yy == 1).sum())
            fp, fn = int(((yy == 0) & (pp == 1)).sum()), int(((yy == 1) & (pp == 0)).sum())
            rows.append({"slice": sname, "value": lab, "n": int(m.sum()), "share": float(m.mean()),
                         "prevalence": pos / max(neg + pos, 1), "fpr": fp / neg if neg else None,
                         "fnr": fn / pos if pos else None, "fp": fp, "fn": fn})
    return pd.DataFrame(rows)


def error_examples(df: pd.DataFrame, y: np.ndarray, s: np.ndarray, yhat: np.ndarray, urls: pd.Series) -> list[dict]:
    """Fixed rule: the N most confident false positives (highest score) and false negatives (lowest)."""
    out = []
    for kind, mask, asc in (("FP", (y == 0) & (yhat == 1), False), ("FN", (y == 1) & (yhat == 0), True)):
        idx = np.flatnonzero(mask)
        idx = idx[np.argsort(s[idx], kind="stable")]
        idx = idx[:N_EXAMPLES] if asc else idx[::-1][:N_EXAMPLES]
        for i in idx:
            out.append({"kind": kind, "score": float(s[i]), "url": defang(urls.iloc[i]),
                        "https": int(df["F30"].iloc[i]), "length": int(df["F01"].iloc[i]),
                        "subdomains": int(df["F23"].iloc[i])})
    return out


def top_error_domains(groups: pd.Series, y: np.ndarray, yhat: np.ndarray, n: int = 5) -> dict:
    e = pd.DataFrame({"g": groups.to_numpy(), "fp": (y == 0) & (yhat == 1), "fn": (y == 1) & (yhat == 0)})
    agg = e.groupby("g")[["fp", "fn"]].sum()
    return {k: {str(g): int(c) for g, c in agg[k].sort_values(ascending=False).head(n).items() if c > 0}
            for k in ("fp", "fn")}


# ------------------------------------------------------------------ driver
def _frozen_bundle(paths: Paths, frozen: dict, bid: str) -> ModelBundle:
    item = next(p for p in frozen["body"]["plan"] if p["bundle_id"] == bid)
    return ModelBundle.load(paths.root / item["bundle"], expected_sha256=frozen["body"]["file_hashes"][item["bundle"] + ".joblib"])


def _metrics(y, s, thr) -> dict:
    m = compute_metrics(y, s, thr)
    v = m["values"]
    return {"f1": v["f1"], "precision": v["precision"], "recall": v["recall"], "fpr": v["fpr"], "mcc": v["mcc"],
            "ap": v["average_precision"], "auc": v["roc_auc"], "threshold": thr}


def run_extensions(paths: Paths, cfg: dict) -> Path:
    frozen = verify_freeze(paths.freeze, paths.root)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = paths.artifacts / "extensions" / f"run_{stamp}_{uuid.uuid4().hex[:8]}"
    out.mkdir(parents=True)
    here = Path(__file__).parent
    manifest = {"status": "running", "decision": "D-40", "research_status": "exploratory extension of frozen v1",
                "parent_freeze_hash": frozen["freeze_hash"], "partitions_used": ["FIT", "VAL"],
                "test_features_read": False, "test_labels_read": False, "dataset_urls_opened": False,
                "code_sha256": {f"pkg/extensions/{p.name}": sha256_file(p) for p in sorted(here.glob("*.py"))}}
    write_json(out / "manifest.json", manifest)
    try:
        threads = effective_threads(cfg)
        seeds = list(cfg["models"]["seeds"])
        B, bseed = int(cfg["statistics"]["bootstrap_replicates"]), int(cfg["statistics"]["bootstrap_seed"])
        data = {s: {p: load_dev(paths, s, p) for p in ("FIT", "VAL")} for s in ("A", "B")}
        rec = pd.read_parquet(paths.processed / "records.parquet", columns=["record_id", "url_raw", "group_key"])
        rec = rec.set_index("record_id")

        # E4 -----------------------------------------------------------
        eda_tab = eda({s: data[s]["FIT"] for s in ("A", "B")})
        eda_tab.to_csv(out / "eda.csv", index=False)
        prevalence = {s: {p: float(data[s][p].label.mean()) for p in ("FIT", "VAL")} for s in ("A", "B")}

        rows, contrasts, slices, examples, domains = [], [], [], [], {}
        for src in ("A", "B"):
            tgt = OTHER[src]
            fit, sval, tval = data[src]["FIT"], data[src]["VAL"], data[tgt]["VAL"]
            y_fit, y_s, y_t = (d.label.to_numpy().astype(int) for d in (fit, sval, tval))
            preds = {}   # config -> list (per seed) of target-VAL and source-VAL binary predictions

            def record(config, model, seed, s_src, s_tgt, thr, kind):
                for ev, y, s in (("source_val", y_s, s_src), ("target_val", y_t, s_tgt)):
                    rows.append({"source": src, "target": tgt, "eval": ev, "config": config, "model": model,
                                 "seed": seed, "kind": kind, **_metrics(y, s, thr)})
                preds.setdefault(config, {"source_val": [], "target_val": []})
                preds[config]["source_val"].append((s_src >= thr).astype(int))
                preds[config]["target_val"].append((s_tgt >= thr).astype(int))

            # E1: baselines
            lr = fit_logreg(fit[list(FEATURE_IDS)], y_fit)
            ls, lt = positive_scores(lr, sval[list(FEATURE_IDS)].to_numpy()), positive_scores(lr, tval[list(FEATURE_IDS)].to_numpy())
            record("LR-ALL", "LR", None, ls, lt, choose_threshold(y_s, ls, "f1_max")["threshold"], "baseline")
            record("HTTPS-rule", "rule", None, https_rule_scores(sval), https_rule_scores(tval), 0.5, "baseline")

            for model in MODELS:
                for seed in seeds:
                    # frozen v1 ALL bundles, frozen thresholds
                    b = _frozen_bundle(paths, frozen, f"{src}-{model}-ALL-k37-s{seed}")
                    b.model.set_params(n_jobs=threads)
                    bs, bt = b.score(sval[b.feature_ids]), b.score(tval[b.feature_ids])
                    record(f"{model}-ALL", model, seed, bs, bt, b.meta["thresholds"]["f1_max"]["threshold"], "frozen_v1")
                    # E2: refit without is_https (exploratory)
                    a = fit_model(model, fit[NO_HTTPS], y_fit, seed, cfg, threads)
                    as_, at = a.score(sval[NO_HTTPS]), a.score(tval[NO_HTTPS])
                    record(f"{model}-noHTTPS", model, seed, as_, at, choose_threshold(y_s, as_, "f1_max")["threshold"], "ablation")
                    if seed == seeds[0]:
                        # E3: error analysis of the frozen bundle (target VAL = transfer, source VAL = internal)
                        for ev, d, y, s in (("target_val", tval, y_t, bt), ("source_val", sval, y_s, bs)):
                            yhat = (s >= b.meta["thresholds"]["f1_max"]["threshold"]).astype(int)
                            t = slice_table(d, y, yhat)
                            t.insert(0, "eval", ev); t.insert(0, "model", model); t.insert(0, "source", src)
                            slices.append(t)
                            info = rec.loc[d.record_id]
                            for e in error_examples(d, y, s, yhat, info["url_raw"]):
                                examples.append({"source": src, "eval": ev, "model": model, **e})
                            domains[f"{src}/{model}/{ev}"] = top_error_domains(info["group_key"], y, yhat)

            # paired domain-cluster bootstrap: a - b, same resampled domains for both arms
            pairs = [(f"{m}-ALL", "LR-ALL") for m in MODELS] + [(f"{m}-ALL", f"{m}-noHTTPS") for m in MODELS] + \
                    [("LR-ALL", "HTTPS-rule")]
            for ev, d, y in (("source_val", sval, y_s), ("target_val", tval, y_t)):
                for a_conf, b_conf in pairs:
                    pa, pb = preds[a_conf][ev], preds[b_conf][ev]
                    n = max(len(pa), len(pb))
                    pa, pb = (pa * n)[:n] if len(pa) == 1 else pa, (pb * n)[:n] if len(pb) == 1 else pb
                    r = paired_cluster_bootstrap(d.group_id.to_numpy(), y, pa, pb, B, bseed)
                    contrasts.append({"source": src, "target": tgt, "eval": ev, "a": a_conf, "b": b_conf, **r})

        pd.DataFrame(rows).to_csv(out / "metrics.csv", index=False)
        pd.concat(slices, ignore_index=True).to_csv(out / "slices.csv", index=False)
        pd.DataFrame(examples).to_csv(out / "error_examples.csv", index=False)
        write_json(out / "results.json", {"contrasts": contrasts, "error_domains": domains, "prevalence": prevalence,
                                          "ablated_features": list(ABLATED), "n_boot": B,
                                          "note": "exploratory; FIT/VAL only; conditional on the v1 split"})
        verify_freeze(paths.freeze, paths.root)
        manifest.update(status="passed", output_sha256={p.name: sha256_file(p) for p in out.iterdir()
                                                        if p.is_file() and p.name != "manifest.json"})
        write_json(out / "manifest.json", manifest)
        write_json(paths.artifacts / "extensions" / "latest.json",
                   {"artifact": out.relative_to(paths.root).as_posix(), "manifest_sha256": sha256_file(out / "manifest.json")})
    except Exception as exc:          # failed runs are kept (AGENTS.md rule 4)
        manifest.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        write_json(out / "manifest.json", manifest)
        raise
    return out


def latest_run(paths: Paths, sub: str = "") -> Path:
    """Verified pointer to the latest passed extension run (sub="dagafs" for D-41)."""
    from ..common import read_json
    ptr = read_json(paths.artifacts / "extensions" / sub / "latest.json")
    run = paths.root / ptr["artifact"]
    if sha256_file(run / "manifest.json") != ptr["manifest_sha256"]:
        raise GateError("extension manifest hash mismatch")
    man = read_json(run / "manifest.json")
    if man["status"] != "passed" or man["test_labels_read"]:
        raise GateError("extension run not passed")
    for name, h in man["output_sha256"].items():
        if sha256_file(run / name) != h:
            raise GateError(f"extension output changed: {name}")
    return run
