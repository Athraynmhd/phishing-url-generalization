"""Exploratory extensions (D-40): helpers are correct and the driver never touches TEST."""
import shutil

import numpy as np
import pandas as pd
import pytest

from phishresearch.common import Paths, read_json
from phishresearch.extensions import analysis as X
from phishresearch.freeze import build_freeze


def test_defang_makes_urls_non_clickable():
    s = X.defang("https://login.bank.example.test/a?b=c")
    assert "https://" not in s and "." not in s.replace("[.]", "")
    assert len(X.defang("http://a.example.test/" + "x" * 200, max_len=40)) == 40


def test_https_rule_and_logreg_guard():
    X0 = pd.DataFrame({"F30": [1, 0, 1]})
    assert X.https_rule_scores(X0).tolist() == [0.0, 1.0, 0.0]
    with pytest.raises(ValueError):
        X.fit_logreg(pd.DataFrame({"a": [-1.0, 2.0]}), np.array([0, 1]))


def test_cohens_d_sign_and_constant():
    assert X.cohens_d(np.array([3.0, 4.0, 5.0]), np.array([0.0, 1.0, 2.0])) > 0
    assert X.cohens_d(np.ones(3), np.ones(3)) == 0.0


def test_slice_table_reconciles_with_totals():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"F30": rng.integers(0, 2, 200), "F01": rng.integers(10, 120, 200),
                       "F23": rng.integers(0, 4, 200), "F29": rng.integers(0, 2, 200)})
    y, yhat = rng.integers(0, 2, 200), rng.integers(0, 2, 200)
    t = X.slice_table(df, y, yhat)
    for _, g in t.groupby("slice"):           # every slice family partitions all rows
        assert g.n.sum() == 200
        assert g.fp.sum() == int(((y == 0) & (yhat == 1)).sum())
        assert g.fn.sum() == int(((y == 1) & (yhat == 0)).sum())


def test_error_examples_pick_most_confident():
    df = pd.DataFrame({"F30": [0] * 6, "F01": [10] * 6, "F23": [0] * 6})
    y = np.array([0, 0, 0, 1, 1, 1])
    s = np.array([0.6, 0.9, 0.2, 0.1, 0.4, 0.8])
    yhat = (s >= 0.5).astype(int)
    ex = X.error_examples(df, y, s, yhat, pd.Series([f"http://u{i}.example.test" for i in range(6)]))
    assert [e["score"] for e in ex if e["kind"] == "FP"] == [0.9, 0.6]
    assert [e["score"] for e in ex if e["kind"] == "FN"] == [0.1, 0.4]


def test_run_extensions_never_reads_test(workspace, tmp_path, monkeypatch):
    cfg, src_paths = workspace
    root = tmp_path / "ws"
    shutil.copytree(src_paths.root, root)
    paths = Paths.from_config(cfg, root)
    build_freeze(root / "configs" / "protocol.yaml", None, paths, "pytest", cfg)
    cfg = {**cfg, "statistics": {**cfg["statistics"], "bootstrap_replicates": 50},
           "models": {**cfg["models"], "rf": {**cfg["models"]["rf"], "n_estimators": 10},
                      "lgbm": {**cfg["models"]["lgbm"], "n_estimators": 10}}}
    real = pd.read_parquet

    def spy(path, *a, **kw):
        p = str(path).replace("\\", "/")
        assert "test_vault" not in p, "extension touched the TEST vault"
        if p.endswith("records.parquet"):
            assert "label" not in kw.get("columns", ["label"]), "records.parquet label column read"
        return real(path, *a, **kw)

    monkeypatch.setattr(pd, "read_parquet", spy)
    out = X.run_extensions(paths, cfg)
    man = read_json(out / "manifest.json")
    assert man["status"] == "passed" and man["test_labels_read"] is False
    assert X.latest_run(paths) == out
    m = pd.read_csv(out / "metrics.csv")
    assert {"LR-ALL", "HTTPS-rule", "RF-ALL", "LGBM-ALL", "RF-noHTTPS", "LGBM-noHTTPS"} <= set(m.config)
    assert set(m["eval"]) == {"source_val", "target_val"}
