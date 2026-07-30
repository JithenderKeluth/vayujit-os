import math
import uuid
from datetime import datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.database import get_session
from vayujit_api.core.observability import correlation_id
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.identity.service import now
from vayujit_api.publishing.connector import ConnectorFailure, WordPressConnector, connector
from vayujit_api.publishing.models import PublishingDestination, PublishingExecution
from vayujit_api.publishing.schemas import (
    AttemptResponse,
    CreateExecution,
    DestinationResponse,
    DestinationUpdate,
    DestinationWrite,
    ExecutionResponse,
    Page,
    PublishingPreviewRequest,
    PublishingPreviewResponse,
    ReconciliationResponse,
    ShopifyConnectorResponse,
    ShopifyConnectorUpdate,
    ShopifyDiscoveryPage,
    ShopifyOverwriteConfirmation,
    ShopifyOverwritePreview,
    ShopifyPreviewResponse,
    ShopifyValidationResult,
    WordPressConnectorResponse,
    WordPressConnectorUpdate,
    WordPressTaxonomyPage,
    WordPressValidationResult,
)
from vayujit_api.publishing.service import (
    cancel_execution,
    confirm_shopify_overwrite,
    create_destination,
    create_execution,
    destination_response,
    execution_response,
    keep_remote_changes,
    move_execution_to_draft,
    owned_destination,
    owned_execution,
    publishing_preview,
    reconcile_execution,
    retry_execution,
    set_destination_status,
    shopify_overwrite_preview,
    shopify_publishing_preview,
    update_destination,
)
from vayujit_api.publishing.shopify import (
    capabilities as shopify_capabilities,
)
from vayujit_api.publishing.shopify import (
    connector_for as shopify_connector_for,
)
from vayujit_api.publishing.shopify import (
    owned_configuration as owned_shopify_configuration,
)
from vayujit_api.publishing.shopify import (
    remove_credential as remove_shopify_credential,
)
from vayujit_api.publishing.shopify import (
    response_for as shopify_response_for,
)
from vayujit_api.publishing.shopify import (
    save_configuration as save_shopify_configuration,
)
from vayujit_api.publishing.shopify_discovery import (
    discover as shopify_discover,
)
from vayujit_api.publishing.shopify_discovery import (
    invalidate as invalidate_shopify,
)
from vayujit_api.publishing.taxonomy import discover, invalidate
from vayujit_api.publishing.wordpress import (
    capabilities,
    connector_for,
    owned_configuration,
    remove_credential,
    response_for,
    save_configuration,
)

