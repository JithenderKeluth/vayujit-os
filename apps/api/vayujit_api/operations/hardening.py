import math
import platform
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from vayujit_api import __version__
from vayujit_api.ai.models import AIProviderConfiguration
from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.core.database import get_session
from vayujit_api.core.observability import maintenance_enabled
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.operations.backup import backup_directory, create_backup, verify_backup
from vayujit_api.operations.models import BackupRecord
from vayujit_api.products.models import Product
from vayujit_api.publishing.models import (
    PublishingExecution,
    WordPressConnectorConfiguration,
)
from vayujit_api.workflows.models import WorkflowInstance

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])
system_router = APIRouter(prefix="/api/v1/system", tags=["system"])
DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(current_user)]


class ComponentHealth(BaseModel):
    component: str
    status: Literal["healthy", "degraded", "unavailable", "unknown"]
    message: str
    checked_at: datetime
    latency_ms: float | None = None


class SystemHealth(BaseModel):
    status: str
    components: list[ComponentHealth]
    current_migration: str
    expected_migration: str
    application_version: str
    build_identifier: str


class ReleaseInfo(BaseModel):
    semantic_version: str
    build_timestamp: str
    git_commit: str
    build_identifier: str
    migration_revision: str
    python_version: str
    api_version: str
    node_version: str
    electron_version: str
    angular_build_version: str


class RecoveryItem(BaseModel):
    id: uuid.UUID
    category: str
    entity_type: str
    product_id: uuid.UUID | None
    product_name: str | None
    brand_id: uuid.UUID
    failure_code: str | None
    safe_failure_message: str
    retryable: bool
    attempt_count: int
    failed_at: datetime
    workflow_id: uuid.UUID | None
    capabilities: list[str]
    related_url: str


class RecoveryPage(BaseModel):
    items: list[RecoveryItem]
    page: int
    page_size: int
    total: int
    pages: int


class BackupResponse(BaseModel):
    id: uuid.UUID
    backup_key: str
    filename: str
    format: str
    size_bytes: int
    checksum_sha256: str
    application_version: str
    migration_revision: str
    database_name: str
    created_at: datetime
    verified_at: datetime | None
    verification_status: str
    status: str
    encryption_status: str = "not_encrypted"


class RestoreCheck(BaseModel):
    backup_id: uuid.UUID
    compatible: bool
    checksum_valid: bool
    target_database: str
    requires_pre_restore_backup: bool = True
    execution_supported: bool = False
    operator_action: str


def revision(db: Session) -> str:
    if not inspect(db.get_bind()).has_table("alembic_version"):
        return "unmanaged-test-schema"
    return str(db.scalar(text("select version_num from alembic_version")) or "unknown")


