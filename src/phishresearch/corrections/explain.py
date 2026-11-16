"""Strict probability-space explanations with faithful RF float32 split semantics.

SHAP 0.49's interventional C++ Node stores thresholds as float32. Round-to-nearest
can move an sklearn float64 split ABOVE its true boundary. sklearn first casts
inputs to float32. On that input lattice, flooring each threshold to float32 is
exactly equivalent to the classifier's original <= comparison. Only the explainer
representation changes: the fitted model and attribution outputs are never patched.
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from ..common import GateError

TOLERANCE = 1e-6


def floor_float32(thresholds):
    original = np.asarray(thresholds, dtype=np.float64)
    rounded = original.astype(np.float32)
    above = rounded.astype(np.float64) > original
    rounded[above] = np.nextafter(rounded[above], np.float32(-np.inf))
    return rounded.astype(np.float64)


def strict_shap(bundle, background, frame):
    import shap

    bg, matrix = bundle.matrix(background), bundle.matrix(frame)
    is_rf = isinstance(bundle.model, RandomForestClassifier)
    if is_rf:
        bg, matrix = bg.astype(np.float32), matrix.astype(np.float32)
    explainer = shap.TreeExplainer(bundle.model, data=bg,
                                   feature_perturbation="interventional", model_output="probability")
    adjusted = 0
    if is_rf:
        old = explainer.model.thresholds.copy()
        explainer.model.thresholds[:] = floor_float32(old)
        adjusted = int(np.count_nonzero(old != explainer.model.thresholds))
        # Independent prediction equivalence, including the background used by the game.
        combined = np.concatenate([bg, matrix])
        original = bundle.model.predict_proba(combined)
        represented = explainer.model.predict(combined)
        representation_error = float(np.max(np.abs(original - represented)))
        if representation_error > 1e-12:
            raise GateError(f"RF explainer differs from actual classifier: {representation_error}")
    else:
        representation_error = None
    values = np.asarray(explainer.shap_values(matrix, check_additivity=True))
    expected = np.asarray(explainer.expected_value)
    positive = list(bundle.model.classes_).index(1)
    if values.ndim == 3:
        values, expected = values[..., positive], expected[positive]
    expected = float(expected)
    scores = bundle.score(frame)
    residuals = expected + values.sum(axis=1) - scores
    error = float(np.max(np.abs(residuals)))
    baseline_error = float(abs(expected - bundle.model.predict_proba(bg)[:, positive].mean()))
    if not np.isfinite(values).all() or not np.isfinite(residuals).all():
        raise GateError("Nonfinite explanation output")
    if error > TOLERANCE or baseline_error > TOLERANCE:
        raise GateError(f"Strict explanation failed: residual={error}; baseline={baseline_error}")
    return {"shap": values, "X": frame.to_numpy(), "expected": expected,
            "scores": scores, "residuals": residuals, "additivity_max_abs_err": error,
            "baseline_max_abs_err": baseline_error, "representation_max_abs_err": representation_error,
            "thresholds_represented_at_float32_floor": adjusted}
