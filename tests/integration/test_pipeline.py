"""I04 freeze tamper, I06 metric recomputation, I08 CLI on synthetic sources,
I09 SHAP additivity/output class + benchmark dependency pruning."""
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from conftest import ROOT
from phishresearch import features as F
from phishresearch.analysis import recompute_check
from phishresearch.common import GateError, read_json
from phishresearch.evaluation import run_evaluation
from phishresearch.explain import shap_values
from phishresearch.freeze import build_freeze, verify_freeze
from phishresearch.models import ModelBundle


@pytest.fixture(scope="module")
def frozen(workspace):
    cfg, paths = workspace
    build_freeze(paths.root / "configs" / "protocol.yaml", None, paths, "pytest", cfg)
    run_evaluation(paths.freeze, paths)
    return cfg, paths


def test_freeze_verifies_untouched(frozen):
    _, paths = frozen
    verify_freeze(paths.freeze, paths.root)


@pytest.mark.parametrize("target", ["config", "model", "split", "manifest_body"])
def test_freeze_tamper_rejected(frozen, tmp_path, target):
    _, paths = frozen
    if target == "manifest_body":
        fr = read_json(paths.freeze)
        fr["body"]["seeds"] = [1]
        bad = tmp_path / "freeze.json"
        bad.write_text(json.dumps(fr), encoding="utf-8")
        with pytest.raises(GateError):
            verify_freeze(bad, paths.root)
        return
    f = {"config": paths.root / "configs" / "protocol.yaml",
         "model": next((paths.dev / "A" / "bundles").glob("*.joblib")),
         "split": paths.processed / "splits.parquet"}[target]
    backup = f.read_bytes()
    try:
        f.write_bytes(backup[:-1] + bytes([backup[-1] ^ 1]))       # flip one bit of one byte
        with pytest.raises(GateError):
            verify_freeze(paths.freeze, paths.root)
        with pytest.raises(GateError):
            run_evaluation(paths.freeze, paths)
    finally:
        f.write_bytes(backup)


def test_metrics_recompute_from_predictions(frozen):
    _, paths = frozen
    P = pd.read_parquet(paths.eval / "predictions.parquet")
    M = pd.DataFrame(read_json(paths.eval / "metrics.json")["metrics"])
    assert recompute_check(P, M)["status"] == "pass"
    for r in M.itertuples():
        assert r.TN + r.FP + r.FN + r.TP == r.n_rows
    assert not P.duplicated(["bundle_id", "target", "record_id"]).any()
    assert P.score_phishing.between(0, 1).all()


def test_cli_smoke_end_to_end():
    from types import SimpleNamespace
    from phishresearch.cli import cmd_smoke
    root = cmd_smoke(SimpleNamespace(config=str(ROOT / "configs" / "protocol.yaml")))
    assert (root / "SYNTHETIC_NOT_A_RESULT.json").exists()
    assert "smoke-synthetic" in read_json(root / "artifacts" / "freeze.json")["approved_by"]
    assert (root / "artifacts" / "analysis" / "contrasts.json").exists()


def test_cli_evaluate_refuses_missing_freeze(tmp_path):
    from phishresearch.cli import main
    assert main(["evaluate", "--freeze", str(tmp_path / "nope.json")]) == 2


def test_shap_additivity_and_positive_class(frozen):
    cfg, paths = frozen
    bpath = next((paths.dev / "A" / "bundles").glob("A-RF-ALL*.joblib")).with_suffix("")
    b = ModelBundle.load(bpath)
    dev = pd.read_parquet(paths.processed / "dev_features.parquet")
    X = dev[dev.dataset_id == "A"][b.feature_ids]
    sv, ev, err = shap_values(b, X.iloc[:30], X.iloc[30:60], cfg)
    assert sv.shape == (30, len(b.feature_ids)) and err < 1e-6
    # explained output is P(phishing): ev + sum(shap) reproduces positive-class probability
    np.testing.assert_allclose(ev + sv.sum(1), b.score(X.iloc[30:60]), atol=1e-6)


def test_selected_extraction_skips_unneeded_operations(monkeypatch):
    calls = {"entropy": 0, "kw": 0}
    real_e, real_k = F._entropy, F._kw
    monkeypatch.setattr(F, "_entropy", lambda s: calls.__setitem__("entropy", calls["entropy"] + 1) or real_e(s))
    monkeypatch.setattr(F, "_kw", lambda s, k: calls.__setitem__("kw", calls["kw"] + 1) or real_k(s, k))
    monkeypatch.setattr(F, "FEATURES", F._build(F.KEYWORDS))
    F.extract_features(["http://login.example.com/a"], ["F01", "F02", "F09"])
    assert calls == {"entropy": 0, "kw": 0}
    F.extract_features(["http://login.example.com/a"], ["F20", "F36"])
    assert calls == {"entropy": 1, "kw": 1}


def test_artifacts_match_json_schemas(frozen):
    import jsonschema
    _, paths = frozen
    sch = ROOT / "schemas"
    jsonschema.validate(read_json(paths.eval / "metrics.json"), read_json(sch / "metrics.schema.json"))
    jsonschema.validate(read_json(paths.freeze), read_json(sch / "freeze.schema.json"))
    real = ROOT / "data" / "raw" / "manifest.json"
    if real.exists():
        jsonschema.validate(read_json(real), read_json(sch / "raw_manifest.schema.json"))
