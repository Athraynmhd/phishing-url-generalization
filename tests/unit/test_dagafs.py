"""DA-GAFS (D-41): component rules are correct and the driver never touches TEST."""
import shutil

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from phishresearch.common import Paths, read_json
from phishresearch.extensions import dagafs as G
from phishresearch.features import FEATURE_IDS
from phishresearch.freeze import build_freeze


def test_weighted_auc_matches_sklearn():
    rng = np.random.default_rng(1)
    x, y, w = rng.integers(0, 6, 400).astype(float), rng.integers(0, 2, 400), rng.integers(0, 4, 400).astype(float)
    assert np.isclose(G.weighted_auc(x, y), roc_auc_score(y, x))
    assert np.isclose(G.weighted_auc(x, y, w), roc_auc_score(y, x, sample_weight=w))


def test_direction_conflict_is_penalised_last():
    n = len(FEATURE_IDS)
    pi = {s: [np.tile(np.linspace(1.0, 0.1, n), (3, 1))] for s in ("A", "B")}   # F01 most important everywhere
    r = {"A": np.full(n, 0.3), "B": np.full(n, 0.3)}
    r["B"][0] = -0.3                       # F01 reverses its class association -> conflict
    r["B"][1] = -0.05                      # F02 reverses, but too weak to count
    tab = G.component_table(pi, r, q=12)
    assert tab.set_index("feature").loc["F01", "conflict"] and not tab.set_index("feature").loc["F02", "conflict"]
    rk = G.rankings(tab)
    assert rk["I"][0] == "F01" and rk["IS"][0] == "F01" and rk["ISD"][-1] == "F01"


def test_pareto_and_tolerance_choice():
    g = np.array([0.90, 0.95, 0.955, 0.96])
    c = np.array([1.0, 2.0, 3.0, 4.0])
    assert G.pareto(g, c).all()
    assert G.choose(g, c, tol=0.01) == 1          # cheapest within 0.01 of 0.96
    assert not G.pareto(np.array([0.9, 0.9]), np.array([1.0, 2.0]))[1]


def test_run_dagafs_never_reads_test(workspace, tmp_path, monkeypatch):
    cfg, src_paths = workspace
    root = tmp_path / "ws"
    shutil.copytree(src_paths.root, root)
    paths = Paths.from_config(cfg, root)
    build_freeze(root / "configs" / "protocol.yaml", None, paths, "pytest", cfg)
    cfg = {**cfg, "statistics": {**cfg["statistics"], "bootstrap_replicates": 20},
           "models": {**cfg["models"], "rf": {**cfg["models"]["rf"], "n_estimators": 5},
                      "lgbm": {**cfg["models"]["lgbm"], "n_estimators": 5}}}
    monkeypatch.setattr(G, "SIGN_BOOT", 5)
    monkeypatch.setattr(G, "COST_URLS", 50)
    monkeypatch.setattr(G, "COST_REPEATS", 1)
    real = pd.read_parquet

    def spy(path, *a, **kw):
        p = str(path).replace("\\", "/")
        assert "test_vault" not in p, "DA-GAFS touched the TEST vault"
        if p.endswith("records.parquet"):
            assert "label" not in kw.get("columns", ["label"]), "records.parquet label column read"
        return real(path, *a, **kw)

    monkeypatch.setattr(pd, "read_parquet", spy)
    out = G.run_dagafs(paths, cfg)
    man = read_json(out / "manifest.json")
    assert man["status"] == "passed" and man["test_labels_read"] is False
    assert G.latest_dagafs(paths) == out
    m = pd.read_csv(out / "metrics.csv")
    assert {"LGBM-DAGAFS", "RF-IS", "LGBM-I", "LGBM-ALL", "RF-STABLE", "GAE", "ENS3"} <= set(m.config)
    sw = pd.read_csv(out / "sweep.csv")
    assert sw.groupby("ranking").chosen.sum().eq(1).all()

    post = G.run_dagafs_posthoc(paths, cfg)                     # D-42 reads the verified D-41 run
    assert read_json(post / "manifest.json")["test_labels_read"] is False
    assert {"RF-I@own", "LGBM-DAGAFS@own"} <= set(pd.read_csv(post / "metrics.csv").config)
    from phishresearch.extensions.report import write_dagafs_report
    mac = write_dagafs_report(out, tmp_path / "ms", post)
    assert (tmp_path / "ms" / "generated" / "dagafs_macros.tex").exists() and "gK" in mac and "hRelI" in mac
