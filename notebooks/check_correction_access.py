"""Exercise a real correction worker while TEST-label file access is denied."""
import datetime as dt
from pathlib import Path
import sys
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from phishresearch.common import Paths, load_yaml, read_json, write_json
from phishresearch.corrections.analysis import _correct_bundle
from phishresearch.freeze import verify_freeze


def main():
    cfg = load_yaml(ROOT / "configs/protocol.yaml")
    paths = Paths.from_config(cfg, ROOT)
    frozen = verify_freeze(paths.freeze, ROOT)
    bid = "A-LGBM-ALL-k37-s17"
    item = next(p for p in frozen["body"]["plan"] if p["bundle_id"] == bid)
    table = pd.read_csv(paths.analysis / "shap_summary.csv")
    entries = table[(table.bundle_id == bid) & (table.cohort == "source")].to_dict("records")
    assert len(entries) == 1
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = paths.artifacts / "publication_corrections" / f"access_check_{stamp}"
    (out / "shap").mkdir(parents=True)
    (out / "checks").mkdir()
    original = pd.read_parquet
    reads = []
    denied = []

    def guarded_read(path, *args, **kwargs):
        name = Path(path).name
        columns = kwargs.get("columns")
        if name == "test_labels.parquet" or (name == "predictions.parquet" and
                (columns is None or "y_true" in columns)):
            denied.append(name)
            raise PermissionError("Individual TEST-label access denied by runtime audit")
        reads.append({"file": str(path), "columns": columns})
        return original(path, *args, **kwargs)

    with patch.object(pd, "read_parquet", side_effect=guarded_read):
        try:
            pd.read_parquet(Path("reserved-fixture") / "test_labels.parquet")
        except PermissionError:
            pass
        else:
            raise AssertionError("Runtime guard failed to deny a label-file request")
        assert denied == ["test_labels.parquet"]
        denied.clear()
        result = _correct_bundle(ROOT, paths, item, entries,
                                 frozen["body"]["file_hashes"][item["bundle"] + ".joblib"], out, cfg)
    assert not denied and len(result) == 1
    assert result[0]["additivity_max_abs_err"] <= 1e-6
    assert all(Path(r["file"]).name == "dev_features.parquet" for r in reads)
    verify_freeze(paths.freeze, ROOT)
    evidence = {"status": "passed", "worker": bid, "cohort": "source", "rows": result[0]["n"],
                "guard_probe_denied_before_file_open": True, "individual_test_label_read_attempts": denied,
                "parquet_reads": reads, "parent_freeze_hash": frozen["freeze_hash"],
                "scope": "real correction worker, source FIT background and saved explanation features",
                "legacy_v1_route_executed": False}
    write_json(out / "access_check.json", evidence)
    write_json(paths.artifacts / "publication_corrections/access_check.json", evidence)
    print("Actual correction worker passed with individual TEST-label access denied.")


if __name__ == "__main__":
    main()
