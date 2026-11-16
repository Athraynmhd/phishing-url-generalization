"""Recover missing presentation outputs from the completed run of the SAME freeze.

No training, benchmarking, TEST-label reads, or overwriting existing artefacts.
Run from the repository root: python notebooks/recover_analysis.py
"""
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from phishresearch.common import GateError, Paths, load_yaml, read_json, sha256_file, write_json
from phishresearch.explain import compare, ranking
from phishresearch.freeze import verify_freeze
from phishresearch.models import ModelBundle
from phishresearch.nbviz import require_artifacts, verify_saved_evaluation


def recover(root: Path = ROOT) -> dict:
    cfg = load_yaml(root / "configs/protocol.yaml")
    paths = Paths.from_config(cfg, root)
    freeze = verify_freeze(paths.freeze, root)
    evaluation = verify_saved_evaluation(paths, freeze)
    source = paths.artifacts / "analysis_run1_contaminated_benchmark"
    dest = paths.analysis
    registry = read_json(source / "results_registry.json")
    if (registry["freeze_hash"] != freeze["freeze_hash"] or registry["run_id"] != evaluation["run_id"]
            or any(registry["status"].get(s) != "completed" for s in ("evaluation", "benchmark", "shap"))):
        raise GateError("Recovery source is incomplete or belongs to another frozen evaluation")
    deterministic = ["summary.csv", "config_ci.csv", "contrasts.json", "selection.json", "transfer_drop.csv"]
    for name in deterministic:
        if sha256_file(source / name) != sha256_file(dest / name):
            raise GateError(f"Recovery source differs on {name}")
    checks = read_json(dest / "checks.json")["I06_recompute"]
    if checks["status"] != "pass" or checks["rows_checked"] != len(evaluation["metrics"]) or checks["max_abs_diff"] != 0:
        raise GateError("Active analysis did not pass metric recomputation")
    require_artifacts(dest / "benchmark.json", dest / "benchmark.csv")
    benchmark = read_json(dest / "benchmark.json")
    expected_bids = {p["bundle_id"] for p in freeze["body"]["plan"] if p["bundle_id"].endswith("-s17")}
    if {b["bundle_id"] for b in benchmark["bundles"]} != expected_bids:
        raise GateError("Active benchmark does not cover the frozen seed-17 bundles")
    shap_meta = read_json(source / "shap_meta.json")
    if any(shap_meta[k] != value for k, value in cfg["explain"].items()):
        raise GateError("SHAP source settings differ from the frozen protocol")
    summary = pd.read_csv(source / "shap_summary.csv")
    rank_table = pd.read_csv(source / "shap_mean_abs.csv", index_col=0)
    comparisons = pd.read_csv(source / "shap_compare.csv")
    plan = {p["bundle_id"]: p for p in freeze["body"]["plan"]}
    rankings, files, errors = {}, [], []
    expected_jobs = set()
    seed = cfg["explain"]["seed"]
    for bid, p in plan.items():
        meta = read_json(root / (p["bundle"] + ".json"))
        if meta["selector"] == "ALL" or (meta["selector"] == "STABLE_PI" and "budget" in meta["roles"] and meta["seed"] == seed):
            expected_jobs.add((bid, "source"))
            if meta["seed"] == seed:
                expected_jobs.add((bid, "target"))
    if set(zip(summary.bundle_id, summary.cohort)) != expected_jobs or len(summary) != len(expected_jobs):
        raise GateError("SHAP source does not cover the frozen explanation plan")
    for row in summary.itertuples():
        item = plan[row.bundle_id]
        bundle = ModelBundle.load(root / item["bundle"],
                                  freeze["body"]["file_hashes"][item["bundle"] + ".joblib"])
        filename = source / "shap" / f"{row.bundle_id}_{row.cohort}.npz"
        with np.load(filename, allow_pickle=False) as z:
            ids, values, matrix = list(z["ids"]), z["shap"], z["X"]
        if ids != bundle.feature_ids or values.shape != matrix.shape or len(matrix) != row.n:
            raise GateError(f"SHAP array/schema mismatch: {filename.name}")
        if not np.isfinite(values).all() or not np.isfinite(matrix).all():
            raise GateError(f"Non-finite SHAP data: {filename.name}")
        err = float(np.max(np.abs(row.expected_value + values.sum(1)
                                  - bundle.score(pd.DataFrame(matrix, columns=ids)))))
        if not np.isclose(err, row.additivity_max_abs_err, atol=1e-12, rtol=1e-5):
            raise GateError(f"SHAP additivity differs from the saved diagnostic: {filename.name}")
        rk = ranking(values, ids)
        np.testing.assert_allclose(rk, rank_table.loc[rk.index, f"{row.bundle_id}|{row.cohort}"], atol=1e-12)
        rankings[(row.bundle_id, row.cohort)] = rk
        errors.append(err)
        files.append(filename)
    for row in comparisons.itertuples():
        if row.kind == "source_vs_target":
            left, right = rankings[(row.bundle_id, "source")], rankings[(row.bundle_id, "target")]
        elif row.kind == "seed_stability_source":
            a, b = row.bundle_id.split(" vs ")
            left, right = rankings[(a, "source")], rankings[(b, "source")]
        else:
            raise GateError("Unknown SHAP comparison")
        result = compare(left, right)
        np.testing.assert_allclose([result["spearman"], result["top10_jaccard"]],
                                   [row.spearman, row.top10_jaccard], atol=1e-12)
    files += [source / n for n in ("shap_summary.csv", "shap_compare.csv", "shap_mean_abs.csv", "shap_meta.json")]
    # Validate every destination before copying anything; never overwrite a partial/failed run.
    for file in files:
        target = dest / file.relative_to(source)
        if target.exists() and sha256_file(target) != sha256_file(file):
            raise GateError(f"Existing recovery target differs: {target}")
    evidence = {"freeze_hash": freeze["freeze_hash"], "run_id": evaluation["run_id"],
                "source": source.relative_to(root).as_posix(), "method": "verified reuse of saved SHAP; active benchmark retained",
                "deterministic_sha256": {n: sha256_file(dest / n) for n in deterministic},
                "reused_sha256": {f.relative_to(source).as_posix(): sha256_file(f) for f in files},
                "active_benchmark_sha256": {n: sha256_file(dest / n) for n in ("benchmark.json", "benchmark.csv")},
                "prediction_sha256": evaluation["predictions_sha256"], "shap_arrays_checked": len(errors),
                "max_additivity_error": max(errors), "additivity_tolerance": 1e-6,
                "additivity_failures": int(sum(e > 1e-6 for e in errors)),
                "individual_test_labels_read": False}
    new_registry = {**registry, "status": {**registry["status"],
                    "shap": "completed_with_additivity_warning" if evidence["additivity_failures"] else "completed"},
                    "recovery_provenance": "recovery.json"}
    for name, doc in (("recovery.json", evidence), ("results_registry.json", new_registry)):
        if (dest / name).exists():
            previous = read_json(dest / name)
            # Threaded RF probability summation can differ in the last few floating-point bits.
            # Keep the original recorded diagnostic; never rewrite it during an identical retry.
            if name == "recovery.json" and np.isclose(previous.get("max_additivity_error", np.inf),
                                                     doc["max_additivity_error"], atol=1e-12, rtol=1e-5):
                doc["max_additivity_error"] = previous["max_additivity_error"]
            if previous != doc and not (name == "results_registry.json" and previous == registry):
                raise GateError(f"Refusing to overwrite existing {name}")
    for file in files:
        target = dest / file.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(file, target)
    for name, doc in (("recovery.json", evidence), ("results_registry.json", new_registry)):
        if not (dest / name).exists():
            write_json(dest / name, doc)
    print(f"Recovered and verified {len(errors)} SHAP arrays; active benchmark preserved.")
    return evidence


if __name__ == "__main__":
    recover()
