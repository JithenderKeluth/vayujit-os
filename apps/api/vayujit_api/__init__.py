"""VAYUJIT OS API package."""

from __future__ import annotations

import os


def _application_version() -> str:
    configured = os.getenv("VAYUJIT_APP_VERSION")
    if configured:
        return configured
    return "0.1.0"


__version__ = _application_version()
