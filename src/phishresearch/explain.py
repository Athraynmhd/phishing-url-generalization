"""SHAP attributions on the actual classifiers (PRD s16).

TreeExplainer, feature_perturbation=interventional, model_output=probability (supported for
both RF and LightGBM in shap 0.49 - verified by additivity against predict_proba).
Same model + same background (<=100 source-FIT rows, fixed seed) for source vs target.
Explanation samples are label-stratified (n/2 per class) and drawn after freeze.
Scope decision D-09: seed-17 bundles of ALL and STABLE_PI(budget); seed stability on ALL.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import spearmanr

from .models import ModelBundle


def stratified_sample(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    parts = [g.sample(min(len(g), n // 2), random_state=seed) for _, g in df.groupby("label")]
    return pd.concat(parts).sort_values("record_id")


def shap_values(bundle: ModelBundle, X_bg: pd.DataFrame, X: pd.DataFrame, cfg: dict) -> tuple[np.ndarray, float, float]:
    import shap
    ec = cfg["explain"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        e = shap.TreeExplainer(bundle.model, data=bundle.matrix(X_bg), feature_perturbation=ec["feature_perturbation"],
                               model_output=ec["model_output"])
        sv = np.asarray(e.shap_values(bundle.matrix(X), check_additivity=False))
    ev = np.asarray(e.expected_value)
    pos = list(bundle.model.classes_).index(1)
    if sv.ndim == 3:                       # (n, features, classes)
        sv, ev = sv[..., pos], ev[pos]
    add_err = float(np.abs(float(ev) + sv.sum(1) - bundle.score(X)).max())
    return sv, float(ev), add_err


def _job(bundle_path, X_bg, cohorts: dict, cfg):
    b = ModelBundle.load(Path(bundle_path))
    out = {}
    for name, X in cohorts.items():
        sv, ev, err = shap_values(b, X_bg[b.feature_ids], X[b.feature_ids], cfg)
        out[name] = {"shap": sv, "expected": ev, "additivity_max_abs_err": err, "X": X[b.feature_ids].to_numpy()}
    return b.meta["bundle_id"], b.feature_ids, out


def ranking(sv: np.ndarray, ids: list[str]) -> pd.Series:
    return pd.Series(np.abs(sv).mean(0), index=ids).sort_values(ascending=False)


def compare(r1: pd.Series, r2: pd.Series, top: int = 10) -> dict:
    common = r1.index
    rho = spearmanr(r1[common].values, r2[common].values).statistic if len(common) > 2 else float("nan")
    t1, t2 = set(r1.index[:top]), set(r2.index[:top])
    return {"spearman": float(rho), f"top{top}_jaccard": len(t1 & t2) / len(t1 | t2)}


def run_explain(jobs: list[dict], cfg: dict, n_jobs: int = 4) -> list:
    """jobs: [{bundle_path, X_bg, cohorts:{name: X}}] -> results per bundle."""
    return Parallel(n_jobs=n_jobs, backend="loky")(
        delayed(_job)(j["bundle_path"], j["X_bg"], j["cohorts"], cfg) for j in jobs)
