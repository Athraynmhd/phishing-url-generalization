"""Label-free SHAP correction of exactly the saved v1 feature cohorts (post-hoc)."""
from __future__ import annotations

import datetime as dt
import itertools
from pathlib import Path
import uuid

from joblib import Parallel, delayed
import numpy as np
import pandas as pd

from ..common import GateError, read_json, sha256_file, write_json
from ..explain import compare, ranking
from ..freeze import verify_freeze
from ..models import ModelBundle
from ..prepare import load_dev
from .explain import TOLERANCE, strict_shap


def _correct_bundle(root, paths, item, entries, expected_hash, out, cfg):
    bundle = ModelBundle.load(root / item["bundle"], expected_sha256=expected_hash)
    bundle.model.set_params(n_jobs=1)
    background = load_dev(paths, item["source"], "FIT").sort_values("record_id").sample(
        cfg["explain"]["background"], random_state=cfg["explain"]["seed"])[bundle.feature_ids]
    summaries = []
    for entry in entries:
        old_path = paths.analysis / "shap" / f"{entry['bundle_id']}_{entry['cohort']}.npz"
        with np.load(old_path, allow_pickle=False) as saved:
            ids = list(saved["ids"])
            frame = pd.DataFrame(saved["X"], columns=ids)
            old_values = saved["shap"].copy()
        if ids != bundle.feature_ids:
            raise GateError("Saved explanation feature order differs from the frozen bundle")
        result = strict_shap(bundle, background, frame)
        artifact = out / "shap" / old_path.name
        np.savez_compressed(artifact, shap=result["shap"], X=result["X"], ids=np.asarray(ids),
                            expected=result["expected"], scores=result["scores"], residuals=result["residuals"])
        rk = ranking(result["shap"], ids)
        row = {k: entry[k] for k in ("bundle_id", "source", "model", "config", "seed", "cohort", "n")}
        row.update({"expected_value": result["expected"],
                    "additivity_max_abs_err": result["additivity_max_abs_err"],
                    "baseline_max_abs_err": result["baseline_max_abs_err"],
                    "representation_max_abs_err": result["representation_max_abs_err"],
                    "thresholds_represented_at_float32_floor": result["thresholds_represented_at_float32_floor"],
                    "old_additivity_max_abs_err": entry["additivity_max_abs_err"],
                    "max_attribution_change": float(np.max(np.abs(result["shap"] - old_values))),
                    "input_sha256": sha256_file(old_path), "output_sha256": sha256_file(artifact),
                    "top10": " ".join(rk.index[:10])})
        write_json(out / "checks" / f"{entry['bundle_id']}_{entry['cohort']}.json", row)
        summaries.append(row)
        print(f"[correction] {entry['bundle_id']} {entry['cohort']}: residual={row['additivity_max_abs_err']:.3g}", flush=True)
    return summaries


def run_correction(paths, cfg, workers=4):
    root = paths.root
    frozen = verify_freeze(paths.freeze, root)
    baseline = read_json(paths.artifacts / "publication_audit/baseline.json")["protected_sha256"]
    if any(sha256_file(root / p) != h for p, h in baseline.items()):
        raise GateError("Protected v1 output differs from its audit baseline")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = paths.artifacts / "corrections" / f"shap_{stamp}_{uuid.uuid4().hex[:8]}"
    (out / "shap").mkdir(parents=True)
    (out / "checks").mkdir()
    manifest = {"status": "running", "research_status": "exploratory correction of frozen v1",
                "parent_freeze_hash": frozen["freeze_hash"], "tolerance": TOLERANCE,
                "method": "RF float32 inputs and downward float32 threshold representation; native LGBM TreeSHAP",
                "model_refits": 0, "test_labels_read": False, "cohorts": "identical matrices from saved v1 explanations",
                "code_sha256": {str(p.relative_to(root)): sha256_file(p) for p in Path(__file__).parent.glob("*.py")},
                "v1_protected_sha256": baseline}
    write_json(out / "manifest.json", manifest)
    summary = pd.read_csv(paths.analysis / "shap_summary.csv")
    plan = {p["bundle_id"]: p for p in frozen["body"]["plan"]}
    try:
        jobs = []
        for bid, entries in summary.groupby("bundle_id", sort=True):
            item = plan[bid]
            jobs.append(delayed(_correct_bundle)(root, paths, item, entries.to_dict("records"),
                        frozen["body"]["file_hashes"][item["bundle"] + ".joblib"], out, cfg))
        results = Parallel(n_jobs=workers, backend="loky", inner_max_num_threads=1)(jobs)
        corrected = pd.DataFrame([row for group in results for row in group])
        ranks = {}
        for row in corrected.itertuples():
            with np.load(out / "shap" / f"{row.bundle_id}_{row.cohort}.npz", allow_pickle=False) as z:
                ranks[(row.bundle_id, row.cohort)] = ranking(z["shap"], list(z["ids"]))
        comparisons = []
        for row in corrected[(corrected.seed == cfg["explain"]["seed"]) & (corrected.cohort == "source")].itertuples():
            comparisons.append({"bundle_id": row.bundle_id, "model": row.model, "source": row.source,
                                "config": row.config, "kind": "source_vs_target",
                                **compare(ranks[(row.bundle_id, "source")], ranks[(row.bundle_id, "target")])})
        for (source, model), group in corrected[(corrected.config == "ALL") & (corrected.cohort == "source")].groupby(["source", "model"]):
            for a, b in itertools.combinations(sorted(group.bundle_id), 2):
                comparisons.append({"bundle_id": f"{a} vs {b}", "model": model, "source": source,
                                    "config": "ALL", "kind": "seed_stability_source",
                                    **compare(ranks[(a, "source")], ranks[(b, "source")])})
        corrected.to_csv(out / "shap_summary.csv", index=False)
        pd.DataFrame(comparisons).to_csv(out / "shap_compare.csv", index=False)
        pd.DataFrame({f"{bid}|{cohort}": rk for (bid, cohort), rk in ranks.items()}).to_csv(out / "shap_mean_abs.csv")
        if len(corrected) != len(summary) or (corrected.additivity_max_abs_err > TOLERANCE).any():
            raise GateError("Incomplete or non-additive correction cohort")
        verify_freeze(paths.freeze, root)
        if any(sha256_file(root / p) != h for p, h in baseline.items()):
            raise GateError("Correction changed protected v1 output")
        manifest.update(status="passed", cohorts_checked=len(corrected), all_additivity_passed=True,
                        max_additivity_residual=float(corrected.additivity_max_abs_err.max()),
                        max_baseline_residual=float(corrected.baseline_max_abs_err.max()),
                        protected_v1_unchanged=True,
                        output_sha256={str(p.relative_to(out)): sha256_file(p) for p in out.rglob("*")
                                       if p.is_file() and p.name != "manifest.json"})
        write_json(out / "manifest.json", manifest)
        write_json(paths.artifacts / "corrections/latest_shap.json", {"artifact": str(out.relative_to(root)),
                   "manifest_sha256": sha256_file(out / "manifest.json"), "status": "passed"})
        print(f"[correction] all {len(corrected)} cohorts passed -> {out}")
    except Exception as exc:
        manifest.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        write_json(out / "manifest.json", manifest)
        raise
    return out
