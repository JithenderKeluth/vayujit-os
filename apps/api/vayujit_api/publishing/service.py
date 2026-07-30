import hashlib
import random
import re
import time
import uuid
from typing import Any, Literal, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand, BrandStatus
from vayujit_api.core.observability import correlation_id, maintenance_enabled
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.media.models import MediaAsset, WordPressMediaMapping
from vayujit_api.media.service import owned_media, storage_path
from vayujit_api.products.models import Product, ProductStatus
from vayujit_api.publishing.connector import (
    ConnectorFailure,
    PublishingConnector,
    WordPressConnector,
    connector,
    wordpress_payload,
)
from vayujit_api.publishing.models import (
    PublishingDestination,
    PublishingExecution,
    PublishingExecutionAttempt,
    ShopifyMediaMapping,
    ShopifyMediaPollAttempt,
    ShopifyProductAssignment,
    ShopifyVariantMapping,
)
from vayujit_api.publishing.schemas import (
    AttemptResponse,
    CreateExecution,
    DestinationResponse,
    DestinationUpdate,
    DestinationWrite,
    ExecutionResponse,
    MockConfiguration,
    PublishingPreviewRequest,
    PublishingPreviewResponse,
    ReconciliationResponse,
    RemoteDriftField,
    SanitizationChange,
    ShopifyAssignmentRemovalPreview,
    ShopifyAssignmentRemovalRequest,
    ShopifyDestinationConfiguration,
    ShopifyOverwriteConfirmation,
    ShopifyOverwritePreview,
    ShopifyPreviewResponse,
    WordPressDestinationConfiguration,
)
from vayujit_api.publishing.shopify import (
    connector_for as shopify_connector_for,
)
from vayujit_api.publishing.shopify import (
    owned_configuration as owned_shopify_configuration,
)
from vayujit_api.publishing.shopify_connector import (
    ShopifyGraphQLClient,
    shopify_product_input,
    shopify_variant_inputs,
)
from vayujit_api.publishing.shopify_media import (
    MediaPollObservation,
    MediaPollPolicy,
    decide_media_reuse,
    poll_media,
)
from vayujit_api.publishing.wordpress import connector_for, owned_configuration


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def destination_response(db: Session, value: PublishingDestination) -> DestinationResponse:
    brand = db.get(Brand, value.brand_id) if value.brand_id else None
    parsed_configuration: (
        WordPressDestinationConfiguration | ShopifyDestinationConfiguration | MockConfiguration
    )
    if value.connector_key == "wordpress":
        parsed_configuration = WordPressDestinationConfiguration.model_validate(
            value.configuration_json
        )
    elif value.connector_key == "shopify":
        parsed_configuration = ShopifyDestinationConfiguration.model_validate(
            value.configuration_json
        )
    else:
        parsed_configuration = MockConfiguration.model_validate(value.configuration_json)
    return DestinationResponse(
        id=value.id,
        brand_id=value.brand_id,
        brand_name=brand.name if brand else None,
        connector_key=value.connector_key,
        name=value.name,
        status=cast(Literal["active", "disabled"], value.status),
        configuration=parsed_configuration,
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
        expected = {
            "wordpress": WordPressDestinationConfiguration,
            "shopify": ShopifyDestinationConfiguration,
        }.get(value.connector_key, MockConfiguration)
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
                calculated_delay_ms=a.calculated_delay_ms,
                applied_delay_ms=a.applied_delay_ms,
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
    if destination.connector_key == "shopify":
        shopify_configuration = owned_shopify_configuration(db, owner.id)
        if not shopify_configuration or not shopify_configuration.enabled:
            raise HTTPException(
                409,
                {
                    "code": "shopify_not_enabled",
                    "message": "Configure, validate, and enable Shopify before publishing.",
                },
            )
        if shopify_configuration.validation_status != "valid":
            raise HTTPException(
                409,
                {
                    "code": "shopify_not_validated",
                    "message": "Validate the Shopify connection before publishing.",
                },
            )
        try:
            return (
                cast(PublishingConnector, shopify_connector_for(shopify_configuration)),
                shopify_configuration.max_retry_attempts,
            )
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
    if destination.connector_key != "wordpress":
        raise HTTPException(409, "Publishing connector is unsupported.")
    wordpress_configuration = owned_configuration(db, owner.id)
    if not wordpress_configuration or not wordpress_configuration.enabled:
        raise HTTPException(
            409,
            {
                "code": "wordpress_not_enabled",
                "message": "Configure, validate, and enable WordPress before publishing.",
            },
        )
    if wordpress_configuration.validation_status != "valid":
        raise HTTPException(
            409,
            {
                "code": "wordpress_not_validated",
                "message": "Validate the WordPress connection before publishing.",
            },
        )
    try:
        return (
            connector_for(wordpress_configuration),
            wordpress_configuration.max_retry_attempts,
        )
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
    selected_media_id = execution.request_snapshot_json.get("featured_media_id")
    if selected_media_id:
        configuration["featured_media_id"] = selected_media_id
    return configuration


def shopify_request_configuration(
    db: Session,
    execution: PublishingExecution,
    destination: PublishingDestination,
) -> dict[str, object]:
    configuration = dict(destination.configuration_json)
    configuration["requested_action"] = execution.requested_action
    configuration["shopify_variants"] = execution.request_snapshot_json.get("shopify_variants", [])
    mappings = db.scalars(
        select(ShopifyVariantMapping).where(
            ShopifyVariantMapping.destination_id == execution.destination_id,
            ShopifyVariantMapping.product_id == execution.product_id,
            ShopifyVariantMapping.owner_id == execution.owner_id,
        )
    ).all()
    configuration["variant_remote_ids"] = {
        value.local_variant_key: value.remote_variant_id for value in mappings
    }
    if execution.requested_action in {"update", "activate", "archive"}:
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
                    "code": "remote_product_missing",
                    "message": "No prior Shopify product is available for this action.",
                },
            )
        configuration["remote_product_id"] = previous.remote_entity_id
    return configuration


