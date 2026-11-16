"""Independently verify all corrected arrays, unchanged v1 numbers and literature evidence."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from phishresearch.common import Paths, load_yaml, read_json, sha256_file, write_json
from phishresearch.freeze import verify_freeze
from phishresearch.models import ModelBundle
from phishresearch.nbviz import verify_shap_correction


def check(root=ROOT):
    cfg = load_yaml(root / "configs/protocol.yaml")
    paths = Paths.from_config(cfg, root)
    frozen = verify_freeze(paths.freeze, root)
    protected = read_json(paths.artifacts / "publication_audit/baseline.json")["protected_sha256"]
    assert all(sha256_file(root / p) == digest for p, digest in protected.items())
    folder, manifest = verify_shap_correction(paths, frozen)
    table = pd.read_csv(folder / "shap_summary.csv")
    plan = {item["bundle_id"]: item for item in frozen["body"]["plan"]}
    arrays, rows, maximum = 0, 0, 0.0
    for bid, entries in table.groupby("bundle_id"):
        item = plan[bid]
        bundle = ModelBundle.load(root / item["bundle"], expected_sha256=frozen["body"]["file_hashes"][item["bundle"] + ".joblib"])
        bundle.model.set_params(n_jobs=1)
        for entry in entries.itertuples():
            with np.load(folder / "shap" / f"{bid}_{entry.cohort}.npz", allow_pickle=False) as z:
                frame = pd.DataFrame(z["X"], columns=list(z["ids"]))
                scores = bundle.score(frame)
                residuals = float(z["expected"]) + z["shap"].sum(axis=1) - scores
                error = float(np.max(np.abs(residuals)))
                np.testing.assert_allclose(scores, z["scores"], rtol=0, atol=1e-12)
                np.testing.assert_allclose(residuals, z["residuals"], rtol=0, atol=1e-12)
                assert error <= 1e-6 and abs(error - entry.additivity_max_abs_err) <= 1e-12
                with np.load(paths.analysis / "shap" / f"{bid}_{entry.cohort}.npz", allow_pickle=False) as old:
                    np.testing.assert_array_equal(z["X"], old["X"])
                    np.testing.assert_array_equal(z["ids"], old["ids"])
                maximum = max(maximum, error)
                arrays += 1
                rows += len(frame)
    assert arrays == len(table) == manifest["cohorts_checked"] == 24
    access = read_json(paths.artifacts / "publication_corrections/access_check.json")
    assert access["status"] == "passed" and access["guard_probe_denied_before_file_open"]
    assert access["parent_freeze_hash"] == frozen["freeze_hash"]
    assert not access["individual_test_label_read_attempts"] and not access["legacy_v1_route_executed"]
    paper = read_json(paths.artifacts / "publication_corrections/R2_fulltext_provenance.json")
    assert paper["review_status"] == "complete" and paper["reviewed_pages"] == list(range(1, 15))
    assert sha256_file(root / paper["file"]) == paper["sha256"]
    assert sha256_file(root / paper["review"]) == paper["review_sha256"]
    assert len(pymupdf.open(root / paper["file"])) == paper["pages"] == 14
    hp = read_json(paths.artifacts / "publication_corrections/hp_encoding.json")
    assert hp["freeze_hash"] == frozen["freeze_hash"] and hp["status"] == "published_class_counts_crossvalidated"
    assert hp["mapping"] == {"benign": 0, "phishing": 1, "matches_all_splits": True}
    assert sum(c["matches_all_splits"] for c in hp["candidates"]) == 1
    assert all(hp["observed_numeric_counts"][part][str(label)] == classes[name]
               for part, classes in hp["published_table_1"].items()
               for label, name in ((0, "benign"), (1, "phishing")))
    target = root / read_json(paths.artifacts / "publication_corrections/manuscript_latest.json")["artifact"]
    old = pd.read_csv(root / "manuscript/generated/provenance.csv").set_index("key").value
    new = pd.read_csv(target / "generated/provenance.csv").set_index("key").value
    changed = [key for key in old.index if str(old[key]) != str(new[key])]
    assert set(old.index) == set(new.index)
    assert all(key.lower().startswith(("rho", "shap")) for key in changed), changed
    pdf = pymupdf.open(target / "main.pdf")
    assert len(pdf) <= 10 and not any("??" in page.get_text() for page in pdf)
    assert "Overfull" not in (target / "main.log").read_text(encoding="utf-8")
    result = {"status": "passed", "parent_freeze_hash": frozen["freeze_hash"],
              "research_status": "exploratory correction; historical v1 deviation retained",
              "shap_arrays_independently_verified": arrays, "explained_rows_verified": rows,
              "max_additivity_residual": maximum, "test_labels_read": False,
              "protected_v1_unchanged": True, "hp_mapping_evidence": hp["evidence_kind"],
              "active_correction_runtime_access_check_passed": True,
              "r2_full_text_review_complete": True, "pdf_pages": len(pdf),
              "corrected_manuscript": str(target.relative_to(root)),
              "corrected_pdf_sha256": sha256_file(target / "main.pdf"),
              "changed_number_macro_keys": changed,
              "correction_manifest_sha256": sha256_file(folder / "manifest.json"),
              "findings": {"shap": "resolved by strict exploratory recomputation",
                           "test_access": "active correction route label-free; frozen legacy blocked and preserved",
                           "hp_encoding": "uniquely crossvalidated against original primary-paper Table 1",
                           "r2_review": "complete, user-supplied original publisher PDF"}}
    write_json(paths.artifacts / "publication_corrections/checks.json", result)
    print(f"Correction checks passed: {arrays} arrays / {rows} rows; residual {maximum:.3g}; PDF {len(pdf)} pages.")
    return result


if __name__ == "__main__":
    check()
