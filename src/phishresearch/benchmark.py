"""Efficiency benchmark (PRD s16).

Stages, timed separately with perf_counter_ns on the same source-VAL URLs for all models:
  extract      parse + selected-feature extraction (dependency pruning active)
  predict      model.predict_proba on precomputed features
  end_to_end   extract + predict, no caching
Batch 1 and batch 1024 are reported separately; per-URL values are labelled as such.
Single-URL latency and batch throughput are not interchangeable.
"""
from __future__ import annotations

import gc
import os
import time
from pathlib import Path

import numpy as np
import psutil

from .features import extract_features
from .models import ModelBundle


def _rss() -> int:
    mi = psutil.Process().memory_info()
    return int(getattr(mi, "peak_wset", mi.rss))


def _time(fn, warmup: int, repeats: int) -> np.ndarray:
    for _ in range(warmup):
        fn()
    out = np.empty(repeats)
    for i in range(repeats):
        t0 = time.perf_counter_ns()
        fn()
        out[i] = time.perf_counter_ns() - t0
    return out


def _summ(ns: np.ndarray, batch: int) -> dict:
    ms = ns / 1e6
    return {"median_ms_per_batch": float(np.median(ms)), "p95_ms_per_batch": float(np.percentile(ms, 95)),
            "median_us_per_url": float(np.median(ms) * 1000 / batch), "repeats": int(len(ns))}


def benchmark_bundle(bundle_path: Path, urls: list[str], cfg: dict) -> dict:
    bc = cfg["benchmark"]
    gc.collect()
    rss0 = psutil.Process().memory_info().rss
    t0 = time.perf_counter_ns()
    b = ModelBundle.load(bundle_path)
    load_ms = (time.perf_counter_ns() - t0) / 1e6
    ids = b.feature_ids
    kw = cfg["features"]["keywords"]
    res = {"bundle_id": b.meta["bundle_id"], "n_features": len(ids),
           "model_file_bytes": os.path.getsize(Path(bundle_path).with_suffix(".joblib")),
           "load_ms": load_ms, "fit_seconds": b.meta.get("fit_seconds"), "stages": {}}
    for threads in bc["threads"]:
        b.model.set_params(n_jobs=threads)        # inference threads only; the fitted model is unchanged
        for batch in bc["batch_sizes"]:
            reps = int(bc["repeats"]) * (10 if batch == 1 else 1)     # batch-1 timings are noisier: 10x samples
            pool = urls[:max(batch, 1024)]
            cursor = {"i": 0}

            def next_batch():
                i = cursor["i"]
                cursor["i"] = (i + batch) % (len(pool) - batch + 1)
                return pool[i:i + batch]

            X_pre = extract_features(pool[:batch], ids, kw)
            res["stages"][f"t{threads}/batch{batch}"] = {
                "extract": _summ(_time(lambda: extract_features(next_batch(), ids, kw), bc["warmup"], reps), batch),
                "predict": _summ(_time(lambda: b.score(X_pre), bc["warmup"], reps), batch),
                "end_to_end": _summ(_time(lambda: b.score(extract_features(next_batch(), ids, kw)), bc["warmup"], reps), batch),
            }
    res["rss_delta_mb"] = (psutil.Process().memory_info().rss - rss0) / 2**20
    res["peak_mb"] = _rss() / 2**20
    del b
    return res