router = APIRouter(prefix="/api/v1/publishing", tags=["publishing"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.get("/connectors")
def connectors(owner: Owner) -> list[dict[str, object]]:
    wordpress = WordPressConnector
    return [
        {
            "key": connector.key,
            "name": connector.name,
            "connector_type": connector.connector_type,
            "available": connector.available(),
            "deterministic": True,
            "local": True,
        },
        {
            "key": wordpress.key,
            "name": wordpress.name,
            "connector_type": wordpress.connector_type,
            "available": True,
            "deterministic": False,
            "local": False,
            "capabilities": capabilities(),
        },
        {
            "key": "shopify",
            "name": "Shopify",
            "connector_type": "remote",
            "available": True,
            "deterministic": False,
            "local": False,
            "capabilities": shopify_capabilities(),
        },
    ]


@router.get("/connectors/shopify", response_model=ShopifyConnectorResponse)
def shopify_configuration(db: DB, owner: Owner) -> ShopifyConnectorResponse:
    return shopify_response_for(owned_shopify_configuration(db, owner.id))


@router.put("/connectors/shopify", response_model=ShopifyConnectorResponse)
def shopify_configuration_update(
    data: ShopifyConnectorUpdate, db: DB, owner: Owner
) -> ShopifyConnectorResponse:
    try:
        result = save_shopify_configuration(db, owner, data)
        invalidate_shopify(owner.id)
        return result
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/connectors/shopify/validate", response_model=ShopifyValidationResult)
def shopify_validate(db: DB, owner: Owner) -> ShopifyValidationResult:
    value = owned_shopify_configuration(db, owner.id)
    if not value:
        raise HTTPException(409, "Shopify is not configured.")
    started = now()
    try:
        data = shopify_connector_for(value).validate()
        shop = data.get("shop")
        if not isinstance(shop, dict):
            raise ValueError("Shopify shop identity response was invalid.")
        latency = max(int((now() - started).total_seconds() * 1000), 0)
        value.validation_status = "valid"
        value.safe_validation_message = "Shopify Admin API credentials are valid."
        value.capabilities_json = cast(dict[str, object], shopify_capabilities())
        valid = True
    except (ValueError, ConnectorFailure) as error:
        latency = max(int((now() - started).total_seconds() * 1000), 0)
        value.validation_status = "invalid"
        value.safe_validation_message = (
            error.safe_message
            if isinstance(error, ConnectorFailure)
            else "Shopify credentials or store configuration are invalid."
        )
        shop, valid = {}, False
    value.last_validated_at = value.updated_at = now()
    value.last_validation_latency_ms = latency
    record_event(
        db,
        actor_id=owner.id,
        action=(
            "publishing.shopify_validated" if valid else "publishing.shopify_validation_failed"
        ),
        entity_type="shopify_connector_configuration",
        entity_id=value.id,
        metadata={"connector": "shopify", "valid": valid},
    )
    db.commit()
    primary = shop.get("primaryDomain")
    return ShopifyValidationResult(
        valid=valid,
        safe_message=value.safe_validation_message or "",
        shop_domain=value.shop_domain,
        api_version=value.api_version,
        shop_id=str(shop["id"]) if shop.get("id") else None,
        shop_name=str(shop["name"])[:160] if shop.get("name") else None,
        primary_domain=(
            str(primary["host"])[:255]
            if isinstance(primary, dict) and primary.get("host")
            else None
        ),
        capabilities=shopify_capabilities(),
        latency_ms=latency,
        correlation_id=correlation_id(),
    )


def set_shopify_enabled(db: Session, owner: User, enabled: bool) -> ShopifyConnectorResponse:
    value = owned_shopify_configuration(db, owner.id)
    if not value:
        raise HTTPException(409, "Shopify is not configured.")
    if enabled and value.validation_status != "valid":
        raise HTTPException(409, "Validate Shopify before enabling it.")
    value.enabled = enabled
    value.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action=f"publishing.shopify_{'enabled' if enabled else 'disabled'}",
        entity_type="shopify_connector_configuration",
        entity_id=value.id,
        metadata={"connector": "shopify"},
    )
    db.commit()
    invalidate_shopify(owner.id)
    return shopify_response_for(value)


@router.post("/connectors/shopify/enable", response_model=ShopifyConnectorResponse)
def shopify_enable(db: DB, owner: Owner) -> ShopifyConnectorResponse:
    return set_shopify_enabled(db, owner, True)


@router.post("/connectors/shopify/disable", response_model=ShopifyConnectorResponse)
def shopify_disable(db: DB, owner: Owner) -> ShopifyConnectorResponse:
    return set_shopify_enabled(db, owner, False)


@router.delete("/connectors/shopify/credential", response_model=ShopifyConnectorResponse)
def shopify_credential_delete(db: DB, owner: Owner) -> ShopifyConnectorResponse:
    try:
        invalidate_shopify(owner.id)
        return remove_shopify_credential(db, owner)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error


def shopify_discovery_page(
    db: Session,
    owner: User,
    kind: str,
    search: str,
    cursor: str | None,
    page_size: int,
    refresh: bool,
) -> ShopifyDiscoveryPage:
    try:
        return shopify_discover(
            db,
            owner,
            cast(Any, kind),
            search=search,
            cursor=cursor,
            page_size=page_size,
            refresh=refresh,
        )
    except (ValueError, ConnectorFailure) as error:
        message = error.safe_message if isinstance(error, ConnectorFailure) else str(error)
        raise HTTPException(502, message) from error


@router.get("/connectors/shopify/collections", response_model=ShopifyDiscoveryPage)
def shopify_collections(
    db: DB,
    owner: Owner,
    search: Annotated[str, Query(max_length=100)] = "",
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    refresh: bool = False,
) -> ShopifyDiscoveryPage:
    return shopify_discovery_page(db, owner, "collections", search, cursor, page_size, refresh)


@router.get("/connectors/shopify/publications", response_model=ShopifyDiscoveryPage)
def shopify_publications(
    db: DB,
    owner: Owner,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    refresh: bool = False,
) -> ShopifyDiscoveryPage:
    return shopify_discovery_page(db, owner, "publications", "", cursor, page_size, refresh)


@router.get("/connectors/wordpress", response_model=WordPressConnectorResponse)
def wordpress_configuration(db: DB, owner: Owner) -> WordPressConnectorResponse:
    return response_for(owned_configuration(db, owner.id))


@router.put("/connectors/wordpress", response_model=WordPressConnectorResponse)
def wordpress_configuration_update(
    data: WordPressConnectorUpdate, db: DB, owner: Owner
) -> WordPressConnectorResponse:
    try:
        return save_configuration(db, owner, data)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/connectors/wordpress/validate", response_model=WordPressValidationResult)
def wordpress_validate(db: DB, owner: Owner) -> WordPressValidationResult:
    value = owned_configuration(db, owner.id)
    if not value:
        raise HTTPException(409, "WordPress is not configured.")
    started = now()
    try:
        remote_user = connector_for(value).validate()
        latency = max(int((now() - started).total_seconds() * 1000), 0)
        value.validation_status = "valid"
        value.safe_validation_message = "WordPress credentials and REST API are valid."
        value.capabilities_json = cast(dict[str, object], capabilities())
        valid = True
    except (ValueError, ConnectorFailure) as error:
        latency = max(int((now() - started).total_seconds() * 1000), 0)
        value.validation_status = "invalid"
        value.safe_validation_message = (
            error.safe_message
            if isinstance(error, ConnectorFailure)
            else "WordPress credentials are not configured."
        )
        remote_user = {}
        valid = False
    value.last_validated_at = now()
    value.last_validation_latency_ms = latency
    value.updated_at = value.last_validated_at
    record_event(
        db,
        actor_id=owner.id,
        action="publishing.connector_validated",
        entity_type="wordpress_connector_configuration",
        entity_id=value.id,
        metadata={"connector": "wordpress", "valid": valid},
    )
    db.commit()
    remote_user_id = remote_user.get("id")
    return WordPressValidationResult(
        valid=valid,
        safe_message=value.safe_validation_message or "",
        site_url=value.site_url,
        user_id=remote_user_id if isinstance(remote_user_id, int) else None,
        display_name=(
            str(remote_user["name"])[:160] if isinstance(remote_user.get("name"), str) else None
        ),
        capabilities=capabilities(),
        latency_ms=latency,
        correlation_id=correlation_id(),
    )


def set_wordpress_enabled(db: Session, owner: User, enabled: bool) -> WordPressConnectorResponse:
    value = owned_configuration(db, owner.id)
    if not value:
        raise HTTPException(409, "WordPress is not configured.")
    if enabled and value.validation_status != "valid":
        raise HTTPException(409, "Validate WordPress before enabling it.")
    value.enabled = enabled
    value.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action=f"publishing.connector_{'enabled' if enabled else 'disabled'}",
        entity_type="wordpress_connector_configuration",
        entity_id=value.id,
        metadata={"connector": "wordpress"},
    )
    db.commit()
    invalidate(owner.id)
    return response_for(value)


