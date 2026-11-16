"""Independent, offline checks of frozen research and publication evidence.

Reads prediction SCORES and aggregate counts only; never loads TEST label columns.
No fitting, no scientific artefact overwrites. Each invocation keeps a separate cycle.
"""
import argparse
import ast
import datetime as dt
import re
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from phishresearch.common import GateError, Paths, hash_ids, load_yaml, read_json, sha256_file, write_json
from phishresearch.features import FEATURE_IDS, extract_features
from phishresearch.freeze import verify_freeze
from phishresearch.models import ModelBundle
from phishresearch.prepare import load_dev
from phishresearch.thresholds import choose_threshold


def require(condition, message):
    if not condition:
        raise GateError(message)


def metrics_from_aggregate(row):
    """Independent algebra; not phishresearch.statistics and not individual outcomes."""
    tn, fp, fn, tp = (row[k] for k in ("TN", "FP", "FN", "TP"))
    divide = lambda a, b: a / b if b else 0.0
    precision, recall = divide(tp, tp + fp), divide(tp, tp + fn)
    specificity = divide(tn, tn + fp)
    denominator = np.sqrt(float(tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return {"precision": precision, "recall": recall, "specificity": specificity,
            "f1": divide(2 * tp, 2 * tp + fp + fn), "accuracy": divide(tp + tn, tn + fp + fn + tp),
            "mcc": divide(tp * tn - fp * fn, denominator), "balanced_accuracy": (recall + specificity) / 2,
            "fpr": divide(fp, fp + tn)}


def audit(root=ROOT, verify_scores=True):
    start = time.perf_counter()
    cfg = load_yaml(root / "configs/protocol.yaml")
    paths = Paths.from_config(cfg, root)
    frozen = verify_freeze(paths.freeze, root)
    baseline = read_json(paths.artifacts / "publication_audit/baseline.json")
    protected = {p: sha256_file(root / p) for p in baseline["protected_sha256"]}
    require(protected == baseline["protected_sha256"], "Protected artefacts differ from audit baseline")
    evidence = {"freeze_hash": frozen["freeze_hash"], "test_labels_read": False,
                "runtime": {"python": sys.version, "executable": sys.executable,
                            "prefix": sys.prefix, "base_prefix": sys.base_prefix},
                "scores_verified": verify_scores, "checks": {}, "blockers": [], "limitations": []}
    checks = evidence["checks"]
    audit_doc = read_json(paths.artifacts / "audit.json")
    require(all(audit_doc["sources"][s]["reconciles"] for s in "AB"), "Attrition does not reconcile")
    require(audit_doc["cross_source"]["cohort_group_intersection"] == 0, "Cross-source groups overlap")
    raw = read_json(paths.raw / "manifest.json")
    require(all(sha256_file(paths.raw / v["local_path"]) == v["sha256"] for v in raw["files"].values()), "Raw hash mismatch")
    checks["raw_files"] = len(raw["files"])
    splits = pd.read_parquet(paths.processed / "splits.parquet", columns=["record_id", "dataset_id", "group_id", "partition"])
    require(not splits.record_id.duplicated().any(), "Duplicate split record IDs")
    require(splits.groupby("group_id").partition.nunique().max() == 1, "Group crosses partitions")
    require(splits.groupby("group_id").dataset_id.nunique().max() == 1, "Group crosses sources")
    checks["group_disjoint"] = True
    dev = {(s, p): load_dev(paths, s, p) for s in "AB" for p in ("FIT", "VAL")}
    # Features are finite in all partitions, without loading TEST labels.
    test = pd.read_parquet(paths.processed / "test_vault/test_features.parquet")
    require("label" not in test and "y_true" not in test, "TEST feature file contains labels")
    require(np.isfinite(test[list(FEATURE_IDS)].to_numpy()).all(), "Non-finite TEST features")
    require(set(test.record_id) == set(splits.loc[splits.partition == "TEST", "record_id"]), "TEST membership mismatch")
    for (source, part), frame in dev.items():
        require(np.isfinite(frame[list(FEATURE_IDS)].to_numpy()).all(), "Non-finite development features")
        expected = splits[(splits.dataset_id == source) & (splits.partition == part)]
        require(set(frame.record_id) == set(expected.record_id), "Development membership mismatch")
    # Re-extract reserved FIT sample rows from stored URL strings, offline. Never print URLs.
    records = pd.read_parquet(paths.processed / "records.parquet", columns=["record_id", "url_raw"])
    for source in "AB":
        sample = dev[(source, "FIT")].head(16)
        urls = records.set_index("record_id").loc[sample.record_id, "url_raw"].tolist()
        expected = extract_features(urls).to_numpy()
        np.testing.assert_allclose(expected, sample[list(FEATURE_IDS)].to_numpy(), rtol=0, atol=0)
    checks["fit_feature_rows_reextracted_offline"] = 32
    evaluation = read_json(paths.eval / "metrics.json")
    require(evaluation["freeze_hash"] == frozen["freeze_hash"], "Evaluation freeze mismatch")
    require(sha256_file(paths.eval / "predictions.parquet") == evaluation["predictions_sha256"], "Prediction bytes changed")
    pred = pd.read_parquet(paths.eval / "predictions.parquet",
                           columns=["bundle_id", "target", "record_id", "group_id", "score_phishing"])
    require(not pred.duplicated(["bundle_id", "target", "record_id"]).any(), "Duplicate prediction keys")
    require(pred.score_phishing.between(0, 1).all(), "Invalid probability range")
    scores_by_key = {key: g.sort_values("record_id") for key, g in pred.groupby(["bundle_id", "target"])}
    metrics = evaluation["metrics"]
    metric_map = {(r["bundle_id"], r["target"], r["threshold_policy"]): r for r in metrics}
    require(len(metric_map) == len(metrics), "Duplicate metric key")
    expected_keys = {(item["bundle_id"], target, policy) for item in frozen["body"]["plan"]
                     for target in item["targets"] for policy in ("f1_max", "fpr_le", "fixed_0.5")}
    require(set(metric_map) == expected_keys, "Evaluation cells/policies incomplete")
    worst_score, threshold_checks = 0.0, 0
    meta_by_bid = {}
    for item in frozen["body"]["plan"]:
        bid = item["bundle_id"]
        bundle_path = root / item["bundle"]
        bundle = ModelBundle.load(bundle_path, frozen["body"]["file_hashes"][item["bundle"] + ".joblib"])
        meta = bundle.meta
        meta_by_bid[bid] = meta
        require(meta["source"] == item["source"] and meta["bundle_id"] == bid, "Bundle identity mismatch")
        require(meta["model_sha256"] == sha256_file(bundle_path.with_suffix(".joblib")), "Bundle metadata hash mismatch")
        fit, val = dev[(item["source"], "FIT")], dev[(item["source"], "VAL")]
        require(meta["fit_ids_hash"] == hash_ids(fit.record_id), "Final fit IDs mismatch")
        require(meta["val_ids_hash"] == hash_ids(val.record_id), "VAL IDs mismatch")
        if verify_scores:
            val_scores = bundle.score(val[bundle.feature_ids])
            for policy, threshold in meta["thresholds"].items():
                selected = choose_threshold(val.label.to_numpy(), val_scores, policy, cfg["thresholds"]["fpr_max"])
                require(abs(selected["threshold"] - threshold["threshold"]) <= 1e-12, "VAL threshold does not reproduce")
                threshold_checks += 1
        for target in item["targets"]:
            saved = scores_by_key[(bid, target)]
            features = test[test.dataset_id == target].sort_values("record_id")
            require(saved.record_id.tolist() == features.record_id.tolist(), "Prediction record order mismatch")
            require(saved.group_id.tolist() == features.group_id.tolist(), "Prediction groups mismatch")
            if verify_scores:
                scores = bundle.score(features[bundle.feature_ids])
                diff = float(np.abs(scores - saved.score_phishing.to_numpy()).max())
                worst_score = max(worst_score, diff)
                require(diff <= 1e-12, "Frozen model does not reproduce saved probabilities")
            for policy, threshold in meta["thresholds"].items():
                row = metric_map[(bid, target, policy)]
                require(row["n_rows"] == len(saved) == sum(row[k] for k in ("TN", "FP", "FN", "TP")), "Count total mismatch")
                require(row["n_domains"] == saved.group_id.nunique(), "Domain denominator mismatch")
                require(abs(row["threshold"] - threshold["threshold"]) <= 1e-12, "Target-specific threshold detected")
                positives = int((saved.score_phishing >= row["threshold"]).sum())
                require(positives == row["TP"] + row["FP"], "Score decisions differ from confusion marginals")
                require(abs(row["prevalence"] - (row["TP"] + row["FN"]) / row["n_rows"]) <= 1e-12,
                        "Prevalence differs from confusion marginals")
                for name, value in metrics_from_aggregate(row).items():
                    require(abs(value - row["values"][name]) <= 1e-12, f"Aggregate {name} does not reproduce")
        print(f"[audit] {bid} verified", flush=True)
    checks.update({"bundles": len(meta_by_bid), "prediction_rows": len(pred), "metric_rows": len(metrics),
                   "max_probability_abs_difference": worst_score, "val_thresholds_reproduced": threshold_checks,
                   "aggregate_metrics_recomputed": True, "score_decision_marginals_checked": True,
                   "AP_AUC_independently_recomputed": False})
    # Reconcile saved summary and primary contrast values from aggregate metric artefacts.
    summary = pd.read_csv(paths.analysis / "summary.csv")
    for row in summary.itertuples():
        selector, _, role = row.config.partition("@")
        selected = [r for r in metrics if r["source"] == row.source and r["target"] == row.target
                    and r["model"] == row.model and r["selector"] == selector
                    and r["threshold_policy"] == row.policy and (selector == "ALL" or role in r["roles"])]
        require(len(selected) == row.n_seeds, "Summary seed coverage differs")
        for name in ("f1", "precision", "recall", "specificity", "mcc", "balanced_accuracy", "accuracy", "roc_auc", "average_precision", "fpr"):
            require(abs(np.mean([r["values"][name] for r in selected]) - getattr(row, name + "_mean")) <= 1e-12,
                    "Summary differs from stored metrics")
    contrasts = read_json(paths.analysis / "contrasts.json")
    require(len(contrasts["primary"]) == 4, "Primary contrast count differs")
    for row in contrasts["primary"]:
        arms = []
        for arm in ("a", "b"):
            selector, role = row[arm].split("@")
            arm_rows = sorted([r for r in metrics if r["source"] == row["source"] and r["target"] == row["target"]
                               and r["model"] == row["model"] and r["selector"] == selector
                               and role in r["roles"] and r["threshold_policy"] == row["policy"]], key=lambda x: x["seed"])
            arms.append(arm_rows)
        require([r["k"] for r in arms[0]] == [r["k"] for r in arms[1]], "Primary contrast is not matched-k")
        delta = np.array([r["values"]["f1"] for r in arms[0]]) - [r["values"]["f1"] for r in arms[1]]
        np.testing.assert_allclose(delta, row["per_seed_delta"], rtol=0, atol=1e-12)
        require(abs(delta.mean() - row["delta"]) <= 1e-12, "Contrast mean differs")
        require(row["n_boot"] == cfg["statistics"]["bootstrap_replicates"], "Bootstrap size differs")
    checks["summary_rows"] = len(summary)
    checks["primary_contrasts_matched_k"] = True
    for source in "AB":
        develop = read_json(paths.dev / source / "develop.json")
        for seed, info in develop["seeds"].items():
            require(info["full_selector_hash"] not in info["outer_selector_hashes"], "Nested selector leakage")
    checks["nested_selector_lineage"] = True
    shap = pd.read_csv(paths.analysis / "shap_summary.csv")
    failures = int((shap.additivity_max_abs_err > 1e-6).sum())
    checks["shap_outputs"] = len(shap)
    checks["shap_additivity_failures"] = failures
    if failures:
        evidence["blockers"].append("SHAP real-data additivity failures: exploratory diagnostics only")
    legacy = ast.parse((root / "src/phishresearch/analysis.py").read_text(encoding="utf-8"))
    direct_reads = [node.lineno for node in ast.walk(legacy) if isinstance(node, ast.Constant)
                    and isinstance(node.value, str) and node.value == "test_labels.parquet"]
    if direct_reads:
        evidence["blockers"].append("Frozen legacy analysis contains direct TEST-label access; CLI execution blocked")
    evidence["limitations"] += ["No new labelled TEST read: AP/AUC and bootstrap replicate resampling rely on existing I06/provenance",
                                "Fixed split/three seeds do not establish training-population uncertainty",
                                "No independent recent holdout or complete primary-paper reproduction",
                                "HP numeric label mapping indirectly verified; direct codebook confirmation pending"]
    require(all(sha256_file(root / p) == h for p, h in protected.items()), "Audit changed protected artefacts")
    verify_freeze(paths.freeze, root)
    evidence["status"] = "engineering_checks_passed_scientific_blockers_remain"
    evidence["seconds"] = time.perf_counter() - start
    evidence["protected_outputs_unchanged"] = True
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    cycle = paths.artifacts / "publication_audit" / f"cycle_{stamp}.json"
    write_json(cycle, evidence)
    write_json(paths.artifacts / "publication_audit/latest_cycle.json", {"artifact": cycle.name, "status": evidence["status"]})
    print(f"[audit] {evidence['status']} -> {cycle}")
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata-only", action="store_true", help="Skip model probability and VAL threshold checks")
    args = parser.parse_args()
    audit(verify_scores=not args.metadata_only)
