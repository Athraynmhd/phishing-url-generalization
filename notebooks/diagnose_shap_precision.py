"""Post-hoc precision diagnostic on saved explanation FEATURES, never TEST labels.

Frozen models and original explanation artefacts are read-only. Results are exploratory.
"""
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from phishresearch.common import Paths, load_yaml, read_json, write_json
from phishresearch.freeze import verify_freeze
from phishresearch.models import ModelBundle
from phishresearch.prepare import load_dev


def main():
    import shap
    cfg = load_yaml(ROOT / "configs/protocol.yaml")
    paths = Paths.from_config(cfg, ROOT)
    frozen = verify_freeze(paths.freeze, ROOT)
    summary = pd.read_csv(paths.analysis / "shap_summary.csv")
    jobs = summary[summary.additivity_max_abs_err > 1e-6]
    plan = {p["bundle_id"]: p for p in frozen["body"]["plan"]}
    results = []
    for row in jobs.itertuples():
        item = plan[row.bundle_id]
        bundle = ModelBundle.load(ROOT / item["bundle"], frozen["body"]["file_hashes"][item["bundle"] + ".joblib"])
        # Inference threads only; nothing is fitted or saved.
        bundle.model.set_params(n_jobs=1)
        with np.load(paths.analysis / "shap" / f"{row.bundle_id}_{row.cohort}.npz", allow_pickle=False) as z:
            matrix, old_values, ids = z["X"], z["shap"], list(z["ids"])
        scores = bundle.score(pd.DataFrame(matrix, columns=ids))
        residual = np.abs(row.expected_value + old_values.sum(1) - scores)
        failing = np.flatnonzero(residual > 1e-6)
        selection = np.unique(np.r_[failing[:3], np.arange(min(3, len(matrix)))])
        fit = load_dev(paths, item["source"], "FIT")
        background = fit.sample(cfg["explain"]["background"], random_state=cfg["explain"]["seed"])[ids].to_numpy()
        result = {"bundle_id": row.bundle_id, "cohort": row.cohort,
                  "old_max_residual": float(residual.max()), "failing_rows": int(len(failing)),
                  "sampled_rows": selection.tolist(), "variants": {}}
        for dtype in (np.float64, np.float32):
            start = time.perf_counter()
            explainer = shap.TreeExplainer(bundle.model, data=background.astype(dtype),
                                           feature_perturbation="interventional", model_output="probability")
            values = np.asarray(explainer.shap_values(matrix[selection].astype(dtype), check_additivity=False))
            expected = np.asarray(explainer.expected_value)
            if values.ndim == 3:
                pos = list(bundle.model.classes_).index(1)
                values, expected = values[..., pos], expected[pos]
            error = float(np.abs(float(expected) + values.sum(1) - scores[selection]).max())
            result["variants"][np.dtype(dtype).name] = {"max_residual": error, "passed_1e_6": error <= 1e-6,
                                                        "seconds": time.perf_counter() - start}
        print(result, flush=True)
        results.append(result)
    out = {"status": "exploratory_precision_diagnostic", "freeze_hash": frozen["freeze_hash"],
           "test_labels_read": False, "model_refits": 0, "results": results}
    write_json(paths.artifacts / "publication_audit/shap_precision_diagnostic.json", out)
    verify_freeze(paths.freeze, ROOT)


if __name__ == "__main__":
    main()
