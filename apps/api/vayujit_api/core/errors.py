from typing import Any
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger()


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, error: Exception) -> JSONResponse:
        correlation_id = request.headers.get("x-correlation-id", str(uuid4()))
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
                "code": "internal_error",
                "message": "An unexpected error occurred.",
                "correlation_id": correlation_id,
            },
        )


def error_openapi_example() -> dict[str, Any]:
    return {"code": "internal_error", "message": "An unexpected error occurred."}
