"""Meesho operations executed by the shared durable publishing worker."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.commerce.meesho import MeeshoCommerceConnector
from vayujit_api.commerce.models import MarketplaceAccount
from vayujit_api.publishing.models import PublishingJob


@dataclass(frozen=True)
class MeeshoJobResult:
    status: str
    retryable: bool = False
    ambiguous: bool = False
    error_code: str | None = None
    safe_message: str | None = None
    remote_id: str | None = None


def job_connector_key(account_id: uuid.UUID) -> str:
    return f"meesho:{account_id}"


def parse_account_id(connector_key: str) -> uuid.UUID | None:
    if not connector_key.startswith("meesho:"):
        return None
    try:
        return uuid.UUID(connector_key.split(":", 1)[1])
    except (ValueError, IndexError):
        return None


def idempotency_key(
    *, operation: str, account_id: uuid.UUID, resource_id: uuid.UUID, fingerprint: str
) -> str:
    digest = hashlib.sha256(
        f"{operation}:{account_id}:{resource_id}:{fingerprint}".encode()
    ).hexdigest()[:32]
    return f"meesho:{operation}:{digest}"


def execute_meesho_job(
    db: Session, job: PublishingJob, *, account_id: uuid.UUID
) -> MeeshoJobResult:
    account = db.scalar(
        select(MarketplaceAccount).where(
            MarketplaceAccount.id == account_id, MarketplaceAccount.marketplace == "meesho"
        )
    )
    if account is None:
        return MeeshoJobResult(
            "failed",
            error_code="meesho_account_missing",
            safe_message="Meesho account was not found.",
        )
    if not account.enabled:
        return MeeshoJobResult(
            "failed",
            error_code="meesho_account_disabled",
            safe_message="Meesho account is disabled.",
        )
    connector = MeeshoCommerceConnector(seller_id=account.seller_account_id)
    if job.requested_action in {"listing_submission", "submit"}:
        result = connector.submit(
            sku=job.idempotency_key,
            payload={"title": "Durable Meesho listing"},
            idempotency_key=job.idempotency_key,
        )
        return MeeshoJobResult(
            "succeeded" if result.remote_id else "failed",
            retryable=result.retryable,
            ambiguous=result.ambiguous,
            remote_id=result.remote_id,
            safe_message=None if result.remote_id else "Meesho listing submission failed.",
        )
    return MeeshoJobResult(
        "failed",
        error_code="unsupported_meesho_job",
        safe_message="The requested Meesho operation is not supported by this worker.",
    )
