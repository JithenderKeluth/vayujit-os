from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger()


def install_exception_handlers(app: FastAPI) -> None:
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
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "internal_error",
                "message": "An unexpected error occurred.",
                "correlation_id": correlation_id,
                "retryable": False,
            },
        )


def error_openapi_example() -> dict[str, Any]:
    return {"code": "internal_error", "message": "An unexpected error occurred."}
