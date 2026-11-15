"""One-shot batch evaluation of every frozen bundle on source TEST and target TEST
(PRD s10, s14, s19). No fit APIs are called here."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from .common import GateError, Paths, sha256_file, write_json
from .freeze import verify_freeze
from .models import ModelBundle
from .statistics import compute_metrics


def _load_test(paths: Paths) -> pd.DataFrame:
    vault = paths.processed / "test_vault"
    X = pd.read_parquet(vault / "test_features.parquet")
    y = pd.read_parquet(vault / "test_labels.parquet")
    if set(y["label"].unique()) - {0, 1}:
        raise GateError("TEST labels outside {0,1}")
    d = X.merge(y, on="record_id", validate="one_to_one")
    dev = pd.read_parquet(paths.processed / "dev_features.parquet", columns=["record_id", "group_id", "dataset_id"])
    if set(d.record_id) & set(dev.record_id):
        raise GateError("TEST records overlap development records")
    for s in ("A", "B"):
        if set(d.loc[d.dataset_id == s, "group_id"]) & set(dev.loc[dev.dataset_id == s, "group_id"]):
            raise GateError(f"TEST groups of {s} overlap its FIT/VAL groups")
    return d.sort_values("record_id").reset_index(drop=True)


def evaluate_frozen(bundle: ModelBundle, test: pd.DataFrame) -> np.ndarray:
    return bundle.score(test[bundle.feature_ids])


def run_evaluation(freeze_path: Path, paths: Paths) -> dict:
    fr = verify_freeze(freeze_path, paths.root)
    hashes = fr["body"]["file_hashes"]
    run_id = "eval-" + fr["freeze_hash"][:12]
    test = _load_test(paths)
    by_src = {s: test[test.dataset_id == s].reset_index(drop=True) for s in ("A", "B")}
    preds, metrics, thr_rows = [], [], []
    for item in fr["body"]["plan"]:
        bpath = paths.root / item["bundle"]
        rel = (item["bundle"] + ".joblib")
        if rel not in hashes:
            raise GateError(f"bundle {item['bundle_id']} not covered by freeze")
        b = ModelBundle.load(bpath, expected_sha256=hashes[rel])
        m = b.meta
        if m.get("source") != item["source"]:
            raise GateError(f"bundle {item['bundle_id']} has no / wrong source id")
        for tgt in item["targets"]:
            d = by_src[tgt]
            s = evaluate_frozen(b, d)
            preds.append(pd.DataFrame({
                "run_id": run_id, "bundle_id": m["bundle_id"], "seed": m["seed"], "source": m["source"], "target": tgt,
                "model": m["model"], "selector": m["selector"], "budget_type": " ".join(m["roles"]), "k": m["k"],
                "record_id": d["record_id"].to_numpy(), "group_id": d["group_id"].to_numpy(),
                "y_true": d["label"].to_numpy().astype(np.int8), "score_phishing": s}))
            for policy, t in m["thresholds"].items():
                r = compute_metrics(d["label"].to_numpy(), s, t["threshold"])
                metrics.append({"run_id": run_id, "bundle_id": m["bundle_id"], "source": m["source"], "target": tgt,
                                "model": m["model"], "selector": m["selector"], "k": m["k"], "seed": m["seed"],
                                "roles": m["roles"], "threshold_policy": policy,
                                "n_domains": int(d["group_id"].nunique()), **r})
                if tgt == item["source"]:
                    thr_rows.append({"bundle_id": m["bundle_id"], "policy": policy, **{k: v for k, v in t.items() if k != "policy"}})
    P = pd.concat(preds, ignore_index=True)
    if P.duplicated(["bundle_id", "target", "record_id"]).any():
        raise GateError("duplicate prediction keys")
    out = paths.eval
    out.mkdir(parents=True, exist_ok=True)
    P.to_parquet(out / "predictions.parquet", index=False)
    pd.DataFrame(thr_rows).to_csv(out / "thresholds.csv", index=False)
    doc = {"schema_version": 1, "run_id": run_id, "freeze_hash": fr["freeze_hash"],
           "evaluated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "predictions_sha256": sha256_file(out / "predictions.parquet"),
           "status": "completed", "metrics": metrics}
    write_json(out / "metrics.json", doc)
    return doc