def retry_delay_seconds(
    attempt_number: int,
    *,
    retry_after: int | None = None,
    jitter_value: float | None = None,
    base_delay: float = 1.0,
    maximum_delay: float = 10.0,
) -> float:
    jitter = random.SystemRandom().uniform(0.8, 1.2) if jitter_value is None else jitter_value
    exponential = min(maximum_delay, base_delay * (2 ** max(attempt_number - 1, 0)))
    return float(
        min(maximum_delay, max(exponential * min(max(jitter, 0.8), 1.2), retry_after or 0))
    )


def persist_shopify_result_mappings(
    db: Session,
    execution: PublishingExecution,
    payload: dict[str, object],
) -> None:
    remote_product_id = execution.remote_entity_id
    if not remote_product_id:
        return
    variants = payload.get("variants")
    if isinstance(variants, list):
        for item in variants:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            local_key = str(item.get("localKey") or "default")
            mapping = db.scalar(
                select(ShopifyVariantMapping).where(
                    ShopifyVariantMapping.destination_id == execution.destination_id,
                    ShopifyVariantMapping.product_id == execution.product_id,
                    ShopifyVariantMapping.local_variant_key == local_key,
                )
            )
            inventory = item.get("inventoryItem")
            values = {
                "remote_product_id": remote_product_id,
                "remote_variant_id": str(item["id"]),
                "remote_inventory_item_id": (
                    str(inventory.get("id"))
                    if isinstance(inventory, dict) and inventory.get("id")
                    else None
                ),
                "sku": str(item.get("sku") or "") or None,
                "option_signature": "|".join(
                    f"{option.get('name')}={option.get('value')}"
                    for option in item.get("selectedOptions", [])
                    if isinstance(option, dict)
                ),
                "status": "mapped",
                "last_verified_at": now(),
            }
            if mapping:
                for key, value in values.items():
                    setattr(mapping, key, value)
            else:
                db.add(
                    ShopifyVariantMapping(
                        owner_id=execution.owner_id,
                        destination_id=execution.destination_id,
                        product_id=execution.product_id,
                        local_variant_key=local_key,
                        created_at=now(),
                        **values,
                    )
                )
    for assignment_type, key in (
        ("collection", "collection_ids"),
        ("publication", "publication_ids"),
    ):
        identifiers = payload.get(key)
        if not isinstance(identifiers, list):
            continue
        for remote_target_id in identifiers:
            if not isinstance(remote_target_id, str):
                continue
            existing = db.scalar(
                select(ShopifyProductAssignment).where(
                    ShopifyProductAssignment.destination_id == execution.destination_id,
                    ShopifyProductAssignment.remote_product_id == remote_product_id,
                    ShopifyProductAssignment.assignment_type == assignment_type,
                    ShopifyProductAssignment.remote_target_id == remote_target_id,
                )
            )
            if not existing:
                db.add(
                    ShopifyProductAssignment(
                        owner_id=execution.owner_id,
                        destination_id=execution.destination_id,
                        product_id=execution.product_id,
                        remote_product_id=remote_product_id,
                        assignment_type=assignment_type,
                        remote_target_id=remote_target_id,
                        managed_by_vayujit=True,
                        status="assigned",
                        created_at=now(),
                        updated_at=now(),
                        last_verified_at=now(),
                    )
                )


