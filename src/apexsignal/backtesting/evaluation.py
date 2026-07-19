"""Walk-forward, time-based evaluation of pre-race models.

Races are processed in chronological order. For each race the model predicts **before** it
sees the result, then updates — so predictions never use future information (no leakage).
Predictions are split by race into train/validation/test blocks purely by time; calibration
is fit on the validation block only and applied to the test block.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from apexsignal.backtesting.metrics import EvaluationMetrics, evaluate
from apexsignal.domain.contracts import (
    RacePrediction,
    RaceResult,
    outcome_dnf,
    outcome_podium,
    outcome_points,
    outcome_win,
)
from apexsignal.models.calibration import fit_calibrator

CONTRACTS = ("win", "podium", "points", "dnf")
_OUTCOME_FN = {
    "win": outcome_win,
    "podium": outcome_podium,
    "points": outcome_points,
    "dnf": outcome_dnf,
}


class _Record(BaseModel):
    race_idx: int
    contract: str
    prob: float
    outcome: int


def _prob_for(pred: RacePrediction, contract: str, driver: str) -> float:
    dcp = pred.drivers[driver]
    return {"win": dcp.win, "podium": dcp.podium, "points": dcp.points, "dnf": dcp.dnf}[contract]


def collect_walk_forward(results: list[RaceResult], model: object) -> list[_Record]:
    """Predict-then-update over the chronological races; return all (prob, outcome) records."""
    records: list[_Record] = []
    for idx, result in enumerate(results):
        pred: RacePrediction = model.predict(result)  # type: ignore[attr-defined]
        for driver in result.drivers():
            if driver not in pred.drivers:
                continue
            for contract in CONTRACTS:
                records.append(
                    _Record(
                        race_idx=idx,
                        contract=contract,
                        prob=_prob_for(pred, contract, driver),
                        outcome=_OUTCOME_FN[contract](result, driver),
                    )
                )
        model.update(result)  # type: ignore[attr-defined]
    return records


class ContractEvaluation(BaseModel):
    contract: str
    raw: EvaluationMetrics
    calibrated: EvaluationMetrics
    calibration_method: str
    validation_log_loss: dict[str, float]


class ModelEvaluation(BaseModel):
    model_name: str
    n_races: int
    n_test_races: int
    contracts: dict[str, ContractEvaluation]


def _split_bounds(n_races: int, val_fraction: float, test_fraction: float) -> tuple[int, int]:
    n_test = max(1, round(n_races * test_fraction))
    n_val = max(1, round(n_races * val_fraction))
    test_start = n_races - n_test
    val_start = max(0, test_start - n_val)
    return val_start, test_start


def evaluate_model(
    results: list[RaceResult],
    model_factory: Callable[[], object],
    *,
    val_fraction: float = 0.2,
    test_fraction: float = 0.3,
) -> ModelEvaluation:
    """Walk-forward evaluate a model, calibrating on validation and scoring on test."""
    model = model_factory()
    records = collect_walk_forward(results, model)
    n_races = len(results)
    val_start, test_start = _split_bounds(n_races, val_fraction, test_fraction)

    contracts: dict[str, ContractEvaluation] = {}
    for contract in CONTRACTS:
        val = [
            (r.prob, r.outcome)
            for r in records
            if r.contract == contract and val_start <= r.race_idx < test_start
        ]
        test = [
            (r.prob, r.outcome)
            for r in records
            if r.contract == contract and r.race_idx >= test_start
        ]
        if not test:
            continue

        test_probs = [p for p, _ in test]
        test_outcomes = [o for _, o in test]

        calibrator, val_scores = (
            fit_calibrator([p for p, _ in val], [o for _, o in val]) if val else (None, {})
        )

        raw = evaluate(test_probs, test_outcomes, label=f"{contract}:raw")
        if calibrator is not None:
            cal_probs = calibrator.transform(test_probs)
            calibrated = evaluate(cal_probs, test_outcomes, label=f"{contract}:cal")
            method = calibrator.method
        else:
            calibrated = raw
            method = "identity"

        contracts[contract] = ContractEvaluation(
            contract=contract,
            raw=raw,
            calibrated=calibrated,
            calibration_method=method,
            validation_log_loss=val_scores,
        )

    return ModelEvaluation(
        model_name=getattr(model, "name", "model"),
        n_races=n_races,
        n_test_races=n_races - test_start,
        contracts=contracts,
    )
