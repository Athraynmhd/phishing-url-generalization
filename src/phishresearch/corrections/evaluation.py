"""Only evaluator code handles original HP labels or TEST stratification.

Public returns contain aggregate counts or label-free explanation feature matrices.
Never return an individual label, raw URL or saved y_true column to analysis.
"""
from __future__ import annotations

import pandas as pd

from ..common import GateError, read_json, sha256_file
from ..evaluation import _load_test
from ..features import FEATURE_IDS


def explanation_cohorts(paths, source, n_source, n_target, seed):
    test = _load_test(paths)
    result = {}
    for role, dataset, size in (("source", source, n_source),
                                ("target", "B" if source == "A" else "A", n_target)):
        parts = [g.sample(min(len(g), size // 2), random_state=seed)
                 for _, g in test[test.dataset_id == dataset].groupby("label")]
        result[role] = pd.concat(parts).sort_values("record_id")[list(FEATURE_IDS)].reset_index(drop=True)
    return result


def verify_hp_encoding(paths, paper_counts):
    """Match two candidate numeric encodings against the published Table 1, all splits."""
    manifest = read_json(paths.raw / "manifest.json")
    counts, files = {}, {}
    for part in ("train", "valid", "test"):
        item = manifest["files"][f"B:Datasets/hp_{part}.csv"]
        path = paths.raw / item["local_path"]
        if sha256_file(path) != item["sha256"]:
            raise GateError(f"Raw HP {part} hash differs from acquisition")
        labels = pd.read_csv(path, usecols=["label"])["label"]
        if labels.isna().any() or set(labels.unique()) != {0, 1}:
            raise GateError(f"Invalid numeric HP labels in {part}")
        counts[part] = {str(k): int(v) for k, v in labels.value_counts().items()}
        files[part] = {"sha256": item["sha256"], "commit": item["commit"], "rows": len(labels)}
    candidates = []
    for benign, phishing in ((0, 1), (1, 0)):
        match = all(counts[p][str(benign)] == paper_counts[p]["benign"]
                    and counts[p][str(phishing)] == paper_counts[p]["phishing"] for p in counts)
        candidates.append({"benign": benign, "phishing": phishing, "matches_all_splits": match})
    matching = [c for c in candidates if c["matches_all_splits"]]
    if len(matching) != 1:
        raise GateError("Published HP counts do not uniquely identify the repository encoding")
    return {"status": "published_class_counts_crossvalidated", "mapping": matching[0],
            "observed_numeric_counts": counts, "published_table_1": paper_counts,
            "raw_provenance": files, "candidates": candidates,
            "evidence_kind": "unique six-cell match to primary-paper Table 1; not an author-written codebook",
            "individual_labels_returned": False, "dataset_urls_opened": False}
