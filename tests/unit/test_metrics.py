"""Evaluation metrics."""

from __future__ import annotations

import numpy as np

from apexsignal.backtesting.metrics import (
    brier_score,
    calibration_slope_intercept,
    evaluate,
    expected_calibration_error,
    log_loss,
)


def test_brier_perfect_and_worst() -> None:
    assert brier_score([1.0, 0.0], [1, 0]) == 0.0
    assert brier_score([0.0, 1.0], [1, 0]) == 1.0
    assert brier_score([0.5, 0.5], [1, 0]) == 0.25


def test_log_loss_perfect_is_small() -> None:
    assert log_loss([0.999999, 0.000001], [1, 0]) < 1e-3


def test_log_loss_penalises_confident_mistakes() -> None:
    assert log_loss([0.01], [1]) > log_loss([0.4], [1])


def test_ece_zero_for_perfectly_calibrated_bins() -> None:
    # Two bins, each prediction matches its empirical frequency exactly.
    probs = [0.0, 0.0, 1.0, 1.0]
    outcomes = [0, 0, 1, 1]
    # ~0 up to the clip epsilon used to keep probabilities away from exactly 0/1.
    assert expected_calibration_error(probs, outcomes, n_bins=2) < 1e-9


def test_calibration_slope_near_one_for_calibrated_data() -> None:
    rng = np.random.default_rng(0)
    p = rng.uniform(0.05, 0.95, size=5000)
    y = (rng.uniform(size=5000) < p).astype(int)
    slope, intercept = calibration_slope_intercept(p, y)
    assert 0.8 < slope < 1.2
    assert abs(intercept) < 0.3


def test_evaluate_bundle_shape() -> None:
    m = evaluate([0.2, 0.8, 0.6], [0, 1, 1], label="x")
    assert m.n == 3
    assert m.label == "x"
    assert 0.0 <= m.base_rate <= 1.0
    assert m.reliability  # at least one populated bin
