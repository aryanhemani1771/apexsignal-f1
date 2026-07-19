"""Evaluation-report summary service (independent of any generated artifact)."""

from __future__ import annotations

from apexsignal.services.evaluation_report import (
    best_model,
    contract_summary,
    load_latest_report,
)

_REPORT = {
    "models": {
        "uniform": {
            "contracts": {
                "win": {
                    "raw": {"brier": 0.048, "log_loss": 0.16, "n": 100},
                    "calibrated": {"brier": 0.046, "log_loss": 0.15, "n": 100},
                    "calibration_method": "platt",
                }
            }
        },
        "elo_grid": {
            "contracts": {
                "win": {
                    "raw": {"brier": 0.034, "log_loss": 0.14, "n": 100},
                    "calibrated": {"brier": 0.031, "log_loss": 0.13, "n": 100},
                    "calibration_method": "isotonic",
                }
            }
        },
    }
}


def test_missing_report_returns_none(tmp_path: object) -> None:
    assert load_latest_report(f"{tmp_path}/nope.json") is None  # type: ignore[str-bytes-safe]


def test_summary_sorted_by_calibrated_brier() -> None:
    rows = contract_summary(_REPORT, "win")
    assert [r["model"] for r in rows] == ["elo_grid", "uniform"]
    assert rows[0]["brier_cal"] == 0.031


def test_best_model_is_lowest_brier() -> None:
    assert best_model(_REPORT, "win") == "elo_grid"