@router.post("/connectors/wordpress/enable", response_model=WordPressConnectorResponse)
def wordpress_enable(db: DB, owner: Owner) -> WordPressConnectorResponse:
    return set_wordpress_enabled(db, owner, True)


@router.post("/connectors/wordpress/disable", response_model=WordPressConnectorResponse)
def wordpress_disable(db: DB, owner: Owner) -> WordPressConnectorResponse:
    return set_wordpress_enabled(db, owner, False)


@router.delete("/connectors/wordpress/credential", response_model=WordPressConnectorResponse)
def wordpress_credential_delete(db: DB, owner: Owner) -> WordPressConnectorResponse:
    try:
        return remove_credential(db, owner)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error


def taxonomy_page(
    db: Session,
    owner: User,
    kind: str,
    search: str,
    page: int,
    page_size: int,
    refresh: bool,
) -> WordPressTaxonomyPage:
    try:
        return discover(
            db,
            owner,
            kind,
            search=search,
            page=page,
            page_size=page_size,
            refresh=refresh,
        )
    except (ValueError, ConnectorFailure) as error:
        message = error.safe_message if isinstance(error, ConnectorFailure) else str(error)
        raise HTTPException(502, message) from error


@router.get("/connectors/wordpress/categories", response_model=WordPressTaxonomyPage)
def wordpress_categories(
    db: DB,
    owner: Owner,
    search: Annotated[str, Query(max_length=100)] = "",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    refresh: bool = False,
) -> WordPressTaxonomyPage:
    return taxonomy_page(db, owner, "categories", search, page, page_size, refresh)


