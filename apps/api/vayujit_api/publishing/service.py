import re
import uuid
from typing import Literal, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand, BrandStatus
from vayujit_api.core.observability import correlation_id
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.products.models import Product, ProductStatus
from vayujit_api.publishing.connector import (
    ConnectorFailure,
    PublishingConnector,
    WordPressConnector,
    connector,
)
from vayujit_api.publishing.models import (
    PublishingDestination,
    PublishingExecution,
    PublishingExecutionAttempt,
)
from vayujit_api.publishing.schemas import (
    AttemptResponse,
    CreateExecution,
    DestinationResponse,
    DestinationUpdate,
    DestinationWrite,
    ExecutionResponse,
    MockConfiguration,
    ReconciliationResponse,
    WordPressDestinationConfiguration,
)
from vayujit_api.publishing.wordpress import connector_for, owned_configuration


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def destination_response(db: Session, value: PublishingDestination) -> DestinationResponse:
    brand = db.get(Brand, value.brand_id) if value.brand_id else None
    configuration_type = (
        WordPressDestinationConfiguration
        if value.connector_key == "wordpress"
        else MockConfiguration
    )
    return DestinationResponse(
        id=value.id,
        brand_id=value.brand_id,
        brand_name=brand.name if brand else None,
        connector_key=value.connector_key,
        name=value.name,
        status=cast(Literal["active", "disabled"], value.status),
        configuration=configuration_type.model_validate(value.configuration_json),
        created_at=value.created_at,
        updated_at=value.updated_at,
        disabled_at=value.disabled_at,
    )


def validate_brand(db: Session, owner_id: uuid.UUID, brand_id: uuid.UUID | None) -> None:
    if not brand_id:
        return
    brand = db.scalar(select(Brand).where(Brand.id == brand_id, Brand.owner_id == owner_id))
    if not brand:
        raise HTTPException(404, "Brand not found.")
    if brand.status == BrandStatus.ARCHIVED.value:
        raise HTTPException(
            409,
            {"code": "brand_archived", "message": "Archived brands cannot receive destinations."},
        )


