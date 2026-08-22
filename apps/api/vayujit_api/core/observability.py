import re
import time
import uuid
from collections import defaultdict, deque
from contextvars import ContextVar
from pathlib import Path
from threading import Lock

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from vayujit_api.core.config import get_settings

CORRELATION_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
correlation_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)
logger = structlog.get_logger()
_metrics: defaultdict[str, int] = defaultdict(int)
_rate_windows: dict[tuple[str, str], deque[float]] = {}
_rate_lock = Lock()


def correlation_id() -> str | None:
    return correlation_context.get()


def metrics_snapshot() -> dict[str, int]:
    return dict(_metrics)


def maintenance_marker() -> Path:
    configured = Path(get_settings().maintenance_marker)
    path = configured if configured.is_absolute() else Path.cwd() / configured
    return path.resolve()


def maintenance_enabled() -> bool:
    return maintenance_marker().is_file()


class OperationalMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-correlation-id", "")
        value = incoming if CORRELATION_PATTERN.fullmatch(incoming) else str(uuid.uuid4())
        token = correlation_context.set(value)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=value,
            request_id=str(uuid.uuid4()),
            service="vayujit-api",
            environment=get_settings().environment,
        )
        request.state.correlation_id = value
        started = time.perf_counter()
        route = request.url.path
        _metrics["http_requests_total"] += 1
        logger.info(
            "request.started", message="Request started.", method=request.method, route=route
        )
        try:
            if self._blocked(request):
                response: Response = JSONResponse(
                    status_code=503,
                    content={
                        "code": "maintenance_mode",
                        "message": "The application is temporarily in maintenance mode.",
                        "correlation_id": value,
                        "retryable": True,
                    },
                )
            else:
                response = await call_next(request)
            matched = request.scope.get("route")
            route = getattr(matched, "path", route)
            response.headers["X-Correlation-ID"] = value
            response.headers["X-Request-ID"] = structlog.contextvars.get_contextvars().get(
                "request_id", ""
            )
            _metrics[f"http_status_{response.status_code}"] += 1
            logger.info(
                "request.completed",
                message="Request completed.",
                method=request.method,
                route=route,
                status_code=response.status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            return response
        except Exception:
            _metrics["http_errors_total"] += 1
            logger.exception(
                "request.failed",
                message="Request failed.",
                method=request.method,
                route=route,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise
        finally:
            structlog.contextvars.clear_contextvars()
            correlation_context.reset(token)

    @staticmethod
    def _blocked(request: Request) -> bool:
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"} or not maintenance_enabled():
            return False
        path = request.url.path
        return not (
            path.startswith("/health")
            or path.startswith("/api/v1/system")
            or path.startswith("/api/v1/operations/backups")
            or path.endswith("/logout")
        )


class SafetyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        if settings.environment == "test":
            return await call_next(request)
        content_length = request.headers.get("content-length")
        if (
            content_length
            and content_length.isdigit()
            and int(content_length) > settings.request_max_body_bytes
        ):
            return JSONResponse(
                status_code=413,
                content={
                    "code": "request_too_large",
                    "message": "Request body exceeds the configured limit.",
                    "retryable": False,
                },
            )
        key = (request.client.host if request.client else "unknown", self._bucket(request))
        limit = settings.request_rate_limit_per_minute
        if request.url.path.startswith("/api/v1/auth"):
            limit = settings.auth_rate_limit_per_minute
        elif request.url.path.startswith("/api/v1/ai"):
            limit = settings.ai_rate_limit_per_minute
        elif request.url.path.startswith("/api/v1/media"):
            limit = settings.upload_rate_limit_per_minute
        now = time.monotonic()
        with _rate_lock:
            window = _rate_windows.setdefault(key, deque())
            while window and window[0] <= now - 60:
                window.popleft()
            if len(window) >= limit:
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": "60"},
                    content={
                        "code": "rate_limited",
                        "message": "Too many requests; retry later.",
                        "retryable": True,
                    },
                )
            window.append(now)
        response = await call_next(request)
        return response

    @staticmethod
    def _bucket(request: Request) -> str:
        return request.url.path.split("/", 4)[0:4].__repr__()
