"""DA-GAFS: Direction-Aware, Generalization-Aware Feature Selection (D-41). Exploratory, FIT/VAL only.

C1 cross-source stability  S_f  share of the saved v1 full-FIT PI vectors (2 sources x seeds x 3 folds)
                                in which f ranks <= q with PI > 0;  importance I_f = mean over sources of
                                max-normalised mean PI (clipped at 0)
C2 direction consistency   D_f  0 when the rank-biserial association of f with the label has opposite signs
                                in the two sources and |r| >= TAU in both, else 1
C3 unified score           G_f = D_f * (I_f + S_f) / 2          (ablations: I only, I+S)
C4 multi-objective         k*  = cheapest prefix whose cross-source FIT AP is within TOL of the best prefix
C5 ensemble                cheapest RF/LGBM/LR soft-vote combination within TOL of the best cross-source FIT AP

Selection uses labelled FIT of BOTH collections, so this is a multi-source setting, not source-only.
Models are fitted on source FIT only, thresholds come from source VAL, and transfer is measured on
target VAL, which nothing above has seen. TEST is never loaded; records.parquet is read without labels.
"""
from __future__ import annotations

import datetime as dt
import itertools
import time
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from ..common import GateError, Paths, effective_threads, read_json, sha256_file, write_json
from ..features import FEATURE_IDS, FEATURE_NAMES, FEATURES, extract_features
from ..freeze import verify_freeze
from ..models import MODELS, fit_model, positive_scores
from ..prepare import load_dev
from ..selection import _fold_ranks
from ..statistics import paired_cluster_bootstrap
from ..thresholds import choose_threshold
from ..urls import canonicalize_url
from .analysis import OTHER, _frozen_bundle, _metrics, fit_logreg

TAU = 0.10            # smallest |rank-biserial| that counts as a class association
TOL = 0.01            # AP tolerance, same as v1 k_tolerance_ap
SIGN_BOOT = 200       # domain-bootstrap replicates for the sign-stability diagnostic
COST_URLS = 2000      # FIT URLs per source for the extraction-cost model
COST_REPEATS = 5
RANKINGS = ("I", "IS", "ISD")
CONF = {"I": "I", "IS": "IS", "ISD": "DAGAFS"}
MEMBERS = ("RF", "LGBM", "LR")


# ------------------------------------------------------------------ C2 direction
def _auc_codes(codes: np.ndarray, n: int, y: np.ndarray, w: np.ndarray) -> float:
    w1 = np.bincount(codes, weights=w * y, minlength=n)
    w0 = np.bincount(codes, weights=w * (1 - y), minlength=n)
    return float(w1 @ (np.cumsum(w0) - 0.5 * w0) / (w1.sum() * w0.sum()))


def weighted_auc(x: np.ndarray, y: np.ndarray, w: np.ndarray | None = None) -> float:
    """Exact (weighted) ROC AUC of score x for y==1, ties count 1/2. Equals sklearn's roc_auc_score."""
    codes = np.unique(x, return_inverse=True)[1]
    return _auc_codes(codes, codes.max() + 1, np.asarray(y, float), np.ones(len(x)) if w is None else w)


def direction(fit: dict[str, pd.DataFrame], n_boot: int, seed: int) -> dict[str, dict[str, np.ndarray]]:
    """Rank-biserial r = 2 AUC - 1 per source and feature, plus the share of domain-bootstrap
    replicates that keep the sign of the point estimate."""
    rng = np.random.default_rng(seed)
    out = {}
    for s, d in fit.items():
        y = d.label.to_numpy().astype(float)
        gidx = np.unique(d.group_id.to_numpy(), return_inverse=True)[1]
        G = gidx.max() + 1
        codes = [np.unique(d[f].to_numpy(), return_inverse=True)[1] for f in FEATURE_IDS]
        sizes = [c.max() + 1 for c in codes]
        one = np.ones(len(y))
        r = np.array([2 * _auc_codes(c, n, y, one) - 1 for c, n in zip(codes, sizes)])
        keep = np.zeros(len(r))
        for _ in range(n_boot):
            w = np.bincount(rng.integers(0, G, G), minlength=G)[gidx].astype(float)
            rb = np.array([2 * _auc_codes(c, n, y, w) - 1 for c, n in zip(codes, sizes)])
            keep += np.sign(rb) == np.sign(r)
        out[s] = {"r": r, "sign_stability": keep / max(n_boot, 1)}
    return out