def health_details(db: Session) -> SystemHealth:
    checked = datetime.now(UTC)
    components: list[ComponentHealth] = []
    try:
        db.execute(text("select 1"))
        database: Literal["healthy", "unavailable"] = "healthy"
        message = "Database connection succeeded."
    except Exception:
        database = "unavailable"
        message = "Database connection failed."
    components.append(
        ComponentHealth(component="Database", status=database, message=message, checked_at=checked)
    )
    current = revision(db) if database == "healthy" else "unknown"
    ai_configuration = db.scalar(
        select(AIProviderConfiguration)
        .where(AIProviderConfiguration.provider_key == "openai_compatible")
        .limit(1)
    )
    ai_status: Literal["healthy", "degraded", "unavailable"] = "healthy"
    ai_message = "Deterministic local mock is registered; real provider is disabled."
    if ai_configuration and ai_configuration.enabled:
        ai_status = (
            "healthy"
            if ai_configuration.validation_status == "valid"
            else (
                "degraded"
                if ai_configuration.fallback_provider_key == "deterministic_mock_v1"
                else "unavailable"
            )
        )
        ai_message = (
            f"Real provider is enabled; validation={ai_configuration.validation_status}; "
            f"credential source is "
            f"{'application' if ai_configuration.encrypted_api_key else 'deployment-or-missing'}; "
            f"fallback={'available' if ai_configuration.fallback_provider_key else 'disabled'}."
        )
    wordpress_configuration = db.scalar(
        select(WordPressConnectorConfiguration)
        .where(WordPressConnectorConfiguration.enabled.is_(True))
        .limit(1)
    )
    wordpress_status: Literal["healthy", "degraded", "unavailable"] = "healthy"
    wordpress_message = "WordPress connector is registered and disabled."
    if wordpress_configuration:
        wordpress_status = (
            "healthy" if wordpress_configuration.validation_status == "valid" else "unavailable"
        )
        wordpress_message = (
            "WordPress connector is enabled; "
            f"validation={wordpress_configuration.validation_status}; "
            "credentials are redacted."
        )
    components.extend(
        [
            ComponentHealth(
                component="Migration",
                status=(
                    "healthy"
                    if current in {"20260731_0011", "unmanaged-test-schema"}
                    else "degraded"
                ),
                message=f"Current {current}; expected 20260731_0011.",
                checked_at=checked,
            ),
            ComponentHealth(
                component="AI provider",
                status=ai_status,
                message=ai_message,
                checked_at=checked,
            ),
            ComponentHealth(
                component="Publishing connector",
                status="healthy",
                message="Local mock connector is registered.",
                checked_at=checked,
            ),
            ComponentHealth(
                component="WordPress connector",
                status=wordpress_status,
                message=wordpress_message,
                checked_at=checked,
            ),
            ComponentHealth(
                component="Audit persistence",
                status=database,
                message="Audit events use PostgreSQL persistence.",
                checked_at=checked,
            ),
            ComponentHealth(
                component="Backup destination",
                status="healthy" if backup_directory().is_dir() else "unavailable",
                message="Configured backup directory is available.",
                checked_at=checked,
            ),
        ]
    )
    overall = "healthy" if all(item.status == "healthy" for item in components) else "degraded"
    return SystemHealth(
        status=overall,
        components=components,
        current_migration=current,
        expected_migration="20260731_0011",
        application_version=__version__,
        build_identifier=get_settings().build_identifier,
    )


@system_router.get("/health", response_model=SystemHealth)
def system_health(db: DatabaseSession, _user: CurrentUser) -> SystemHealth:
    return health_details(db)


@system_router.get("/release", response_model=ReleaseInfo)
def release(db: DatabaseSession, _user: CurrentUser) -> ReleaseInfo:
    settings = get_settings()
    return ReleaseInfo(
        semantic_version=__version__,
        build_timestamp=settings.build_timestamp,
        git_commit=settings.git_commit[:40],
        build_identifier=settings.build_identifier,
        migration_revision=revision(db),
        python_version=platform.python_version(),
        api_version=__version__,
        node_version=settings.node_version,
        electron_version=settings.electron_version,
        angular_build_version=settings.angular_build_version,
    )


@system_router.get("/maintenance")
def maintenance(_user: CurrentUser) -> dict[str, bool]:
    return {"enabled": maintenance_enabled()}


