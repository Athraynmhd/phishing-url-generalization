"""Presentation guards must reject missing/tampered results without reading labels."""
import ast
from pathlib import Path

import nbformat
import pytest

from phishresearch import nbviz
from phishresearch.common import GateError, Paths, sha256_file, write_json


def test_saved_evaluation_checks_bytes_without_loading_test_labels(tmp_path, monkeypatch):
    paths = Paths(tmp_path, tmp_path / "raw", tmp_path / "processed", tmp_path / "artifacts")
    paths.eval.mkdir(parents=True)
    prediction = paths.eval / "predictions.parquet"
    prediction.write_bytes(b"opaque prediction bytes: do not parse labels")
    evaluation = {"status": "completed", "freeze_hash": "fixture-freeze",
                  "predictions_sha256": sha256_file(prediction)}
    write_json(paths.eval / "metrics.json", evaluation)
    monkeypatch.setattr(nbviz.pd, "read_parquet", lambda *a, **k: pytest.fail("Label-bearing parquet was opened"))
    freeze = {"freeze_hash": "fixture-freeze"}
    assert nbviz.verify_saved_evaluation(paths, freeze) == evaluation
    with pytest.raises(GateError, match="another freeze"):
        nbviz.verify_saved_evaluation(paths, {"freeze_hash": "different"})
    prediction.write_bytes(b"tampered")
    with pytest.raises(GateError, match="prediction hash"):
        nbviz.verify_saved_evaluation(paths, freeze)


def test_notebook_missing_outputs_preserve_partial_run(tmp_path):
    partial = tmp_path / "partial.csv"
    partial.write_bytes(b"preserve failed output")
    with pytest.raises(GateError, match="Preserve partial/failed runs"):
        nbviz.require_artifacts(partial, tmp_path / "results_registry.json")
    assert partial.read_bytes() == b"preserve failed output"


def test_notebook_cannot_launch_research_or_read_individual_labels():
    root = Path(__file__).resolve().parents[2]
    notebook = nbformat.read(root / "notebooks/phishing_research_pipeline.ipynb", as_version=4)
    forbidden = {"acquire", "run_audit", "run_prepare", "develop_source", "build_freeze", "run_evaluation", "run_analysis", "_load_test"}
    for cell in notebook.cells:
        if cell.cell_type != "code":
            continue
        tree = ast.parse(cell.source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                assert name not in forbidden
                if name == "read_parquet":
                    columns = next(k.value for k in node.keywords if k.arg == "columns")
                    assert not {"label", "y_true", "url_raw"} & set(ast.literal_eval(columns))
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert "test_labels.parquet" not in node.value