def ensure_shopify_media(
    db: Session,
    execution: PublishingExecution,
    destination: PublishingDestination,
    client: ShopifyGraphQLClient,
    payload: dict[str, object],
) -> None:
    selections = execution.request_snapshot_json.get("shopify_media")
    if not isinstance(selections, list) or not selections:
        return
    if not execution.remote_entity_id:
        raise ConnectorFailure(
            "shopify_media_product_missing",
            "A remote draft is required before media can be uploaded.",
            retryable=False,
        )
    policy = str(destination.configuration_json.get("media_policy") or "fail")
    fingerprint = hashlib.sha256(client.shop_domain.encode()).hexdigest()
    results: list[dict[str, object]] = []
    for selection in sorted(
        (value for value in selections if isinstance(value, dict)),
        key=lambda value: int(value.get("position", 0)),
    ):
        try:
            media = db.scalar(
                select(MediaAsset).where(
                    MediaAsset.id == uuid.UUID(str(selection.get("media_id"))),
                    MediaAsset.owner_id == execution.owner_id,
                    MediaAsset.status == "ready",
                )
            )
            if not media:
                raise ConnectorFailure(
                    "shopify_media_not_found",
                    "A selected media asset is unavailable.",
                    retryable=False,
                )
            mapping = db.scalar(
                select(ShopifyMediaMapping).where(
                    ShopifyMediaMapping.owner_id == execution.owner_id,
                    ShopifyMediaMapping.destination_id == destination.id,
                    ShopifyMediaMapping.media_id == media.id,
                    ShopifyMediaMapping.shop_fingerprint == fingerprint,
                    ShopifyMediaMapping.checksum_sha256 == media.checksum_sha256,
                )
            )
            if mapping:
                try:
                    remote_state = client.media_status(
                        product_id=execution.remote_entity_id,
                        media_id=mapping.remote_media_id,
                    )
                    reuse_state = decide_media_reuse(
                        destination_matches=mapping.destination_id == destination.id,
                        shop_matches=mapping.shop_fingerprint == fingerprint,
                        checksum_matches=mapping.checksum_sha256 == media.checksum_sha256,
                        remote_exists=cast(bool | None, remote_state.get("exists")),
                        remote_accessible=True,
                        remote_product_matches=(
                            mapping.remote_product_id == execution.remote_entity_id
                        ),
                        remote_status=remote_state.get("status"),
                    )
                except ConnectorFailure:
                    reuse_state = "inaccessible"
                    remote_state = {}
                mapping.reuse_state = reuse_state
                mapping.last_verified_at = now()
                mapping.updated_at = mapping.last_verified_at
                record_event(
                    db,
                    actor_id=execution.owner_id,
                    action=(
                        "publishing.shopify_media_mapping_verified"
                        if reuse_state == "reusable"
                        else "publishing.shopify_media_mapping_stale"
                    ),
                    entity_type="shopify_media_mapping",
                    entity_id=mapping.id,
                    metadata={"reuse_state": reuse_state},
                )
                if reuse_state == "reusable":
                    remote_id, state = mapping.remote_media_id, "reused"
                elif reuse_state == "processing":
                    remote_id, state = mapping.remote_media_id, "processing"
                else:
                    mapping.status = reuse_state
                    mapping = None
            if not mapping:
                remote = client.upload_product_media(
                    product_id=execution.remote_entity_id,
                    filename=media.safe_filename,
                    mime_type=media.mime_type,
                    content=storage_path(media.storage_key).read_bytes(),
                    alt_text=str(selection.get("alt_text") or ""),
                )
                if not isinstance(remote.get("id"), str):
                    raise ConnectorFailure(
                        "shopify_media_result_invalid",
                        "Shopify omitted the remote media identifier.",
                        retryable=False,
                    )
                remote_id, state = (
                    str(remote["id"]),
                    str(remote.get("status") or "processing").casefold(),
                )
                stamp = now()
                mapping = ShopifyMediaMapping(
                    owner_id=execution.owner_id,
                    destination_id=destination.id,
                    media_id=media.id,
                    shop_fingerprint=fingerprint,
                    remote_product_id=execution.remote_entity_id,
                    remote_media_id=remote_id,
                    remote_url=None,
                    checksum_sha256=media.checksum_sha256,
                    alt_text=str(selection.get("alt_text") or ""),
                    position=int(selection.get("position", 0)),
                    status=state,
                    reuse_state="processing",
                    polling_attempt_count=0,
                    safe_error_message=None,
                    created_at=stamp,
                    updated_at=stamp,
                    last_verified_at=stamp,
                )
                db.add(mapping)
                db.flush()
            if state not in {"ready", "reused"}:
                poll_mapping = mapping
                record_event(
                    db,
                    actor_id=execution.owner_id,
                    action="publishing.shopify_media_poll_started",
                    entity_type="shopify_media_mapping",
                    entity_id=mapping.id,
                    metadata={"maximum_attempts": 12, "maximum_duration_seconds": 60},
                )

                def persist_observation(
                    observation: MediaPollObservation,
                    poll_mapping: ShopifyMediaMapping = poll_mapping,
                ) -> None:
                    poll_mapping.polling_attempt_count = observation.attempt
                    poll_mapping.status = observation.state
                    poll_mapping.remote_url = observation.remote_url or poll_mapping.remote_url
                    poll_mapping.safe_error_message = observation.safe_error
                    poll_mapping.updated_at = now()
                    db.add(
                        ShopifyMediaPollAttempt(
                            owner_id=execution.owner_id,
                            execution_id=execution.id,
                            media_mapping_id=poll_mapping.id,
                            attempt_number=observation.attempt,
                            remote_status=observation.state,
                            delay_ms=int(observation.delay_seconds * 1000),
                            latency_ms=int(observation.latency_seconds * 1000),
                            correlation_id=execution.correlation_id,
                            safe_error_message=observation.safe_error,
                            created_at=now(),
                        )
                    )
                    db.flush()

                def fetch_media_status(
                    media_id: str = poll_mapping.remote_media_id,
                ) -> dict[str, object]:
                    return client.media_status(
                        product_id=execution.remote_entity_id or "",
                        media_id=media_id,
                    )

                def cancellation_requested(execution_id: uuid.UUID = execution.id) -> bool:
                    return (
                        db.scalar(
                            select(PublishingExecution.cancellation_requested_at).where(
                                PublishingExecution.id == execution_id
                            )
                        )
                        is not None
                    )

                polled = poll_media(
                    fetch_media_status,
                    policy=MediaPollPolicy(),
                    clock=time.monotonic,
                    delay=time.sleep,
                    cancelled=cancellation_requested,
                    observe=persist_observation,
                )
                mapping.status = polled.state
                mapping.reuse_state = "reusable" if polled.state == "ready" else polled.state
                mapping.remote_url = polled.remote_url or mapping.remote_url
                mapping.last_verified_at = now()
                mapping.updated_at = mapping.last_verified_at
                state = polled.state
                record_event(
                    db,
                    actor_id=execution.owner_id,
                    action=(
                        "publishing.shopify_media_poll_timed_out"
                        if state == "timed_out"
                        else "publishing.shopify_media_poll_completed"
                    ),
                    entity_type="shopify_media_mapping",
                    entity_id=mapping.id,
                    metadata={"status": state, "attempts": mapping.polling_attempt_count},
                )
                if state == "cancelled":
                    raise ConnectorFailure(
                        "shopify_media_poll_cancelled",
                        "Local media polling was cancelled; the remote media was not deleted.",
                        retryable=True,
                    )
                if state not in {"ready"}:
                    raise ConnectorFailure(
                        (
                            "shopify_media_processing_timeout"
                            if state == "timed_out"
                            else "shopify_media_processing_failed"
                        ),
                        (
                            "Shopify media processing timed out and requires reconciliation."
                            if state == "timed_out"
                            else "Shopify could not process the uploaded media."
                        ),
                        retryable=True,
                    )
            results.append(
                {
                    "media_id": str(media.id),
                    "remote_media_id": remote_id,
                    "status": state,
                    "position": int(selection.get("position", 0)),
                    "alt_text": str(selection.get("alt_text") or ""),
                }
            )
        except (ConnectorFailure, ValueError) as error:
            failure = (
                error
                if isinstance(error, ConnectorFailure)
                else ConnectorFailure(
                    "shopify_media_invalid", "A selected media asset was invalid.", retryable=False
                )
            )
            if policy == "fail":
                raise failure from error
            results.append(
                {
                    "media_id": str(selection.get("media_id") or ""),
                    "status": "omitted" if policy == "draft_without_media" else "failed",
                    "safe_error": failure.safe_message,
                }
            )
            if policy == "degraded":
                execution.status, execution.remote_status = "degraded", "draft"
    payload["media"] = results


