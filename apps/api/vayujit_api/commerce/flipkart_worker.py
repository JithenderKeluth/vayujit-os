"""Flipkart operations executed by the shared durable publishing worker."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.commerce.flipkart import FlipkartCommerceConnector
from vayujit_api.commerce.models import MarketplaceAccount
from vayujit_api.publishing.models import PublishingJob


@dataclass(frozen=True)
class FlipkartJobResult:
    status: str
    retryable: bool = False
    ambiguous: bool = False
    error_code: str | None = None
    safe_message: str | None = None
    remote_id: str | None = None


def job_connector_key(account_id: uuid.UUID) -> str:
    return f"flipkart:{account_id}"


def parse_account_id(connector_key: str) -> uuid.UUID | None:
    if not connector_key.startswith("flipkart:"):
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
    return f"flipkart:{operation}:{digest}"


def execute_flipkart_job(
    db: Session, job: PublishingJob, *, account_id: uuid.UUID
) -> FlipkartJobResult:
    account = db.scalar(
        select(MarketplaceAccount).where(
            MarketplaceAccount.id == account_id, MarketplaceAccount.marketplace == "flipkart"
        )
    )
    if account is None:
        return FlipkartJobResult(
            "failed",
            error_code="flipkart_account_missing",
            safe_message="Flipkart account was not found.",
        )
    if not account.enabled:
        return FlipkartJobResult(
            "failed",
            error_code="flipkart_account_disabled",
            safe_message="Flipkart account is disabled.",
        )
    connector = FlipkartCommerceConnector(seller_id=account.seller_account_id)
    if job.requested_action in {"listing_submission", "submit"}:
        result = connector.submit(
            sku=job.idempotency_key,
            payload={"title": "Durable Flipkart listing"},
            idempotency_key=job.idempotency_key,
        )
        return FlipkartJobResult(
            "succeeded" if result.remote_id else "failed",
            retryable=result.retryable,
            ambiguous=result.ambiguous,
            remote_id=result.remote_id,
            safe_message=None if result.remote_id else "Flipkart listing submission failed.",
        )
    return FlipkartJobResult(
        "failed",
        error_code="unsupported_flipkart_job",
        safe_message="The requested Flipkart operation is not supported by this worker.",
    )
