import uuid
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.credentials import decrypt_credential, encrypt_credential
from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.publishing.connector import (
    WordPressConnector,
    validate_wordpress_site_url,
)
from vayujit_api.publishing.models import WordPressConnectorConfiguration
from vayujit_api.publishing.schemas import (
    WordPressConnectorResponse,
    WordPressConnectorUpdate,
)


def owned_configuration(db: Session, owner_id: uuid.UUID) -> WordPressConnectorConfiguration | None:
    return db.scalar(
        select(WordPressConnectorConfiguration).where(
            WordPressConnectorConfiguration.owner_id == owner_id
        )
    )


def credentials_for(
    value: WordPressConnectorConfiguration | None,
) -> tuple[
    str | None,
    str | None,
    str | None,
    Literal["application", "deployment", "not_configured"],
]:
    settings = get_settings()
    if value and value.encrypted_application_password:
        return (
            value.site_url,
            value.username,
            decrypt_credential(
                value.encrypted_application_password,
                settings.credential_encryption_key,
            ),
            "application",
        )
    if (
        settings.wordpress_site_url
        and settings.wordpress_username
        and settings.wordpress_application_password
    ):
        return (
            settings.wordpress_site_url,
            settings.wordpress_username,
            settings.wordpress_application_password,
            "deployment",
        )
    return (
        value.site_url if value else None,
        value.username if value else None,
        None,
        "not_configured",
    )


def capabilities() -> dict[str, bool]:
    return {
        name: bool(value)
        for name, value in WordPressConnector.capabilities.__dict__.items()
        if name.startswith("supports_")
    }


def response_for(
    value: WordPressConnectorConfiguration | None,
) -> WordPressConnectorResponse:
    site, username, password, source = credentials_for(value)
    masked = f"{username[:2]}•••{username[-1:]}" if username else None
    return WordPressConnectorResponse(
        configured=bool(site and username and password),
        credential_source=source,
        masked_username=masked,
        site_url=site or "",
        enabled=value.enabled if value else False,
        default_post_status=value.default_post_status if value else "draft",
        request_timeout_seconds=value.request_timeout_seconds if value else 45,
        max_retry_attempts=value.max_retry_attempts if value else 3,
        validation_status=value.validation_status if value else "unknown",
        safe_validation_message=value.safe_validation_message if value else None,
        last_validated_at=value.last_validated_at if value else None,
        last_validation_latency_ms=value.last_validation_latency_ms if value else None,
        capabilities=capabilities(),
    )


def save_configuration(
    db: Session, owner: User, data: WordPressConnectorUpdate
) -> WordPressConnectorResponse:
    settings = get_settings()
    site_url = validate_wordpress_site_url(data.site_url, environment=settings.environment)
    value = owned_configuration(db, owner.id)
    stamp = now()
    replacing = bool(value and value.encrypted_application_password and data.application_password)
    if value is None:
        value = WordPressConnectorConfiguration(
            owner_id=owner.id,
            site_url=site_url,
            username=data.username,
            created_at=stamp,
            updated_at=stamp,
            capabilities_json=capabilities(),
        )
        db.add(value)
    if data.application_password is not None:
        value.encrypted_application_password = encrypt_credential(
            data.application_password, settings.credential_encryption_key
        )
        value.credential_version = (value.credential_version or 0) + 1
        value.validation_status = "unknown"
    value.site_url = site_url
    value.username = data.username
    value.enabled = data.enabled
    value.default_post_status = data.default_post_status
    value.request_timeout_seconds = data.request_timeout_seconds
    value.max_retry_attempts = data.max_retry_attempts
    value.updated_at = stamp
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action=(
            "publishing.connector_credential_replaced"
            if replacing
            else "publishing.connector_configured"
        ),
        entity_type="wordpress_connector_configuration",
        entity_id=value.id,
        metadata={
            "connector": "wordpress",
            "enabled": value.enabled,
            "credential_changed": data.application_password is not None,
        },
    )
    db.commit()
    from vayujit_api.publishing.taxonomy import invalidate

    invalidate(owner.id)
    return response_for(value)


def connector_for(value: WordPressConnectorConfiguration) -> WordPressConnector:
    site, username, password, _source = credentials_for(value)
    if not site or not username or not password:
        raise ValueError("WordPress connector credentials are not configured.")
    return WordPressConnector(
        site_url=site,
        username=username,
        application_password=password,
        timeout_seconds=value.request_timeout_seconds,
        environment=get_settings().environment,
    )


def remove_credential(db: Session, owner: User) -> WordPressConnectorResponse:
    value = owned_configuration(db, owner.id)
    if value is None:
        raise ValueError("WordPress connector is not configured.")
    value.encrypted_application_password = None
    value.enabled = False
    value.validation_status = "unknown"
    value.safe_validation_message = "Application credential removed."
    value.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action="publishing.connector_credential_removed",
        entity_type="wordpress_connector_configuration",
        entity_id=value.id,
        metadata={"connector": "wordpress"},
    )
    db.commit()
    from vayujit_api.publishing.taxonomy import invalidate

    invalidate(owner.id)
    return response_for(value)
