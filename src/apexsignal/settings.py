"""Application settings with validation and hard safety guards.

Settings load from environment variables (and an optional ``.env``). The fixture demo runs
with zero credentials; live/authenticated adapters are unlocked only when their credentials
are present. Two guarantees are enforced here, not merely documented:

* real-money trading cannot be switched on (``ENABLE_LIVE_TRADING`` must stay false);
* Polymarket stays read-only.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LiveTradingDisabledError(RuntimeError):
    """Raised whenever real-money execution is requested. It is never implemented."""


class AppMode(StrEnum):
    FIXTURE = "fixture"
    REPLAY = "replay"
    LIVE = "live"
    PAPER = "paper"


class ExecutionMode(StrEnum):
    PAPER = "paper"
    KALSHI_DEMO = "kalshi_demo"
    SYNTHETIC = "synthetic"


class LLMProvider(StrEnum):
    NONE = "none"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class Settings(BaseSettings):
    """Validated runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    app_mode: AppMode = AppMode.FIXTURE
    execution_mode: ExecutionMode = ExecutionMode.PAPER

    # Hard safety guard. Real-money execution is not implemented on this branch.
    enable_live_trading: bool = False

    fastf1_cache_dir: str = ".cache/fastf1"

    openf1_username: str | None = None
    openf1_password: str | None = None

    kalshi_env: str = "demo"
    kalshi_api_key_id: str | None = None
    kalshi_private_key_path: str | None = None

    # Polymarket is read-only, always.
    polymarket_read_only: bool = True

    newsapi_key: str | None = None
    gdelt_api_key: str | None = None

    llm_provider: LLMProvider = LLMProvider.NONE
    llm_model: str | None = None
    llm_api_key: str | None = None

    database_url: str = "sqlite:///data/apexsignal.db"
    log_level: str = "INFO"
    simulation_paths: int = Field(default=5000, gt=0)
    random_seed: int = 42

    @model_validator(mode="after")
    def _enforce_safety(self) -> Settings:
        if self.enable_live_trading:
            raise LiveTradingDisabledError(
                "ENABLE_LIVE_TRADING is true, but real-money execution is not implemented "
                "in ApexSignal F1. Set ENABLE_LIVE_TRADING=false. Supported execution "
                "modes are paper, synthetic, and kalshi_demo."
            )
        if not self.polymarket_read_only:
            raise ValueError(
                "POLYMARKET_READ_ONLY must remain true; the Polymarket adapter is read-only."
            )
        if self.kalshi_env not in {"demo"}:
            raise ValueError(
                f"KALSHI_ENV={self.kalshi_env!r} is not allowed; only 'demo' is supported."
            )
        return self

    @property
    def kalshi_demo_configured(self) -> bool:
        return bool(self.kalshi_api_key_id and self.kalshi_private_key_path)

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider is not LLMProvider.NONE and bool(self.llm_api_key)


def load_settings() -> Settings:
    """Load and validate settings. Raises on an unsafe or malformed configuration."""
    return Settings()