def create_destination(db: Session, owner: User, data: DestinationWrite) -> DestinationResponse:
    validate_brand(db, owner.id, data.brand_id)
    stamp = now()
    value = PublishingDestination(
        owner_id=owner.id,
        brand_id=data.brand_id,
        connector_key=data.connector_key,
        name=data.name,
        normalized_name=normalize(data.name),
        status="active",
        configuration_json=data.configuration.model_dump(mode="json"),
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A destination with this name already exists.") from None
    record_event(
        db,
        actor_id=owner.id,
        action="publishing.destination_created",
        entity_type="publishing_destination",
        entity_id=value.id,
        metadata={
            "brand_id": str(value.brand_id) if value.brand_id else None,
            "connector_key": value.connector_key,
        },
    )
    db.commit()
    return destination_response(db, value)


def owned_destination(
    db: Session, owner_id: uuid.UUID, destination_id: uuid.UUID
) -> PublishingDestination:
    value = db.scalar(
        select(PublishingDestination).where(
            PublishingDestination.id == destination_id, PublishingDestination.owner_id == owner_id
        )
    )
    if not value:
        raise HTTPException(404, "Publishing destination not found.")
    return value


def update_destination(
    db: Session, owner: User, value: PublishingDestination, data: DestinationUpdate
) -> DestinationResponse:
    changes = data.model_dump(exclude_unset=True)
    if "brand_id" in changes:
        validate_brand(db, owner.id, data.brand_id)
        value.brand_id = data.brand_id
    if data.name is not None:
        value.name, value.normalized_name = data.name, normalize(data.name)
    if data.configuration is not None:
        expected = (
            WordPressDestinationConfiguration
            if value.connector_key == "wordpress"
            else MockConfiguration
        )
        if not isinstance(data.configuration, expected):
            raise HTTPException(422, "Destination configuration does not match its connector.")
        value.configuration_json = data.configuration.model_dump(mode="json")
    value.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action="publishing.destination_updated",
        entity_type="publishing_destination",
        entity_id=value.id,
        metadata={"changed_fields": sorted(changes)},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A destination with this name already exists.") from None
    return destination_response(db, value)


def set_destination_status(
    db: Session, owner: User, value: PublishingDestination, status: str
) -> DestinationResponse:
    if value.status == status:
        return destination_response(db, value)
    value.status, value.updated_at = status, now()
    value.disabled_at = value.updated_at if status == "disabled" else None
    record_event(
        db,
        actor_id=owner.id,
        action=f"publishing.destination_{'disabled' if status == 'disabled' else 'enabled'}",
        entity_type="publishing_destination",
        entity_id=value.id,
        metadata={"status": status},
    )
    db.commit()
    return destination_response(db, value)


def execution_response(db: Session, value: PublishingExecution) -> ExecutionResponse:
    attempts = db.scalars(
        select(PublishingExecutionAttempt)
        .where(PublishingExecutionAttempt.execution_id == value.id)
        .order_by(PublishingExecutionAttempt.attempt_number)
    ).all()
    return ExecutionResponse(
        id=value.id,
        artifact_id=value.artifact_id,
        destination_id=value.destination_id,
        brand_id=value.brand_id,
        product_id=value.product_id,
        connector_key=value.connector_key,
        status=value.status,
        idempotency_key=value.idempotency_key,
        attempt_count=value.attempt_count,
        content_snapshot=value.content_snapshot_json,
        request_snapshot=value.request_snapshot_json,
        result=value.result_json,
        external_reference=value.external_reference,
        external_url=value.external_url,
        error_code=value.error_code,
        safe_error_message=value.safe_error_message,
        retryable=value.retryable,
        created_at=value.created_at,
        started_at=value.started_at,
        completed_at=value.completed_at,
        failed_at=value.failed_at,
        attempts=[
            AttemptResponse(
                attempt_number=a.attempt_number,
                status=a.status,
                result=a.result_json,
                error_code=a.error_code,
                safe_error_message=a.safe_error_message,
                retryable=a.retryable,
                started_at=a.started_at,
                completed_at=a.completed_at,
                failed_at=a.failed_at,
                operation=a.operation,
                latency_ms=a.latency_ms,
                response_status=a.response_status,
                retry_after_seconds=a.retry_after_seconds,
                ambiguous_result=a.ambiguous_result,
                correlation_id=a.correlation_id,
            )
            for a in attempts
        ],
        requested_action=value.requested_action,
        remote_entity_id=value.remote_entity_id,
        remote_status=value.remote_status,
        remote_slug=value.remote_slug,
        remote_edit_url=value.remote_edit_url,
        reconciliation_status=value.reconciliation_status,
        last_reconciled_at=value.last_reconciled_at,
        correlation_id=value.correlation_id,
        cancellation_requested_at=value.cancellation_requested_at,
        cancelled_at=value.cancelled_at,
    )


def execution_connector(
    db: Session, owner: User, destination: PublishingDestination
) -> tuple[PublishingConnector, int]:
    if destination.connector_key == connector.key:
        return connector, 1
    if destination.connector_key != "wordpress":
        raise HTTPException(409, "Publishing connector is unsupported.")
    configuration = owned_configuration(db, owner.id)
    if not configuration or not configuration.enabled:
        raise HTTPException(
            409,
            {
                "code": "wordpress_not_enabled",
                "message": "Configure, validate, and enable WordPress before publishing.",
            },
        )
    if configuration.validation_status != "valid":
        raise HTTPException(
            409,
            {
                "code": "wordpress_not_validated",
                "message": "Validate the WordPress connection before publishing.",
            },
        )
    try:
        return connector_for(configuration), configuration.max_retry_attempts
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


def wordpress_request_configuration(
    db: Session,
    execution: PublishingExecution,
    destination: PublishingDestination,
) -> dict[str, object]:
    configuration = dict(destination.configuration_json)
    configuration["post_status"] = (
        "draft" if execution.requested_action == "create_draft" else "publish"
    )
    if execution.requested_action == "update":
        previous = db.scalar(
            select(PublishingExecution)
            .where(
                PublishingExecution.owner_id == execution.owner_id,
                PublishingExecution.destination_id == execution.destination_id,
                PublishingExecution.product_id == execution.product_id,
                PublishingExecution.status == "succeeded",
                PublishingExecution.remote_entity_id.is_not(None),
                PublishingExecution.id != execution.id,
            )
            .order_by(PublishingExecution.completed_at.desc())
        )
        if not previous or not previous.remote_entity_id:
            raise HTTPException(
                409,
                {
                    "code": "remote_post_missing",
                    "message": "No prior WordPress post is available to update.",
                },
            )
        configuration["remote_post_id"] = previous.remote_entity_id
    return configuration


def run_attempt(
    db: Session,
    owner: User,
    execution: PublishingExecution,
    destination: PublishingDestination,
    *,
    retry: bool,
) -> ExecutionResponse:
    active_connector, max_attempts = execution_connector(db, owner, destination)
    request_configuration = (
        wordpress_request_configuration(db, execution, destination)
        if destination.connector_key == "wordpress"
        else destination.configuration_json
    )
    stamp = now()
    execution.status, execution.started_at, execution.updated_at = "running", stamp, stamp
    if retry:
        record_event(
            db,
            actor_id=owner.id,
            action="publishing.execution_retried",
            entity_type="publishing_execution",
            entity_id=execution.id,
            metadata={"attempt_number": execution.attempt_count},
        )
    action = "publishing.execution_failed"
    for transport_attempt in range(max_attempts):
        execution.attempt_count += 1
        attempt = PublishingExecutionAttempt(
            execution_id=execution.id,
            attempt_number=execution.attempt_count,
            operation=execution.requested_action,
            status="running",
            request_snapshot_json=execution.request_snapshot_json,
            retryable=False,
            started_at=now(),
            created_at=now(),
            correlation_id=correlation_id(),
            request_method="POST",
            safe_endpoint_label="posts",
        )
        db.add(attempt)
        db.flush()
        try:
            result = active_connector.publish(
                request_configuration, execution.content_snapshot_json
            )
            finished = now()
            if execution.cancellation_requested_at:
                execution.status = "cancelled"
                execution.cancelled_at = finished
                execution.updated_at = finished
                attempt.status = "succeeded"
                attempt.result_json = {"late_result_discarded": True}
                attempt.completed_at = finished
                action = "publishing.execution_cancelled"
                break
            attempt.status, attempt.result_json, attempt.completed_at = (
                "succeeded",
                result.payload,
                finished,
            )
            execution.status, execution.result_json, execution.completed_at = (
                "succeeded",
                result.payload,
                finished,
            )
            execution.external_reference = result.external_reference
            execution.external_url = result.external_url
            execution.remote_entity_type = "post"
            execution.remote_entity_id = result.external_reference
            execution.remote_edit_url = (
                f"{active_connector.site_url}/wp-admin/post.php"
                f"?post={result.external_reference}&action=edit"
                if isinstance(active_connector, WordPressConnector)
                else None
            )
            execution.remote_status = result.remote_status
            execution.remote_slug = result.remote_slug
            execution.error_code = execution.safe_error_message = None
            execution.retryable, execution.failed_at, execution.updated_at = False, None, finished
            action = "publishing.execution_succeeded"
            break
        except ConnectorFailure as error:
            finished = now()
            attempt.status, attempt.error_code, attempt.safe_error_message = (
                "failed",
                error.code,
                error.safe_message,
            )
            attempt.retryable, attempt.failed_at = error.retryable, finished
            attempt.response_status = error.status_code
            attempt.retry_after_seconds = error.retry_after
            attempt.ambiguous_result = error.ambiguous
            execution.status, execution.error_code, execution.safe_error_message = (
                "failed",
                error.code,
                error.safe_message,
            )
            execution.retryable, execution.failed_at, execution.updated_at = (
                error.retryable and not error.ambiguous,
                finished,
                finished,
            )
            if error.ambiguous:
                execution.reconciliation_status = "reconciliation_required"
            if not error.retryable or error.ambiguous or transport_attempt + 1 >= max_attempts:
                break
    record_event(
        db,
        actor_id=owner.id,
        action=action,
        entity_type="publishing_execution",
        entity_id=execution.id,
        metadata={
            "attempt_number": execution.attempt_count,
            "retryable": execution.retryable,
            "connector_key": execution.connector_key,
            "correlation_id": execution.correlation_id,
        },
    )
    db.commit()
    return execution_response(db, execution)


def create_execution(db: Session, owner: User, data: CreateExecution) -> ExecutionResponse:
    key = data.idempotency_key or str(uuid.uuid4())
    existing = db.scalar(
        select(PublishingExecution).where(
            PublishingExecution.owner_id == owner.id, PublishingExecution.idempotency_key == key
        )
    )
    if existing:
        if (
            existing.artifact_id != data.artifact_id
            or existing.destination_id != data.destination_id
        ):
            raise HTTPException(409, "Idempotency key was already used for different input.")
        return execution_response(db, existing)
    artifact = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == data.artifact_id, GeneratedArtifact.owner_id == owner.id
        )
    )
    if not artifact:
        raise HTTPException(404, "AI artifact not found.")
    if artifact.status != "approved":
        raise HTTPException(
            409,
            {
                "code": "artifact_not_approved",
                "message": "Only approved artifacts may be published.",
            },
        )
    product = db.scalar(
        select(Product).where(Product.id == artifact.product_id, Product.owner_id == owner.id)
    )
    brand = db.scalar(
        select(Brand).where(Brand.id == artifact.brand_id, Brand.owner_id == owner.id)
    )
    destination = owned_destination(db, owner.id, data.destination_id)
    if not product or not brand:
        raise HTTPException(404, "Publishable product was not found.")
    if product.status == ProductStatus.ARCHIVED.value:
        raise HTTPException(
            409, {"code": "product_archived", "message": "Archived products cannot be published."}
        )
    if brand.status == BrandStatus.ARCHIVED.value:
        raise HTTPException(
            409,
            {
                "code": "brand_archived",
                "message": "Products in archived brands cannot be published.",
            },
        )
    if destination.status != "active":
        raise HTTPException(
            409, {"code": "destination_disabled", "message": "The destination is disabled."}
        )
    if destination.brand_id and destination.brand_id != brand.id:
        raise HTTPException(
            409,
            {
                "code": "destination_brand_mismatch",
                "message": "Destination Brand scope does not match.",
            },
        )
    snapshot = {
        "schema_version": 1,
        "product_id": str(product.id),
        "product_name": product.name,
        "brand_id": str(brand.id),
        "brand_name": brand.name,
        "artifact_id": str(artifact.id),
        "artifact_version": artifact.version_number,
        **artifact.content_json,
        "sku": product.sku,
        "price_amount": str(product.price_amount) if product.price_amount is not None else None,
        "price_currency": product.price_currency,
    }
    stamp = now()
    execution = PublishingExecution(
        owner_id=owner.id,
        brand_id=brand.id,
        product_id=product.id,
        artifact_id=artifact.id,
        destination_id=destination.id,
        connector_key=destination.connector_key,
        status="pending",
        idempotency_key=key,
        attempt_count=0,
        content_snapshot_json=snapshot,
        request_snapshot_json={
            "schema_version": 1,
            "destination_id": str(destination.id),
            "destination_name": destination.name,
            "configuration": destination.configuration_json,
        },
        retryable=False,
        created_at=stamp,
        updated_at=stamp,
        requested_action=data.action,
        reconciliation_status="unknown",
        correlation_id=correlation_id(),
    )
    db.add(execution)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="publishing.execution_requested",
        entity_type="publishing_execution",
        entity_id=execution.id,
        metadata={
            "brand_id": str(brand.id),
            "product_id": str(product.id),
            "artifact_id": str(artifact.id),
            "destination_id": str(destination.id),
        },
    )
    return run_attempt(db, owner, execution, destination, retry=False)