@router.get("/recovery", response_model=RecoveryPage)
def recovery(
    db: DatabaseSession,
    user: CurrentUser,
    category: Literal["workflow", "publishing"] | None = None,
    retryable: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> RecoveryPage:
    items: list[RecoveryItem] = []
    if category in {None, "publishing"}:
        publishing_rows = db.execute(
            select(PublishingExecution, Product)
            .join(Product, Product.id == PublishingExecution.product_id)
            .where(
                PublishingExecution.owner_id == user.id,
                PublishingExecution.status == "failed",
            )
        ).all()
        for execution, product in publishing_rows:
            items.append(
                RecoveryItem(
                    id=execution.id,
                    category="publishing",
                    entity_type="publishing_execution",
                    product_id=product.id,
                    product_name=product.name,
                    brand_id=execution.brand_id,
                    failure_code=execution.error_code,
                    safe_failure_message=execution.safe_error_message or "Publishing failed.",
                    retryable=execution.retryable,
                    attempt_count=execution.attempt_count,
                    failed_at=execution.failed_at or execution.updated_at,
                    workflow_id=None,
                    capabilities=(
                        (["retry_publishing"] if execution.retryable else [])
                        + (
                            ["reconcile_publishing"]
                            if execution.connector_key == "wordpress"
                            and (
                                execution.remote_entity_id
                                or execution.reconciliation_status == "reconciliation_required"
                            )
                            else []
                        )
                        + (
                            ["move_to_draft"]
                            if execution.connector_key == "wordpress" and execution.remote_entity_id
                            else []
                        )
                    ),
                    related_url=f"/publishing/executions/{execution.id}",
                )
            )
    if category in {None, "workflow"}:
        workflow_rows = db.execute(
            select(WorkflowInstance, Product)
            .join(Product, Product.id == WorkflowInstance.product_id)
            .where(WorkflowInstance.owner_id == user.id, WorkflowInstance.status == "failed")
        ).all()
        for workflow, product in workflow_rows:
            is_retryable = workflow.error_code not in {"artifact_rejected"}
            items.append(
                RecoveryItem(
                    id=workflow.id,
                    category="workflow",
                    entity_type="workflow_instance",
                    product_id=product.id,
                    product_name=product.name,
                    brand_id=workflow.brand_id,
                    failure_code=workflow.error_code,
                    safe_failure_message=workflow.safe_error_message or "Workflow failed.",
                    retryable=is_retryable,
                    attempt_count=workflow.retry_count,
                    failed_at=workflow.failed_at or workflow.updated_at,
                    workflow_id=workflow.id,
                    capabilities=["retry_workflow"] if is_retryable else [],
                    related_url=f"/workflows/{workflow.id}",
                )
            )
    if retryable is not None:
        items = [item for item in items if item.retryable is retryable]
    items.sort(key=lambda item: item.failed_at, reverse=True)
    total = len(items)
    start = (page - 1) * page_size
    return RecoveryPage(
        items=items[start : start + page_size],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


def owned_backup(db: Session, owner_id: uuid.UUID, identifier: uuid.UUID) -> BackupRecord:
    value = db.scalar(
        select(BackupRecord).where(BackupRecord.id == identifier, BackupRecord.owner_id == owner_id)
    )
    if value is None:
        raise HTTPException(404, "Backup was not found.")
    return value


@router.get("/backups", response_model=list[BackupResponse])
def backups(db: DatabaseSession, user: CurrentUser) -> list[BackupRecord]:
    return list(
        db.scalars(
            select(BackupRecord)
            .where(BackupRecord.owner_id == user.id)
            .order_by(BackupRecord.created_at.desc())
            .limit(100)
        )
    )


@router.post("/backups", response_model=BackupResponse)
def create(db: DatabaseSession, user: CurrentUser) -> BackupRecord:
    try:
        value = create_backup(db, user.id)
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from None
    record_event(
        db,
        actor_id=user.id,
        action="operations.backup_created",
        entity_type="backup",
        entity_id=value.id,
        metadata={"backup_key": value.backup_key, "size_bytes": value.size_bytes},
    )
    db.commit()
    db.refresh(value)
    return value


@router.get("/backups/{backup_id}", response_model=BackupResponse)
def backup(backup_id: uuid.UUID, db: DatabaseSession, user: CurrentUser) -> BackupRecord:
    return owned_backup(db, user.id, backup_id)


@router.post("/backups/{backup_id}/verify", response_model=BackupResponse)
def verify(backup_id: uuid.UUID, db: DatabaseSession, user: CurrentUser) -> BackupRecord:
    value = owned_backup(db, user.id, backup_id)
    verify_backup(value)
    record_event(
        db,
        actor_id=user.id,
        action="operations.backup_verified",
        entity_type="backup",
        entity_id=value.id,
        metadata={"verification_status": value.verification_status},
    )
    db.commit()
    db.refresh(value)
    return value


@router.post("/backups/{backup_id}/restore-check", response_model=RestoreCheck)
def restore_check(
    backup_id: uuid.UUID, db: DatabaseSession, user: CurrentUser, response: Response
) -> RestoreCheck:
    value = owned_backup(db, user.id, backup_id)
    checksum_valid = verify_backup(value)
    compatible = checksum_valid and value.migration_revision == revision(db)
    db.commit()
    if not compatible:
        response.status_code = 409
    return RestoreCheck(
        backup_id=value.id,
        compatible=compatible,
        checksum_valid=checksum_valid,
        target_database=value.database_name,
        operator_action=(
            "Create a fresh pre-restore backup, enable maintenance mode, and run the documented "
            "operator restore against a disposable restore-test database."
        ),
    )
