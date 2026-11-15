"""Post-evaluation analysis (PRD s14-16). Reads frozen predictions; never refits a model
or changes a threshold. Outputs go to artifacts/analysis/."""
from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd

from .common import GateError, Paths, environment_info, read_json, write_json
from .features import FEATURE_IDS, FEATURE_NAMES
from .freeze import verify_freeze
from .statistics import cluster_bootstrap_ci, compute_metrics, confusion, metrics_from_counts, paired_cluster_bootstrap

MAIN_POLICY = "f1_max"
METRIC_KEYS = ["f1", "precision", "recall", "specificity", "mcc", "balanced_accuracy", "accuracy", "roc_auc",
               "average_precision", "fpr"]


def _config_rows(meta_rows: pd.DataFrame) -> pd.DataFrame:
    """One row per (bundle, role): config label ALL / MEAN_PI@budget / STABLE_PI@matched ..."""
    out = []
    for r in meta_rows.itertuples():
        roles = r.roles if isinstance(r.roles, list) else str(r.roles).split()
        for role in roles:
            out.append({"bundle_id": r.bundle_id, "config": "ALL" if r.selector == "ALL" else f"{r.selector}@{role}"})
    return pd.DataFrame(out)


def recompute_check(P: pd.DataFrame, metrics: pd.DataFrame) -> dict:
    """I06: every reported metric row is reproduced exactly from saved predictions."""
    if P.duplicated(["bundle_id", "target", "record_id"]).any():
        raise GateError("duplicate prediction keys")
    groups = {k: g for k, g in P.groupby(["bundle_id", "target"])}
    worst = 0.0
    for r in metrics.itertuples():
        g = groups[(r.bundle_id, r.target)]
        m = compute_metrics(g.y_true.to_numpy(), g.score_phishing.to_numpy(), r.threshold)
        if (m["TN"], m["FP"], m["FN"], m["TP"]) != (r.TN, r.FP, r.FN, r.TP) or m["n_rows"] != r.TN + r.FP + r.FN + r.TP:
            raise GateError(f"confusion mismatch for {r.bundle_id}/{r.target}/{r.threshold_policy}")
        for k in METRIC_KEYS:
            a, b = m["values"][k], r.values[k]
            if (a is None) != (b is None) or (a is not None and abs(a - b) > 1e-12):
                raise GateError(f"metric {k} mismatch for {r.bundle_id}")
            if a is not None:
                worst = max(worst, abs(a - b))
    return {"rows_checked": int(len(metrics)), "max_abs_diff": worst, "status": "pass"}


def _domain_balanced(y, yhat, groups) -> dict:
    w = 1.0 / pd.Series(groups).map(pd.Series(groups).value_counts()).to_numpy()
    y, yhat = np.asarray(y), np.asarray(yhat)
    c = {"TN": float(w[(y == 0) & (yhat == 0)].sum()), "FP": float(w[(y == 0) & (yhat == 1)].sum()),
         "FN": float(w[(y == 1) & (yhat == 0)].sum()), "TP": float(w[(y == 1) & (yhat == 1)].sum())}
    return metrics_from_counts(c)