def ensure_wordpress_media(
    db: Session,
    owner: User,
    connector_value: WordPressConnector,
    configuration: dict[str, object],
) -> None:
    raw_media_id = configuration.get("featured_media_id")
    if not raw_media_id:
        return
    media = owned_media(db, owner.id, uuid.UUID(str(raw_media_id)))
    if media.status != "ready":
        raise HTTPException(409, "The selected featured image is archived.")
    site_fingerprint = hashlib.sha256(connector_value.site_url.encode()).hexdigest()
    mapping = db.scalar(
        select(WordPressMediaMapping).where(
            WordPressMediaMapping.owner_id == owner.id,
            WordPressMediaMapping.media_id == media.id,
            WordPressMediaMapping.site_fingerprint == site_fingerprint,
        )
    )
    if mapping:
        try:
            connector_value.request("GET", f"/media/{int(mapping.remote_media_id)}")
            mapping.last_verified_at = now()
            mapping.updated_at = mapping.last_verified_at
            configuration["featured_media_remote_id"] = mapping.remote_media_id
            record_event(
                db,
                actor_id=owner.id,
                action="publishing.remote_media_reused",
                entity_type="media_asset",
                entity_id=media.id,
                metadata={"remote_media_id": mapping.remote_media_id},
            )
            return
        except ConnectorFailure as error:
            if error.code != "wordpress_not_found":
                raise
            db.delete(mapping)
            db.flush()
    uploaded = connector_value.upload_media(
        media.safe_filename, media.mime_type, storage_path(media.storage_key).read_bytes()
    )
    remote_id = str(uploaded["id"])
    stamp = now()
    db.add(
        WordPressMediaMapping(
            owner_id=owner.id,
            media_id=media.id,
            site_fingerprint=site_fingerprint,
            remote_media_id=remote_id,
            remote_url=str(uploaded.get("source_url") or "")[:500] or None,
            remote_status="mapped",
            last_verified_at=stamp,
            created_at=stamp,
            updated_at=stamp,
        )
    )
    configuration["featured_media_remote_id"] = remote_id
    record_event(
        db,
        actor_id=owner.id,
        action="publishing.featured_media_selected",
        entity_type="media_asset",
        entity_id=media.id,
        metadata={"remote_media_id": remote_id},
    )


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
        else (
            shopify_request_configuration(db, execution, destination)
            if destination.connector_key == "shopify"
            else destination.configuration_json
        )
    )
    if isinstance(active_connector, WordPressConnector):
        ensure_wordpress_media(db, owner, active_connector, request_configuration)
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
            safe_endpoint_label=(
                "shopify_graphql" if destination.connector_key == "shopify" else "posts"
            ),
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
            attempt.latency_ms = max(
                0, round((finished - attempt.started_at).total_seconds() * 1000)
            )
            execution.status, execution.result_json, execution.completed_at = (
                "succeeded",
                result.payload,
                finished,
            )
            execution.external_reference = result.external_reference
            execution.external_url = result.external_url
            execution.remote_entity_type = (
                "product" if destination.connector_key == "shopify" else "post"
            )
            execution.remote_entity_id = result.external_reference
            execution.remote_edit_url = (
                f"{active_connector.site_url}/wp-admin/post.php"
                f"?post={result.external_reference}&action=edit"
                if isinstance(active_connector, WordPressConnector)
                else (
                    result.external_url
                    if isinstance(active_connector, ShopifyGraphQLClient)
                    else None
                )
            )
            execution.remote_status = result.remote_status
            execution.remote_slug = result.remote_slug
            if destination.connector_key == "shopify":
                ensure_shopify_media(
                    db,
                    execution,
                    destination,
                    cast(ShopifyGraphQLClient, active_connector),
                    result.payload,
                )
                persist_shopify_result_mappings(db, execution, result.payload)
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
            attempt.latency_ms = max(
                0, round((finished - attempt.started_at).total_seconds() * 1000)
            )
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
            delay = retry_delay_seconds(
                transport_attempt + 1,
                retry_after=error.retry_after,
            )
            attempt.calculated_delay_ms = round(delay * 1000)
            attempt.applied_delay_ms = round(delay * 1000)
            record_event(
                db,
                actor_id=owner.id,
                action="publishing.shopify_retry_scheduled",
                entity_type="publishing_execution",
                entity_id=execution.id,
                metadata={
                    "attempt_number": attempt.attempt_number,
                    "delay_ms": attempt.applied_delay_ms,
                    "error_code": error.code,
                    "correlation_id": execution.correlation_id,
                },
            )
            time.sleep(delay)
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
    if execution.connector_key == "shopify" and execution.status == "succeeded":
        shopify_action = {
            "create_draft": "publishing.shopify_product_draft_created",
            "activate": "publishing.shopify_product_activated",
            "update": "publishing.shopify_product_updated",
            "archive": "publishing.shopify_product_archived",
        }.get(execution.requested_action)
        if shopify_action:
            record_event(
                db,
                actor_id=owner.id,
                action=shopify_action,
                entity_type="publishing_execution",
                entity_id=execution.id,
                metadata={
                    "connector": "shopify",
                    "remote_product_id": execution.remote_entity_id,
                    "remote_status": execution.remote_status,
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
    selected_media_id = data.featured_media_id
    if destination.connector_key == "wordpress":
        destination_configuration = WordPressDestinationConfiguration.model_validate(
            destination.configuration_json
        )
        selected_media_id = selected_media_id or destination_configuration.default_media_id
        if (
            destination_configuration.featured_image_policy == "required"
            and selected_media_id is None
        ):
            raise HTTPException(
                409,
                {
                    "code": "featured_media_required",
                    "message": "This destination requires a featured image.",
                },
            )
        if selected_media_id:
            media = owned_media(db, owner.id, selected_media_id)
            if media.status != "ready":
                raise HTTPException(409, "The selected featured image is archived.")
    if destination.connector_key == "shopify":
        shopify_configuration = ShopifyDestinationConfiguration.model_validate(
            destination.configuration_json
        )
        if data.action == "publish":
            raise HTTPException(
                422,
                "Use create_draft or explicit activate for Shopify products.",
            )
        if data.action == "activate" and shopify_configuration.default_product_status != "active":
            raise HTTPException(
                409,
                {
                    "code": "shopify_activation_not_enabled",
                    "message": "This destination does not permit product activation.",
                },
            )
        if shopify_configuration.inventory_policy != "no_inventory_write":
            raise HTTPException(
                409,
                "Inventory quantity writes are not supported in this Shopify slice.",
            )
    snapshot = content_snapshot(product, brand, artifact)
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
            "featured_media_id": str(selected_media_id) if selected_media_id else None,
            "shopify_variants": [item.model_dump(mode="json") for item in data.shopify_variants],
            "shopify_media": [item.model_dump(mode="json") for item in data.shopify_media],
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
    if data.action == "update":
        record_event(
            db,
            actor_id=owner.id,
            action="publishing.remote_overwrite_confirmed",
            entity_type="publishing_execution",
            entity_id=execution.id,
            metadata={"destination_id": str(destination.id)},
        )
    return run_attempt(db, owner, execution, destination, retry=False)


def keep_remote_changes(db: Session, owner: User, execution_id: uuid.UUID) -> ExecutionResponse:
    value = owned_execution(db, owner.id, execution_id)
    if (
        value.connector_key not in {"wordpress", "shopify"}
        or value.reconciliation_status != "changed_remotely"
    ):
        raise HTTPException(409, "No reviewed remote drift is available to keep.")
    value.reconciliation_status = "remote_changes_kept"
    value.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action="publishing.remote_drift_reviewed",
        entity_type="publishing_execution",
        entity_id=value.id,
        metadata={"decision": "keep_remote"},
    )
    db.commit()
    return execution_response(db, value)


def content_snapshot(
    product: Product, brand: Brand, artifact: GeneratedArtifact
) -> dict[str, object]:
    return {
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
        "compare_at_price_amount": (
            str(product.compare_at_price_amount)
            if product.compare_at_price_amount is not None
            else None
        ),
        "barcode": product.barcode,
        "weight_value": str(product.weight_value) if product.weight_value is not None else None,
        "weight_unit": product.weight_unit,
        "inventory_tracking_enabled": product.inventory_tracking_enabled,
    }


def publishing_preview(
    db: Session, owner: User, data: PublishingPreviewRequest
) -> PublishingPreviewResponse:
    artifact = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == data.artifact_id,
            GeneratedArtifact.owner_id == owner.id,
        )
    )
    if not artifact or artifact.status != "approved":
        raise HTTPException(409, "An approved artifact is required for preview.")
    product = db.scalar(
        select(Product).where(Product.id == artifact.product_id, Product.owner_id == owner.id)
    )
    brand = db.scalar(
        select(Brand).where(Brand.id == artifact.brand_id, Brand.owner_id == owner.id)
    )
    destination = owned_destination(db, owner.id, data.destination_id)
    if not product or not brand or destination.connector_key != "wordpress":
        raise HTTPException(409, "A WordPress-compatible artifact and destination are required.")
    configuration = WordPressDestinationConfiguration.model_validate(destination.configuration_json)
    selected_media_id = data.featured_media_id or configuration.default_media_id
    if selected_media_id:
        owned_media(db, owner.id, selected_media_id)
    snapshot = content_snapshot(product, brand, artifact)
    status = "draft" if data.action == "create_draft" else "publish"
    payload = wordpress_payload(
        snapshot,
        status=status,
        categories=configuration.category_ids,
        tags=configuration.tag_ids,
        author=configuration.author_id,
    )
    original = str(snapshot.get("long_description") or "")
    changes = [
        SanitizationChange(
            kind="converted_paragraphs",
            message="Plain-text paragraphs are converted to safe WordPress paragraph markup.",
        )
    ]
    if "<" in original or ">" in original:
        changes.append(
            SanitizationChange(
                kind="escaped_html",
                message="HTML-like input is escaped and rendered as text.",
            )
        )
    changes.append(
        SanitizationChange(
            kind="normalized_slug",
            message="The slug is normalized to lowercase letters, numbers, and hyphens.",
        )
    )
    previous = db.scalar(
        select(PublishingExecution)
        .where(
            PublishingExecution.owner_id == owner.id,
            PublishingExecution.destination_id == destination.id,
            PublishingExecution.product_id == product.id,
            PublishingExecution.remote_entity_id.is_not(None),
        )
        .order_by(PublishingExecution.completed_at.desc())
    )
    return PublishingPreviewResponse(
        title=str(payload["title"]),
        slug=str(payload["slug"]),
        excerpt=str(payload["excerpt"]),
        sanitized_body=str(payload["content"]),
        post_status=status,
        author_id=configuration.author_id,
        category_ids=configuration.category_ids,
        tag_ids=configuration.tag_ids,
        featured_media_id=selected_media_id,
        destination_id=destination.id,
        destination_name=destination.name,
        remote_update_target=previous.remote_entity_id if previous else None,
        artifact_id=artifact.id,
        artifact_version=artifact.version_number,
        product_id=product.id,
        product_name=product.name,
        brand_id=brand.id,
        brand_name=brand.name,
        original_text=original,
        sanitization_changes=changes,
    )


