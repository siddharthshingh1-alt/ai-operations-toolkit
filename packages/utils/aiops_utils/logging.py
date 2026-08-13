"""Structured JSON logging.

One line of JSON per event keeps logs greppable locally and parseable by any
hosted log viewer (Railway / Render) without extra tooling.

CLAUDE.md Section 22: "Do not log sensitive content unnecessarily." Prompts and
AI outputs are deliberately NOT logged here — only metadata (model, duration,
status, tokens, cost).
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

_CONFIGURED = False

# Attributes present on every LogRecord; anything else was passed via `extra`.
_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Render a log record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge anything passed as logger.info("...", extra={"key": value}).
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger. Safe to call repeatedly."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # uvicorn installs its own colourised handlers; route them through ours so
    # every line in the terminal has the same shape.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Use the module's `__name__`."""
    return logging.getLogger(name)
