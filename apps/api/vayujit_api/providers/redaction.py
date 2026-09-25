"""Centralized safe projection for provider metadata and failures."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from vayujit_api.providers.contracts import is_secret_key

_SECRET_TEXT = re.compile(
    r"(?i)(authorization\s*[:=]\s*bearer\s+|api[_ -]?key\s*[:=]\s*|token\s*[:=]\s*)[^\s,;]+"
)


def redact(value: Any) -> Any:
    """Return a bounded JSON-safe value with secret-shaped fields removed."""

    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if is_secret_key(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value[:200]]
    if isinstance(value, str):
        return _SECRET_TEXT.sub(lambda match: f"{match.group(1)}[REDACTED]", value)[:4000]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:4000]


def safe_error_message(value: object) -> str:
    return str(redact(str(value)))[:500]


def contains_secret(value: object, secret: str) -> bool:
    if not secret:
        return False
    return secret in str(redact(value))
