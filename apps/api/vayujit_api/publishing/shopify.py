import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.credentials import decrypt_credential, encrypt_credential
from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.publishing.models import ShopifyConnectorConfiguration
from vayujit_api.publishing.schemas import ShopifyConnectorResponse, ShopifyConnectorUpdate
from vayujit_api.publishing.shopify_connector import (
    ShopifyGraphQLClient,
    validate_api_version,
    validate_shop_domain,
)


def capabilities() -> dict[str, bool]:
    return {
        "supports_product_draft": True,
        "supports_product_activation": True,
        "supports_product_update": True,
        "supports_media": True,
        "supports_collections": True,
        "supports_publications": True,
        "supports_variants": True,
        "supports_inventory_quantity_write": False,
        "supports_seo": True,
        "supports_remote_status_lookup": True,
        "supports_idempotency_key": True,
        "supports_unpublish": True,
        "supports_delete": False,
    }


def owned_configuration(db: Session, owner_id: uuid.UUID) -> ShopifyConnectorConfiguration | None:
    return db.scalar(
        select(ShopifyConnectorConfiguration).where(
            ShopifyConnectorConfiguration.owner_id == owner_id
        )
    )


def credentials_for(
    value: ShopifyConnectorConfiguration | None,
) -> tuple[str | None, str | None, str, str]:
    settings = get_settings()
    if value and value.encrypted_access_token:
        return (
            value.shop_domain,
            decrypt_credential(value.encrypted_access_token, settings.credential_encryption_key),
            value.api_version,
            "application",
        )
    if settings.shopify_shop_domain and settings.shopify_admin_api_access_token:
        return (
            validate_shop_domain(settings.shopify_shop_domain),
            settings.shopify_admin_api_access_token,
            validate_api_version(settings.shopify_api_version),
            "deployment",
        )
    return (
        value.shop_domain if value else settings.shopify_shop_domain,
        None,
        value.api_version if value else settings.shopify_api_version,
        "not_configured",
    )


def response_for(value: ShopifyConnectorConfiguration | None) -> ShopifyConnectorResponse:
    domain, token, api_version, source = credentials_for(value)
    return ShopifyConnectorResponse(
        configured=bool(domain and token),
        credential_source=source,
        shop_domain=domain or "",
        api_version=api_version,
        enabled=bool(value and value.enabled),
        default_product_status=value.default_product_status if value else "draft",
        inventory_policy=value.inventory_policy if value else "no_inventory_write",
        variant_policy=value.variant_policy if value else "default_variant",
        media_policy=value.media_policy if value else "fail",
        default_publication_ids=value.default_publication_ids_json if value else [],
        request_timeout_seconds=value.request_timeout_seconds if value else 45,
        max_retry_attempts=value.max_retry_attempts if value else 3,
        validation_status=value.validation_status if value else "unknown",
        safe_validation_message=value.safe_validation_message if value else None,
        last_validated_at=value.last_validated_at if value else None,
        last_validation_latency_ms=value.last_validation_latency_ms if value else None,
        capabilities={
            key: bool(item)
            for key, item in (value.capabilities_json if value else capabilities()).items()
        },
    )


def save_configuration(
    db: Session, owner: User, data: ShopifyConnectorUpdate
) -> ShopifyConnectorResponse:
    settings = get_settings()
    domain = validate_shop_domain(data.shop_domain)
    api_version = validate_api_version(data.api_version)
    value = owned_configuration(db, owner.id)
    stamp = now()
    if not value:
        value = ShopifyConnectorConfiguration(
            owner_id=owner.id,
            shop_domain=domain,
            api_version=api_version,
            credential_version=1,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(value)
    credential_changed = data.access_token is not None
    value.shop_domain = domain
    value.api_version = api_version
    value.enabled = False
    value.default_product_status = data.default_product_status
    value.inventory_policy = data.inventory_policy
    value.variant_policy = data.variant_policy
    value.media_policy = data.media_policy
    value.default_publication_ids_json = data.default_publication_ids
    value.request_timeout_seconds = data.request_timeout_seconds
    value.max_retry_attempts = data.max_retry_attempts
    value.validation_status = "unknown"
    value.safe_validation_message = "Validate the Shopify connection before enabling it."
    value.updated_at = stamp
    if data.access_token is not None:
        value.encrypted_access_token = encrypt_credential(
            data.access_token, settings.credential_encryption_key
        )
        value.credential_version = (value.credential_version or 0) + 1
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action=(
            "publishing.shopify_credential_replaced"
            if credential_changed
            else "publishing.shopify_configured"
        ),
        entity_type="shopify_connector_configuration",
        entity_id=value.id,
        metadata={"connector": "shopify", "credential_changed": credential_changed},
    )
    db.commit()
    return response_for(value)


def connector_for(
    value: ShopifyConnectorConfiguration | None,
    *,
    transport: object | None = None,
    resolve_dns: bool = True,
) -> ShopifyGraphQLClient:
    domain, token, api_version, _source = credentials_for(value)
    if not domain or not token:
        raise ValueError("Shopify connector credentials are not configured.")
    return ShopifyGraphQLClient(
        shop_domain=domain,
        access_token=token,
        api_version=api_version,
        timeout_seconds=value.request_timeout_seconds if value else 45,
        transport=transport,  # type: ignore[arg-type]
        resolve_dns=resolve_dns,
    )


def remove_credential(db: Session, owner: User) -> ShopifyConnectorResponse:
    value = owned_configuration(db, owner.id)
    if not value:
        raise ValueError("Shopify is not configured.")
    value.encrypted_access_token = None
    value.enabled = False
    value.validation_status = "unknown"
    value.safe_validation_message = "Application credential removed."
    value.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action="publishing.shopify_credential_removed",
        entity_type="shopify_connector_configuration",
        entity_id=value.id,
        metadata={"connector": "shopify"},
    )
    db.commit()
    return response_for(value)