def run_analysis(freeze_path: Path, cfg: dict, paths: Paths, skip_shap: bool = False, skip_benchmark: bool = False) -> dict:
    fr = verify_freeze(freeze_path, paths.root)
    ev = read_json(paths.eval / "metrics.json")
    if ev["freeze_hash"] != fr["freeze_hash"]:
        raise GateError("evaluation was produced under a different freeze")
    out = paths.analysis
    out.mkdir(parents=True, exist_ok=True)
    P = pd.read_parquet(paths.eval / "predictions.parquet").sort_values(["bundle_id", "target", "record_id"])
    M = pd.DataFrame(ev["metrics"])
    checks = {"I06_recompute": recompute_check(P, M)}
    thr = pd.read_csv(paths.eval / "thresholds.csv")
    tmap = {(r.bundle_id, r.policy): r.threshold for r in thr.itertuples()}
    meta = M.drop_duplicates("bundle_id")[["bundle_id", "source", "model", "selector", "k", "seed", "roles"]]
    cfgmap = _config_rows(meta).merge(meta, on="bundle_id")
    B = int(cfg["statistics"]["bootstrap_replicates"])
    bseed = int(cfg["statistics"]["bootstrap_seed"])

    # ---------------------------------------------------------- per-config summary (+ CI)
    preds = {k: g for k, g in P.groupby(["bundle_id", "target"])}
    rows, cis = [], []
    for (src, model, conf), cg in cfgmap.groupby(["source", "model", "config"]):
        for tgt in (src, "B" if src == "A" else "A"):
            per_seed = M[M.bundle_id.isin(cg.bundle_id) & (M.target == tgt)]
            for policy, pg in per_seed.groupby("threshold_policy"):
                vals = pd.DataFrame(list(pg["values"]))
                row = {"source": src, "target": tgt, "direction": "internal" if src == tgt else f"{src}->{tgt}",
                       "model": model, "config": conf, "policy": policy, "n_seeds": len(pg),
                       "k_per_seed": " ".join(str(k) for k in pg.sort_values("seed").k),
                       "n_rows": int(pg.n_rows.iloc[0]), "n_domains": int(pg.n_domains.iloc[0]),
                       "prevalence": float(pg.prevalence.iloc[0])}
                for k in METRIC_KEYS:
                    row[f"{k}_mean"] = float(vals[k].astype(float).mean())
                    row[f"{k}_sd"] = float(vals[k].astype(float).std(ddof=1)) if len(vals) > 1 else 0.0
                db = [_domain_balanced(preds[(b, tgt)].y_true, preds[(b, tgt)].score_phishing >= tmap[(b, policy)],
                                       preds[(b, tgt)].group_id) for b in pg.bundle_id]
                row["f1_domain_balanced_mean"] = float(np.mean([d["f1"] for d in db]))
                rows.append(row)
                if policy == MAIN_POLICY:
                    bl = sorted(pg.bundle_id)
                    g0 = preds[(bl[0], tgt)]
                    ci = cluster_bootstrap_ci(g0.group_id.to_numpy(), g0.y_true.to_numpy(),
                                              [(preds[(b, tgt)].score_phishing >= tmap[(b, policy)]).to_numpy().astype(int) for b in bl],
                                              B, bseed)
                    cis.append({"source": src, "target": tgt, "model": model, "config": conf, **ci})
    summary = pd.DataFrame(rows)
    summary.to_csv(out / "summary.csv", index=False)
    pd.DataFrame(cis).to_csv(out / "config_ci.csv", index=False)

    # ---------------------------------------------------------- transfer drop (same model & threshold)
    td = []
    for r in M[M.threshold_policy == MAIN_POLICY].itertuples():
        if r.target != r.source:
            continue
        ext = M[(M.bundle_id == r.bundle_id) & (M.threshold_policy == MAIN_POLICY) & (M.target != r.source)].iloc[0]
        td.append({"bundle_id": r.bundle_id, "source": r.source, "model": r.model, "selector": r.selector, "k": r.k,
                   "seed": r.seed, "f1_source_test": r.values["f1"], "f1_target_test": ext["values"]["f1"],
                   "drop_pp": 100 * (r.values["f1"] - ext["values"]["f1"]),
                   "ap_source_test": r.values["average_precision"], "ap_target_test": ext["values"]["average_precision"]})
    td = pd.DataFrame(td).merge(cfgmap[["bundle_id", "config"]], on="bundle_id")
    td.to_csv(out / "transfer_drop.csv", index=False)

    # ---------------------------------------------------------- primary + secondary contrasts
    def contrast(src, tgt, model, conf_a, conf_b, policy=MAIN_POLICY):
        ca = cfgmap[(cfgmap.source == src) & (cfgmap.model == model) & (cfgmap.config == conf_a)].sort_values("seed")
        cb = cfgmap[(cfgmap.source == src) & (cfgmap.model == model) & (cfgmap.config == conf_b)].sort_values("seed")
        if list(ca.seed) != list(cb.seed):
            raise GateError("contrast arms have different seeds")
        pa = [(preds[(b, tgt)].score_phishing >= tmap[(b, policy)]).to_numpy().astype(int) for b in ca.bundle_id]
        pb = [(preds[(b, tgt)].score_phishing >= tmap[(b, policy)]).to_numpy().astype(int) for b in cb.bundle_id]
        g0 = preds[(ca.bundle_id.iloc[0], tgt)]
        y = g0.y_true.to_numpy()
        for b in list(ca.bundle_id) + list(cb.bundle_id):
            if not (preds[(b, tgt)].record_id.to_numpy() == g0.record_id.to_numpy()).all():
                raise GateError("prediction rows not aligned for paired bootstrap")
        r = paired_cluster_bootstrap(g0.group_id.to_numpy(), y, pa, pb, B, bseed)
        per_seed = [metrics_from_counts(confusion(y, a))["f1"] - metrics_from_counts(confusion(y, b))["f1"] for a, b in zip(pa, pb)]
        same_model = [a == b for a, b in zip(ca.bundle_id, cb.bundle_id)]
        return {"source": src, "target": tgt, "model": model, "a": conf_a, "b": conf_b, "policy": policy,
                "per_seed_delta": per_seed, "k_a": list(ca.k), "k_b": list(cb.k), "identical_bundle": same_model,
                "unstable_interval": r["invalid_fraction"] > cfg["statistics"]["invalid_fraction_warn"], **r}

    primary, secondary = [], []
    for src, model in itertools.product(("A", "B"), ("RF", "LGBM")):
        tgt = "B" if src == "A" else "A"
        primary.append(contrast(src, tgt, model, "STABLE_PI@matched", "MEAN_PI@matched"))
        for a, b in (("STABLE_PI@budget", "ALL"), ("MEAN_PI@budget", "ALL"), ("STABLE_PI@budget", "MEAN_PI@budget")):
            secondary.append(contrast(src, tgt, model, a, b))
        secondary.append(contrast(src, src, model, "STABLE_PI@matched", "MEAN_PI@matched"))
        secondary.append(contrast(src, src, model, "STABLE_PI@budget", "ALL"))
    write_json(out / "contrasts.json", {"primary": primary, "secondary": secondary, "n_boot": B,
                                        "effect_threshold_f1_abs": cfg["effects"]["f1_abs"],
                                        "note": "CIs are conditional on the fixed split and seed set; no familywise claim."})

    # ---------------------------------------------------------- selection diagnostics (source FIT only)
    write_json(out / "selection.json", selection_diagnostics(paths, cfg))
    checks["environment"] = environment_info()
    write_json(out / "checks.json", checks)
    registry = {"run_id": ev["run_id"], "freeze_hash": fr["freeze_hash"], "status": {}}
    registry["status"]["evaluation"] = ev["status"]

    if not skip_benchmark:
        registry["status"]["benchmark"] = _run_benchmark(cfg, paths, cfgmap, out)
    if not skip_shap:
        registry["status"]["shap"] = _run_shap(cfg, paths, cfgmap, out)
    write_json(out / "results_registry.json", registry)
    print(f"[analyze] done -> {out}")
    return registry


