"""`audit` and `prepare` stages + the development loader.

Loader policy (PRD s10-11): development code calls `load_dev`, which only exposes FIT and
VAL. TEST features live in test_vault/ without labels; TEST labels sit in a separate file
that only evaluation.py opens, and only after the freeze manifest verifies.
This is a procedural software control, not a cryptographic guarantee.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .adapters import load_dataset, load_verification_copy
from .cohort import audit_report, build_cohort, label_mapping_check, parse_records
from .common import GateError, Paths, load_yaml, read_json, write_json
from .features import FEATURE_IDS, extract_parsed, feature_schema_hash
from .splits import ALGORITHM, check_splits, make_group_splits
from .urls import canonicalize_url, psl_hash

DEV_PARTS = ("FIT", "VAL")


def run_audit(cfg: dict, registry: dict | None, paths: Paths, verify_labels: bool = True,
              frames: list[pd.DataFrame] | None = None) -> dict:
    """frames: pre-loaded [A, B] canonical frames (synthetic smoke); default = registry sources."""
    frames = frames or [load_dataset(s, registry, paths.raw) for s in ("A", "B")]
    raw = pd.concat(frames, ignore_index=True)
    parsed = parse_records(raw, cfg["parser"]["max_url_length"])
    cohort = build_cohort(parsed, cfg["cohort"]["purge_shared_groups"])
    rep = audit_report(cohort, cfg)
    rep["psl_sha256"] = psl_hash()
    if verify_labels:
        rep["label_mapping_check"] = label_mapping_check(frames[0], load_verification_copy(registry, paths.raw))
        if rep["label_mapping_check"]["agreement"] != 1.0:
            raise GateError("label mapping check failed - training blocked")
    # observed counts back into the raw manifest
    man_path = paths.raw / "manifest.json"
    if man_path.exists():
        man = read_json(man_path)
        counts = raw.groupby(["dataset_id", "source_file"]).size()
        for key, f in man["files"].items():
            if (f["source_id"], f["file"]) in counts.index:
                f["observed_records"] = int(counts[(f["source_id"], f["file"])])
                if f.get("expected_records") and f["observed_records"] != f["expected_records"]:
                    rep["warnings"].append(f"{key}: observed {f['observed_records']} != expected {f['expected_records']}")
        write_json(man_path, man)
    paths.processed.mkdir(parents=True, exist_ok=True)
    cohort.to_parquet(paths.processed / "records.parquet", index=False)
    cohort[~cohort.in_cohort].to_parquet(paths.processed / "quarantine.parquet", index=False)
    write_json(paths.artifacts / "audit.json", rep)
    return rep


def run_prepare(cfg: dict, paths: Paths) -> dict:
    rec = pd.read_parquet(paths.processed / "records.parquet")
    coh = rec[rec.in_cohort].reset_index(drop=True)
    splits = make_group_splits(coh, cfg)
    splits.to_parquet(paths.processed / "splits.parquet", index=False)
    kw = cfg["features"]["keywords"]
    parsed = [canonicalize_url(u, cfg["parser"]["max_url_length"]) for u in coh["url_raw"]]
    X = extract_parsed(parsed, FEATURE_IDS, kw)
    feats = pd.concat([coh[["record_id", "dataset_id", "group_id", "label"]], X], axis=1)
    feats = feats.merge(splits[["record_id", "partition"]], on="record_id", validate="one_to_one")
    dev = feats[feats.partition.isin(DEV_PARTS)]
    test = feats[feats.partition == "TEST"]
    dev.to_parquet(paths.processed / "dev_features.parquet", index=False)
    vault = paths.processed / "test_vault"
    vault.mkdir(parents=True, exist_ok=True)
    test.drop(columns=["label"]).to_parquet(vault / "test_features.parquet", index=False)
    test[["record_id", "label"]].to_parquet(vault / "test_labels.parquet", index=False)
    rep = {"split_algorithm": ALGORITHM, "split_seed": cfg["splits"]["seed"],
           "feature_schema_hash": feature_schema_hash(kw), "n_features": len(FEATURE_IDS),
           "partitions": check_splits(feats[["record_id", "dataset_id", "group_id", "partition", "label"]])}
    write_json(paths.artifacts / "prepare.json", rep)
    return rep


def load_dev(paths: Paths, source: str, part: str) -> pd.DataFrame:
    if part not in DEV_PARTS:
        raise GateError(f"development loader refuses partition {part!r}; TEST is read only by `evaluate`")
    d = pd.read_parquet(paths.processed / "dev_features.parquet")
    return d[(d.dataset_id == source) & (d.partition == part)].sort_values("record_id").reset_index(drop=True)


def load_configs(config: Path, registry: Path | None = None) -> tuple[dict, dict | None]:
    return load_yaml(config), (load_yaml(registry) if registry else None)
