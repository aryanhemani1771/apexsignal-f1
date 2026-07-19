"""Settings validation and safety guards."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from apexsignal.settings import (
    AppMode,
    ExecutionMode,
    LiveTradingDisabledError,
    LLMProvider,
    Settings,
)


def _settings(**overrides: object) -> Settings:
    # _env_file=None keeps the test hermetic (ignores any local .env / shell env osmosis).
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_safe_defaults() -> None:
    s = _settings()
    assert s.app_mode is AppMode.FIXTURE
    assert s.execution_mode is ExecutionMode.PAPER
    assert s.enable_live_trading is False
    assert s.polymarket_read_only is True
    assert s.simulation_paths > 0


def test_live_trading_is_hard_blocked() -> None:
    with pytest.raises(LiveTradingDisabledError):
        _settings(enable_live_trading=True)


def test_polymarket_must_stay_read_only() -> None:
    with pytest.raises(ValueError, match="POLYMARKET_READ_ONLY"):
        _settings(polymarket_read_only=False)


def test_only_kalshi_demo_allowed() -> None:
    with pytest.raises(ValueError, match="KALSHI_ENV"):
        _settings(kalshi_env="prod")


def test_simulation_paths_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        _settings(simulation_paths=0)


def test_kalshi_demo_configured_property() -> None:
    assert _settings().kalshi_demo_configured is False
    configured = _settings(kalshi_api_key_id="id", kalshi_private_key_path="/tmp/k.pem")
    assert configured.kalshi_demo_configured is True


def test_llm_enabled_property() -> None:
    assert _settings().llm_enabled is False
    enabled = _settings(llm_provider=LLMProvider.ANTHROPIC, llm_api_key="x")
    assert enabled.llm_enabled is True
