"""Permutation-importance selectors MEAN_PI and STABLE_PI (PRD s12).

fit_selector never sees anything but the rows it is given. The PI computation (3 stratified
group folds x RF proxy x 5 permutations, AP scoring) does not depend on k or on the
ranking rule, so one PiResult serves both selectors and every k on the same training rows.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.model_selection import StratifiedGroupKFold

from .common import hash_ids

FitHook = Callable[[np.ndarray, str], None] | None   # spy for leakage tests: (record_ids, purpose)


def group_folds(y: np.ndarray, groups: np.ndarray, n_splits: int, seed: int):
    return list(StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed).split(np.zeros(len(y)), y, groups))


@dataclass
class PiResult:
    feature_ids: list[str]
    pi_folds: np.ndarray                  # folds x features (mean over repeats)
    pi_repeats: np.ndarray                # folds x repeats x features
    fit_ids_hash: str
    n_rows: int

    def to_json(self) -> dict:
        return {"feature_ids": self.feature_ids, "pi_folds": self.pi_folds.tolist(),
                "pi_repeats": self.pi_repeats.tolist(), "fit_ids_hash": self.fit_ids_hash, "n_rows": self.n_rows}


@dataclass
class SelectorArtifact:
    method: str
    k: int
    selected: list[str]
    ranking: list[str]
    fit_ids_hash: str
    degenerate: bool
    stats: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return asdict(self)


def compute_pi(X: pd.DataFrame, y: np.ndarray, groups: np.ndarray, record_ids: np.ndarray, *, seed: int,
               fold_seed: int, cfg: dict, threads: int, n_estimators: int | None = None,
               fit_hook: FitHook = None) -> PiResult:
    sc = cfg["selection"]
    pp = dict(sc["proxy_rf"])
    if n_estimators is not None:
        pp["n_estimators"] = n_estimators
    folds = group_folds(y, groups, sc["folds"], fold_seed)
    reps = []
    for tr, ho in folds:
        if fit_hook:
            fit_hook(record_ids[tr], "selector_proxy_fit")
            fit_hook(record_ids[ho], "selector_pi_score")
        proxy = RandomForestClassifier(**pp, class_weight=None, random_state=seed, n_jobs=threads)
        proxy.fit(X.iloc[tr].to_numpy(), y[tr])
        r = permutation_importance(proxy, X.iloc[ho].to_numpy(), y[ho], scoring="average_precision",
                                   n_repeats=sc["pi_repeats"], random_state=seed, n_jobs=1)
        reps.append(r.importances.T)       # repeats x features
    rep = np.stack(reps)                   # folds x repeats x features
    return PiResult(list(X.columns), rep.mean(axis=1), rep, hash_ids(record_ids), len(y))


def _fold_ranks(pi_folds: np.ndarray, ids: list[str]) -> np.ndarray:
    """rank (1 = best) of each feature within each fold: PI desc, tie feature id asc."""
    ranks = np.empty_like(pi_folds)
    order_ids = np.array(ids)
    for f in range(pi_folds.shape[0]):
        order = sorted(range(len(ids)), key=lambda j: (-pi_folds[f, j], order_ids[j]))
        ranks[f, order] = np.arange(1, len(ids) + 1)
    return ranks


def rank_features(pi: PiResult, method: str, q: int) -> tuple[list[str], dict]:
    ids, P = pi.feature_ids, pi.pi_folds
    mean = P.mean(axis=0)
    ranks = _fold_ranks(P, ids)
    med = np.median(P, axis=0)
    mad = np.median(np.abs(ranks - np.median(ranks, axis=0)), axis=0)
    votes = ((ranks <= q) & (P > 0)).sum(axis=0)
    if method == "MEAN_PI":
        order = sorted(range(len(ids)), key=lambda j: (-mean[j], ids[j]))
    elif method == "STABLE_PI":
        order = sorted(range(len(ids)), key=lambda j: (-votes[j], -med[j], mad[j], ids[j]))
    else:
        raise ValueError(method)
    stats = {"mean_pi": dict(zip(ids, mean.tolist())), "median_pi": dict(zip(ids, med.tolist())),
             "rank_mad": dict(zip(ids, mad.tolist())), "votes": dict(zip(ids, votes.astype(int).tolist()))}
    return [ids[j] for j in order], stats


def select(pi: PiResult, method: str, k: int, q: int) -> SelectorArtifact:
    ranking, stats = rank_features(pi, method, q)
    return SelectorArtifact(method=method, k=k, selected=sorted(ranking[:k]), ranking=ranking,
                            fit_ids_hash=pi.fit_ids_hash, degenerate=bool((pi.pi_folds <= 0).all()), stats=stats)


def fit_selector(X, y, groups, record_ids, k: int, method: str, *, seed: int, fold_seed: int, cfg: dict,
                 threads: int, fit_hook: FitHook = None) -> SelectorArtifact:
    """PRD-named entry point; develop() reuses compute_pi across k/methods instead."""
    pi = compute_pi(X, y, groups, record_ids, seed=seed, fold_seed=fold_seed, cfg=cfg, threads=threads,
                    fit_hook=fit_hook)
    return select(pi, method, k, cfg["selection"]["q"])


def choose_k(outer_ap: dict[int, float], tol: float) -> int:
    """Smallest k whose mean outer AP is within `tol` of the best."""
    best = max(outer_ap.values())
    return min(k for k, ap in outer_ap.items() if ap >= best - tol)
