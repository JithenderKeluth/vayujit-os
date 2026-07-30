import time
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.credentials import (
    decrypt_credential,
    encrypt_credential,
    mask_credential,
)
from vayujit_api.ai.models import AIProviderConfiguration
from vayujit_api.ai.provider import (
    ModelInfo,
    OpenAICompatibleProvider,
    ProviderError,
    validate_base_url,
    validate_model_identifier,
)
from vayujit_api.ai.schemas import (
    ProviderConfigurationResponse,
    ProviderConfigurationUpdate,
)
from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now

PROVIDER_KEY = "openai_compatible"


@dataclass
class CachedModels:
    expires_at: float
    values: list[ModelInfo]


model_cache: dict[uuid.UUID, CachedModels] = {}


def owned_configuration(
    db: Session, owner_id: uuid.UUID, *, required: bool = False
) -> AIProviderConfiguration | None:
    value = db.scalar(
        select(AIProviderConfiguration).where(
            AIProviderConfiguration.owner_id == owner_id,
            AIProviderConfiguration.provider_key == PROVIDER_KEY,
        )
    )
    if required and value is None:
        raise ProviderError("provider_not_configured", "The real AI provider is not configured.")
    return value


def credential_for(
    configuration: AIProviderConfiguration | None,
) -> tuple[str | None, Literal["application", "deployment", "not_configured"]]:
    settings = get_settings()
    if configuration and configuration.encrypted_api_key:
        return (
            decrypt_credential(configuration.encrypted_api_key, settings.credential_encryption_key),
            "application",
        )
    if settings.openai_api_key:
        return settings.openai_api_key, "deployment"
    return None, "not_configured"


def response_for_configuration(
    configuration: AIProviderConfiguration | None,
) -> ProviderConfigurationResponse:
    credential, source = credential_for(configuration)
    return ProviderConfigurationResponse(
        provider_key=PROVIDER_KEY,
        display_name="OpenAI-compatible",
        configured=credential is not None,
        credential_source=source,
        masked_credential=mask_credential(credential) if credential else None,
        base_url=configuration.base_url if configuration else "https://api.openai.com/v1",
        default_model=configuration.default_model if configuration else "",
        manual_model_allowed=configuration.manual_model_allowed if configuration else False,
        enabled=configuration.enabled if configuration else False,
        fallback_provider_key=configuration.fallback_provider_key if configuration else None,
        request_timeout_seconds=configuration.request_timeout_seconds if configuration else 45,
        max_retry_attempts=configuration.max_retry_attempts if configuration else 3,
        validation_status=configuration.validation_status if configuration else "unknown",
        safe_validation_message=(configuration.safe_validation_message if configuration else None),
        last_validated_at=configuration.last_validated_at if configuration else None,
        last_validation_latency_ms=(
            configuration.last_validation_latency_ms if configuration else None
        ),
    )


def save_configuration(
    db: Session,
    owner: User,
    data: ProviderConfigurationUpdate,
) -> ProviderConfigurationResponse:
    settings = get_settings()
    base_url = validate_base_url(data.base_url, environment=settings.environment)
    validate_model_identifier(data.default_model)
    value = owned_configuration(db, owner.id)
    stamp = now()
    created = value is None
    if value is None:
        value = AIProviderConfiguration(
            owner_id=owner.id,
            provider_key=PROVIDER_KEY,
            display_name="OpenAI-compatible",
            base_url=base_url,
            default_model=data.default_model,
            created_at=stamp,
            updated_at=stamp,
            validation_status="unknown",
        )
        db.add(value)
    old_had_key = bool(value.encrypted_api_key)
    if data.api_key is not None:
        value.encrypted_api_key = encrypt_credential(
            data.api_key, settings.credential_encryption_key
        )
        value.credential_version = (value.credential_version or 0) + 1
        value.validation_status = "unknown"
        value.safe_validation_message = "Credential changed; validation is required."
    value.base_url = base_url
    value.default_model = data.default_model
    value.manual_model_allowed = data.manual_model_allowed
    value.enabled = data.enabled
    value.fallback_provider_key = data.fallback_provider_key
    value.request_timeout_seconds = data.request_timeout_seconds
    value.max_retry_attempts = data.max_retry_attempts
    value.updated_at = stamp
    db.flush()
    action = (
        "ai.provider_key_replaced"
        if data.api_key is not None and old_had_key
        else "ai.provider_configured"
    )
    record_event(
        db,
        actor_id=owner.id,
        action=action,
        entity_type="ai_provider_configuration",
        entity_id=value.id,
        metadata={
            "provider": PROVIDER_KEY,
            "enabled": value.enabled,
            "credential_changed": data.api_key is not None,
            "created": created,
        },
    )
    db.commit()
    model_cache.pop(owner.id, None)
    return response_for_configuration(value)


def provider_for(configuration: AIProviderConfiguration) -> OpenAICompatibleProvider:
    credential, _source = credential_for(configuration)
    if not credential:
        raise ProviderError("provider_not_configured", "The provider credential is not configured.")
    settings = get_settings()
    return OpenAICompatibleProvider(
        api_key=credential,
        base_url=configuration.base_url,
        timeout_seconds=configuration.request_timeout_seconds,
        max_attempts=configuration.max_retry_attempts,
        environment=settings.environment,
    )


def discover_models(db: Session, owner_id: uuid.UUID, *, refresh: bool = False) -> list[ModelInfo]:
    cached = model_cache.get(owner_id)
    if cached and not refresh and cached.expires_at > time.monotonic():
        return cached.values
    configuration = owned_configuration(db, owner_id, required=True)
    assert configuration is not None
    values = provider_for(configuration).discover_models()
    if not values:
        raise ProviderError("models_unavailable", "The provider returned no usable models.")
    model_cache[owner_id] = CachedModels(
        time.monotonic() + get_settings().ai_model_cache_seconds, values
    )
    return values


def remove_credential(db: Session, owner: User) -> ProviderConfigurationResponse:
    value = owned_configuration(db, owner.id, required=True)
    assert value is not None
    value.encrypted_api_key = None
    value.enabled = False
    value.validation_status = "unknown"
    value.safe_validation_message = "Application credential removed."
    value.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.provider_key_removed",
        entity_type="ai_provider_configuration",
        entity_id=value.id,
        metadata={"provider": PROVIDER_KEY},
    )
    db.commit()
    model_cache.pop(owner.id, None)
    return response_for_configuration(value)


def set_enabled(db: Session, owner: User, enabled: bool) -> ProviderConfigurationResponse:
    value = owned_configuration(db, owner.id, required=True)
    assert value is not None
    if enabled:
        credential, _source = credential_for(value)
        if not credential:
            raise ProviderError("provider_not_configured", "A provider credential is required.")
    value.enabled = enabled
    value.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action="ai.provider_enabled" if enabled else "ai.provider_disabled",
        entity_type="ai_provider_configuration",
        entity_id=value.id,
        metadata={"provider": PROVIDER_KEY},
    )
    db.commit()
    return response_for_configuration(value)
