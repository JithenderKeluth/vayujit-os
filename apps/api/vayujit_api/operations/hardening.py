import math
import os
import platform
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from vayujit_api import __version__
from vayujit_api.ai.models import AIProviderConfiguration
from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.campaigns.models import Campaign, CampaignActivity
from vayujit_api.core.config import get_settings
from vayujit_api.core.database import get_session
from vayujit_api.core.observability import maintenance_enabled
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.media.service import storage_root
from vayujit_api.operations.backup import backup_directory, create_backup, verify_backup
from vayujit_api.operations.models import BackupRecord
from vayujit_api.products.models import Product
from vayujit_api.publishing.models import (
    PublishingExecution,
    PublishingExecutionAttempt,
    PublishingJob,
    ShopifyConnectorConfiguration,
    ShopifyMediaMapping,
    ShopifyMediaPollAttempt,
    ShopifyProductAssignment,
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
    brand_id: uuid.UUID | None
    failure_code: str | None
    safe_failure_message: str
    retryable: bool
    attempt_count: int
    failed_at: datetime
    workflow_id: uuid.UUID | None
    capabilities: list[str]
    related_url: str
    schedule_id: uuid.UUID | None = None
    job_state: str | None = None
    connector: str | None = None
    destination_id: uuid.UUID | None = None
    artifact_id: uuid.UUID | None = None
    artifact_version: int | None = None
    scheduled_at: datetime | None = None
    available_at: datetime | None = None
    lease_owner: str | None = None
    lease_expiry: datetime | None = None
    next_retry: datetime | None = None
    correlation_id: str | None = None
    campaign_id: uuid.UUID | None = None
    campaign_name: str | None = None
    activity_id: uuid.UUID | None = None
    activity_name: str | None = None


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
    shopify_configuration = db.scalar(
        select(ShopifyConnectorConfiguration)
        .where(ShopifyConnectorConfiguration.enabled.is_(True))
        .limit(1)
    )
    shopify_status: Literal["healthy", "degraded", "unavailable"] = "healthy"
    shopify_message = "Shopify connector is registered and disabled."
    if shopify_configuration:
        window_start = checked - timedelta(hours=24)
        recent_count, recent_success, recent_failure = db.execute(
            select(
                func.count(PublishingExecution.id),
                func.count(PublishingExecution.id).filter(
                    PublishingExecution.status == "succeeded"
                ),
                func.count(PublishingExecution.id).filter(
                    PublishingExecution.status.in_(["failed", "degraded"])
                ),
            ).where(
                PublishingExecution.connector_key == "shopify",
                PublishingExecution.created_at >= window_start,
            )
        ).one()
        recent_latencies = list(
            db.scalars(
                select(PublishingExecutionAttempt.latency_ms)
                .join(
                    PublishingExecution,
                    PublishingExecution.id == PublishingExecutionAttempt.execution_id,
                )
                .where(
                    PublishingExecution.connector_key == "shopify",
                    PublishingExecutionAttempt.created_at >= window_start,
                    PublishingExecutionAttempt.latency_ms.is_not(None),
                )
                .order_by(PublishingExecutionAttempt.latency_ms)
                .limit(200)
            )
        )
        median_latency = recent_latencies[len(recent_latencies) // 2] if recent_latencies else None
        throttle_count = (
            db.scalar(
                select(func.count(PublishingExecutionAttempt.id))
                .join(
                    PublishingExecution,
                    PublishingExecution.id == PublishingExecutionAttempt.execution_id,
                )
                .where(
                    PublishingExecution.connector_key == "shopify",
                    PublishingExecutionAttempt.created_at >= window_start,
                    PublishingExecutionAttempt.error_code == "shopify_throttled",
                )
            )
            or 0
        )
        media_processing, media_timeout, stale_media, failed_media = db.execute(
            select(
                func.count(ShopifyMediaMapping.id).filter(
                    ShopifyMediaMapping.status.in_(["uploaded", "processing"])
                ),
                func.count(ShopifyMediaMapping.id).filter(
                    ShopifyMediaMapping.status == "timed_out"
                ),
                func.count(ShopifyMediaMapping.id).filter(
                    ShopifyMediaMapping.reuse_state == "stale"
                ),
                func.count(ShopifyMediaMapping.id).filter(ShopifyMediaMapping.status == "failed"),
            ).where(ShopifyMediaMapping.updated_at >= window_start)
        ).one()
        assignment_failures: dict[str, int] = {
            assignment_type: int(total)
            for assignment_type, total in db.execute(
                select(
                    ShopifyProductAssignment.assignment_type,
                    func.count(ShopifyProductAssignment.id),
                )
                .where(
                    ShopifyProductAssignment.updated_at >= window_start,
                    ShopifyProductAssignment.status.in_(["assignment_failed", "removal_failed"]),
                )
                .group_by(ShopifyProductAssignment.assignment_type)
            ).all()
        }
        polling_latencies = list(
            db.scalars(
                select(ShopifyMediaPollAttempt.latency_ms)
                .where(ShopifyMediaPollAttempt.created_at >= window_start)
                .order_by(ShopifyMediaPollAttempt.latency_ms)
                .limit(200)
            )
        )
        median_polling_latency = (
            polling_latencies[len(polling_latencies) // 2] if polling_latencies else None
        )
        partial_products = (
            db.scalar(
                select(func.count(PublishingExecution.id)).where(
                    PublishingExecution.connector_key == "shopify",
                    PublishingExecution.reconciliation_status == "partially_published",
                    PublishingExecution.updated_at >= window_start,
                )
            )
            or 0
        )
        success_rate = (
            round(int(recent_success) * 100 / int(recent_count), 1) if recent_count else 100.0
        )
        shopify_status = (
            "healthy" if shopify_configuration.validation_status == "valid" else "degraded"
        )
        shopify_message = (
            "Shopify connector is enabled; "
            f"validation={shopify_configuration.validation_status}; "
            f"shop={shopify_configuration.shop_domain}; "
            f"api_version={shopify_configuration.api_version}; credentials are redacted."
            f" recent_24h={recent_count}; successes={recent_success}; failures={recent_failure};"
            f" success_rate={success_rate}%; median_latency_ms={median_latency};"
            f" throttles={throttle_count}; media_processing={media_processing};"
            f" media_timeouts={media_timeout}; stale_mappings={stale_media};"
            f" failed_media={failed_media};"
            f" collection_failures={assignment_failures.get('collection', 0)};"
            f" publication_failures={assignment_failures.get('publication', 0)};"
            f" partially_published={partial_products};"
            f" median_polling_latency_ms={median_polling_latency}."
        )
    try:
        media_root = storage_root()
        media_writable = os.access(media_root, os.W_OK)
        free_bytes = shutil.disk_usage(media_root).free
        media_status: Literal["healthy", "degraded", "unavailable"] = (
            "healthy"
            if media_writable and free_bytes >= get_settings().media_min_free_bytes
            else ("degraded" if media_writable else "unavailable")
        )
        media_message = (
            "Media storage is writable; "
            "free-space threshold="
            f"{'met' if free_bytes >= get_settings().media_min_free_bytes else 'low'}."
        )
    except OSError:
        media_status = "unavailable"
        media_message = "Media storage is unavailable."
    components.extend(
        [
            ComponentHealth(
                component="Migration",
                status=(
                    "healthy"
                    if current in {"20260808_0019", "unmanaged-test-schema"}
                    else "degraded"
                ),
                message=f"Current {current}; expected 20260808_0019.",
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
                component="Media storage",
                status=media_status,
                message=media_message,
                checked_at=checked,
            ),
            ComponentHealth(
                component="WordPress taxonomy",
                status=wordpress_status,
                message=(
                    "Category, tag, author, and media capabilities are available after validation."
                    if wordpress_configuration
                    else "Remote taxonomy and media checks are inactive."
                ),
                checked_at=checked,
            ),
            ComponentHealth(
                component="Shopify connector",
                status=shopify_status,
                message=shopify_message,
                checked_at=checked,
            ),
            ComponentHealth(
                component="Shopify discovery",
                status=shopify_status,
                message=(
                    "Collection and publication capabilities are available after validation; "
                    "inventory quantity writes remain disabled."
                    if shopify_configuration
                    else "Remote Shopify discovery checks are inactive."
                ),
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
        expected_migration="20260808_0019",
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
    category: Literal["workflow", "publishing", "media", "campaign"] | None = None,
    retryable: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> RecoveryPage:
    items: list[RecoveryItem] = []
    if category in {None, "campaign"}:
        campaign_rows = db.execute(
            select(CampaignActivity, Campaign, Product)
            .join(Campaign, Campaign.id == CampaignActivity.campaign_id)
            .outerjoin(Product, Product.id == CampaignActivity.product_id)
            .where(
                CampaignActivity.owner_id == user.id,
                CampaignActivity.status.in_(
                    [
                        "blocked",
                        "failed",
                        "dead_letter",
                        "maintenance_blocked",
                        "reconciliation_required",
                    ]
                ),
            )
            .order_by(CampaignActivity.updated_at.desc())
            .limit(100)
        ).all()
        for activity, campaign, product in campaign_rows:
            campaign_capabilities = ["open_campaign", "review_readiness", "review_dependency"]
            if activity.status in {"failed", "dead_letter"}:
                campaign_capabilities.extend(["retry_activity", "reconcile_activity"])
            if not activity.required:
                campaign_capabilities.append("skip_optional_activity")
            items.append(
                RecoveryItem(
                    id=activity.id,
                    category="campaign",
                    entity_type="campaign_activity",
                    product_id=activity.product_id,
                    product_name=product.name if product else None,
                    brand_id=campaign.brand_id,
                    failure_code=activity.failure_code or activity.readiness_status,
                    safe_failure_message=activity.safe_failure_message
                    or "Campaign activity needs review.",
                    retryable=activity.status in {"failed", "dead_letter"},
                    attempt_count=0,
                    failed_at=activity.updated_at,
                    workflow_id=activity.workflow_instance_id,
                    capabilities=campaign_capabilities,
                    related_url=f"/campaigns/{campaign.id}",
                    schedule_id=activity.schedule_id,
                    job_state=activity.status,
                    connector=activity.connector_key,
                    destination_id=activity.destination_id,
                    artifact_id=activity.artifact_id,
                    artifact_version=activity.artifact_version,
                    scheduled_at=activity.scheduled_at_utc,
                    correlation_id=activity.correlation_id,
                    campaign_id=campaign.id,
                    campaign_name=campaign.name,
                    activity_id=activity.id,
                    activity_name=activity.name,
                )
            )
    if category in {None, "media"}:
        media_events = db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.actor_id == user.id,
                AuditEvent.action.in_(["media.upload_failed", "publishing.taxonomy_lookup_failed"]),
            )
            .order_by(AuditEvent.occurred_at.desc())
            .limit(100)
        ).all()
        for event in media_events:
            taxonomy = event.action == "publishing.taxonomy_lookup_failed"
            items.append(
                RecoveryItem(
                    id=event.id,
                    category="media",
                    entity_type=event.entity_type,
                    product_id=None,
                    product_name=None,
                    brand_id=None,
                    failure_code=str(event.metadata_json.get("code") or "media_failure"),
                    safe_failure_message=(
                        "WordPress taxonomy lookup failed."
                        if taxonomy
                        else "Local media validation failed."
                    ),
                    retryable=True,
                    attempt_count=1,
                    failed_at=event.occurred_at,
                    workflow_id=None,
                    capabilities=(
                        ["refresh_taxonomy", "open_destination"]
                        if taxonomy
                        else ["retry_media_upload", "select_another_media"]
                    ),
                    related_url=(
                        "/settings/publishing/connectors/wordpress" if taxonomy else "/media/upload"
                    ),
                )
            )
    if category in {None, "publishing"}:
        scheduler_rows = db.execute(
            select(PublishingJob, Product)
            .join(Product, Product.id == PublishingJob.product_id)
            .where(
                PublishingJob.owner_id == user.id,
                PublishingJob.state.in_(
                    [
                        "retry_wait",
                        "failed",
                        "dead_letter",
                        "cancel_requested",
                        "claimed",
                        "running",
                    ]
                ),
            )
        ).all()
        current = datetime.now(UTC)
        for job, product in scheduler_rows:
            expired = bool(job.lease_expires_at and job.lease_expires_at < current)
            capabilities: list[str] = ["open_schedule"] if job.schedule_id else []
            if job.state in {"failed", "dead_letter"} and job.retryable:
                capabilities.append("retry_job")
            if expired:
                capabilities.append("recover_expired_lease")
            if job.publishing_execution_id or job.recovery_state == "manual_review":
                capabilities.append("reconcile_remote_execution")
            if job.state not in {"succeeded", "failed", "dead_letter", "cancelled", "expired"}:
                capabilities.append("cancel_job")
            state_message = {
                "retry_wait": "Waiting for retry.",
                "dead_letter": "Job exhausted its bounded attempts.",
                "cancel_requested": "Cancellation requested.",
            }.get(
                job.state,
                job.recovery_reason or job.last_error_message or "Publishing job needs review.",
            )
            items.append(
                RecoveryItem(
                    id=job.id,
                    category="publishing",
                    entity_type="publishing_job",
                    product_id=product.id,
                    product_name=product.name,
                    brand_id=product.brand_id,
                    failure_code=job.last_error_code or job.recovery_state,
                    safe_failure_message=state_message,
                    retryable=job.retryable,
                    attempt_count=job.execution_attempt_count,
                    failed_at=job.completed_at or job.updated_at,
                    workflow_id=job.workflow_instance_id,
                    capabilities=capabilities,
                    related_url=f"/publishing/jobs/{job.id}",
                    schedule_id=job.schedule_id,
                    job_state=job.state,
                    connector=job.connector_key,
                    destination_id=job.destination_id,
                    artifact_id=job.artifact_id,
                    artifact_version=job.artifact_version,
                    scheduled_at=job.scheduled_at_utc,
                    available_at=job.available_at_utc,
                    lease_owner=job.lease_owner,
                    lease_expiry=job.lease_expires_at,
                    next_retry=job.next_retry_at,
                    correlation_id=job.correlation_id,
                )
            )
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
                            if execution.connector_key in {"wordpress", "shopify"}
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
                        + (
                            (
                                ["review_drift", "keep_remote_changes"]
                                if execution.reconciliation_status == "changed_remotely"
                                else []
                            )
                            + (
                                [
                                    "poll_media_again",
                                    "verify_remote_media",
                                    "retry_media_upload",
                                    "continue_without_media",
                                    "preserve_degraded_draft",
                                ]
                                if execution.error_code and "media" in execution.error_code
                                else []
                            )
                            + (
                                ["retry_variant_mutation"]
                                if execution.error_code and "variant" in execution.error_code
                                else []
                            )
                            + (
                                [
                                    "retry_publication_assignment",
                                    "restore_required_publication",
                                    "reconcile_partial_publication",
                                    "retry_activation_after_publication_repair",
                                ]
                                if execution.error_code and "publication" in execution.error_code
                                else []
                            )
                            + (
                                ["activate_product"]
                                if execution.remote_entity_id and execution.remote_status == "draft"
                                else []
                            )
                            + (
                                ["archive_product"]
                                if execution.remote_entity_id
                                and execution.remote_status not in {"archived", None}
                                else []
                            )
                            + ["open_shopify_admin", "open_destination"]
                            if execution.connector_key == "shopify"
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