@router.get("/connectors/wordpress/tags", response_model=WordPressTaxonomyPage)
def wordpress_tags(
    db: DB,
    owner: Owner,
    search: Annotated[str, Query(max_length=100)] = "",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    refresh: bool = False,
) -> WordPressTaxonomyPage:
    return taxonomy_page(db, owner, "tags", search, page, page_size, refresh)


@router.get("/connectors/wordpress/authors", response_model=WordPressTaxonomyPage)
def wordpress_authors(
    db: DB,
    owner: Owner,
    search: Annotated[str, Query(max_length=100)] = "",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    refresh: bool = False,
) -> WordPressTaxonomyPage:
    return taxonomy_page(db, owner, "authors", search, page, page_size, refresh)


@router.get("/destinations", response_model=Page)
def destinations(
    db: DB,
    owner: Owner,
    brand_id: uuid.UUID | None = None,
    connector_key: str | None = None,
    status: str | None = None,
    search: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page:
    filters = [PublishingDestination.owner_id == owner.id]
    if brand_id:
        filters.append(PublishingDestination.brand_id == brand_id)
    if connector_key:
        filters.append(PublishingDestination.connector_key == connector_key)
    if status:
        filters.append(PublishingDestination.status == status)
    if search:
        filters.append(
            or_(
                PublishingDestination.name.ilike(f"%{search}%"),
                PublishingDestination.normalized_name.ilike(f"%{search.casefold()}%"),
            )
        )
    total = db.scalar(select(func.count()).select_from(PublishingDestination).where(*filters)) or 0
    values = db.scalars(
        select(PublishingDestination)
        .where(*filters)
        .order_by(PublishingDestination.name, PublishingDestination.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Page(
        items=[destination_response(db, value) for value in values],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/destinations", response_model=DestinationResponse, status_code=201)
def destination_create(data: DestinationWrite, db: DB, owner: Owner) -> DestinationResponse:
    return create_destination(db, owner, data)


@router.get("/destinations/{destination_id}", response_model=DestinationResponse)
def destination_get(destination_id: uuid.UUID, db: DB, owner: Owner) -> DestinationResponse:
    return destination_response(db, owned_destination(db, owner.id, destination_id))


@router.patch("/destinations/{destination_id}", response_model=DestinationResponse)
def destination_patch(
    destination_id: uuid.UUID, data: DestinationUpdate, db: DB, owner: Owner
) -> DestinationResponse:
    return update_destination(db, owner, owned_destination(db, owner.id, destination_id), data)


@router.post("/destinations/{destination_id}/disable", response_model=DestinationResponse)
def destination_disable(destination_id: uuid.UUID, db: DB, owner: Owner) -> DestinationResponse:
    return set_destination_status(
        db, owner, owned_destination(db, owner.id, destination_id), "disabled"
    )


@router.post("/destinations/{destination_id}/enable", response_model=DestinationResponse)
def destination_enable(destination_id: uuid.UUID, db: DB, owner: Owner) -> DestinationResponse:
    return set_destination_status(
        db, owner, owned_destination(db, owner.id, destination_id), "active"
    )


@router.post("/executions", response_model=ExecutionResponse, status_code=201)
def execution_create(data: CreateExecution, db: DB, owner: Owner) -> ExecutionResponse:
    return create_execution(db, owner, data)


@router.post("/preview", response_model=PublishingPreviewResponse)
def preview_create(
    data: PublishingPreviewRequest, db: DB, owner: Owner
) -> PublishingPreviewResponse:
    return publishing_preview(db, owner, data)


@router.post("/preview/shopify", response_model=ShopifyPreviewResponse)
def shopify_preview_create(
    data: PublishingPreviewRequest, db: DB, owner: Owner
) -> ShopifyPreviewResponse:
    return shopify_publishing_preview(db, owner, data)


@router.get("/executions", response_model=Page)
def executions(
    db: DB,
    owner: Owner,
    product_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
    artifact_id: uuid.UUID | None = None,
    destination_id: uuid.UUID | None = None,
    connector_key: str | None = None,
    status: str | None = None,
    retryable: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page:
    filters = [PublishingExecution.owner_id == owner.id]
    for column, value in (
        (PublishingExecution.product_id, product_id),
        (PublishingExecution.brand_id, brand_id),
        (PublishingExecution.artifact_id, artifact_id),
        (PublishingExecution.destination_id, destination_id),
        (PublishingExecution.connector_key, connector_key),
        (PublishingExecution.status, status),
        (PublishingExecution.retryable, retryable),
    ):
        if value is not None:
            filters.append(column == value)
    if date_from:
        filters.append(PublishingExecution.created_at >= date_from)
    if date_to:
        filters.append(PublishingExecution.created_at <= date_to)
    total = db.scalar(select(func.count()).select_from(PublishingExecution).where(*filters)) or 0
    values = db.scalars(
        select(PublishingExecution)
        .where(*filters)
        .order_by(PublishingExecution.created_at.desc(), PublishingExecution.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Page(
        items=[execution_response(db, value) for value in values],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
def execution_get(execution_id: uuid.UUID, db: DB, owner: Owner) -> ExecutionResponse:
    return execution_response(db, owned_execution(db, owner.id, execution_id))


@router.post("/executions/{execution_id}/retry", response_model=ExecutionResponse)
def execution_retry(execution_id: uuid.UUID, db: DB, owner: Owner) -> ExecutionResponse:
    return retry_execution(db, owner, execution_id)


@router.get("/executions/{execution_id}/attempts")
def execution_attempts(execution_id: uuid.UUID, db: DB, owner: Owner) -> list[AttemptResponse]:
    return execution_response(db, owned_execution(db, owner.id, execution_id)).attempts


@router.post("/executions/{execution_id}/cancel", response_model=ExecutionResponse)
def execution_cancel(execution_id: uuid.UUID, db: DB, owner: Owner) -> ExecutionResponse:
    return cancel_execution(db, owner, execution_id)


@router.post("/executions/{execution_id}/reconcile", response_model=ReconciliationResponse)
def execution_reconcile(execution_id: uuid.UUID, db: DB, owner: Owner) -> ReconciliationResponse:
    return reconcile_execution(db, owner, execution_id)


@router.post(
    "/executions/{execution_id}/overwrite-preview",
    response_model=ShopifyOverwritePreview,
)
def execution_overwrite_preview(
    execution_id: uuid.UUID, db: DB, owner: Owner
) -> ShopifyOverwritePreview:
    return shopify_overwrite_preview(db, owner, execution_id)


@router.post("/executions/{execution_id}/overwrite", response_model=ExecutionResponse)
def execution_overwrite(
    execution_id: uuid.UUID,
    data: ShopifyOverwriteConfirmation,
    db: DB,
    owner: Owner,
) -> ExecutionResponse:
    return confirm_shopify_overwrite(db, owner, execution_id, data)


@router.post("/executions/{execution_id}/move-to-draft", response_model=ExecutionResponse)
def execution_move_to_draft(execution_id: uuid.UUID, db: DB, owner: Owner) -> ExecutionResponse:
    return move_execution_to_draft(db, owner, execution_id)


@router.post("/executions/{execution_id}/keep-remote", response_model=ExecutionResponse)
def execution_keep_remote(execution_id: uuid.UUID, db: DB, owner: Owner) -> ExecutionResponse:
    return keep_remote_changes(db, owner, execution_id)
