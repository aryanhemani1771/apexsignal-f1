"""Probabilistic evaluation metrics for binary contract predictions.

All metrics operate on a vector of predicted probabilities and matching binary outcomes.
No metric is hard-coded — everything is computed from the passed data.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from apexsignal.models._numeric import Floats, as_array, clip01, fit_logistic_1d, logit


def brier_score(probs: object, outcomes: object) -> float:
    """Mean squared error between probabilities and outcomes (lower is better)."""
    p = as_array(probs)
    y = as_array(outcomes)
    if p.size == 0:
        return float("nan")
    return float(np.mean((p - y) ** 2))


def log_loss(probs: object, outcomes: object) -> float:
    """Binary cross-entropy (lower is better)."""
    p = clip01(as_array(probs))
    y = as_array(outcomes)
    if p.size == 0:
        return float("nan")
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def _bin_stats(p: Floats, y: Floats, n_bins: int) -> list[tuple[float, float, float, int]]:
    """Return per-bin (mean_pred, frac_pos, weight_fraction, count)."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    rows: list[tuple[float, float, float, int]] = []
    total = p.size
    for b in range(n_bins):
        mask = idx == b
        count = int(np.sum(mask))
        if count == 0:
            continue
        rows.append((float(np.mean(p[mask])), float(np.mean(y[mask])), count / total, count))
    return rows


def expected_calibration_error(probs: object, outcomes: object, n_bins: int = 10) -> float:
    """Weighted mean gap between predicted confidence and empirical frequency."""
    p = clip01(as_array(probs))
    y = as_array(outcomes)
    if p.size == 0:
        return float("nan")
    return float(
        sum(
            weight * abs(mean_pred - frac_pos)
            for mean_pred, frac_pos, weight, _ in _bin_stats(p, y, n_bins)
        )
    )


def calibration_slope_intercept(probs: object, outcomes: object) -> tuple[float, float]:
    """Slope and intercept of ``y ~ sigmoid(slope*logit(p) + intercept)``.

    Perfect calibration is slope 1, intercept 0. Slope < 1 indicates over-confidence.
    """
    p = as_array(probs)
    y = as_array(outcomes)
    if p.size == 0 or len(np.unique(y)) < 2:
        return float("nan"), float("nan")
    slope, intercept = fit_logistic_1d(logit(p), y)
    return slope, intercept


class ReliabilityBin(BaseModel):
    mean_predicted: float
    fraction_positive: float
    count: int


class EvaluationMetrics(BaseModel):
    """A bundle of evaluation metrics for one contract family / model."""

    label: str
    n: int
    brier: float
    log_loss: float
    ece: float
    calibration_slope: float
    calibration_intercept: float
    base_rate: float
    reliability: list[ReliabilityBin]


def evaluate(
    probs: object, outcomes: object, *, label: str = "model", n_bins: int = 10
) -> EvaluationMetrics:
    """Compute the full metric bundle for a set of predictions."""
    p = as_array(probs)
    y = as_array(outcomes)
    slope, intercept = calibration_slope_intercept(p, y)
    reliability = [
        ReliabilityBin(mean_predicted=mp, fraction_positive=fp, count=c)
        for mp, fp, _, c in _bin_stats(clip01(p), y, n_bins)
    ]
    return EvaluationMetrics(
        label=label,
        n=int(p.size),
        brier=brier_score(p, y),
        log_loss=log_loss(p, y),
        ece=expected_calibration_error(p, y, n_bins),
        calibration_slope=slope,
        calibration_intercept=intercept,
        base_rate=float(np.mean(y)) if y.size else float("nan"),
        reliability=reliability,
    )