def shopify_publishing_preview(
    db: Session, owner: User, data: PublishingPreviewRequest
) -> ShopifyPreviewResponse:
    artifact = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == data.artifact_id,
            GeneratedArtifact.owner_id == owner.id,
        )
    )
    if not artifact or artifact.status != "approved":
        raise HTTPException(409, "An approved artifact is required for preview.")
    product = db.scalar(
        select(Product).where(Product.id == artifact.product_id, Product.owner_id == owner.id)
    )
    brand = db.scalar(
        select(Brand).where(Brand.id == artifact.brand_id, Brand.owner_id == owner.id)
    )
    destination = owned_destination(db, owner.id, data.destination_id)
    if not product or not brand or destination.connector_key != "shopify":
        raise HTTPException(409, "A Shopify-compatible artifact and destination are required.")
    configuration = ShopifyDestinationConfiguration.model_validate(destination.configuration_json)
    status: Literal["DRAFT", "ACTIVE", "ARCHIVED"] = (
        "ACTIVE"
        if data.action == "activate"
        else ("ARCHIVED" if data.action == "archive" else "DRAFT")
    )
    snapshot = content_snapshot(product, brand, artifact)
    payload = shopify_product_input(
        snapshot,
        configuration.model_dump(mode="json"),
        status=status,
    )
    seo = payload.get("seo")
    return ShopifyPreviewResponse(
        title=str(payload["title"]),
        sanitized_description_html=str(payload["descriptionHtml"]),
        status=status,
        vendor=str(payload["vendor"]),
        product_type=str(payload["productType"]),
        tags=[str(item) for item in cast(list[object], payload["tags"])],
        seo_title=str(seo.get("title") or "") if isinstance(seo, dict) else "",
        seo_description=str(seo.get("description") or "") if isinstance(seo, dict) else "",
        collection_ids=configuration.default_collection_ids,
        publication_ids=configuration.default_publication_ids,
        inventory_policy=configuration.inventory_policy,
        destination_id=destination.id,
        destination_name=destination.name,
        artifact_id=artifact.id,
        artifact_version=artifact.version_number,
        product_id=product.id,
        product_name=product.name,
        brand_id=brand.id,
        brand_name=brand.name,
        original_text=str(snapshot.get("long_description") or ""),
    )


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
    if value.connector_key not in {"wordpress", "shopify"} or not value.remote_entity_id:
        raise HTTPException(409, "This execution has no remote entity to reconcile.")
    destination = owned_destination(db, owner.id, value.destination_id)
    active_connector, _ = execution_connector(db, owner, destination)
    if value.connector_key == "wordpress":
        assert isinstance(active_connector, WordPressConnector)
    remote_connector = cast(Any, active_connector)
    drift: list[str] = []
    differences: list[RemoteDriftField] = []
    try:
        result = remote_connector.reconcile(value.remote_entity_id)
        if value.connector_key == "shopify":
            raw_configuration = value.request_snapshot_json.get("configuration")
            expected_configuration = (
                raw_configuration if isinstance(raw_configuration, dict) else {}
            )
            expected = shopify_product_input(
                value.content_snapshot_json,
                expected_configuration,
                status=("ACTIVE" if value.requested_action == "activate" else "DRAFT"),
                remote_id=value.remote_entity_id,
            )
            remote_payload = result.payload
            comparisons = {
                "product.title": (expected.get("title"), remote_payload.get("title")),
                "product.status": (
                    str(expected.get("status", "")).casefold(),
                    result.remote_status,
                ),
                "product.handle": (None, result.remote_slug),
                "product.description": (
                    expected.get("descriptionHtml"),
                    remote_payload.get("descriptionHtml"),
                ),
                "product.vendor": (expected.get("vendor"), remote_payload.get("vendor")),
                "product.product_type": (
                    expected.get("productType"),
                    remote_payload.get("productType"),
                ),
                "product.tags": (expected.get("tags"), remote_payload.get("tags")),
                "product.seo.title": (
                    cast(dict[str, object], expected.get("seo", {})).get("title"),
                    cast(dict[str, object], remote_payload.get("seo", {})).get("title"),
                ),
                "product.seo.description": (
                    cast(dict[str, object], expected.get("seo", {})).get("description"),
                    cast(dict[str, object], remote_payload.get("seo", {})).get("description"),
                ),
                "product.updated_at": (None, remote_payload.get("updatedAt")),
            }
            expected_variants = shopify_variant_inputs(
                value.content_snapshot_json,
                value.request_snapshot_json.get("shopify_variants"),
                require_price=bool(expected_configuration.get("require_variant_price")),
                require_sku=bool(expected_configuration.get("require_variant_sku")),
            )
            remote_variants_wrapper = remote_payload.get("variants")
            remote_variants = (
                remote_variants_wrapper.get("nodes")
                if isinstance(remote_variants_wrapper, dict)
                else []
            )
            mappings = db.scalars(
                select(ShopifyVariantMapping).where(
                    ShopifyVariantMapping.owner_id == owner.id,
                    ShopifyVariantMapping.destination_id == value.destination_id,
                    ShopifyVariantMapping.product_id == value.product_id,
                )
            ).all()
            remote_variant_values = remote_variants if isinstance(remote_variants, list) else []
            remote_by_id = {
                str(item.get("id")): item
                for item in remote_variant_values
                if isinstance(item, dict) and item.get("id")
            }
            for local in expected_variants:
                local_key = str(local["localKey"])
                mapping = next(
                    (item for item in mappings if item.local_variant_key == local_key), None
                )
                remote_variant = (
                    remote_by_id.pop(mapping.remote_variant_id, None) if mapping else None
                )
                for local_field, remote_field in (
                    ("sku", "sku"),
                    ("price", "price"),
                    ("compareAtPrice", "compareAtPrice"),
                    ("barcode", "barcode"),
                    ("optionValues", "selectedOptions"),
                ):
                    comparisons[f"variants[{local_key}].{local_field}"] = (
                        local.get(local_field),
                        remote_variant.get(remote_field) if remote_variant else None,
                    )
            for remote_variant_id, remote_variant in remote_by_id.items():
                comparisons[f"variants[remote:{remote_variant_id}]"] = (None, remote_variant)
            expected_media = value.result_json.get("media", []) if value.result_json else []
            remote_media_wrapper = remote_payload.get("media")
            remote_media = (
                remote_media_wrapper.get("nodes") if isinstance(remote_media_wrapper, dict) else []
            )
            comparisons["media"] = (expected_media, remote_media)
            remote_collection_wrapper = remote_payload.get("collections")
            remote_collection_nodes = (
                remote_collection_wrapper.get("nodes")
                if isinstance(remote_collection_wrapper, dict)
                else []
            )
            comparisons["collections"] = (
                expected_configuration.get("default_collection_ids", []),
                [
                    item.get("id")
                    for item in (
                        remote_collection_nodes if isinstance(remote_collection_nodes, list) else []
                    )
                    if isinstance(item, dict)
                ],
            )
            remote_publication_wrapper = remote_payload.get("resourcePublications")
            remote_publication_nodes = (
                remote_publication_wrapper.get("nodes")
                if isinstance(remote_publication_wrapper, dict)
                else []
            )
            comparisons["publications"] = (
                (
                    expected_configuration.get("default_publication_ids", [])
                    if value.requested_action == "activate"
                    else []
                ),
                [
                    cast(dict[str, object], item.get("publication", {})).get("id")
                    for item in (
                        remote_publication_nodes
                        if isinstance(remote_publication_nodes, list)
                        else []
                    )
                    if isinstance(item, dict) and item.get("isPublished")
                ],
            )
            for field, (expected_value, remote) in comparisons.items():
                shopify_status: Literal["in_sync", "changed_remotely", "unknown"] = (
                    "unknown"
                    if remote is None
                    else (
                        "in_sync"
                        if expected_value == remote or expected_value is None
                        else "changed_remotely"
                    )
                )
                differences.append(
                    RemoteDriftField(
                        field=field,
                        display_label=field.replace(".", " ").replace("_", " ").title(),
                        expected=expected_value,
                        remote=remote,
                        status=shopify_status,
                        drift_type=(
                            "missing_remote"
                            if remote is None and expected_value is not None
                            else (
                                "extra_remote"
                                if expected_value is None and remote is not None
                                else "value_changed"
                            )
                        ),
                        severity=("blocking" if field == "product.status" else "warning"),
                        resolution=(
                            "manual" if field.startswith("variants[remote:") else "overwrite"
                        ),
                        safe_explanation=(
                            "Remote Shopify state differs from the approved local mapping."
                        ),
                    )
                )
                if shopify_status == "changed_remotely":
                    drift.append(field)
            value.remote_status = result.remote_status
            value.remote_slug = result.remote_slug
            value.external_url = result.external_url
            value.reconciliation_status = "changed_remotely" if drift else "in_sync"
            raise StopIteration
        raw_configuration = value.request_snapshot_json.get("configuration")
        expected_configuration = raw_configuration if isinstance(raw_configuration, dict) else {}
        raw_categories_value = expected_configuration.get("category_ids")
        raw_tags_value = expected_configuration.get("tag_ids")
        raw_categories = raw_categories_value if isinstance(raw_categories_value, list) else []
        raw_tags = raw_tags_value if isinstance(raw_tags_value, list) else []
        raw_author = expected_configuration.get("author_id")
        expected_payload = wordpress_payload(
            value.content_snapshot_json,
            status=(
                "draft"
                if value.requested_action == "create_draft"
                else str(value.remote_status or "publish")
            ),
            categories=[int(str(item)) for item in raw_categories],
            tags=[int(str(item)) for item in raw_tags],
            author=int(str(raw_author)) if raw_author else None,
        )
        remote_payload = result.payload

        def rendered_field(key: str) -> object | None:
            raw = remote_payload.get(key)
            return raw.get("rendered") if isinstance(raw, dict) else raw

        comparisons = {
            "title": (
                expected_payload.get("title"),
                rendered_field("title"),
            ),
            "status": (expected_payload.get("status"), result.remote_status),
            "slug": (expected_payload.get("slug"), result.remote_slug),
            "excerpt": (
                expected_payload.get("excerpt"),
                rendered_field("excerpt"),
            ),
            "categories": (
                expected_payload.get("categories", []),
                remote_payload.get("categories"),
            ),
            "tags": (expected_payload.get("tags", []), remote_payload.get("tags")),
            "author": (expected_payload.get("author"), remote_payload.get("author")),
            "featured_media": (
                value.result_json.get("featured_media") if value.result_json else None,
                remote_payload.get("featured_media"),
            ),
            "modified": (
                None,
                remote_payload.get("modified_gmt") or remote_payload.get("modified"),
            ),
        }
        for field, (expected_field, remote) in comparisons.items():
            status_value: Literal["in_sync", "changed_remotely", "unknown"] = (
                "unknown"
                if remote is None
                else (
                    "in_sync"
                    if expected_field == remote or expected_field is None
                    else "changed_remotely"
                )
            )
            differences.append(
                RemoteDriftField(
                    field=field,
                    expected=expected_field,
                    remote=remote,
                    status=status_value,
                )
            )
            if status_value == "changed_remotely":
                drift.append(field)
        if value.external_url and value.external_url != result.external_url:
            drift.append("url")
        value.remote_status = result.remote_status
        value.remote_slug = result.remote_slug
        value.external_url = result.external_url
        value.reconciliation_status = "changed_remotely" if drift else "in_sync"
    except StopIteration:
        pass
    except ConnectorFailure as error:
        value.reconciliation_status = (
            "missing_remotely"
            if error.code in {"wordpress_not_found", "shopify_not_found"}
            else "reconciliation_failed"
        )
        drift = (
            ["remote_missing"] if error.code in {"wordpress_not_found", "shopify_not_found"} else []
        )
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
        differences=differences,
        correlation_id=correlation_id(),
    )


