"""Kalshi demo execution entry point.

Re-exports the demo executor. Real-money execution is never implemented; the guarded path
raises ``LiveTradingDisabledError``. Demo order placement requires demo credentials.
"""

from __future__ import annotations

from apexsignal.ingestion.kalshi_adapter import KalshiDemoExecutor

__all__ = ["KalshiDemoExecutor"]
