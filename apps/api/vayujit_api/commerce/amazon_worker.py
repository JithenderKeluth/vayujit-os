"""Amazon jobs executed by the existing durable Publishing worker runtime."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.commerce.amazon import AmazonCommerceConnector, AmazonOperationResult
from vayujit_api.commerce.models import MarketplaceAccount, MarketplaceInventory, MarketplaceListing
from vayujit_api.identity.service import now
from vayujit_api.publishing.models import PublishingJob

AmazonJobType = Literal[
    "listing_submission",
    "listing_reconciliation",
    "listing_update",
    "inventory_read",
    "inventory_update",
    "order_import",
    "financial_event_import",
]


@dataclass(frozen=True)
class AmazonJobResult:
    status: str
    retryable: bool = False
    ambiguous: bool = False
    error_code: str | None = None
    safe_message: str | None = None
    remote_id: str | None = None
    metadata: dict[str, object] | None = None


def amazon_idempotency_key(
    *,
    operation: AmazonJobType,
    account_id: uuid.UUID,
    resource_id: uuid.UUID,
    fingerprint: str,
) -> str:
    digest = hashlib.sha256(
        f"{operation}:{account_id}:{resource_id}:{fingerprint}".encode()
    ).hexdigest()[:32]
    return f"amazon:{operation}:{digest}"


def retry_delay_seconds(attempt: int, retry_after_seconds: int | None = None) -> int:
    if retry_after_seconds is not None:
        return min(max(retry_after_seconds, 1), 3600)
    return min(30 * (2 ** max(attempt - 1, 0)), 3600)


def _connector(
    db: Session, account_id: uuid.UUID
) -> tuple[MarketplaceAccount, AmazonCommerceConnector] | None:
    account = db.scalar(
        select(MarketplaceAccount).where(
            MarketplaceAccount.id == account_id,
            MarketplaceAccount.marketplace == "amazon",
        )
    )
    if account is None:
        return None
    from vayujit_api.commerce.amazon import FakeAmazonSPAPITransport, amazon_marketplace

    config = account.configuration_json or {}
    connector = AmazonCommerceConnector(
        seller_id=account.seller_account_id,
        marketplace=amazon_marketplace(str(config.get("country_code", "IN"))),
        transport=FakeAmazonSPAPITransport(),
    )
    return account, connector


def reconcile_ambiguous(
    connector: AmazonCommerceConnector,
    *,
    sku: str,
) -> AmazonOperationResult:
    """Resolve a timeout by seller SKU before allowing another submission."""
    return connector.find_by_sku(sku)


def execute_amazon_job(
    db: Session, job: PublishingJob, *, account_id: uuid.UUID
) -> AmazonJobResult:
    value = _connector(db, account_id)
    if value is None:
        return AmazonJobResult(
            "failed",
            error_code="amazon_account_missing",
            safe_message="Amazon account was not found.",
        )
    _, connector = value
    listing = db.scalar(
        select(MarketplaceListing)
        .where(
            MarketplaceListing.owner_id == job.owner_id,
            MarketplaceListing.product_id == job.product_id,
            MarketplaceListing.account_id == account_id,
        )
        .order_by(MarketplaceListing.updated_at.desc())
    )
    if listing is None:
        return AmazonJobResult(
            "failed",
            error_code="amazon_listing_missing",
            safe_message="Amazon listing was not found.",
        )
    sku = listing.marketplace_sku or f"VJ-{listing.id.hex[:10]}"
    operation = (
        job.idempotency_key.split(":", 2)[1] if job.idempotency_key.startswith("amazon:") else ""
    )
    if job.requested_action in {"publish", "create_draft"}:
        existing_remote = reconcile_ambiguous(connector, sku=sku)
        if existing_remote.status == "succeeded":
            listing.remote_listing_id = existing_remote.remote_id
            listing.status = "processing"
            listing.publication_state = "processing"
            listing.updated_at = now()
            return AmazonJobResult(
                "succeeded",
                remote_id=existing_remote.remote_id,
                metadata={"ambiguous_reused": True},
            )
        result = connector.submit(
            sku=sku,
            payload={"title": listing.title, "product_type": listing.category or "PRODUCT"},
            idempotency_key=job.idempotency_key,
        )
        if result.ambiguous:
            resolved = reconcile_ambiguous(connector, sku=sku)
            if resolved.status == "succeeded":
                return AmazonJobResult(
                    "succeeded", remote_id=resolved.remote_id, metadata={"ambiguous_reused": True}
                )
            return AmazonJobResult(
                "retry_wait",
                retryable=True,
                ambiguous=True,
                error_code="amazon_ambiguous_result",
                safe_message="Amazon submission outcome is ambiguous; reconciliation is required.",
            )
        if result.status in {"accepted", "succeeded"}:
            listing.remote_listing_id = result.remote_id
            listing.status = "processing"
            listing.publication_state = "processing"
            listing.raw_safe_status = result.remote_status
            listing.updated_at = now()
            return AmazonJobResult(
                "succeeded",
                remote_id=result.remote_id,
                metadata={"remote_status": result.remote_status},
            )
        return AmazonJobResult(
            "retry_wait" if result.retryable else "failed",
            retryable=result.retryable,
            error_code=str(result.issues[0].code) if result.issues else "amazon_submission_failed",
            safe_message=(
                result.issues[0].message if result.issues else "Amazon submission failed safely."
            ),
        )
    if job.requested_action == "reconcile":
        if not listing.remote_listing_id:
            return AmazonJobResult(
                "failed",
                error_code="amazon_remote_id_missing",
                safe_message="Amazon listing has no remote identifier.",
            )
        result = connector.process(listing.remote_listing_id)
        if result.status == "succeeded":
            status = {"ACTIVE": "active", "PROCESSING": "processing", "REJECTED": "rejected"}.get(
                result.remote_status or "", "error"
            )
            listing.status = status
            listing.publication_state = status
            listing.raw_safe_status = result.remote_status
            listing.last_synchronized_at = now()
            listing.updated_at = now()
            return AmazonJobResult(
                "succeeded",
                remote_id=listing.remote_listing_id,
                metadata={"remote_status": result.remote_status},
            )
        return AmazonJobResult(
            "retry_wait" if result.retryable else "failed",
            retryable=result.retryable,
            error_code="amazon_reconcile_failed",
            safe_message="Amazon reconciliation failed safely.",
        )
    if job.requested_action == "update" and operation not in {
        "inventory_read",
        "inventory_update",
        "order_import",
        "financial_event_import",
    }:
        if not listing.remote_listing_id:
            return AmazonJobResult(
                "failed",
                error_code="amazon_remote_id_missing",
                safe_message="Amazon listing has no remote identifier.",
            )
        listing_result = connector.update_listing(
            remote_id=listing.remote_listing_id, title=listing.title, sku=sku
        )
        return AmazonJobResult(
            "succeeded" if listing_result.get("status") else "failed",
            remote_id=listing.remote_listing_id,
        )
    if operation == "inventory_update":
        quantity = db.scalar(
            select(MarketplaceInventory.available_quantity).where(
                MarketplaceInventory.listing_id == listing.id,
                MarketplaceInventory.variant_id.is_(None),
            )
        )
        if quantity is None:
            return AmazonJobResult(
                "failed",
                error_code="amazon_inventory_missing",
                safe_message="A bounded local inventory target is required.",
            )
        inventory_result = connector.update_inventory(sku, int(quantity))
        return AmazonJobResult("succeeded", metadata={"quantity": inventory_result.get("quantity")})
    if operation == "order_import":
        return AmazonJobResult("succeeded", metadata={"imported": len(connector.get_orders())})
    if operation == "financial_event_import":
        return AmazonJobResult(
            "succeeded",
            metadata={
                "imported": len(connector.get_fees()),
                "settlements": len(connector.get_settlements()),
            },
        )
    inventory_payload = connector.get_inventory(sku)
    return AmazonJobResult("succeeded", metadata={"quantity": inventory_payload.get("quantity")})


def enqueue_amazon_job(
    db: Session,
    *,
    owner_id: uuid.UUID,
    account_id: uuid.UUID,
    destination_id: uuid.UUID,
    product_id: uuid.UUID,
    artifact_id: uuid.UUID,
    artifact_version: int,
    operation: AmazonJobType,
    fingerprint: str,
    scheduled_at: object,
    correlation_id: str,
) -> PublishingJob:
    action = {
        "listing_submission": "publish",
        "listing_reconciliation": "reconcile",
        "listing_update": "update",
        "inventory_read": "update",
        "inventory_update": "update",
        "order_import": "update",
        "financial_event_import": "update",
    }[operation]
    timestamp = now()
    job = PublishingJob(
        owner_id=owner_id,
        schedule_id=None,
        workflow_instance_id=None,
        publishing_execution_id=None,
        product_id=product_id,
        artifact_id=artifact_id,
        artifact_version=artifact_version,
        destination_id=destination_id,
        connector_key=job_connector_key(account_id),
        requested_action=action,
        idempotency_key=amazon_idempotency_key(
            operation=operation,
            account_id=account_id,
            resource_id=product_id,
            fingerprint=fingerprint,
        ),
        state="pending",
        priority=0,
        scheduled_at_utc=scheduled_at,
        available_at_utc=scheduled_at,
        claim_count=0,
        execution_attempt_count=0,
        max_execution_attempts=5,
        correlation_id=correlation_id,
        created_at=timestamp,
        updated_at=timestamp,
        row_version=1,
    )
    db.add(job)
    db.flush()
    return job


def job_connector_key(account_id: uuid.UUID) -> str:
    return f"amazon:{account_id}"


def parse_account_id(connector_key: str) -> uuid.UUID | None:
    if not connector_key.startswith("amazon:"):
        return None
    try:
        return uuid.UUID(connector_key.split(":", 1)[1])
    except ValueError:
        return None
