"""Bootstrap the local environment: create working dirs and validate configuration.

Safe to run repeatedly. Requires no credentials.

    uv run python scripts/bootstrap.py
"""

from __future__ import annotations

from pathlib import Path

from apexsignal.logging import configure_logging, get_logger
from apexsignal.settings import load_settings


def main() -> int:
    settings = load_settings()
    configure_logging(settings.log_level)
    log = get_logger("bootstrap")

    for directory in (
        Path(settings.fastf1_cache_dir),
        Path("data/raw"),
        Path("artifacts/models"),
        Path("artifacts/calibration"),
        Path("artifacts/reports"),
    ):
        directory.mkdir(parents=True, exist_ok=True)

    log.info(
        "bootstrap.ok",
        app_mode=settings.app_mode.value,
        execution_mode=settings.execution_mode.value,
        enable_live_trading=settings.enable_live_trading,
        kalshi_demo_configured=settings.kalshi_demo_configured,
        llm_enabled=settings.llm_enabled,
    )
    print("Bootstrap complete. Configuration is valid and working directories exist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
