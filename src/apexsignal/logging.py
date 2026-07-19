"""Structured logging via structlog, with secret redaction.

Secrets must never reach the logs. ``redact_secrets`` scrubs common sensitive keys and any
value that looks like a credential before rendering.
"""

from __future__ import annotations

import logging
from typing import cast

import structlog
from structlog.types import EventDict, WrappedLogger

_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "api_key",
        "apikey",
        "llm_api_key",
        "newsapi_key",
        "gdelt_api_key",
        "kalshi_api_key_id",
        "private_key",
        "secret",
        "token",
        "authorization",
    }
)

_REDACTED = "***redacted***"


def redact_secrets(_logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
    """structlog processor that redacts sensitive keys anywhere in the event dict."""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS and event_dict[key] not in (None, ""):
            event_dict[key] = _REDACTED
    return event_dict


def configure_logging(level: str = "INFO", *, json: bool = False) -> None:
    """Configure structlog + stdlib logging once at startup."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=log_level)

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_secrets,
            structlog.processors.StackInfoRenderer(),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
