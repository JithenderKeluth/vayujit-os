from typing import Annotated

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from vayujit_api import __version__
from vayujit_api.ai.router import router as ai_router
from vayujit_api.brands.router import router as brands_router
from vayujit_api.campaigns.router import router as campaigns_router
from vayujit_api.campaigns.workflow_service import restore_campaign_waits
from vayujit_api.commerce.amazon_router import router as amazon_router
from vayujit_api.commerce.flipkart_router import router as flipkart_router
from vayujit_api.commerce.meesho_router import router as meesho_router
from vayujit_api.commerce.router import router as commerce_router
from vayujit_api.core.config import get_settings
from vayujit_api.core.database import SessionFactory, get_session
from vayujit_api.core.errors import install_exception_handlers
from vayujit_api.core.logging import configure_logging
from vayujit_api.core.observability import OperationalMiddleware
from vayujit_api.core.origin import OriginProtectionMiddleware
from vayujit_api.core.schemas import HealthResponse
from vayujit_api.identity.router import router as auth_router
from vayujit_api.media.router import router as media_router
from vayujit_api.operations.hardening import health_details
from vayujit_api.operations.hardening import router as hardening_router
from vayujit_api.operations.hardening import system_router as hardening_system_router
from vayujit_api.operations.router import (
    approval_router,
    dashboard_router,
    operations_router,
)
from vayujit_api.products.router import router as products_router
from vayujit_api.publishing.router import router as publishing_router
from vayujit_api.publishing.scheduler_router import operations_router as scheduler_operations_router
from vayujit_api.publishing.scheduler_router import router as scheduler_router
from vayujit_api.settings.router import router as settings_router
from vayujit_api.settings.router import system_router
from vayujit_api.workflows.router import router as workflows_router

DatabaseSession = Annotated[Session, Depends(get_session)]


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(title="VAYUJIT OS API", version=__version__)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(settings.allowed_origin_set),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
    )
    application.add_middleware(OriginProtectionMiddleware)
    application.add_middleware(OperationalMiddleware)
    install_exception_handlers(application)
    application.include_router(auth_router)
    application.include_router(brands_router)
    application.include_router(campaigns_router)
    application.include_router(commerce_router)
    application.include_router(amazon_router)
    application.include_router(flipkart_router)
    application.include_router(meesho_router)
    application.include_router(products_router)
    application.include_router(ai_router)
    application.include_router(media_router)
    application.include_router(publishing_router)
    application.include_router(scheduler_router)
    application.include_router(scheduler_operations_router)
    application.include_router(workflows_router)
    application.include_router(dashboard_router)
    application.include_router(approval_router)
    application.include_router(operations_router)
    application.include_router(hardening_router)
    application.include_router(settings_router)
    application.include_router(system_router)
    application.include_router(hardening_system_router)

    @application.on_event("startup")
    def restore_durable_campaign_waits() -> None:
        with SessionFactory() as db:
            restore_campaign_waits(db)

    @application.get("/health", response_model=HealthResponse, tags=["health"])
    @application.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="vayujit-api",
            version=__version__,
            environment=settings.environment,
        )

    @application.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "alive", "service": "vayujit-api"}

    @application.get("/health/ready", tags=["health"])
    def ready(response: Response, db: DatabaseSession) -> dict[str, object]:
        details = health_details(db)
        essential_failure = any(
            component.status == "unavailable"
            and (
                component.component in {"Database", "Migration"}
                or (component.component == "AI provider" and settings.ai_real_provider_required)
                or (component.component == "WordPress connector" and settings.wordpress_required)
            )
            for component in details.components
        )
        if essential_failure:
            response.status_code = 503
        return details.model_dump(mode="json")

    return application


app = create_app()
