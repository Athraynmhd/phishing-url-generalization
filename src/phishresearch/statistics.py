"""Metrics (PRD s14) and paired domain-cluster bootstrap (PRD s15)."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


def confusion(y: np.ndarray, yhat: np.ndarray) -> dict:
    y, yhat = np.asarray(y).astype(int), np.asarray(yhat).astype(int)
    return {"TN": int(((y == 0) & (yhat == 0)).sum()), "FP": int(((y == 0) & (yhat == 1)).sum()),
            "FN": int(((y == 1) & (yhat == 0)).sum()), "TP": int(((y == 1) & (yhat == 1)).sum())}


def _div(a, b, flags, name):
    if b == 0:
        flags.append(f"zero_denominator:{name}")
        return 0.0
    return a / b


def metrics_from_counts(c: dict, flags: list | None = None) -> dict:
    flags = [] if flags is None else flags
    TN, FP, FN, TP = c["TN"], c["FP"], c["FN"], c["TP"]
    prec = _div(TP, TP + FP, flags, "precision")
    rec = _div(TP, TP + FN, flags, "recall")
    spec = _div(TN, TN + FP, flags, "specificity")
    f1 = _div(2 * TP, 2 * TP + FP + FN, flags, "f1")
    mcc_den = np.sqrt(float(TP + FP) * (TP + FN) * (TN + FP) * (TN + FN))
    mcc = _div(TP * TN - FP * FN, mcc_den, flags, "mcc")
    n = TN + FP + FN + TP
    return {"precision": prec, "recall": rec, "specificity": spec, "f1": f1, "mcc": float(mcc),
            "balanced_accuracy": (rec + spec) / 2, "accuracy": _div(TP + TN, n, flags, "accuracy"),
            "fpr": _div(FP, FP + TN, flags, "fpr")}


def compute_metrics(y, scores, threshold: float) -> dict:
    y = np.asarray(y).astype(int)
    s = np.asarray(scores, dtype=np.float64)
    if not np.isfinite(s).all() or (s < 0).any() or (s > 1).any():
        raise ValueError("scores must be finite probabilities in [0,1]")
    yhat = (s >= threshold).astype(int)
    c = confusion(y, yhat)
    flags: list = []
    m = metrics_from_counts(c, flags)
    if len(np.unique(y)) == 2:
        m["roc_auc"] = float(roc_auc_score(y, s))
        m["average_precision"] = float(average_precision_score(y, s, pos_label=1))
    else:
        flags.append("single_class:auc_ap_undefined")
        m["roc_auc"] = m["average_precision"] = None
    return {**c, "n_rows": int(len(y)), "prevalence": float(y.mean()) if len(y) else 0.0,
            "threshold": float(threshold), "values": m, "warnings": flags}


# ------------------------------------------------------------------ cluster bootstrap
def _group_counts(y, yhat, gidx, n_groups):
    y, yhat = np.asarray(y).astype(int), np.asarray(yhat).astype(int)
    out = np.zeros((n_groups, 4))
    for j, (a, b) in enumerate(((0, 0), (0, 1), (1, 0), (1, 1))):   # TN FP FN TP
        out[:, j] = np.bincount(gidx, weights=((y == a) & (yhat == b)).astype(float), minlength=n_groups)
    return out


def _f1(c):  # c[..., 4] = TN FP FN TP
    den = 2 * c[..., 3] + c[..., 1] + c[..., 2]
    return np.where(den > 0, 2 * c[..., 3] / np.where(den > 0, den, 1), 0.0)


def paired_cluster_bootstrap(groups: np.ndarray, y: np.ndarray, pred_a: list[np.ndarray], pred_b: list[np.ndarray],
                             n_boot: int, seed: int) -> dict:
    """Delta F1 (A - B), averaged over seeds, with domains resampled with replacement.
    pred_a/pred_b: one binary prediction vector per seed, aligned with y/groups. Every replicate
    uses the same resampled domains for both models and all seeds."""
    uniq, gidx = np.unique(groups, return_inverse=True)
    G = len(uniq)
    ca = [_group_counts(y, p, gidx, G) for p in pred_a]
    cb = [_group_counts(y, p, gidx, G) for p in pred_b]
    gpos = np.bincount(gidx, weights=np.asarray(y).astype(float), minlength=G)
    gn = np.bincount(gidx, minlength=G).astype(float)
    point = float(np.mean([_f1(a.sum(0)) - _f1(b.sum(0)) for a, b in zip(ca, cb)]))
    rng = np.random.default_rng(seed)
    deltas, invalid = [], 0
    for _ in range(n_boot):
        w = np.bincount(rng.integers(0, G, G), minlength=G).astype(float)
        pos = w @ gpos
        if pos == 0 or pos == w @ gn:          # single-class replicate -> skip
            invalid += 1
            continue
        deltas.append(np.mean([_f1(w @ a) - _f1(w @ b) for a, b in zip(ca, cb)]))
    d = np.array(deltas)
    return {"delta": point, "ci_low": float(np.percentile(d, 2.5)) if len(d) else None,
            "ci_high": float(np.percentile(d, 97.5)) if len(d) else None,
            "n_boot": n_boot, "n_invalid": invalid, "invalid_fraction": invalid / n_boot,
            "n_domains": int(G), "median_cluster_size": float(np.median(gn)),
            "largest_cluster_share": float(gn.max() / gn.sum())}


def cluster_bootstrap_ci(groups, y, preds: list[np.ndarray], n_boot: int, seed: int) -> dict:
    """CI of a single configuration's seed-mean F1 (zero-vector comparator)."""
    zero = [np.zeros_like(p) for p in preds]
    r = paired_cluster_bootstrap(groups, y, preds, zero, n_boot, seed)
    return {"f1": r["delta"], "ci_low": r["ci_low"], "ci_high": r["ci_high"], "invalid_fraction": r["invalid_fraction"]}