def selection_diagnostics(paths: Paths, cfg: dict) -> dict:
    from .selection import PiResult, rank_features
    res = {}
    dev_fit = pd.read_parquet(paths.processed / "dev_features.parquet")
    for src in ("A", "B"):
        d = read_json(paths.dev / src / "develop.json")
        fin = pd.read_csv(paths.dev / src / "finals.csv")
        cv = pd.read_csv(paths.dev / src / "outer_cv.csv")
        subsets = {}
        for r in fin.itertuples():
            if r.selector != "ALL":
                subsets[r.bundle_id] = read_json(paths.dev / src / "bundles" / f"{r.bundle_id}.json")["feature_ids"]
        per_seed_pi = {}
        for seed in d["seeds"]:
            pj = read_json(paths.dev / src / "selectors" / f"pi_s{seed}_full.json")
            pi = PiResult(pj["feature_ids"], np.array(pj["pi_folds"]), np.array(pj["pi_repeats"]), pj["fit_ids_hash"], pj["n_rows"])
            _, stats = rank_features(pi, "STABLE_PI", cfg["selection"]["q"])
            per_seed_pi[seed] = {"mean_pi": stats["mean_pi"], "votes": stats["votes"], "rank_mad": stats["rank_mad"]}
        cv_summary = cv.groupby(["model", "selector", "k"])[["ap", "f1_at_0.5"]].agg(["mean", "std"]).round(5)
        cv_summary.columns = ["_".join(c) for c in cv_summary.columns]
        fit = dev_fit[(dev_fit.dataset_id == src) & (dev_fit.partition == "FIT")][list(FEATURE_IDS)]
        corr = fit.corr(method="spearman").fillna(0)
        high = [(a, b, float(corr.loc[a, b])) for a, b in itertools.combinations(FEATURE_IDS, 2) if abs(corr.loc[a, b]) >= 0.9]
        res[src] = {"chosen_k": {s: v["chosen_k"] for s, v in d["seeds"].items()}, "subsets": subsets,
                    "pi_full": per_seed_pi, "outer_cv": cv_summary.reset_index().to_dict(orient="records"),
                    "high_corr_pairs_fit": high, "timing": d["timing"],
                    "constant_features_fit": [f for f in FEATURE_IDS if fit[f].nunique() <= 1]}
    res["feature_names"] = FEATURE_NAMES
    return res