# ------------------------------------------------------------------ C1 + C3
def load_saved_pi(paths: Paths, frozen: dict, src: str, seeds: list[int]) -> list[np.ndarray]:
    """v1 full-FIT PI (folds x features) per seed, hash-verified against the freeze."""
    mats = []
    for seed in seeds:
        p = paths.dev / src / "selectors" / f"pi_s{seed}_full.json"
        key = p.relative_to(paths.root).as_posix()
        if frozen["body"]["file_hashes"].get(key) != sha256_file(p):
            raise GateError(f"saved PI not verified by the freeze: {key}")
        doc = read_json(p)
        if doc["feature_ids"] != list(FEATURE_IDS):
            raise GateError(f"unexpected feature order in {key}")
        mats.append(np.asarray(doc["pi_folds"], dtype=np.float64))
    return mats


def component_table(pi: dict[str, list[np.ndarray]], r: dict[str, np.ndarray], q: int) -> pd.DataFrame:
    ids = list(FEATURE_IDS)
    imp, votes, n = [], np.zeros(len(ids)), 0
    for s in ("A", "B"):
        P = np.vstack(pi[s])                                 # (seeds * folds) x features
        m = P.mean(axis=0)
        imp.append(np.clip(m / m.max(), 0, None) if m.max() > 0 else np.zeros_like(m))
        votes += ((_fold_ranks(P, ids) <= q) & (P > 0)).sum(axis=0)
        n += len(P)
    I, S = np.mean(imp, axis=0), votes / n
    conflict = (r["A"] * r["B"] < 0) & (np.minimum(np.abs(r["A"]), np.abs(r["B"])) >= TAU)
    D = (~conflict).astype(float)
    return pd.DataFrame({"feature": ids, "name": [FEATURE_NAMES[f] for f in ids], "I": I, "S": S,
                         "r_A": r["A"], "r_B": r["B"], "conflict": conflict, "D": D,
                         "IS": (I + S) / 2, "G": D * (I + S) / 2})


def rankings(tab: pd.DataFrame) -> dict[str, list[str]]:
    """Descending score, ties by the next score and then feature id. ISD = DA-GAFS."""
    keys = {"I": ["I"], "IS": ["IS"], "ISD": ["G", "IS"]}
    return {R: tab.sort_values(c + ["feature"], ascending=[False] * len(c) + [True]).feature.tolist()
            for R, c in keys.items()}


# ------------------------------------------------------------------ C4 / C5 choice rule
def pareto(g: np.ndarray, c: np.ndarray) -> np.ndarray:
    """True where no other point has >= objective and <= cost with one strict."""
    g, c = np.asarray(g, float), np.asarray(c, float)
    dom = ((g[None] >= g[:, None]) & (c[None] <= c[:, None]) & ((g[None] > g[:, None]) | (c[None] < c[:, None])))
    return ~dom.any(axis=1)


def choose(g: np.ndarray, c: np.ndarray, tol: float = TOL) -> int:
    """Cheapest point within tol of the best objective; ties -> lower index."""
    g, c = np.asarray(g, float), np.asarray(c, float)
    ok = np.flatnonzero(g >= g.max() - tol)
    return int(ok[np.argmin(c[ok])])          # argmin returns the first minimum


# ------------------------------------------------------------------ cost
def _median_ns(fn, repeats: int) -> float:
    fn()
    t = []
    for _ in range(repeats):
        t0 = time.perf_counter_ns()
        fn()
        t.append(time.perf_counter_ns() - t0)
    return float(np.median(t))


