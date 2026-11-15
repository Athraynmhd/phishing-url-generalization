"""Fixed-hyperparameter RF and LightGBM + model bundle (PRD s13, s19)."""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier

from .common import sha256_file, write_json
from .features import validate_ids

MODELS = ("RF", "LGBM")


def make_model(name: str, seed: int, cfg: dict, threads: int, n_estimators: int | None = None):
    if name == "RF":
        p = dict(cfg["models"]["rf"])
        if n_estimators:
            p["n_estimators"] = n_estimators
        return RandomForestClassifier(**p, class_weight=None, random_state=seed, n_jobs=threads)
    if name == "LGBM":
        p = dict(cfg["models"]["lgbm"])
        if n_estimators:
            p["n_estimators"] = n_estimators
        return LGBMClassifier(**p, class_weight=None, random_state=seed, n_jobs=threads, verbose=-1)
    raise ValueError(name)


def positive_scores(model, X: np.ndarray) -> np.ndarray:
    """P(phishing): column located through classes_, never assumed to be index 1."""
    classes = list(model.classes_)
    if 1 not in classes:
        raise ValueError(f"positive class 1 missing from classes_ {classes}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)   # lightgbm feature-name notice on ndarray input
        return model.predict_proba(X)[:, classes.index(1)]


@dataclass
class ModelBundle:
    model: object
    feature_ids: list[str]
    meta: dict = field(default_factory=dict)

    def matrix(self, X: pd.DataFrame) -> np.ndarray:
        """Exact, ordered columns; extra or missing columns are rejected."""
        if list(X.columns) != self.feature_ids:
            raise ValueError(f"input columns {list(X.columns)} != bundle features {self.feature_ids}")
        return X.to_numpy(dtype=np.float64)

    def score(self, X: pd.DataFrame) -> np.ndarray:
        return positive_scores(self.model, self.matrix(X))

    def save(self, path: Path) -> dict:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, path.with_suffix(".joblib"))
        self.meta["model_sha256"] = sha256_file(path.with_suffix(".joblib"))
        self.meta["feature_ids"] = self.feature_ids
        write_json(path.with_suffix(".json"), self.meta)
        return self.meta

    @classmethod
    def load(cls, path: Path, expected_sha256: str | None = None) -> "ModelBundle":
        from .common import read_json
        mpath = path.with_suffix(".joblib")
        if expected_sha256 is not None and sha256_file(mpath) != expected_sha256:
            raise ValueError(f"model hash mismatch: {mpath}")
        meta = read_json(path.with_suffix(".json"))
        return cls(joblib.load(mpath), meta["feature_ids"], meta)


def fit_model(name: str, X: pd.DataFrame, y: np.ndarray, seed: int, cfg: dict, threads: int,
              n_estimators: int | None = None) -> ModelBundle:
    ids = validate_ids(X.columns)
    if list(X.columns) != ids:
        X = X[ids]
    m = make_model(name, seed, cfg, threads, n_estimators)
    m.fit(X.to_numpy(dtype=np.float64), y)
    return ModelBundle(m, ids, {"model": name, "seed": seed, "params": m.get_params()})