def shopify_overwrite_preview(
    db: Session, owner: User, execution_id: uuid.UUID
) -> ShopifyOverwritePreview:
    reconciliation = reconcile_execution(db, owner, execution_id)
    execution = owned_execution(db, owner.id, execution_id)
    if execution.connector_key != "shopify":
        raise HTTPException(409, "Overwrite preview is available only for Shopify executions.")
    fields = [
        item.field
        for item in reconciliation.differences
        if item.status == "changed_remotely" and item.resolution == "overwrite"
    ]
    record_event(
        db,
        actor_id=owner.id,
        action="publishing.shopify_overwrite_previewed",
        entity_type="publishing_execution",
        entity_id=execution.id,
        metadata={"field_count": len(fields), "correlation_id": execution.correlation_id},
    )
    db.commit()
    return ShopifyOverwritePreview(
        execution_id=execution.id,
        reconciliation_status=reconciliation.reconciliation_status,
        fields_available=fields,
        remote_only_fields_preserved=[
            "inventory_quantity",
            "remote_only_variants",
            "remote_only_media",
            "unrelated_metafields",
        ],
        differences=reconciliation.differences,
        correlation_id=execution.correlation_id,
    )


def confirm_shopify_overwrite(
    db: Session,
    owner: User,
    execution_id: uuid.UUID,
    confirmation: ShopifyOverwriteConfirmation,
) -> ExecutionResponse:
    preview = shopify_overwrite_preview(db, owner, execution_id)
    requested = list(dict.fromkeys(confirmation.fields))
    if any(field not in preview.fields_available for field in requested):
        raise HTTPException(409, "Overwrite fields must come from the refreshed drift preview.")
    source = owned_execution(db, owner.id, execution_id)
    artifact = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == source.artifact_id,
            GeneratedArtifact.owner_id == owner.id,
            GeneratedArtifact.status == "approved",
        )
    )
    destination = owned_destination(db, owner.id, source.destination_id)
    if not artifact or destination.status != "active":
        raise HTTPException(409, "The approved Artifact and active destination are required.")
    field_key = hashlib.sha256("|".join(sorted(requested)).encode()).hexdigest()[:16]
    record_event(
        db,
        actor_id=owner.id,
        action="publishing.shopify_remote_overwrite_confirmed",
        entity_type="publishing_execution",
        entity_id=source.id,
        metadata={
            "fields": requested,
            "correlation_id": source.correlation_id,
            "inventory_quantity_preserved": True,
        },
    )
    db.commit()
    return create_execution(
        db,
        owner,
        CreateExecution.model_validate(
            {
                "artifact_id": source.artifact_id,
                "destination_id": source.destination_id,
                "idempotency_key": f"overwrite:{source.id}:{field_key}",
                "action": "update",
                "shopify_variants": source.request_snapshot_json.get("shopify_variants", []),
                "shopify_media": source.request_snapshot_json.get("shopify_media", []),
            }
        ),
    )


