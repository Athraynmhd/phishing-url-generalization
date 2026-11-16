import ast
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from phishresearch.common import GateError, Paths, sha256_file, write_json
from phishresearch.corrections import evaluation
from phishresearch.corrections.explain import floor_float32, strict_shap
from phishresearch.models import ModelBundle


def test_float32_boundary_correction_preserves_actual_classifier():
    model = RandomForestClassifier(n_estimators=1, bootstrap=False, max_depth=1, random_state=17)
    model.fit(np.array([[0.1], [0.2]]), [0, 1])
    threshold = model.estimators_[0].tree_.threshold[0]
    rounded = np.float32(threshold)
    assert float(rounded) > threshold  # The exact round-up case behind the RF failure.
    bundle = ModelBundle(model, ["F01"])
    background = pd.DataFrame({"F01": [0.1, 0.2]})
    sample = pd.DataFrame({"F01": [float(rounded)]})
    before = model.estimators_[0].tree_.threshold.copy()
    result = strict_shap(bundle, background, sample)
    assert result["additivity_max_abs_err"] < 1e-6
    assert result["shap"][0, 0] == pytest.approx(0.5, abs=1e-6)
    assert result["expected"] == pytest.approx(0.5)
    np.testing.assert_array_equal(model.estimators_[0].tree_.threshold, before)


def test_floor_matches_double_threshold_on_float32_lattice():
    thresholds = np.array([0.15000000223517418, -0.15000000223517418, 1 / 3, 10000.12345])
    floored = floor_float32(thresholds)
    for threshold, floor in zip(thresholds, floored):
        mid = np.float32(threshold)
        points = np.array([np.nextafter(mid, np.float32(-np.inf)), mid,
                           np.nextafter(mid, np.float32(np.inf))], dtype=np.float64)
        np.testing.assert_array_equal(points <= threshold, points <= floor)


def test_corrected_shap_matches_exact_coalition_enumeration():
    background = pd.DataFrame(list(itertools.product([0.1, 0.2], repeat=2)), columns=["F01", "F02"])
    model = RandomForestClassifier(n_estimators=3, bootstrap=False, max_depth=2, random_state=17)
    model.fit(background.to_numpy(), [0, 1, 1, 0])
    bundle = ModelBundle(model, list(background.columns))
    sample = pd.DataFrame([[float(np.float32(0.15000000223517418)), 0.2]], columns=background.columns)
    values = {}
    for mask in range(4):
        mixed = background.copy()
        for feature in range(2):
            if mask & (1 << feature):
                mixed.iloc[:, feature] = sample.iloc[0, feature]
        values[mask] = bundle.score(mixed).mean()
    exact = np.array([0.5 * ((values[1] - values[0]) + (values[3] - values[2])),
                      0.5 * ((values[2] - values[0]) + (values[3] - values[1]))])
    result = strict_shap(bundle, background, sample)
    np.testing.assert_allclose(result["shap"][0], exact, atol=1e-6)


def test_explanation_cohort_boundary_never_returns_labels(monkeypatch):
    features = {f"F{i:02d}": np.arange(8) for i in range(1, 38)}
    frame = pd.DataFrame(dict(features, record_id=[str(i) for i in range(8)],
                              dataset_id=["A"] * 4 + ["B"] * 4, label=[0, 0, 1, 1] * 2))
    monkeypatch.setattr(evaluation, "_load_test", lambda paths: frame)
    cohorts = evaluation.explanation_cohorts(None, "A", 4, 4, 17)
    assert all(len(c) == 4 and "label" not in c and "y_true" not in c for c in cohorts.values())


def test_hp_mapping_uses_all_published_split_counts_and_rejects_mismatch(tmp_path):
    paths = Paths(tmp_path, tmp_path / "raw", tmp_path / "processed", tmp_path / "artifacts")
    paths.raw.mkdir()
    counts = {"train": {"benign": 3, "phishing": 2}, "valid": {"benign": 2, "phishing": 4},
              "test": {"benign": 1, "phishing": 3}}
    manifest = {"files": {}}
    for split, classes in counts.items():
        p = paths.raw / f"hp_{split}.csv"
        pd.DataFrame({"label": [0] * classes["benign"] + [1] * classes["phishing"]}).to_csv(p, index=False)
        manifest["files"][f"B:Datasets/hp_{split}.csv"] = {"local_path": p.name,
                      "sha256": sha256_file(p), "commit": "fixture"}
    write_json(paths.raw / "manifest.json", manifest)
    report = evaluation.verify_hp_encoding(paths, counts)
    assert report["mapping"] == {"benign": 0, "phishing": 1, "matches_all_splits": True}
    assert not report["individual_labels_returned"]
    counts["test"]["phishing"] = 99
    with pytest.raises(GateError, match="do not uniquely identify"):
        evaluation.verify_hp_encoding(paths, counts)


def test_correction_analysis_has_no_individual_test_label_reader():
    root = Path(__file__).resolve().parents[2] / "src/phishresearch/corrections"
    for p in root.glob("*.py"):
        if p.name == "evaluation.py":
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        assert not any(isinstance(n, ast.Attribute) and n.attr in {"y_true", "label"} for n in ast.walk(tree))
        assert not any(isinstance(n, ast.Constant) and n.value == "test_labels.parquet" for n in ast.walk(tree))
