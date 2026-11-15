"""Source-only development for one source (PRD s12-14): nested k selection on FIT,
final fits on FIT, thresholds on source VAL. Never touches TEST.

Per seed:
  outer 3 group folds of FIT -> PI on outer-train only (3 inner folds) -> for every
  classifier/selector/k: fit on outer-train, score outer-holdout (AP, F1@0.5)
  -> k = smallest within tol of best mean AP -> PI on full FIT -> final models:
  ALL, MEAN_PI@k_mean (budget), STABLE_PI@k_stable (budget = matched), MEAN_PI@k_stable (matched).
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from .common import GateError, hash_ids, write_json
from .features import FEATURE_IDS
from .models import fit_model
from .selection import FitHook, compute_pi, choose_k, group_folds, select
from .statistics import compute_metrics
from .thresholds import choose_threshold

SELECTORS = ("MEAN_PI", "STABLE_PI")
POLICIES = ("f1_max", "fpr_le", "fixed_0.5")


def bundle_id(source, model, selector, k, seed) -> str:
    return f"{source}-{model}-{selector}-k{k}-s{seed}"


def _xyz(df: pd.DataFrame):
    return (df[list(FEATURE_IDS)], df["label"].to_numpy().astype(int), df["group_id"].to_numpy(),
            df["record_id"].to_numpy())


def develop_source(source: str, fit_df: pd.DataFrame, val_df: pd.DataFrame, cfg: dict, threads: int,
                   out_dir: Path, *, seeds=None, models=("RF", "LGBM"), n_estimators: int | None = None,
                   fit_hook: FitHook = None, log=print, provenance: dict | None = None) -> dict:
    sc = cfg["selection"]
    seeds = list(seeds or cfg["models"]["seeds"])
    fold_seed = int(cfg["splits"]["seed"])
    X, y, g, ids = _xyz(fit_df)
    Xv, yv, _, idv = _xyz(val_df)
    if set(ids) & set(idv):
        raise GateError("FIT and VAL overlap")
    outer = group_folds(y, g, sc["folds"], fold_seed)
    out_dir = Path(out_dir)
    (out_dir / "bundles").mkdir(parents=True, exist_ok=True)
    (out_dir / "selectors").mkdir(parents=True, exist_ok=True)
    cv_rows, finals, timing = [], [], {"pi_seconds": 0.0, "outer_fit_seconds": 0.0, "final_fit_seconds": {}}
    summary = {"source": source, "fit_n": len(y), "val_n": len(yv), "fit_ids_hash": hash_ids(ids),
               "val_ids_hash": hash_ids(idv), "seeds": {}, "outer_fold_sizes": [[len(a), len(b)] for a, b in outer]}

    for seed in seeds:
        outer_hashes = []
        for o, (tr, ho) in enumerate(outer):
            t0 = time.perf_counter()
            pi = compute_pi(X.iloc[tr], y[tr], g[tr], ids[tr], seed=seed, fold_seed=fold_seed + 1 + o, cfg=cfg,
                            threads=threads, n_estimators=n_estimators, fit_hook=fit_hook)
            timing["pi_seconds"] += time.perf_counter() - t0
            outer_hashes.append(pi.fit_ids_hash)
            write_json(out_dir / "selectors" / f"pi_s{seed}_outer{o}.json", pi.to_json())
            for method in SELECTORS:
                for k in sc["k_candidates"]:
                    sel = select(pi, method, k, sc["q"])
                    for model in models:
                        if fit_hook:
                            fit_hook(ids[tr], "outer_classifier_fit")
                            fit_hook(ids[ho], "outer_holdout_score")
                        t0 = time.perf_counter()
                        b = fit_model(model, X.iloc[tr][sel.selected], y[tr], seed, cfg, threads, n_estimators)
                        s = b.score(X.iloc[ho][sel.selected])
                        timing["outer_fit_seconds"] += time.perf_counter() - t0
                        cv_rows.append({"source": source, "seed": seed, "outer_fold": o, "model": model,
                                        "selector": method, "k": k, "selected": " ".join(sel.selected),
                                        "ap": average_precision_score(y[ho], s),
                                        "f1_at_0.5": compute_metrics(y[ho], s, 0.5)["values"]["f1"]})
            log(f"[develop {source}] seed {seed} outer fold {o} done")

        cv = pd.DataFrame([r for r in cv_rows if r["seed"] == seed])
        chosen = {}
        for model in models:
            for method in SELECTORS:
                ap = cv[(cv.model == model) & (cv.selector == method)].groupby("k")["ap"].mean()
                chosen[(model, method)] = choose_k({int(k): float(v) for k, v in ap.items()}, sc["k_tolerance_ap"])

        t0 = time.perf_counter()
        pi_full = compute_pi(X, y, g, ids, seed=seed, fold_seed=fold_seed, cfg=cfg, threads=threads,
                             n_estimators=n_estimators, fit_hook=fit_hook)
        timing["pi_seconds"] += time.perf_counter() - t0
        if pi_full.fit_ids_hash in outer_hashes:
            raise GateError("full-FIT selector hash equals an outer-train selector hash (nested CV broken)")
        write_json(out_dir / "selectors" / f"pi_s{seed}_full.json", pi_full.to_json())

        seed_info = {"chosen_k": {f"{m}/{s}": k for (m, s), k in chosen.items()}, "outer_selector_hashes": outer_hashes,
                     "full_selector_hash": pi_full.fit_ids_hash, "bundles": []}
        for model in models:
            k_mean, k_stab = chosen[(model, "MEAN_PI")], chosen[(model, "STABLE_PI")]
            plan = {("ALL", len(FEATURE_IDS)): ["all"]}
            plan.setdefault(("MEAN_PI", k_mean), []).append("budget")
            plan.setdefault(("STABLE_PI", k_stab), []).extend(["budget", "matched"])
            plan.setdefault(("MEAN_PI", k_stab), []).append("matched")
            for (method, k), roles in plan.items():
                if method == "ALL":
                    selected, sel_json = list(FEATURE_IDS), None
                else:
                    sel = select(pi_full, method, k, sc["q"])
                    selected, sel_json = sel.selected, sel.to_json()
                bid = bundle_id(source, model, method, k, seed)
                if fit_hook:
                    fit_hook(ids, "final_fit")
                t0 = time.perf_counter()
                b = fit_model(model, X[selected], y, seed, cfg, threads, n_estimators)
                fit_s = time.perf_counter() - t0
                timing["final_fit_seconds"][bid] = fit_s
                if fit_hook:
                    fit_hook(idv, "threshold_val")
                sv = b.score(Xv[selected])
                thr = {p: choose_threshold(yv, sv, p, cfg["thresholds"]["fpr_max"]) for p in POLICIES}
                b.meta.update({"bundle_id": bid, "source": source, "selector": method, "k": k, "roles": roles,
                               "seed": seed, "selector_artifact": sel_json, "thresholds": thr,
                               "fit_ids_hash": hash_ids(ids), "val_ids_hash": hash_ids(idv),
                               "fit_seconds": fit_s, "provenance": provenance or {},
                               "val_metrics": {p: compute_metrics(yv, sv, t["threshold"]) for p, t in thr.items()}})
                b.save(out_dir / "bundles" / bid)
                seed_info["bundles"].append(bid)
                finals.append({"bundle_id": bid, "model": model, "selector": method, "k": k, "seed": seed,
                               "roles": " ".join(roles), "val_f1": thr["f1_max"]["val_f1"],
                               "threshold_f1": thr["f1_max"]["threshold"], "threshold_fpr": thr["fpr_le"]["threshold"]})
        summary["seeds"][str(seed)] = seed_info
        log(f"[develop {source}] seed {seed} finals: {seed_info['chosen_k']}")

    pd.DataFrame(cv_rows).to_csv(out_dir / "outer_cv.csv", index=False)
    pd.DataFrame(finals).to_csv(out_dir / "finals.csv", index=False)
    summary["timing"] = timing
    summary["n_estimators_override"] = n_estimators
    summary["provenance"] = provenance or {}
    write_json(out_dir / "develop.json", summary)
    return summary