def retry_execution(db: Session, owner: User, execution_id: uuid.UUID) -> ExecutionResponse:
    execution = db.scalar(
        select(PublishingExecution)
        .where(PublishingExecution.id == execution_id, PublishingExecution.owner_id == owner.id)
        .with_for_update()
    )
    if not execution:
        raise HTTPException(404, "Publishing execution not found.")
    if execution.status != "failed" or not execution.retryable:
        raise HTTPException(409, "This execution is not eligible for retry.")
    destination = owned_destination(db, owner.id, execution.destination_id)
    if destination.status != "active":
        raise HTTPException(409, "The destination is disabled.")
    return run_attempt(db, owner, execution, destination, retry=True)


def owned_execution(
    db: Session, owner_id: uuid.UUID, execution_id: uuid.UUID
) -> PublishingExecution:
    value = db.scalar(
        select(PublishingExecution).where(
            PublishingExecution.id == execution_id,
            PublishingExecution.owner_id == owner_id,
        )
    )
    if not value:
        raise HTTPException(404, "Publishing execution not found.")
    return value


def cancel_execution(db: Session, owner: User, execution_id: uuid.UUID) -> ExecutionResponse:
    value = owned_execution(db, owner.id, execution_id)
    if value.status not in {"pending", "running"}:
        raise HTTPException(409, "Only pending or running executions can be cancelled.")
    stamp = now()
    value.cancellation_requested_at = stamp
    value.cancelled_at = stamp
    value.status = "cancelled"
    value.updated_at = stamp
    record_event(
        db,
        actor_id=owner.id,
        action="publishing.execution_cancelled",
        entity_type="publishing_execution",
        entity_id=value.id,
        metadata={"remote_cancellation": False},
    )
    db.commit()
    return execution_response(db, value)


