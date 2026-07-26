from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vayujit_api import __version__
from vayujit_api.core.config import get_settings
from vayujit_api.core.errors import install_exception_handlers
from vayujit_api.core.logging import configure_logging
from vayujit_api.core.schemas import HealthResponse


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(title="VAYUJIT OS API", version=__version__)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
    )
    install_exception_handlers(application)

    @application.get("/health", response_model=HealthResponse, tags=["health"])
    @application.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="vayujit-api",
            version=__version__,
            environment=settings.environment,
        )

    return application


app = create_app()
