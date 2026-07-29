import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

REDACTED_KEYS = {
    "authorization",
    "cookie",
    "database_url",
    "password",
    "password_hash",
    "session_token",
    "token",
}


def redact(
    _logger: object, _method: str, event: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event):
        if key.casefold() in REDACTED_KEYS:
            event[key] = "[REDACTED]"
    return event


def configure_logging(level: str) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level.upper())
            if isinstance(logging.getLevelName(level.upper()), int)
            else logging.INFO
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
