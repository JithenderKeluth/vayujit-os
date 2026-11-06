"""Allowlisted QA-only exception evidence; no SQL, arguments, messages or bodies."""

from __future__ import annotations

import json
import re
import traceback
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import Engine
from starlette.types import ASGIApp, Message, Receive, Scope, Send

PATHS = {"/api/v1/ads/anomalies", "/api/v1/ads/optimization/overview"}


def safe_exception(error: BaseException) -> dict[str, object]:
    original = getattr(error, "orig", None)
    diag = getattr(original, "diag", None)
    constraint = getattr(diag, "constraint_name", None)
    state = getattr(original, "sqlstate", None)
    frames = traceback.extract_tb(error.__traceback__)
    locations = []
    for frame in frames:
        normalized = frame.filename.replace("\\", "/")
        if "/vayujit_api/ads/" in normalized:
            locations.append(
                {
                    "file": "ads/" + normalized.rsplit("/ads/", 1)[1],
                    "line": frame.lineno,
                }
            )
    return {
        "exception_type": (
            type(error).__name__
            if type(error).__name__
            in {
                "IntegrityError",
                "OperationalError",
                "ResponseValidationError",
                "TypeError",
                "ValueError",
            }
            else "OTHER_EXCEPTION"
        ),
        "sqlstate": (
            state if isinstance(state, str) and re.fullmatch(r"[A-Z0-9]{5}", state) else None
        ),
        "constraint": (
            constraint if constraint == "uq_ad_performance_anomaly_fingerprint" else None
        ),
        "locations": locations,
        "raw_error_persisted": False,
    }


class DiagnosticMiddleware:
    def __init__(self, app: ASGIApp, *, output: Path, token: str) -> None:
        self.app, self.output, self.token = app, output, token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] not in PATHS:
            return await self.app(scope, receive, send)
        row: dict[str, object] = {
            "token": self.token,
            "path": scope["path"],
            "method": scope["method"],
            "status": None,
        }

        async def observed_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                row["status"] = message["status"]
                for name, value in message.get("headers", []):
                    if name.lower() == b"x-correlation-id":
                        candidate = value.decode("ascii", errors="ignore")
                        if re.fullmatch(r"[a-f0-9-]{36}", candidate):
                            row["correlation_id"] = candidate
            await send(message)

        try:
            await self.app(scope, receive, observed_send)
        except Exception as error:
            row.update(safe_exception(error))
            row["status"] = 500
            candidate = scope.get("state", {}).get("correlation_id")
            if isinstance(candidate, str) and re.fullmatch(r"[a-f0-9-]{36}", candidate):
                row["correlation_id"] = candidate
            raise
        finally:
            with (self.output / "wp7br1-server-diagnostics.jsonl").open(
                "a", encoding="utf-8"
            ) as stream:
                stream.write(json.dumps(row) + "\n")


def install(app: FastAPI, token: str, output: Path, engine: Engine) -> None:
    from vayujit_api.core.test_database import assert_safe_test_database

    with engine.connect() as connection:
        assert_safe_test_database(connection, database_url=str(engine.url), environment="test")
    app.add_middleware(DiagnosticMiddleware, output=output, token=token)