def extraction_costs(urls: list[str], repeats: int = COST_REPEATS) -> tuple[float, dict[str, float]]:
    """Parse cost and per-feature extraction cost in microseconds per URL (additive model)."""
    parsed = [canonicalize_url(u) for u in urls]
    n = len(urls)
    parse = _median_ns(lambda: [canonicalize_url(u) for u in urls], repeats) / n / 1e3
    per = {f: _median_ns(lambda fn=FEATURES[f][1]: [fn(p) for p in parsed], repeats) / n / 1e3 for f in FEATURE_IDS}
    return parse, per


def predict_us(score, X: np.ndarray, repeats: int = 20) -> float:
    return _median_ns(lambda: score(X), repeats) / len(X) / 1e3


# ------------------------------------------------------------------ driver
def run_dagafs(paths: Paths, cfg: dict) -> Path:
    frozen = verify_freeze(paths.freeze, paths.root)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    base = paths.artifacts / "extensions" / "dagafs"
    out = base / f"run_{stamp}_{uuid.uuid4().hex[:8]}"
    out.mkdir(parents=True)
    here = Path(__file__).parent
    manifest = {"status": "running", "decision": "D-41", "research_status": "exploratory extension of frozen v1",
                "setting": "multi-source selection (labelled FIT of both collections); fit on source FIT; "
                           "thresholds on source VAL; transfer on target VAL",
                "parent_freeze_hash": frozen["freeze_hash"], "partitions_used": ["FIT", "VAL"],
                "test_features_read": False, "test_labels_read": False, "dataset_urls_opened": False,
                "constants": {"tau": TAU, "tol": TOL, "sign_boot": SIGN_BOOT, "cost_urls": COST_URLS},
                "code_sha256": {f"pkg/extensions/{p.name}": sha256_file(p) for p in sorted(here.glob("*.py"))}}
    write_json(out / "manifest.json", manifest)
    try:
        threads = effective_threads(cfg)
        seeds = list(cfg["models"]["seeds"])
        s0 = seeds[0]
        B, bseed = int(cfg["statistics"]["bootstrap_replicates"]), int(cfg["statistics"]["bootstrap_seed"])
        data = {s: {p: load_dev(paths, s, p) for p in ("FIT", "VAL")} for s in ("A", "B")}
        y = {s: {p: data[s][p].label.to_numpy().astype(int) for p in ("FIT", "VAL")} for s in ("A", "B")}

        # C1-C3 ---------------------------------------------------------
        dirn = direction({s: data[s]["FIT"] for s in ("A", "B")}, SIGN_BOOT, bseed)
        pi = {s: load_saved_pi(paths, frozen, s, seeds) for s in ("A", "B")}
        tab = component_table(pi, {s: dirn[s]["r"] for s in ("A", "B")}, int(cfg["selection"]["q"]))
        for s in ("A", "B"):
            tab[f"sign_stability_{s}"] = dirn[s]["sign_stability"]
        ranks = rankings(tab)

        # cost model (FIT URLs only, no labels) ---------------------------
        rec = pd.read_parquet(paths.processed / "records.parquet", columns=["record_id", "url_raw"]).set_index("record_id")
        rng = np.random.default_rng(bseed)
        urls = []
        for s in ("A", "B"):
            ids = data[s]["FIT"].record_id.to_numpy()
            urls += rec.loc[rng.choice(ids, min(COST_URLS, len(ids)), replace=False), "url_raw"].tolist()
        parse_us, feat_us = extraction_costs(urls, COST_REPEATS)
        tab["cost_us"] = tab.feature.map(feat_us)
        for R, order in ranks.items():
            tab[f"rank_{R}"] = tab.feature.map({f: i + 1 for i, f in enumerate(order)})
        tab.to_csv(out / "features.csv", index=False)

        def cost(feats) -> float:
            return parse_us + sum(feat_us[f] for f in feats)

        # C4: cross-source AP of every ranking prefix (FIT only) ---------
        cache, sweep = {}, []
        for R, order in ranks.items():
            for k in range(1, len(order) + 1):
                feats = tuple(sorted(order[:k]))
                if feats not in cache:
                    ap = {}
                    for src in ("A", "B"):
                        tgt = OTHER[src]
                        b = fit_model("LGBM", data[src]["FIT"][list(feats)], y[src]["FIT"], s0, cfg, threads)
                        ap[src] = float(average_precision_score(y[tgt]["FIT"], b.score(data[tgt]["FIT"][list(feats)])))
                    cache[feats] = ap
                ap = cache[feats]
                sweep.append({"ranking": R, "k": k, "ap_A_to_B": ap["A"], "ap_B_to_A": ap["B"],
                              "g": (ap["A"] + ap["B"]) / 2, "cost_us": cost(feats), "features": " ".join(feats)})
        sw = pd.DataFrame(sweep)
        sw["pareto"] = pareto(sw.g, sw.cost_us)
        sw["chosen"] = False
        kstar = {}
        for R in RANKINGS:
            part = sw[sw.ranking == R]
            i = part.index[choose(part.g.to_numpy(), part.cost_us.to_numpy())]
            sw.loc[i, "chosen"] = True
            kstar[R] = int(sw.loc[i, "k"])
        sw.to_csv(out / "sweep.csv", index=False)
        k = kstar["ISD"]                                     # DA-GAFS budget; ablations matched at k
        feats = {R: sorted(ranks[R][:k]) for R in RANKINGS}

        # final models, scores on source VAL / target VAL / target FIT -----
        rows, preds, fitted, members = [], {}, {}, {}
        ens_rows = []
        for src in ("A", "B"):
            tgt = OTHER[src]
            fit, sval, tval, tfit = data[src]["FIT"], data[src]["VAL"], data[tgt]["VAL"], data[tgt]["FIT"]
            P = preds[src] = {}

            def record(config, model, seed, s_src, s_tgt, thr, kind, n_feat):
                for ev, yy, s in (("source_val", y[src]["VAL"], s_src), ("target_val", y[tgt]["VAL"], s_tgt)):
                    rows.append({"source": src, "target": tgt, "eval": ev, "config": config, "model": model,
                                 "seed": seed, "kind": kind, "k": n_feat, **_metrics(yy, s, thr)})
                P.setdefault(config, {"source_val": [], "target_val": []})
                P[config]["source_val"].append((s_src >= thr).astype(int))
                P[config]["target_val"].append((s_tgt >= thr).astype(int))

            for model in MODELS:
                for seed in seeds:
                    for method, tag in (("ALL", "ALL"), ("STABLE_PI", "STABLE")):
                        item = next(p for p in frozen["body"]["plan"]
                                    if p["bundle_id"].startswith(f"{src}-{model}-{method}-k") and p["bundle_id"].endswith(f"-s{seed}"))
                        b = _frozen_bundle(paths, frozen, item["bundle_id"])
                        b.model.set_params(n_jobs=threads)
                        record(f"{model}-{tag}", model, seed, b.score(sval[b.feature_ids]), b.score(tval[b.feature_ids]),
                               b.meta["thresholds"]["f1_max"]["threshold"], "frozen_v1", len(b.feature_ids))
                    for R in RANKINGS:
                        key = (src, model, seed, tuple(feats[R]))
                        if key not in fitted:
                            fitted[key] = fit_model(model, fit[feats[R]], y[src]["FIT"], seed, cfg, threads)
                        b = fitted[key]
                        ss, st = b.score(sval[feats[R]]), b.score(tval[feats[R]])
                        record(f"{model}-{CONF[R]}", model, seed, ss, st,
                               choose_threshold(y[src]["VAL"], ss, "f1_max")["threshold"], "dagafs", k)

            # C5: members on DA-GAFS features
            F = feats["ISD"]
            lr = fit_logreg(fit[F], y[src]["FIT"])
            lr_score = lambda X, m=lr: positive_scores(m, X)      # noqa: E731
            mem = {}   # member -> seed -> (source VAL, target VAL, target FIT) scores
            for seed in seeds:
                for model in ("RF", "LGBM"):
                    b = fitted[(src, model, seed, tuple(F))]
                    mem.setdefault(model, {})[seed] = (b.score(sval[F]), b.score(tval[F]),
                                                       b.score(tfit[F]) if seed == s0 else None)
            mem["LR"] = {seed: (lr_score(sval[F].to_numpy()), lr_score(tval[F].to_numpy()),
                                lr_score(tfit[F].to_numpy()) if seed == s0 else None) for seed in seeds}
            ls = mem["LR"][s0][0]
            record("LR-DAGAFS", "LR", None, ls, mem["LR"][s0][1],
                   choose_threshold(y[src]["VAL"], ls, "f1_max")["threshold"], "dagafs", k)
            Xt = fit[F].iloc[:1024].to_numpy(dtype=np.float64)
            pus = {}
            for model in ("RF", "LGBM"):
                b = fitted[(src, model, s0, tuple(F))]
                b.model.set_params(n_jobs=1)
                pus[model] = predict_us(lambda X, bb=b: positive_scores(bb.model, X), Xt)
                b.model.set_params(n_jobs=threads)
            pus["LR"] = predict_us(lr_score, Xt)
            for r_ in range(1, 4):
                for combo in itertools.combinations(MEMBERS, r_):
                    sc = np.mean([mem[m][s0][2] for m in combo], axis=0)
                    ens_rows.append({"source": src, "combo": "+".join(combo),
                                     "ap_tgt_fit": float(average_precision_score(y[tgt]["FIT"], sc)),
                                     "predict_us": sum(pus[m] for m in combo), "extract_us": cost(F)})
            members[src] = mem

        ens = pd.DataFrame(ens_rows)
        eg = ens.groupby("combo").agg(g=("ap_tgt_fit", "mean"), predict_us=("predict_us", "mean"),
                                      extract_us=("extract_us", "mean")).reset_index()
        eg["cost_us"] = eg.predict_us + eg.extract_us
        eg["pareto"] = pareto(eg.g, eg.cost_us)
        eg["chosen"] = False
        gae = eg.loc[choose(eg.g.to_numpy(), eg.cost_us.to_numpy()), "combo"]
        eg.loc[eg.combo == gae, "chosen"] = True
        ens.to_csv(out / "ensemble_by_direction.csv", index=False)
        eg.to_csv(out / "ensemble.csv", index=False)

        for src in ("A", "B"):
            tgt = OTHER[src]
            mem = members[src]
            for conf, combo in (("GAE", gae.split("+")), ("ENS3", list(MEMBERS))):
                preds[src].setdefault(conf, {"source_val": [], "target_val": []})
                for seed in seeds:
                    ss = np.mean([mem[m][seed][0] for m in combo], axis=0)
                    st = np.mean([mem[m][seed][1] for m in combo], axis=0)
                    thr = choose_threshold(y[src]["VAL"], ss, "f1_max")["threshold"]
                    for ev, yy, s in (("source_val", y[src]["VAL"], ss), ("target_val", y[tgt]["VAL"], st)):
                        rows.append({"source": src, "target": tgt, "eval": ev, "config": conf, "model": "+".join(combo),
                                     "seed": seed, "kind": "ensemble", "k": k, **_metrics(yy, s, thr)})
                    preds[src][conf]["source_val"].append((ss >= thr).astype(int))
                    preds[src][conf]["target_val"].append((st >= thr).astype(int))

        # paired contrasts (fixed in D-41) --------------------------------
        pairs = [(f"{m}-DAGAFS", f"{m}-ALL") for m in MODELS] + [(f"{m}-DAGAFS", f"{m}-STABLE") for m in MODELS] + \
                [(f"{m}-DAGAFS", f"{m}-IS") for m in MODELS] + [(f"{m}-IS", f"{m}-I") for m in MODELS] + \
                [("GAE", "LGBM-DAGAFS"), ("ENS3", "LGBM-DAGAFS")]
        contrasts = []
        for src in ("A", "B"):
            tgt = OTHER[src]
            for ev, d, yy in (("source_val", data[src]["VAL"], y[src]["VAL"]), ("target_val", data[tgt]["VAL"], y[tgt]["VAL"])):
                for a, b in pairs:
                    pa, pb = preds[src][a][ev], preds[src][b][ev]
                    r = paired_cluster_bootstrap(d.group_id.to_numpy(), yy, pa, pb, B, bseed)
                    contrasts.append({"source": src, "target": tgt, "eval": ev, "a": a, "b": b, **r})

        # additive-cost check: measured extraction of the chosen and the full set
        measured = {name: _median_ns(lambda fs=fs: extract_features(urls, fs), COST_REPEATS) / len(urls) / 1e3
                    for name, fs in (("DAGAFS", feats["ISD"]), ("ALL", list(FEATURE_IDS)))}

        pd.DataFrame(rows).to_csv(out / "metrics.csv", index=False)
        write_json(out / "results.json", {
            "contrasts": contrasts, "k_star": kstar, "k": k, "features": feats, "rankings": ranks,
            "conflicts": tab.loc[tab.conflict, "feature"].tolist(), "gae": gae,
            "parse_us": parse_us, "extract_us_additive": {"DAGAFS": cost(feats["ISD"]), "ALL": cost(FEATURE_IDS)},
            "extract_us_measured": measured, "n_boot": B, "n_cost_urls": len(urls),
            "note": "exploratory; multi-source selection on FIT of both collections; VAL evaluation; TEST unread"})
        verify_freeze(paths.freeze, paths.root)
        manifest.update(status="passed", output_sha256={p.name: sha256_file(p) for p in out.iterdir()
                                                        if p.is_file() and p.name != "manifest.json"})
        write_json(out / "manifest.json", manifest)
        write_json(base / "latest.json", {"artifact": out.relative_to(paths.root).as_posix(),
                                          "manifest_sha256": sha256_file(out / "manifest.json")})
    except Exception as exc:          # failed runs are kept (AGENTS.md rule 4)
        manifest.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        write_json(out / "manifest.json", manifest)
        raise
    return out


