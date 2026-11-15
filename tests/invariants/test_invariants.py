"""I01 no leakage, I02 purge/partitions, I03 nested selection, I05 determinism, I07 offline."""
import socket

import numpy as np
import pandas as pd
import pytest

from conftest import FAST_TREES, build_workspace, fast_cfg
from phishresearch.cohort import build_cohort, parse_records
from phishresearch.common import GateError, read_json
from phishresearch.develop import develop_source
from phishresearch.features import extract_features
from phishresearch.models import ModelBundle
from phishresearch.prepare import load_dev
from phishresearch.selection import group_folds
from phishresearch.splits import make_group_splits
from phishresearch.synthetic import make_sources


# ---------------------------------------------------------------- I01
def test_fit_ids_never_touch_val_test_or_outer_holdout(tmp_path):
    events = []
    cfg, paths = build_workspace(tmp_path, fit_hook=lambda ids, why: events.append((why, set(ids))))
    fit = set(load_dev(paths, "A", "FIT").record_id)
    val = set(load_dev(paths, "A", "VAL").record_id)
    test = set(pd.read_parquet(paths.processed / "test_vault" / "test_features.parquet").record_id)
    for why, ids in events:
        if why == "threshold_val":
            assert ids == val
        else:
            assert ids <= fit, why
            assert not ids & (val | test), why
    # selector blocks (3 proxy fits + 3 PI scorings) must exclude the outer holdout they are scored on
    i, n_checked = 0, 0
    while i < len(events):
        if events[i][0] == "selector_proxy_fit":
            block = events[i:i + 6]
            union = set().union(*(ids for _, ids in block))
            nxt = next((e for e in events[i + 6:] if e[0] in ("outer_holdout_score", "final_fit")), None)
            if nxt and nxt[0] == "outer_holdout_score":
                assert not union & nxt[1] and union | nxt[1] == fit
                n_checked += 1
            else:
                assert union == fit
            i += 6
        else:
            i += 1
    assert n_checked == 3


def test_val_only_signal_does_not_change_selection(tmp_path, workspace):
    cfg, paths = workspace
    fit, val = load_dev(paths, "A", "FIT"), load_dev(paths, "A", "VAL")
    poisoned = val.copy()
    poisoned["F01"] = poisoned["label"] * 1e6        # leak label into VAL only
    out = develop_source("A", fit, poisoned, cfg, 2, tmp_path / "p", n_estimators=FAST_TREES, log=lambda *_: None)
    ref = read_json(paths.dev / "A" / "develop.json")
    assert out["seeds"]["17"]["chosen_k"] == ref["seeds"]["17"]["chosen_k"]
    for bid in ref["seeds"]["17"]["bundles"]:
        a = read_json(paths.dev / "A" / "bundles" / f"{bid}.json")["feature_ids"]
        b = read_json(tmp_path / "p" / "bundles" / f"{bid}.json")["feature_ids"]
        assert a == b


def test_dev_loader_refuses_test(workspace):
    _, paths = workspace
    with pytest.raises(GateError):
        load_dev(paths, "A", "TEST")


# ---------------------------------------------------------------- I02
def test_purge_and_partitions_group_disjoint(workspace):
    _, paths = workspace
    rec = pd.read_parquet(paths.processed / "records.parquet")
    coh = rec[rec.in_cohort]
    assert not set(coh[coh.dataset_id == "A"].group_id) & set(coh[coh.dataset_id == "B"].group_id)
    assert (rec.reason == "cross_source_domain_purge").sum() > 0          # synthetic shared domain removed
    sp = pd.read_parquet(paths.processed / "splits.parquet")
    for _, d in sp.groupby("dataset_id"):
        parts = d.groupby("partition")["group_id"].apply(set)
        assert not parts["FIT"] & parts["VAL"] and not parts["FIT"] & parts["TEST"] and not parts["VAL"] & parts["TEST"]


def test_label_conflicts_fully_quarantined():
    from phishresearch.adapters import _frame
    a = _frame("A", "a.json", ["http://x.example.test/1", "http://x.example.test/1", "http://y.example.test/"], [0, 1, 0], None)
    b = _frame("B", "b.csv", ["HTTP://X.example.test/1", "http://z.example.test/"], [0, 1], None)
    c = build_cohort(parse_records(pd.concat([a, b], ignore_index=True), 16384))
    conflict_rows = c[c.url_key == "http://x.example.test/1"]
    assert len(conflict_rows) == 3 and not conflict_rows.in_cohort.any()
    assert set(conflict_rows.reason) == {"label_conflict"}


def test_within_source_duplicate_keeps_first():
    from phishresearch.adapters import _frame
    a = _frame("A", "a.json", ["http://d.example.test/a", "http://d.example.test/a"], [1, 1], None)
    c = build_cohort(parse_records(a, 16384))
    assert c.in_cohort.tolist() == [True, False] and c.reason.tolist()[1] == "within_source_duplicate"


# ---------------------------------------------------------------- I03
def test_nested_selector_hashes_and_disjoint_folds(workspace):
    cfg, paths = workspace
    dev = read_json(paths.dev / "A" / "develop.json")["seeds"]["17"]
    assert dev["full_selector_hash"] not in dev["outer_selector_hashes"]
    assert len(set(dev["outer_selector_hashes"])) == 3
    fit = load_dev(paths, "A", "FIT")
    for tr, ho in group_folds(fit.label.values, fit.group_id.values, 3, cfg["splits"]["seed"]):
        assert not set(fit.group_id.values[tr]) & set(fit.group_id.values[ho])


# ---------------------------------------------------------------- I05
def test_shuffled_input_same_cohort_and_splits():
    cfg = fast_cfg()
    raw = pd.concat(make_sources(), ignore_index=True)
    def run(df):
        c = build_cohort(parse_records(df, 16384))
        s = make_group_splits(c[c.in_cohort], cfg)
        return c.sort_values("record_id")[["record_id", "in_cohort"]].reset_index(drop=True), s
    c1, s1 = run(raw)
    c2, s2 = run(raw.sample(frac=1, random_state=3).reset_index(drop=True))
    pd.testing.assert_frame_equal(c1, c2)
    pd.testing.assert_frame_equal(s1, s2)


def test_rerun_same_seed_same_predictions(tmp_path, workspace):
    cfg, paths = workspace
    fit, val = load_dev(paths, "B", "FIT"), load_dev(paths, "B", "VAL")
    develop_source("B", fit, val, cfg, 2, tmp_path / "r", n_estimators=FAST_TREES, log=lambda *_: None)
    for bid in read_json(paths.dev / "B" / "develop.json")["seeds"]["17"]["bundles"]:
        a, b = ModelBundle.load(paths.dev / "B" / "bundles" / bid), ModelBundle.load(tmp_path / "r" / "bundles" / bid)
        X = val[a.feature_ids]
        np.testing.assert_allclose(a.score(X), b.score(X), atol=1e-12)


# ---------------------------------------------------------------- I07
def test_extraction_is_offline(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network access attempted")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    X = extract_features(["http://login.example.co.uk/a", "bücher.example/x"])
    assert X.shape == (2, 37)
