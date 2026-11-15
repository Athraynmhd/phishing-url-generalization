"""Parse -> within-source dedup -> label-conflict quarantine -> cross-source overlap audit
-> symmetric domain purge (PRD s9). Also produces the data-quality report.

Every removed record has exactly one primary reason (first stage that removed it, fixed
priority) plus independent secondary flags, so attrition reconciles without double counting.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .urls import PARSER_VERSION, ParsedURL, canonicalize_url, group_id_for

REASON_PRIORITY = ["parse_quarantine", "within_source_duplicate", "label_conflict", "cross_source_domain_purge"]


def parse_records(df: pd.DataFrame, max_length: int) -> pd.DataFrame:
    out = df.copy()
    keys, hosts, gkeys, status = [], [], [], []
    for u in out["url_raw"]:
        p = canonicalize_url(u, max_length)
        if isinstance(p, ParsedURL):
            keys.append(p.url_key); hosts.append(p.host); gkeys.append(p.group_key); status.append("ok")
        else:
            keys.append(None); hosts.append(None); gkeys.append(None); status.append(p.reason)
    out["url_key"], out["host_key"], out["group_key"], out["parse_status"] = keys, hosts, gkeys, status
    out["group_id"] = [group_id_for(g) if g is not None else None for g in gkeys]
    out["parser_version"] = PARSER_VERSION
    return out


def build_cohort(records: pd.DataFrame, purge_shared_groups: bool = True) -> pd.DataFrame:
    """records: parsed rows of both sources. Returns all rows with `reason` (None = kept)
    and secondary flags."""
    df = records.sort_values(["dataset_id", "source_file", "original_row"], kind="mergesort").reset_index(drop=True)
    reason = pd.Series([None] * len(df), dtype=object)
    ok = df["parse_status"].eq("ok")
    reason[~ok] = "parse_quarantine"

    # within-source exact duplicates (same url_key & label): keep first in file/row order
    dup = ok & df.duplicated(["dataset_id", "url_key", "label"], keep="first")
    reason[dup & reason.isna()] = "within_source_duplicate"
    df["flag_within_source_duplicate"] = dup

    # url_key with conflicting labels anywhere (within or across sources) -> quarantine all
    n_lab = df[ok].groupby("url_key")["label"].nunique()
    conflict_keys = set(n_lab[n_lab > 1].index)
    conflict = ok & df["url_key"].isin(conflict_keys)
    reason[conflict & reason.isna()] = "label_conflict"
    df["flag_label_conflict"] = conflict

    # cross-source overlap audit (on rows still alive)
    alive = reason.isna()
    keys_by_src = {s: set(df.loc[alive & df.dataset_id.eq(s), "url_key"]) for s in ("A", "B")}
    grp_by_src = {s: set(df.loc[alive & df.dataset_id.eq(s), "group_id"]) for s in ("A", "B")}
    shared_keys = keys_by_src["A"] & keys_by_src["B"]
    shared_groups = grp_by_src["A"] & grp_by_src["B"]
    df["flag_cross_source_exact"] = ok & df["url_key"].isin(shared_keys)
    df["flag_cross_source_group"] = ok & df["group_id"].isin(shared_groups)
    if purge_shared_groups:
        reason[alive & df["flag_cross_source_group"]] = "cross_source_domain_purge"
    df["reason"] = reason
    df["in_cohort"] = reason.isna()
    return df


def _class_counts(d: pd.DataFrame) -> dict:
    vc = d["label"].value_counts()
    return {"n": int(len(d)), "benign": int(vc.get(0, 0)), "phishing": int(vc.get(1, 0))}


def _group_stats(d: pd.DataFrame) -> dict:
    g = d.groupby("group_id")
    sizes = g.size()
    mix = g["label"].agg(["min", "max"])
    top = d.groupby("group_key").size().sort_values(ascending=False).head(10)
    return {
        "n_groups": int(len(sizes)),
        "size_max": int(sizes.max()) if len(sizes) else 0,
        "size_quantiles": {str(q): float(sizes.quantile(q)) for q in (0.5, 0.9, 0.99)} if len(sizes) else {},
        "largest_group_share": float(sizes.max() / sizes.sum()) if len(sizes) else 0.0,
        "groups_benign_only": int(((mix["min"] == 0) & (mix["max"] == 0)).sum()),
        "groups_phishing_only": int(((mix["min"] == 1) & (mix["max"] == 1)).sum()),
        "groups_mixed": int(((mix["min"] == 0) & (mix["max"] == 1)).sum()),
        "groups_with_benign": int((mix["min"] == 0).sum()),
        "groups_with_phishing": int((mix["max"] == 1).sum()),
        "top_groups": {k: int(v) for k, v in top.items()},
    }


def audit_report(cohort: pd.DataFrame, cfg: dict) -> dict:
    rep: dict = {"parser_version": PARSER_VERSION, "sources": {}, "warnings": []}
    fc = cfg["cohort"]
    for s in ("A", "B"):
        d = cohort[cohort.dataset_id == s]
        stages = {"loaded": _class_counts(d)}
        alive = pd.Series(True, index=d.index)
        for r in REASON_PRIORITY:
            alive &= d["reason"].ne(r)
            stages[f"after_{r}"] = _class_counts(d[alive])
        removed = {r: _class_counts(d[d.reason == r]) for r in REASON_PRIORITY}
        parse_fail = d.loc[d.parse_status != "ok", "parse_status"].value_counts().to_dict()
        lens = d["url_raw"].str.len()
        kept = d[d.in_cohort]
        pre_purge = d[d.reason.isna() | d.reason.eq("cross_source_domain_purge")]
        s_rep = {
            "stages": stages,
            "removed_primary_reason": removed,
            "parse_fail_reasons": {k: int(v) for k, v in parse_fail.items()},
            "empty_url": int((d["url_raw"].str.strip() == "").sum()),
            "secondary_flags": {c: int(d[c].sum()) for c in d.columns if c.startswith("flag_")},
            "url_length": {"max": int(lens.max()), "p99": float(lens.quantile(0.99)), "median": float(lens.median())},
            "groups_before_purge": _group_stats(pre_purge),
            "groups_cohort": _group_stats(kept),
            "reconciles": int(sum(v["n"] for v in removed.values()) + len(kept)) == int(len(d)),
        }
        for cls, lab in (("benign", 0), ("phishing", 1)):
            before = int((pre_purge.label == lab).sum())
            after = int((kept.label == lab).sum())
            loss = 1 - after / before if before else 1.0
            s_rep[f"purge_loss_{cls}"] = loss
            if loss > fc["feasibility_max_class_loss"]:
                rep["warnings"].append(f"FEASIBILITY: source {s} purge removed {loss:.1%} of {cls}")
            ng = s_rep["groups_cohort"][f"groups_with_{cls}"]
            if ng < fc["feasibility_min_groups_per_class"]:
                rep["warnings"].append(f"FEASIBILITY: source {s} has only {ng} {cls} groups")
        rep["sources"][s] = s_rep
    alive = cohort[cohort.reason.isna() | cohort.reason.eq("cross_source_domain_purge")]
    rep["cross_source"] = {
        "exact_url_key_overlap_records": int(cohort["flag_cross_source_exact"].sum()),
        "shared_groups": int(alive.loc[alive.flag_cross_source_group, "group_id"].nunique()),
        "top_shared_groups": {k: int(v) for k, v in alive[alive.flag_cross_source_group]
                              .groupby("group_key").size().sort_values(ascending=False).head(15).items()},
        "cohort_group_intersection": int(len(set(cohort.loc[cohort.in_cohort & cohort.dataset_id.eq("A"), "group_id"])
                                             & set(cohort.loc[cohort.in_cohort & cohort.dataset_id.eq("B"), "group_id"]))),
    }
    return rep


def label_mapping_check(source_a: pd.DataFrame, verification: pd.DataFrame) -> dict:
    """Join repo B's EBBU copy with source A on the raw URL; agreement => same label convention."""
    a = source_a[["url_raw", "label"]].drop_duplicates("url_raw")
    m = verification.merge(a, on="url_raw", suffixes=("_repoB", "_A"))
    agree = float(np.mean(m["label_repoB"].values == m["label_A"].values)) if len(m) else float("nan")
    return {"verification_rows": int(len(verification)), "joined_rows": int(len(m)), "agreement": agree,
            "conclusion": "repo B uses 1=phishing, 0=benign" if agree == 1.0 else "AMBIGUOUS - block training"}
