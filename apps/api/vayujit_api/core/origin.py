from urllib.parse import urlsplit

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from vayujit_api.core.config import get_settings

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class OriginProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in UNSAFE_METHODS:
            return await call_next(request)

        settings = get_settings()
        origin = request.headers.get("origin")
        if origin is None:
            if settings.allow_missing_origin:
                return await call_next(request)
            return JSONResponse(status_code=403, content={"detail": "Request origin is required."})

        try:
            parsed = urlsplit(origin)
            valid = bool(parsed.scheme and parsed.netloc) and origin in settings.allowed_origin_set
        except ValueError:
            valid = False

        if not valid:
            return JSONResponse(
                status_code=403, content={"detail": "Request origin is not allowed."}
            )
        return await call_next(request)
