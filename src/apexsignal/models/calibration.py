"""Probability calibration — isotonic and Platt (logistic), selected on validation only.

A calibrator is fit on a validation set of (prediction, outcome) pairs and then applied to
future predictions. The method is chosen by validation log loss; nothing peeks at test data.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from apexsignal.backtesting.metrics import log_loss
from apexsignal.models._numeric import (
    Floats,
    as_array,
    clip01,
    fit_logistic_1d,
    logit,
    pool_adjacent_violators,
    sigmoid,
)


class Calibrator(Protocol):
    method: str

    def transform(self, probs: object) -> Floats: ...


class IdentityCalibrator:
    method = "identity"

    def transform(self, probs: object) -> Floats:
        return clip01(as_array(probs))


class PlattCalibrator:
    """Logistic recalibration on the logit of the raw probability."""

    method = "platt"

    def __init__(self, slope: float = 1.0, intercept: float = 0.0) -> None:
        self.slope = slope
        self.intercept = intercept

    @classmethod
    def fit(cls, probs: object, outcomes: object) -> PlattCalibrator:
        a, b = fit_logistic_1d(logit(as_array(probs)), as_array(outcomes))
        return cls(slope=a, intercept=b)

    def transform(self, probs: object) -> Floats:
        return clip01(sigmoid(self.slope * logit(as_array(probs)) + self.intercept))


class IsotonicCalibrator:
    """Non-parametric monotone recalibration via pool-adjacent-violators."""

    method = "isotonic"

    def __init__(self, x: Floats, y: Floats) -> None:
        self._x = x  # sorted unique-ish predictor knots
        self._y = y  # fitted (monotone) values

    @classmethod
    def fit(cls, probs: object, outcomes: object) -> IsotonicCalibrator:
        p = as_array(probs)
        y = as_array(outcomes)
        order = np.argsort(p, kind="stable")
        xs = p[order]
        ys = pool_adjacent_violators(y[order])
        return cls(x=xs, y=ys)

    def transform(self, probs: object) -> Floats:
        p = as_array(probs)
        if self._x.size == 0:
            return clip01(p)
        return clip01(np.interp(p, self._x, self._y))


def fit_calibrator(val_probs: object, val_outcomes: object) -> tuple[Calibrator, dict[str, float]]:
    """Fit candidate calibrators and pick the one with the best validation log loss.

    Returns the chosen calibrator plus each candidate's validation log loss (transparency).
    """
    p = as_array(val_probs)
    y = as_array(val_outcomes)

    candidates: list[Calibrator] = [IdentityCalibrator()]
    if p.size >= 10 and len(np.unique(y)) >= 2:
        candidates.append(PlattCalibrator.fit(p, y))
        candidates.append(IsotonicCalibrator.fit(p, y))

    scores = {c.method: log_loss(c.transform(p), y) for c in candidates}
    best = min(candidates, key=lambda c: scores[c.method])
    return best, scores
