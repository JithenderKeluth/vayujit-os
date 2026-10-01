from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from vayujit_api.core.config import get_settings

logger = structlog.get_logger()


def _error_response(request: Request, status_code: int, content: dict[str, object]) -> JSONResponse:
    response = JSONResponse(status_code=status_code, content=content)
    origin = request.headers.get("origin")
    if origin and origin in get_settings().allowed_origin_set:
        response.headers["access-control-allow-origin"] = origin
        response.headers["access-control-allow-credentials"] = "true"
        response.headers["vary"] = "Origin"
    return response


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        details = [
            {key: value for key, value in item.items() if key not in {"input", "ctx"}}
            for item in error.errors()
        ]
        return _error_response(request, 422, {"detail": details})

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, error: Exception) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        logger.exception(
            "unhandled_exception",
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            error_type=type(error).__name__,
        )
        return _error_response(
            request,
            500,
            {
                "error_code": "internal_error",
                "message": "An unexpected error occurred.",
                "correlation_id": correlation_id,
                "retryable": False,
            },
        )


def error_openapi_example() -> dict[str, Any]:
    return {"code": "internal_error", "message": "An unexpected error occurred."}