def shopify_assignment_removal_preview(
    db: Session,
    owner: User,
    execution_id: uuid.UUID,
    assignment_type: Literal["collection", "publication"],
) -> ShopifyAssignmentRemovalPreview:
    execution = owned_execution(db, owner.id, execution_id)
    if execution.connector_key != "shopify" or not execution.remote_entity_id:
        raise HTTPException(409, "A mapped Shopify Product is required.")
    reconcile_execution(db, owner, execution_id)
    assignments = list(
        db.scalars(
            select(ShopifyProductAssignment).where(
                ShopifyProductAssignment.owner_id == owner.id,
                ShopifyProductAssignment.destination_id == execution.destination_id,
                ShopifyProductAssignment.product_id == execution.product_id,
                ShopifyProductAssignment.assignment_type == assignment_type,
                ShopifyProductAssignment.status == "assigned",
            )
        )
    )
    removable = sorted(item.remote_target_id for item in assignments if item.managed_by_vayujit)
    configuration = execution.request_snapshot_json.get("configuration")
    settings = configuration if isinstance(configuration, dict) else {}
    required = (
        [
            str(value)
            for value in settings.get("default_publication_ids", [])
            if isinstance(value, str)
        ]
        if assignment_type == "publication"
        else []
    )
    record_event(
        db,
        actor_id=owner.id,
        action=f"publishing.shopify_{assignment_type}_removal_previewed",
        entity_type="publishing_execution",
        entity_id=execution.id,
        metadata={"managed_count": len(removable)},
    )
    db.commit()
    return ShopifyAssignmentRemovalPreview(
        execution_id=execution.id,
        assignment_type=assignment_type,
        removable_target_ids=removable,
        preserved_target_ids=[],
        required_target_ids=required,
        activation_impact=(
            "Removing a required publication leaves the Product partially published "
            "and blocks activation."
            if assignment_type == "publication" and set(removable) & set(required)
            else "The remote Product and unrelated assignments are preserved."
        ),
        correlation_id=execution.correlation_id,
    )


