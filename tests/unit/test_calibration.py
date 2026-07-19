"""Probability calibration."""

from __future__ import annotations

import numpy as np

from apexsignal.backtesting.metrics import log_loss
from apexsignal.models.calibration import (
    IsotonicCalibrator,
    PlattCalibrator,
    fit_calibrator,
)


def test_isotonic_is_monotone() -> None:
    rng = np.random.default_rng(1)
    p = rng.uniform(size=500)
    y = (rng.uniform(size=500) < p).astype(int)
    cal = IsotonicCalibrator.fit(p, y)
    grid = np.linspace(0.0, 1.0, 50)
    out = cal.transform(grid)
    assert np.all(np.diff(out) >= -1e-9)


def test_platt_reduces_loss_on_overconfident_probs() -> None:
    rng = np.random.default_rng(2)
    true_p = rng.uniform(0.2, 0.8, size=2000)
    y = (rng.uniform(size=2000) < true_p).astype(int)
    # Overconfident predictions: push probabilities toward 0/1.
    over = np.clip((true_p - 0.5) * 2.2 + 0.5, 0.01, 0.99)
    cal = PlattCalibrator.fit(over, y)
    assert log_loss(cal.transform(over), y) <= log_loss(over, y) + 1e-9


def test_fit_calibrator_returns_choice_and_scores() -> None:
    rng = np.random.default_rng(3)
    p = rng.uniform(size=400)
    y = (rng.uniform(size=400) < p).astype(int)
    calibrator, scores = fit_calibrator(p, y)
    assert calibrator.method in {"identity", "platt", "isotonic"}
    assert set(scores) <= {"identity", "platt", "isotonic"}
    # The chosen method has the minimum validation log loss.
    assert scores[calibrator.method] == min(scores.values())