def _source_val_urls(paths: Paths, src: str, n: int, seed: int) -> list[str]:
    rec = pd.read_parquet(paths.processed / "records.parquet", columns=["record_id", "url_raw", "dataset_id"])
    sp = pd.read_parquet(paths.processed / "splits.parquet")
    ids = sp[(sp.dataset_id == src) & (sp.partition == "VAL")].record_id
    urls = rec[rec.record_id.isin(ids)].sort_values("record_id").url_raw
    return urls.sample(min(n, len(urls)), random_state=seed).tolist()


def _run_benchmark(cfg, paths, cfgmap, out) -> str:
    from .benchmark import benchmark_bundle
    seed = int(cfg["benchmark"]["seed"])
    sel = cfgmap[cfgmap.seed == seed].drop_duplicates("bundle_id")
    url_pool = {s: _source_val_urls(paths, s, 4096, seed) for s in ("A", "B")}
    # same URLs for every model: pool of source A VAL + source B VAL (benchmark is source-agnostic)
    urls = [u for pair in zip(url_pool["A"], url_pool["B"]) for u in pair]
    res = []
    for r in sel.sort_values("bundle_id").itertuples():
        b = benchmark_bundle(paths.dev / r.source / "bundles" / r.bundle_id, urls, cfg)
        b.update({"source": r.source, "model": r.model, "selector": r.selector, "k": int(r.k)})
        res.append(b)
        print(f"[benchmark] {r.bundle_id}: e2e b1 {b['stages']['t1/batch1']['end_to_end']['median_ms_per_batch']:.3f} ms")
    flat = []
    for b in res:
        for bs, st in b["stages"].items():
            for stage, v in st.items():
                flat.append({"bundle_id": b["bundle_id"], "source": b["source"], "model": b["model"], "selector": b["selector"],
                             "k": b["k"], "threads": int(bs.split("/")[0][1:]), "batch": bs.split("/")[1], "stage": stage, **v})
    flat = pd.DataFrame(flat)
    base = flat[flat.selector == "ALL"].set_index(["source", "model", "threads", "batch", "stage"])["median_ms_per_batch"]
    flat["rel_to_all"] = [r.median_ms_per_batch / base[(r.source, r.model, r.threads, r.batch, r.stage)] for r in flat.itertuples()]
    flat.to_csv(out / "benchmark.csv", index=False)
    write_json(out / "benchmark.json", {"environment": environment_info(), "threads": cfg["models"]["threads"],
                                        "bundles": res, "url_pool": "interleaved source-VAL URLs of A and B",
                                        "note": "seed-17 bundle of every final configuration"})
    return "completed"