def confirm_shopify_assignment_removal(
    db: Session,
    owner: User,
    execution_id: uuid.UUID,
    data: ShopifyAssignmentRemovalRequest,
) -> ExecutionResponse:
    if maintenance_enabled():
        raise HTTPException(503, "Publishing changes are unavailable during maintenance.")
    execution = owned_execution(db, owner.id, execution_id)
    artifact = db.get(GeneratedArtifact, execution.artifact_id)
    destination = owned_destination(db, owner.id, execution.destination_id)
    if not artifact or artifact.status != "approved":
        raise HTTPException(409, "The Artifact must remain approved.")
    if destination.status != "active":
        raise HTTPException(409, "The Shopify destination must remain enabled.")
    preview = shopify_assignment_removal_preview(db, owner, execution_id, data.assignment_type)
    selected = set(data.remote_target_ids)
    if not selected.issubset(set(preview.removable_target_ids)):
        raise HTTPException(
            409, "Only VAYUJIT-managed assignments from the refreshed preview may be removed."
        )
    connector_value = shopify_connector_for(
        owned_shopify_configuration(db, owner.id), resolve_dns=False
    )
    for target_id in sorted(selected):
        assignment = db.scalar(
            select(ShopifyProductAssignment).where(
                ShopifyProductAssignment.owner_id == owner.id,
                ShopifyProductAssignment.destination_id == execution.destination_id,
                ShopifyProductAssignment.product_id == execution.product_id,
                ShopifyProductAssignment.assignment_type == data.assignment_type,
                ShopifyProductAssignment.remote_target_id == target_id,
                ShopifyProductAssignment.managed_by_vayujit.is_(True),
            )
        )
        if not assignment:
            raise HTTPException(409, "The selected assignment is no longer removable.")
        if data.assignment_type == "collection":
            connector_value.remove_collection_assignment(
                product_id=execution.remote_entity_id or "", collection_id=target_id
            )
        else:
            connector_value.remove_publication_assignment(
                product_id=execution.remote_entity_id or "", publication_id=target_id
            )
        assignment.status = "removed"
        assignment.updated_at = now()
        assignment.last_verified_at = assignment.updated_at
        record_event(
            db,
            actor_id=owner.id,
            action=f"publishing.shopify_{data.assignment_type}_removed",
            entity_type="shopify_product_assignment",
            entity_id=assignment.id,
            metadata={"remote_target_id": target_id},
        )
    if data.assignment_type == "publication" and selected & set(preview.required_target_ids):
        execution.reconciliation_status = "partially_published"
        record_event(
            db,
            actor_id=owner.id,
            action="publishing.shopify_partial_publication_detected",
            entity_type="publishing_execution",
            entity_id=execution.id,
            metadata={"missing_required_count": len(selected & set(preview.required_target_ids))},
        )
    db.commit()
    reconcile_execution(db, owner, execution_id)
    return execution_response(db, owned_execution(db, owner.id, execution_id))


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