def reconcile_execution(
    db: Session, owner: User, execution_id: uuid.UUID
) -> ReconciliationResponse:
    value = owned_execution(db, owner.id, execution_id)
    if value.connector_key != "wordpress" or not value.remote_entity_id:
        raise HTTPException(409, "This execution has no WordPress post to reconcile.")
    destination = owned_destination(db, owner.id, value.destination_id)
    active_connector, _ = execution_connector(db, owner, destination)
    assert isinstance(active_connector, WordPressConnector)
    drift: list[str] = []
    try:
        result = active_connector.reconcile(value.remote_entity_id)
        if value.remote_status and value.remote_status != result.remote_status:
            drift.append("status")
        if value.remote_slug and value.remote_slug != result.remote_slug:
            drift.append("slug")
        if value.external_url and value.external_url != result.external_url:
            drift.append("url")
        value.remote_status = result.remote_status
        value.remote_slug = result.remote_slug
        value.external_url = result.external_url
        value.reconciliation_status = "changed_remotely" if drift else "in_sync"
    except ConnectorFailure as error:
        value.reconciliation_status = (
            "missing_remotely" if error.code == "wordpress_not_found" else "reconciliation_failed"
        )
        drift = ["remote_missing"] if error.code == "wordpress_not_found" else []
    value.last_reconciled_at = now()
    value.updated_at = value.last_reconciled_at
    record_event(
        db,
        actor_id=owner.id,
        action="publishing.execution_reconciled",
        entity_type="publishing_execution",
        entity_id=value.id,
        metadata={"status": value.reconciliation_status, "drift_fields": drift},
    )
    db.commit()
    return ReconciliationResponse(
        id=value.id,
        reconciliation_status=value.reconciliation_status,
        remote_status=value.remote_status,
        remote_slug=value.remote_slug,
        remote_url=value.external_url,
        drift_fields=drift,
        correlation_id=correlation_id(),
    )


def move_execution_to_draft(db: Session, owner: User, execution_id: uuid.UUID) -> ExecutionResponse:
    value = owned_execution(db, owner.id, execution_id)
    if value.connector_key != "wordpress" or not value.remote_entity_id:
        raise HTTPException(409, "This execution has no WordPress post to move to draft.")
    destination = owned_destination(db, owner.id, value.destination_id)
    active_connector, _ = execution_connector(db, owner, destination)
    assert isinstance(active_connector, WordPressConnector)
    result = active_connector.move_to_draft(value.remote_entity_id)
    value.remote_status = result.remote_status
    value.result_json = result.payload
    value.external_url = result.external_url
    value.reconciliation_status = "in_sync"
    value.last_reconciled_at = now()
    value.updated_at = value.last_reconciled_at
    record_event(
        db,
        actor_id=owner.id,
        action="publishing.execution_moved_to_draft",
        entity_type="publishing_execution",
        entity_id=value.id,
        metadata={"remote_entity_id": value.remote_entity_id},
    )
    db.commit()
    return execution_response(db, value)
