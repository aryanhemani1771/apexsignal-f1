"""Load and summarize the latest model-evaluation report for the dashboard.

Reports are produced by ``scripts/train_models.py``. If none exists, the caller should show
"Not yet evaluated" rather than any placeholder number.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPORT = _REPO_ROOT / "artifacts" / "reports" / "evaluation_latest.json"


def load_latest_report(path: str | Path | None = None) -> dict[str, Any] | None:
    """Return the parsed report, or None if it has not been generated yet."""
    p = Path(path) if path else DEFAULT_REPORT
    if not p.exists():
        return None
    return cast(dict[str, Any], json.loads(p.read_text(encoding="utf-8")))


def contract_summary(report: dict[str, Any], contract: str = "win") -> list[dict[str, Any]]:
    """Flatten a report into per-model rows for one contract (raw vs calibrated)."""
    rows: list[dict[str, Any]] = []
    for name, ev in report.get("models", {}).items():
        ce = ev.get("contracts", {}).get(contract)
        if not ce:
            continue
        rows.append(
            {
                "model": name,
                "brier_raw": round(ce["raw"]["brier"], 4),
                "brier_cal": round(ce["calibrated"]["brier"], 4),
                "logloss_cal": round(ce["calibrated"]["log_loss"], 4),
                "calibration": ce["calibration_method"],
                "n": ce["calibrated"]["n"],
            }
        )
    rows.sort(key=lambda r: r["brier_cal"])
    return rows


def best_model(report: dict[str, Any], contract: str = "win") -> str | None:
    rows = contract_summary(report, contract)
    return rows[0]["model"] if rows else None
