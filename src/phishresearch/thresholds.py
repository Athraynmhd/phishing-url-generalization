"""Source-VAL threshold selection (PRD s14). Decision rule: score >= threshold."""
from __future__ import annotations

import numpy as np


def _sweep(y: np.ndarray, s: np.ndarray):
    """Candidates = unique scores + nextafter(max, inf) (all-negative). Returns thresholds
    (ascending) with TP, FP at each."""
    y = np.asarray(y).astype(int)
    s = np.asarray(s, dtype=np.float64)
    cand = np.unique(s)
    cand = np.append(cand, np.nextafter(cand[-1], np.inf))
    pos_sorted = np.sort(s[y == 1])
    neg_sorted = np.sort(s[y == 0])
    tp = len(pos_sorted) - np.searchsorted(pos_sorted, cand, side="left")   # count(score >= t)
    fp = len(neg_sorted) - np.searchsorted(neg_sorted, cand, side="left")
    return cand, tp, fp, int((y == 1).sum()), int((y == 0).sum())


def choose_threshold(y_val, scores, policy: str, fpr_max: float = 0.01) -> dict:
    cand, tp, fp, P, N = _sweep(y_val, scores)
    fn = P - tp
    if policy == "f1_max":
        denom = 2 * tp + fp + fn
        f1 = np.where(denom > 0, 2 * tp / np.maximum(denom, 1), 0.0)
        best = f1.max()
        idx = int(np.flatnonzero(f1 == best)[-1])          # tie -> largest threshold
        return {"policy": policy, "threshold": float(cand[idx]), "val_f1": float(best),
                "val_tp": int(tp[idx]), "val_fp": int(fp[idx]), "n_pos": P, "n_neg": N}
    if policy == "fpr_le":
        fpr = fp / max(N, 1)
        ok = np.flatnonzero(fpr <= fpr_max)                 # never empty: sentinel gives FP=0
        rec = tp[ok] / max(P, 1)
        best = rec.max()
        idx = int(ok[np.flatnonzero(rec == best)[-1]])     # tie on recall -> largest threshold
        return {"policy": policy, "fpr_max": fpr_max, "threshold": float(cand[idx]),
                "val_recall": float(tp[idx] / max(P, 1)), "val_fp": int(fp[idx]), "n_neg": N,
                "val_achieved_fpr": float(fp[idx] / max(N, 1)), "n_pos": P}
    if policy == "fixed_0.5":
        return {"policy": policy, "threshold": 0.5}
    raise ValueError(policy)