def _run_shap(cfg, paths, cfgmap, out) -> str:
    from .explain import compare, ranking, run_explain, stratified_sample
    ec = cfg["explain"]
    seed = int(ec["seed"])
    dev = pd.read_parquet(paths.processed / "dev_features.parquet")
    vault = paths.processed / "test_vault"
    test = pd.read_parquet(vault / "test_features.parquet").merge(pd.read_parquet(vault / "test_labels.parquet"), on="record_id")
    jobs, keys = [], []
    for r in cfgmap[(cfgmap.config.isin(["ALL", "STABLE_PI@budget"]))].drop_duplicates("bundle_id").itertuples():
        if r.seed != seed and r.config != "ALL":
            continue
        tgt = "B" if r.source == "A" else "A"
        bg = dev[(dev.dataset_id == r.source) & (dev.partition == "FIT")].sort_values("record_id").sample(ec["background"], random_state=seed)
        src_s = stratified_sample(test[test.dataset_id == r.source], ec["n_source"], seed)
        cohorts = {"source": src_s}
        if r.seed == seed:
            cohorts["target"] = stratified_sample(test[test.dataset_id == tgt], ec["n_target"], seed)
        jobs.append({"bundle_path": paths.dev / r.source / "bundles" / r.bundle_id, "X_bg": bg, "cohorts": cohorts})
        keys.append(r)
    results = run_explain(jobs, cfg, n_jobs=min(8, len(jobs)))
    shap_dir = out / "shap"
    shap_dir.mkdir(exist_ok=True)
    summary, rankings = [], {}
    for r, (bid, ids, res) in zip(keys, results):
        for name, v in res.items():
            np.savez_compressed(shap_dir / f"{bid}_{name}.npz", shap=v["shap"], X=v["X"], ids=np.array(ids))
            rk = ranking(v["shap"], ids)
            rankings[(bid, name)] = rk
            summary.append({"bundle_id": bid, "source": r.source, "model": r.model, "config": r.config, "seed": r.seed,
                            "cohort": name, "n": int(v["shap"].shape[0]), "expected_value": v["expected"],
                            "additivity_max_abs_err": v["additivity_max_abs_err"],
                            "top10": " ".join(rk.index[:10])})
    comps = []
    for r in keys:
        if r.seed == seed:
            comps.append({"bundle_id": r.bundle_id, "model": r.model, "source": r.source, "config": r.config,
                          "kind": "source_vs_target", **compare(rankings[(r.bundle_id, "source")], rankings[(r.bundle_id, "target")])})
    for (src, model), g in pd.DataFrame([k._asdict() for k in keys if k.config == "ALL"]).groupby(["source", "model"]):
        bl = sorted(g.bundle_id)
        for a, b in itertools.combinations(bl, 2):
            comps.append({"bundle_id": f"{a} vs {b}", "model": model, "source": src, "config": "ALL",
                          "kind": "seed_stability_source", **compare(rankings[(a, "source")], rankings[(b, "source")])})
    pd.DataFrame(summary).to_csv(out / "shap_summary.csv", index=False)
    pd.DataFrame(comps).to_csv(out / "shap_compare.csv", index=False)
    rk_tab = pd.DataFrame({f"{bid}|{name}": rk for (bid, name), rk in rankings.items()})
    rk_tab.to_csv(out / "shap_mean_abs.csv")
    write_json(out / "shap_meta.json", {"explainer": "TreeExplainer", **{k: ec[k] for k in ec},
                                        "sampling": "label-stratified n/2 per class from TEST, seed fixed; background = source FIT"})
    return "completed"