def latest_dagafs(paths: Paths) -> Path:
    from .analysis import latest_run
    return latest_run(paths, "dagafs")


# ------------------------------------------------------------------ D-42 post-hoc: each ranking at its own k*
def run_dagafs_posthoc(paths: Paths, cfg: dict) -> Path:
    """Evaluate the rule-chosen prefix of every ranking (from the verified D-41 run) on target VAL."""
    from .analysis import latest_run
    frozen = verify_freeze(paths.freeze, paths.root)
    parent = latest_run(paths, "dagafs")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    base = paths.artifacts / "extensions" / "dagafs_posthoc"
    out = base / f"run_{stamp}_{uuid.uuid4().hex[:8]}"
    out.mkdir(parents=True)
    here = Path(__file__).parent
    manifest = {"status": "running", "decision": "D-42", "research_status": "post-hoc exploratory (not preregistered)",
                "parent_run": parent.relative_to(paths.root).as_posix(),
                "parent_manifest_sha256": sha256_file(parent / "manifest.json"),
                "parent_freeze_hash": frozen["freeze_hash"], "partitions_used": ["FIT", "VAL"],
                "test_features_read": False, "test_labels_read": False, "dataset_urls_opened": False,
                "code_sha256": {f"pkg/extensions/{p.name}": sha256_file(p) for p in sorted(here.glob("*.py"))}}
    write_json(out / "manifest.json", manifest)
    try:
        threads = effective_threads(cfg)
        seeds = list(cfg["models"]["seeds"])
        B, bseed = int(cfg["statistics"]["bootstrap_replicates"]), int(cfg["statistics"]["bootstrap_seed"])
        sw = pd.read_csv(parent / "sweep.csv")
        own = {CONF[r.ranking]: r.features.split() for r in sw[sw.chosen].itertuples()}
        data = {s: {p: load_dev(paths, s, p) for p in ("FIT", "VAL")} for s in ("A", "B")}
        rows, preds = [], {}
        for src in ("A", "B"):
            tgt = OTHER[src]
            fit, sval, tval = data[src]["FIT"], data[src]["VAL"], data[tgt]["VAL"]
            ys, yt = sval.label.to_numpy().astype(int), tval.label.to_numpy().astype(int)
            P = preds[src] = {}
            for model in MODELS:
                for seed in seeds:
                    runs = []
                    for method, tag in (("ALL", "ALL"), ("STABLE_PI", "STABLE")):
                        item = next(p for p in frozen["body"]["plan"] if p["bundle_id"].startswith(f"{src}-{model}-{method}-k")
                                    and p["bundle_id"].endswith(f"-s{seed}"))
                        b = _frozen_bundle(paths, frozen, item["bundle_id"])
                        b.model.set_params(n_jobs=threads)
                        runs.append((f"{model}-{tag}", b, b.meta["thresholds"]["f1_max"]["threshold"], "frozen_v1"))
                    for tag, F in own.items():
                        b = fit_model(model, fit[F], fit.label.to_numpy().astype(int), seed, cfg, threads)
                        runs.append((f"{model}-{tag}@own", b, None, "posthoc"))
                    for conf, b, thr, kind in runs:
                        ss, st = b.score(sval[b.feature_ids]), b.score(tval[b.feature_ids])
                        thr = choose_threshold(ys, ss, "f1_max")["threshold"] if thr is None else thr
                        for ev, yy, s in (("source_val", ys, ss), ("target_val", yt, st)):
                            rows.append({"source": src, "target": tgt, "eval": ev, "config": conf, "model": model,
                                         "seed": seed, "kind": kind, "k": len(b.feature_ids), **_metrics(yy, s, thr)})
                        P.setdefault(conf, {"source_val": [], "target_val": []})
                        P[conf]["source_val"].append((ss >= thr).astype(int))
                        P[conf]["target_val"].append((st >= thr).astype(int))
        contrasts = []
        for src in ("A", "B"):
            tgt = OTHER[src]
            for ev, d in (("source_val", data[src]["VAL"]), ("target_val", data[tgt]["VAL"])):
                yy = d.label.to_numpy().astype(int)
                for model in MODELS:
                    for tag in own:
                        for ref in ("ALL", "STABLE"):
                            a, b = f"{model}-{tag}@own", f"{model}-{ref}"
                            r = paired_cluster_bootstrap(d.group_id.to_numpy(), yy, preds[src][a][ev], preds[src][b][ev], B, bseed)
                            contrasts.append({"source": src, "target": tgt, "eval": ev, "a": a, "b": b, **r})
        rec = pd.read_parquet(paths.processed / "records.parquet", columns=["record_id", "url_raw"]).set_index("record_id")
        rng = np.random.default_rng(bseed)
        urls = []
        for s in ("A", "B"):
            ids = data[s]["FIT"].record_id.to_numpy()
            urls += rec.loc[rng.choice(ids, min(COST_URLS, len(ids)), replace=False), "url_raw"].tolist()
        sets = {**own, "ALL": list(FEATURE_IDS)}
        measured = {n: _median_ns(lambda fs=fs: extract_features(urls, fs), COST_REPEATS) / len(urls) / 1e3 for n, fs in sets.items()}
        pd.DataFrame(rows).to_csv(out / "metrics.csv", index=False)
        write_json(out / "results.json", {"contrasts": contrasts, "own_k": {t: len(F) for t, F in own.items()},
                                          "features": own, "extract_us_measured": measured, "n_boot": B,
                                          "note": "post-hoc D-42; rule-chosen prefix per ranking; FIT/VAL only"})
        verify_freeze(paths.freeze, paths.root)
        manifest.update(status="passed", output_sha256={p.name: sha256_file(p) for p in out.iterdir()
                                                        if p.is_file() and p.name != "manifest.json"})
        write_json(out / "manifest.json", manifest)
        write_json(base / "latest.json", {"artifact": out.relative_to(paths.root).as_posix(),
                                          "manifest_sha256": sha256_file(out / "manifest.json")})
    except Exception as exc:          # failed runs are kept (AGENTS.md rule 4)
        manifest.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        write_json(out / "manifest.json", manifest)
        raise
    return out
