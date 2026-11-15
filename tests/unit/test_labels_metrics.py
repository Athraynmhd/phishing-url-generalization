"""U03 label/adapters and U04 metrics/thresholds."""
import json

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from phishresearch.adapters import load_ebbu_json, load_hp_csv, record_id
from phishresearch.common import GateError
from phishresearch.models import positive_scores
from phishresearch.statistics import compute_metrics, paired_cluster_bootstrap
from phishresearch.thresholds import choose_threshold


# ---------------------------------------------------------------- U03
def test_hp_adapter_header_and_labels(tmp_path):
    p = tmp_path / "hp.csv"
    p.write_text(",index,url,label,Unnamed: 0\n0,0,http://a.example.test/,0,\n1,1,http://b.example.test/,1,\n", encoding="utf-8")
    d = load_hp_csv(p, "hp.csv", "train")
    assert d["label"].tolist() == [0, 1] and d["url_raw"].tolist()[1] == "http://b.example.test/"
    assert d["original_split"].unique().tolist() == ["train"]
    p2 = tmp_path / "hp2.csv"
    p2.write_text(",idx,url,label,Unnamed: 0\n0,0,http://a.example.test/,0,\n", encoding="utf-8")
    with pytest.raises(GateError):
        load_hp_csv(p2, "hp2.csv", "train")
    p3 = tmp_path / "hp3.csv"
    p3.write_text(",index,url,label,Unnamed: 0\n0,0,http://a.example.test/,2,\n", encoding="utf-8")
    with pytest.raises(GateError):
        load_hp_csv(p3, "hp3.csv", "train")


def test_ebbu_adapter_file_label(tmp_path):
    p = tmp_path / "data_phishing.json"
    p.write_text(json.dumps(["login.example.test/x"]), encoding="utf-8")
    assert load_ebbu_json(p, "data_phishing.json", 1)["label"].tolist() == [1]


def test_record_id_unambiguous():
    assert record_id("A", "f", 1, "2x") != record_id("A", "f1", 0, "2x") != record_id("A", "f", 12, "x")


def test_positive_column_follows_classes_order():
    X = np.array([[0.0], [1.0], [0.0], [1.0]])
    y = np.array([1, 0, 1, 0])                  # feature 0 -> phishing
    rf = RandomForestClassifier(n_estimators=5, random_state=0).fit(X, y)
    rf.classes_ = np.array([1, 0])              # simulate reversed class order
    proba = rf.predict_proba(X)
    s = positive_scores(rf, X)
    np.testing.assert_array_equal(s, proba[:, 0])


# ---------------------------------------------------------------- U04
def test_confusion_hand_calculated():
    y = [1, 1, 1, 0, 0, 0, 0]
    s = [0.9, 0.6, 0.2, 0.7, 0.1, 0.1, 0.3]
    r = compute_metrics(y, s, 0.5)
    assert (r["TN"], r["FP"], r["FN"], r["TP"]) == (3, 1, 1, 2)
    v = r["values"]
    assert v["precision"] == pytest.approx(2 / 3) and v["recall"] == pytest.approx(2 / 3)
    assert v["f1"] == pytest.approx(2 / 3) and v["specificity"] == pytest.approx(0.75)
    assert v["mcc"] == pytest.approx((2 * 3 - 1 * 1) / np.sqrt(3 * 3 * 4 * 4))


def test_threshold_f1_unique_best():
    y = np.array([1, 0, 1, 0])
    s = np.array([0.8, 0.6, 0.4, 0.2])
    # t=.8: TP1 FN1 -> 2/3 | t=.6: 1/2 | t=.4: TP2 FP1 -> 4/5 | t=.2: 4/6
    assert choose_threshold(y, s, "f1_max")["threshold"] == 0.4


def test_threshold_f1_tie_takes_largest():
    y = np.array([1, 0, 0, 1])
    s = np.array([0.9, 0.7, 0.5, 0.3])
    # t=.9: TP1 FN1 -> 2/3 | t=.7: 1/2 | t=.5: 2/5 | t=.3: TP2 FP2 -> 4/6 = 2/3  => tie, take 0.9
    assert choose_threshold(y, s, "f1_max")["threshold"] == 0.9


def test_threshold_all_negative_sentinel():
    y = np.array([0, 0, 0, 1])
    s = np.array([0.9, 0.8, 0.7, 0.1])
    # FPR <= 0 is only reachable above the max score -> sentinel, recall 0
    t = choose_threshold(y, s, "fpr_le", 0.0)
    assert t["threshold"] > 0.9 and t["val_fp"] == 0 and t["val_recall"] == 0
    assert compute_metrics(y, s, t["threshold"])["TP"] + compute_metrics(y, s, t["threshold"])["FP"] == 0


def test_fpr_policy_recall_tie_takes_largest():
    y = np.array([1, 0, 1, 0, 0])
    s = np.array([0.9, 0.8, 0.6, 0.5, 0.1])
    # FP=0 allowed: t in {sentinel, .9} -> recall 0, .5 ; t=.8 has FP1. best recall .5 only at t=.9
    t = choose_threshold(y, s, "fpr_le", 0.0)
    assert t["threshold"] == 0.9 and t["val_recall"] == 0.5


def test_source_fpr_exact():
    y = np.array([0] * 100 + [1] * 10)
    s = np.concatenate([np.linspace(0, 0.5, 100), np.linspace(0.3, 1.0, 10)])
    t = choose_threshold(y, s, "fpr_le", 0.01)
    assert t["val_fp"] <= 1 and t["val_achieved_fpr"] <= 0.01
    r = compute_metrics(y, s, t["threshold"])
    assert r["FP"] == t["val_fp"]


def test_single_class_metrics_flagged():
    r = compute_metrics([0, 0, 0], [0.1, 0.6, 0.2], 0.5)
    assert r["values"]["average_precision"] is None and any("single_class" in w for w in r["warnings"])
    assert any("zero_denominator" in w for w in r["warnings"])


def test_bootstrap_identical_models_zero_delta():
    rng = np.random.default_rng(0)
    g = rng.integers(0, 50, 500)
    y = rng.integers(0, 2, 500)
    p = rng.integers(0, 2, 500)
    r = paired_cluster_bootstrap(g, y, [p], [p.copy()], 200, 1)
    assert r["delta"] == 0 and r["ci_low"] == 0 and r["ci_high"] == 0
