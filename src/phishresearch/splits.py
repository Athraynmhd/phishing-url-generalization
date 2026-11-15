"""Deterministic stratified group assignment FIT/VAL/TEST (PRD s10).

Groups are never split. Order of input rows does not matter: groups are first sorted by
group_id, shuffled with the split seed, then placed largest-first into the partition whose
per-class quota is most unfilled relative to the group's class mix.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import GateError

ALGORITHM = "greedy-stratified-group-v1"
PARTS = ("FIT", "VAL", "TEST")


def assign_groups(group_ids: np.ndarray, labels: np.ndarray, ratios: dict, seed: int) -> dict[str, str]:
    g = pd.DataFrame({"g": group_ids, "y": labels})
    tab = g.groupby("g")["y"].agg(n="size", pos="sum").sort_index()
    tab["neg"] = tab["n"] - tab["pos"]
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(tab))
    tab = tab.iloc[order]
    tab = tab.iloc[np.argsort(-tab["n"].to_numpy(), kind="stable")]   # largest first, ties by shuffle
    r = np.array([ratios[p] for p in PARTS], dtype=float)
    r = r / r.sum()
    totals = np.array([tab["neg"].sum(), tab["pos"].sum()], dtype=float)
    target = r[:, None] * totals[None, :]                               # parts x classes
    filled = np.zeros_like(target)
    out = {}
    for gid, neg, pos in zip(tab.index, tab["neg"].to_numpy(), tab["pos"].to_numpy()):
        v = np.array([neg, pos], dtype=float)
        # remaining relative need of each partition, weighted by this group's class mix
        need = ((target - filled) / np.maximum(totals, 1)[None, :]) @ v
        p = int(np.argmax(need))                                        # ties -> FIT, VAL, TEST order
        filled[p] += v
        out[gid] = PARTS[p]
    return out


def make_group_splits(cohort: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """cohort: in-cohort rows with dataset_id, record_id, group_id, label."""
    sc = cfg["splits"]
    frames = []
    for s in sorted(cohort["dataset_id"].unique()):
        d = cohort[cohort.dataset_id == s].sort_values("record_id")
        mapping = assign_groups(d["group_id"].to_numpy(), d["label"].to_numpy(), sc["ratios"], int(sc["seed"]))
        frames.append(pd.DataFrame({"record_id": d["record_id"].to_numpy(), "dataset_id": s,
                                    "group_id": d["group_id"].to_numpy(),
                                    "partition": d["group_id"].map(mapping).to_numpy()}))
    splits = pd.concat(frames, ignore_index=True).sort_values(["dataset_id", "record_id"]).reset_index(drop=True)
    check_splits(splits.merge(cohort[["record_id", "label"]], on="record_id"))
    return splits


def check_splits(s: pd.DataFrame) -> dict:
    """Gate: group-disjoint partitions, both classes present in every partition."""
    rep = {}
    for ds, d in s.groupby("dataset_id"):
        parts = {p: set(d.loc[d.partition == p, "group_id"]) for p in PARTS}
        for i, a in enumerate(PARTS):
            for b in PARTS[i + 1:]:
                if parts[a] & parts[b]:
                    raise GateError(f"{ds}: groups shared between {a} and {b}")
        for p in PARTS:
            dp = d[d.partition == p]
            if "label" in dp and dp["label"].nunique() < 2:
                raise GateError(f"{ds}/{p}: single-class partition")
            rep[f"{ds}/{p}"] = {"n": int(len(dp)), "groups": int(dp.group_id.nunique()),
                                "frac": float(len(dp) / len(d)),
                                **({"prevalence": float(dp.label.mean())} if "label" in dp else {})}
    return rep
