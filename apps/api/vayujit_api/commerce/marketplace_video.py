"""Normalized, local fake-certified marketplace Video integration.

This module deliberately shares the Commerce owner/listing/account boundary and
uses deterministic transports.  It never makes a live marketplace request.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.commerce.models import MarketplaceAccount, MarketplaceListing
from vayujit_api.core.database import Base, get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.media.models import MediaAsset
from vayujit_api.video.models import VideoGeneration, VideoOutput

MARKETPLACES = ("amazon", "flipkart", "meesho")
VIDEO_FAILURE_ACTIONS: dict[str, list[str]] = {
    "commerce.video.account_disabled": ["change_account", "open_recovery", "cancel"],
    "commerce.video.invalid_credentials": ["change_account", "open_recovery", "cancel"],
    "commerce.video.unsupported_video": ["replace_video", "review_failure", "cancel"],
    "commerce.video.video_not_ready": ["retry", "review_failure", "cancel"],
    "commerce.video.listing_not_ready": ["open_listing", "refresh_listing", "cancel"],
    "commerce.video.throttled": ["retry", "reconcile", "cancel"],
    "commerce.video.timeout": ["retry", "reconcile", "cancel"],
    "commerce.video.connector_unavailable": ["retry", "reconcile", "cancel"],
    "commerce.video.ambiguous_result": ["reconcile", "review_failure"],
    "commerce.video.stale_video": ["replace_video", "review_failure", "cancel"],
    "commerce.video.stale_listing": ["refresh_listing", "reconcile", "cancel"],
    "commerce.video.policy_rejection": ["replace_video", "review_failure", "cancel"],
}

MARKETPLACE_VIDEO_CAPABILITIES: dict[str, dict[str, object]] = {
    "amazon": {
        "supports_video": True,
        "mime_types": ["video/mp4"],
        "max_file_size_bytes": 50_000_000,
        "min_duration_seconds": 1,
        "max_duration_seconds": 180,
        "aspect_ratios": ["16:9", "1:1", "9:16"],
        "dimensions": {"min_width": 240, "min_height": 240, "max_width": 3840, "max_height": 3840},
        "attachment_support": True,
        "update_support": True,
        "replacement_support": True,
        "reconciliation_support": True,
        "remote_video_id_support": True,
        "ruleset": "LOCAL FAKE-CERTIFIED RULESET",
    },
    "flipkart": {
        "supports_video": True,
        "mime_types": ["video/mp4"],
        "max_file_size_bytes": 50_000_000,
        "min_duration_seconds": 1,
        "max_duration_seconds": 180,
        "aspect_ratios": ["16:9", "1:1", "9:16"],
        "dimensions": {"min_width": 240, "min_height": 240, "max_width": 3840, "max_height": 3840},
        "attachment_support": True,
        "update_support": True,
        "replacement_support": True,
        "reconciliation_support": True,
        "remote_video_id_support": True,
        "ruleset": "LOCAL FAKE-CERTIFIED RULESET",
    },
    "meesho": {
        "supports_video": True,
        "mime_types": ["video/mp4"],
        "max_file_size_bytes": 50_000_000,
        "min_duration_seconds": 1,
        "max_duration_seconds": 180,
        "aspect_ratios": ["16:9", "1:1", "9:16"],
        "dimensions": {"min_width": 240, "min_height": 240, "max_width": 3840, "max_height": 3840},
        "attachment_support": True,
        "update_support": True,
        "replacement_support": True,
        "reconciliation_support": True,
        "remote_video_id_support": True,
        "ruleset": "LOCAL FAKE-CERTIFIED RULESET",
    },
}


class MarketplaceVideoMapping(Base):
    __tablename__ = "marketplace_video_mappings"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "account_id",
            "listing_id",
            "video_output_id",
            name="uq_marketplace_video_mapping_exact",
        ),
        UniqueConstraint(
            "owner_id", "account_id", "remote_video_id", name="uq_marketplace_video_mapping_remote"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="RESTRICT"), index=True
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="RESTRICT"), index=True
    )
    marketplace: Mapped[str] = mapped_column(String(30), index=True)
    video_generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_generations.id", ondelete="RESTRICT"), index=True
    )
    video_output_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_outputs.id", ondelete="RESTRICT"), index=True
    )
    video_media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )
    video_version: Mapped[int] = mapped_column(Integer)
    remote_video_id: Mapped[str | None] = mapped_column(String(200), index=True)
    attachment_state: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    reconciliation_state: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    drift_state: Mapped[str] = mapped_column(String(40), default="none", index=True)
    readiness_fingerprint: Mapped[str] = mapped_column(String(64))
    mutation_fingerprint: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    operation: Mapped[str] = mapped_column(String(30), default="attach")
    remote_state_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MarketplaceVideoJob(Base):
    __tablename__ = "marketplace_video_jobs"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_marketplace_video_job_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mapping_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_video_mappings.id", ondelete="SET NULL"),
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="RESTRICT"), index=True
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="RESTRICT"), index=True
    )
    marketplace: Mapped[str] = mapped_column(String(30), index=True)
    operation: Mapped[str] = mapped_column(String(30))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketplaceVideoRequest(BaseModel):
    listing_id: uuid.UUID
    video_generation_id: uuid.UUID
    video_output_id: uuid.UUID
    video_media_id: uuid.UUID
    video_version: int = Field(gt=0)
    account_id: uuid.UUID | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    correlation_id: str | None = Field(default=None, min_length=1, max_length=64)


class MarketplaceVideoConfirm(MarketplaceVideoRequest):
    fingerprint: str = Field(min_length=64, max_length=64)
    confirm: bool = False


class MarketplaceVideoReplacementRequest(MarketplaceVideoRequest):
    mapping_id: uuid.UUID


class MarketplaceVideoReplacementConfirm(MarketplaceVideoReplacementRequest):
    fingerprint: str = Field(min_length=64, max_length=64)
    confirm: bool = False


class MarketplaceVideoWorkerRequest(BaseModel):
    crash_point: str | None = Field(default=None, pattern="^(before_connector|after_connector)$")


class FakeMarketplaceVideoConnector:
    """Deterministic, network-free transport shared by all three adapters."""

    def __init__(self, marketplace: str) -> None:
        self.marketplace = marketplace
        self.mutations = 0
        self.payloads: list[dict[str, object]] = []
        self.remote: dict[str, dict[str, object]] = {}
        self.by_key: dict[str, dict[str, object]] = {}

    def attach(
        self,
        *,
        listing_id: uuid.UUID,
        product_id: uuid.UUID,
        output_id: uuid.UUID,
        version: int,
        operation: str,
    ) -> dict[str, object]:
        key = f"{self.marketplace}:{listing_id}:{output_id}:{operation}"
        if key in self.by_key:
            return dict(self.by_key[key])
        self.mutations += 1
        remote_id = f"fake-{self.marketplace}-video-{hashlib.sha256(key.encode()).hexdigest()[:16]}"
        payload: dict[str, object] = {
            "listing_id": str(listing_id),
            "product_id": str(product_id),
            "video_output_id": str(output_id),
            "video_version": version,
            "operation": operation,
        }
        self.payloads.append(payload)
        value: dict[str, object] = {
            "remote_video_id": remote_id,
            "state": "active",
            "payload": payload,
        }
        self.remote[remote_id] = value
        self.by_key[key] = value

        return value

    def lookup(self, remote_id: str) -> dict[str, object]:
        return dict(self.remote.get(remote_id, {"remote_video_id": remote_id, "state": "missing"}))


_VIDEO_CONNECTORS = {
    marketplace: FakeMarketplaceVideoConnector(marketplace) for marketplace in MARKETPLACES
}


def video_connector_for(marketplace: str) -> FakeMarketplaceVideoConnector:
    return _VIDEO_CONNECTORS.setdefault(marketplace, FakeMarketplaceVideoConnector(marketplace))


def fake_video_connector_state() -> dict[str, dict[str, object]]:
    return {
        key: {
            "mutations": value.mutations,
            "remote_count": len(value.remote),
            "payloads": list(value.payloads),
        }
        for key, value in _VIDEO_CONNECTORS.items()
    }


def _now() -> datetime:
    return datetime.now(UTC)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _account_listing(
    db: Session, owner: User, listing_id: uuid.UUID, account_id: uuid.UUID | None
) -> tuple[MarketplaceAccount, MarketplaceListing]:
    listing = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id, MarketplaceListing.owner_id == owner.id
        )
    )
    if listing is None or listing.marketplace not in MARKETPLACES:
        raise HTTPException(404, "Marketplace listing was not found.")
    account = db.scalar(
        select(MarketplaceAccount).where(
            MarketplaceAccount.id == listing.account_id, MarketplaceAccount.owner_id == owner.id
        )
    )
    if account is None or (account_id is not None and account.id != account_id):
        raise HTTPException(404, "Marketplace account was not found.")
    return account, listing


def _approved_video(
    db: Session, owner: User, request: MarketplaceVideoRequest
) -> tuple[VideoGeneration, VideoOutput, MediaAsset]:
    generation = db.scalar(
        select(VideoGeneration).where(
            VideoGeneration.id == request.video_generation_id, VideoGeneration.owner_id == owner.id
        )
    )
    output = db.scalar(
        select(VideoOutput).where(
            VideoOutput.id == request.video_output_id,
            VideoOutput.generation_id == request.video_generation_id,
            VideoOutput.owner_id == owner.id,
        )
    )
    media = db.scalar(
        select(MediaAsset).where(
            MediaAsset.id == request.video_media_id, MediaAsset.owner_id == owner.id
        )
    )
    if generation is None or output is None or media is None:
        raise HTTPException(404, "The exact approved Video Output and Media were not found.")
    if generation.product_id != db.scalar(
        select(MarketplaceListing.product_id).where(MarketplaceListing.id == request.listing_id)
    ):
        raise HTTPException(409, "The Video belongs to a different Product.")
    if generation.status != "succeeded" or output.status != "approved" or media.status != "ready":
        raise HTTPException(409, "Only an approved, ready Video Output and Media can be attached.")
    actual_version = _generation_version(db, generation)
    if request.video_version != actual_version:
        raise HTTPException(409, "The exact approved Video version is no longer current.")
    return generation, output, media


def _readiness(db: Session, owner: User, request: MarketplaceVideoRequest) -> dict[str, object]:
    account, listing = _account_listing(db, owner, request.listing_id, request.account_id)
    generation, output, media = _approved_video(db, owner, request)
    capability = MARKETPLACE_VIDEO_CAPABILITIES[listing.marketplace]
    blockers: list[str] = []
    warnings: list[str] = []
    if not account.enabled:
        blockers.append("account_disabled")
    if account.validation_status != "valid":
        blockers.append("account_not_validated")
    if listing.status not in {"active", "ready"}:
        blockers.append("listing_not_ready")
    if generation.product_id != listing.product_id:
        blockers.append("product_mismatch")
    if output.mime_type not in cast(list[str], capability["mime_types"]):
        blockers.append("unsupported_mime_type")
    if output.size_bytes > int(cast(int, capability["max_file_size_bytes"])):
        blockers.append("video_file_too_large")
    if output.duration_seconds < int(
        cast(int, capability["min_duration_seconds"])
    ) or output.duration_seconds > int(cast(int, capability["max_duration_seconds"])):
        blockers.append("duration_out_of_range")
    if output.aspect_ratio not in cast(list[str], capability["aspect_ratios"]):
        warnings.append("aspect_ratio_requires_review")
    state = {
        "listing_id": str(listing.id),
        "listing_updated_at": listing.updated_at.isoformat(),
        "account_id": str(account.id),
        "marketplace": listing.marketplace,
        "product_id": str(listing.product_id),
        "video_generation_id": str(generation.id),
        "video_output_id": str(output.id),
        "video_media_id": str(media.id),
        "video_version": request.video_version,
        "remote_video_id": None,
    }
    fingerprint = _fingerprint(state)
    return {
        "status": "ready" if not blockers else "blocked",
        "ready": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "marketplace": listing.marketplace,
        "account_id": account.id,
        "listing_id": listing.id,
        "product_id": listing.product_id,
        "marketplace_sku": listing.marketplace_sku,
        "video_generation_id": generation.id,
        "video_output_id": output.id,
        "video_media_id": media.id,
        "video_version": request.video_version,
        "video_state": {
            "generation": generation.status,
            "output": output.status,
            "media": media.status,
        },
        "media": {
            "mime_type": media.mime_type,
            "size_bytes": media.size_bytes,
            "width": media.width,
            "height": media.height,
            "duration_seconds": output.duration_seconds,
            "aspect_ratio": output.aspect_ratio,
        },
        "compatibility": capability,
        "fingerprint": fingerprint,
        "ruleset": "LOCAL FAKE-CERTIFIED RULESET",
    }


def preview(db: Session, owner: User, request: MarketplaceVideoRequest) -> dict[str, object]:
    value = _readiness(db, owner, request)
    value["intended_mutation"] = "attach_video"
    value["current_marketplace_video_state"] = {"remote_video_id": None, "state": "not_attached"}
    return value


def confirm(db: Session, owner: User, request: MarketplaceVideoConfirm) -> dict[str, object]:
    if not request.confirm:
        raise HTTPException(400, "Explicit confirmation is required.")
    current = preview(db, owner, request)
    if current["fingerprint"] != request.fingerprint:
        raise HTTPException(409, "This Marketplace Video preview is stale; create a fresh preview.")
    if current["blockers"]:
        raise HTTPException(409, "Marketplace Video is not ready for attachment.")
    key = (
        request.idempotency_key
        or f"marketplace-video:{request.listing_id}:{request.video_output_id}:attach"
    )
    existing = db.scalar(
        select(MarketplaceVideoJob).where(
            MarketplaceVideoJob.owner_id == owner.id, MarketplaceVideoJob.idempotency_key == key
        )
    )
    if existing:
        return {
            "job_id": existing.id,
            "state": existing.state,
            "idempotent_reuse": True,
            "fingerprint": request.fingerprint,
        }
    stamp = _now()
    job = MarketplaceVideoJob(
        owner_id=owner.id,
        product_id=current["product_id"],
        account_id=request.account_id or current["account_id"],
        listing_id=request.listing_id,
        marketplace=str(current["marketplace"]),
        operation="attach",
        idempotency_key=key,
        state="pending",
        attempt_count=0,
        payload_json={
            "video_generation_id": str(request.video_generation_id),
            "video_output_id": str(request.video_output_id),
            "video_media_id": str(request.video_media_id),
            "video_version": request.video_version,
            "fingerprint": request.fingerprint,
        },
        correlation_id=request.correlation_id or uuid.uuid4().hex[:32],
        created_at=stamp,
    )
    db.add(job)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="commerce.video.confirmed",
        entity_type="marketplace_video_job",
        entity_id=job.id,
        metadata={"marketplace": job.marketplace, "operation": job.operation},
    )
    db.commit()
    return {
        "job_id": job.id,
        "state": job.state,
        "idempotent_reuse": False,
        "fingerprint": request.fingerprint,
    }


def run_job(
    db: Session, owner: User, job: MarketplaceVideoJob, *, crash_point: str | None = None
) -> dict[str, object]:
    if job.owner_id != owner.id:
        raise HTTPException(404, "Marketplace Video job was not found.")
    if job.state == "succeeded":
        return {
            "job_id": job.id,
            "state": job.state,
            "idempotent_reuse": True,
            "mapping_id": job.mapping_id,
        }
    job.state = "running"
    job.started_at = _now()
    job.attempt_count += 1
    db.flush()
    if crash_point == "before_connector":
        db.rollback()
        raise HTTPException(
            500, "Marketplace Video worker lease was recovered before connector execution."
        )
    payload = job.payload_json
    account = db.scalar(
        select(MarketplaceAccount).where(
            MarketplaceAccount.id == job.account_id,
            MarketplaceAccount.owner_id == owner.id,
        )
    )
    if account is None or not account.enabled or account.validation_status != "valid":
        job.state = "failed"
        job.last_error_code = "commerce.video.account_disabled"
        job.safe_error_message = "The marketplace account is disabled or not validated."
        job.completed_at = _now()
        db.commit()
        record_event(
            db,
            actor_id=owner.id,
            action="commerce.video.failed",
            entity_type="marketplace_video_job",
            entity_id=job.id,
            metadata={"error_code": job.last_error_code},
        )
        db.commit()
        return {
            "job_id": job.id,
            "state": job.state,
            "error_code": job.last_error_code,
            "safe_error_message": job.safe_error_message,
            "idempotent_reuse": False,
        }
    result = payload.get("remote")
    if not isinstance(result, dict):
        result = video_connector_for(job.marketplace).attach(
            listing_id=job.listing_id,
            product_id=job.product_id,
            output_id=uuid.UUID(str(payload["video_output_id"])),
            version=int(cast(int, payload["video_version"])),
            operation=job.operation,
        )
        job.payload_json = {**payload, "remote": result}
        db.flush()
    if crash_point == "after_connector":
        db.commit()
        raise HTTPException(500, "Marketplace Video worker resumed after remote checkpoint.")
    stamp = _now()
    mapping = db.scalar(
        select(MarketplaceVideoMapping).where(
            MarketplaceVideoMapping.owner_id == owner.id,
            MarketplaceVideoMapping.account_id == job.account_id,
            MarketplaceVideoMapping.listing_id == job.listing_id,
            MarketplaceVideoMapping.video_output_id == uuid.UUID(str(payload["video_output_id"])),
        )
    )
    if mapping is None:
        mapping = MarketplaceVideoMapping(
            owner_id=owner.id,
            product_id=job.product_id,
            account_id=job.account_id,
            listing_id=job.listing_id,
            marketplace=job.marketplace,
            video_generation_id=uuid.UUID(str(payload["video_generation_id"])),
            video_output_id=uuid.UUID(str(payload["video_output_id"])),
            video_media_id=uuid.UUID(str(payload["video_media_id"])),
            video_version=int(cast(int, payload["video_version"])),
            remote_video_id=str(result["remote_video_id"]),
            attachment_state="active",
            reconciliation_state="reconciled",
            drift_state="none",
            readiness_fingerprint=str(payload["fingerprint"]),
            mutation_fingerprint=_fingerprint(
                {"job": str(job.id), "remote": result["remote_video_id"]}
            ),
            actor_id=owner.id,
            correlation_id=job.correlation_id,
            operation=job.operation,
            remote_state_json=result,
            last_reconciled_at=stamp,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(mapping)
        db.flush()
    job.mapping_id = mapping.id
    job.state = "succeeded"
    job.completed_at = stamp
    db.add(job)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="commerce.video.attached",
        entity_type="marketplace_video_mapping",
        entity_id=mapping.id,
        metadata={
            "marketplace": job.marketplace,
            "video_output_id": str(mapping.video_output_id),
            "remote_video_id": mapping.remote_video_id,
        },
    )
    db.commit()
    return {
        "job_id": job.id,
        "state": job.state,
        "mapping_id": mapping.id,
        "remote_video_id": mapping.remote_video_id,
        "idempotent_reuse": False,
    }


def reconcile(db: Session, owner: User, mapping: MarketplaceVideoMapping) -> dict[str, object]:
    if mapping.owner_id != owner.id:
        raise HTTPException(404, "Marketplace Video mapping was not found.")
    remote = video_connector_for(mapping.marketplace).lookup(mapping.remote_video_id or "")
    mapping.remote_state_json = remote
    mapping.reconciliation_state = "reconciled" if remote.get("state") == "active" else "drift"
    mapping.drift_state = "none" if remote.get("state") == "active" else "detected"
    mapping.last_reconciled_at = _now()
    mapping.updated_at = _now()
    db.commit()
    record_event(
        db,
        actor_id=owner.id,
        action="commerce.video.reconciled",
        entity_type="marketplace_video_mapping",
        entity_id=mapping.id,
        metadata={"state": mapping.reconciliation_state},
    )
    db.commit()
    return mapping_response(mapping)


def _generation_version(db: Session, generation: VideoGeneration) -> int:
    version = 1
    parent_id = generation.parent_generation_id
    seen: set[uuid.UUID] = set()
    while parent_id and parent_id not in seen:
        seen.add(parent_id)
        version += 1
        parent = db.get(VideoGeneration, parent_id)
        if parent is None:
            break
        parent_id = parent.parent_generation_id
    return version


def mapping_response(mapping: MarketplaceVideoMapping) -> dict[str, object]:
    return {
        "id": mapping.id,
        "owner_id": mapping.owner_id,
        "product_id": mapping.product_id,
        "account_id": mapping.account_id,
        "listing_id": mapping.listing_id,
        "marketplace": mapping.marketplace,
        "video_generation_id": mapping.video_generation_id,
        "video_output_id": mapping.video_output_id,
        "video_media_id": mapping.video_media_id,
        "video_version": mapping.video_version,
        "remote_video_id": mapping.remote_video_id,
        "attachment_state": mapping.attachment_state,
        "reconciliation_state": mapping.reconciliation_state,
        "drift_state": mapping.drift_state,
        "readiness_fingerprint": mapping.readiness_fingerprint,
        "mutation_fingerprint": mapping.mutation_fingerprint,
        "correlation_id": mapping.correlation_id,
        "operation": mapping.operation,
        "remote_state": mapping.remote_state_json,
        "last_reconciled_at": mapping.last_reconciled_at,
    }


router = APIRouter(prefix="/api/v1/marketplaces/video", tags=["marketplace-video"])
SessionDep = Annotated[Session, Depends(get_session)]
OwnerDep = Annotated[User, Depends(current_user)]


@router.get("/capabilities")
def capabilities() -> dict[str, object]:
    return {
        "ruleset": "LOCAL FAKE-CERTIFIED RULESET",
        "marketplaces": MARKETPLACE_VIDEO_CAPABILITIES,
    }


@router.post("/readiness")
def readiness(
    request: MarketplaceVideoRequest, db: SessionDep, owner: OwnerDep
) -> dict[str, object]:
    return _readiness(db, owner, request)


@router.post("/preview")
def preview_route(
    request: MarketplaceVideoRequest, db: SessionDep, owner: OwnerDep
) -> dict[str, object]:
    return preview(db, owner, request)


@router.post("/confirm")
def confirm_route(
    request: MarketplaceVideoConfirm, db: SessionDep, owner: OwnerDep
) -> dict[str, object]:
    return confirm(db, owner, request)


@router.post("/jobs/{job_id}/run")
def run_route(
    job_id: uuid.UUID,
    db: SessionDep,
    owner: OwnerDep,
    body: MarketplaceVideoWorkerRequest | None = None,
) -> dict[str, object]:
    job = db.scalar(
        select(MarketplaceVideoJob).where(
            MarketplaceVideoJob.id == job_id, MarketplaceVideoJob.owner_id == owner.id
        )
    )
    if job is None:
        raise HTTPException(404, "Marketplace Video job was not found.")
    return run_job(db, owner, job, crash_point=body.crash_point if body else None)


def replacement_preview(
    db: Session, owner: User, request: MarketplaceVideoReplacementRequest
) -> dict[str, object]:
    current = db.scalar(
        select(MarketplaceVideoMapping).where(
            MarketplaceVideoMapping.id == request.mapping_id,
            MarketplaceVideoMapping.owner_id == owner.id,
        )
    )
    if current is None:
        raise HTTPException(404, "Marketplace Video mapping was not found.")
    if current.listing_id != request.listing_id or current.account_id != request.account_id:
        raise HTTPException(409, "The replacement target does not match the current listing.")
    proposed = preview(db, owner, request)
    fingerprint = _fingerprint(
        {
            "current_mapping_id": str(current.id),
            "current_output_id": str(current.video_output_id),
            "current_version": current.video_version,
            "proposed": proposed["fingerprint"],
        }
    )
    return {
        "status": proposed["status"],
        "ready": proposed["ready"],
        "blockers": proposed["blockers"],
        "warnings": proposed["warnings"],
        "marketplace": proposed["marketplace"],
        "listing_id": current.listing_id,
        "current_video": {
            "video_generation_id": current.video_generation_id,
            "video_output_id": current.video_output_id,
            "video_media_id": current.video_media_id,
            "version": current.video_version,
            "remote_video_id": current.remote_video_id,
        },
        "proposed_video": {
            "video_generation_id": proposed["video_generation_id"],
            "video_output_id": proposed["video_output_id"],
            "video_media_id": proposed["video_media_id"],
            "version": request.video_version,
        },
        "readiness": proposed,
        "fingerprint": fingerprint,
        "intended_mutation": "replace_video",
        "ruleset": "LOCAL FAKE-CERTIFIED RULESET",
    }


def replacement_confirm(
    db: Session, owner: User, request: MarketplaceVideoReplacementConfirm
) -> dict[str, object]:
    if not request.confirm:
        raise HTTPException(400, "Explicit confirmation is required.")
    fresh = replacement_preview(db, owner, request)
    if fresh["fingerprint"] != request.fingerprint:
        raise HTTPException(
            409, "This Marketplace Video replacement preview is stale; create a fresh preview."
        )
    if fresh["blockers"]:
        raise HTTPException(409, "Marketplace Video replacement is not ready.")
    key = (
        request.idempotency_key
        or f"marketplace-video:{request.mapping_id}:{request.video_output_id}:replace"
    )
    existing = db.scalar(
        select(MarketplaceVideoJob).where(
            MarketplaceVideoJob.owner_id == owner.id,
            MarketplaceVideoJob.idempotency_key == key,
        )
    )
    if existing:
        return {
            "job_id": existing.id,
            "state": existing.state,
            "idempotent_reuse": True,
            "fingerprint": request.fingerprint,
        }
    current = db.get(MarketplaceVideoMapping, request.mapping_id)
    if current is None:
        raise HTTPException(404, "Marketplace Video mapping was not found.")
    stamp = _now()
    job = MarketplaceVideoJob(
        owner_id=owner.id,
        product_id=current.product_id,
        account_id=current.account_id,
        listing_id=current.listing_id,
        marketplace=current.marketplace,
        operation="replace",
        idempotency_key=key,
        state="pending",
        attempt_count=0,
        payload_json={
            "mapping_id": str(current.id),
            "video_generation_id": str(request.video_generation_id),
            "video_output_id": str(request.video_output_id),
            "video_media_id": str(request.video_media_id),
            "video_version": request.video_version,
            "fingerprint": request.fingerprint,
        },
        correlation_id=request.correlation_id or uuid.uuid4().hex[:32],
        created_at=stamp,
    )
    db.add(job)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="commerce.video.replacement_confirmed",
        entity_type="marketplace_video_job",
        entity_id=job.id,
        metadata={"marketplace": job.marketplace, "mapping_id": str(current.id)},
    )
    db.commit()
    return {
        "job_id": job.id,
        "state": job.state,
        "idempotent_reuse": False,
        "fingerprint": request.fingerprint,
    }


@router.post("/replacement/preview")
def replacement_preview_route(
    request: MarketplaceVideoReplacementRequest,
    db: SessionDep,
    owner: OwnerDep,
) -> dict[str, object]:
    return replacement_preview(db, owner, request)


@router.post("/replacement/confirm")
def replacement_confirm_route(
    request: MarketplaceVideoReplacementConfirm,
    db: SessionDep,
    owner: OwnerDep,
) -> dict[str, object]:
    return replacement_confirm(db, owner, request)


@router.post("/listings/{listing_id}/video/readiness")
def listing_readiness(
    listing_id: uuid.UUID,
    request: MarketplaceVideoRequest,
    db: SessionDep,
    owner: OwnerDep,
) -> dict[str, object]:
    return _readiness(db, owner, request.model_copy(update={"listing_id": listing_id}))


@router.post("/listings/{listing_id}/video/preview")
def listing_preview(
    listing_id: uuid.UUID,
    request: MarketplaceVideoRequest,
    db: SessionDep,
    owner: OwnerDep,
) -> dict[str, object]:
    return preview(db, owner, request.model_copy(update={"listing_id": listing_id}))


@router.post("/listings/{listing_id}/video/confirm")
def listing_confirm(
    listing_id: uuid.UUID,
    request: MarketplaceVideoConfirm,
    db: SessionDep,
    owner: OwnerDep,
) -> dict[str, object]:
    return confirm(db, owner, request.model_copy(update={"listing_id": listing_id}))


@router.get("/jobs")
def jobs(db: SessionDep, owner: OwnerDep) -> list[dict[str, object]]:
    return [
        {
            "id": row.id,
            "marketplace": row.marketplace,
            "operation": row.operation,
            "state": row.state,
            "mapping_id": row.mapping_id,
            "attempt_count": row.attempt_count,
            "safe_error_message": row.safe_error_message,
        }
        for row in db.scalars(
            select(MarketplaceVideoJob)
            .where(MarketplaceVideoJob.owner_id == owner.id)
            .order_by(MarketplaceVideoJob.created_at.desc())
        ).all()
    ]


@router.get("/mappings")
def mappings(db: SessionDep, owner: OwnerDep) -> list[dict[str, object]]:
    return [
        mapping_response(row)
        for row in db.scalars(
            select(MarketplaceVideoMapping)
            .where(MarketplaceVideoMapping.owner_id == owner.id)
            .order_by(MarketplaceVideoMapping.updated_at.desc())
        ).all()
    ]


@router.get("/mappings/{mapping_id}")
def mapping(mapping_id: uuid.UUID, db: SessionDep, owner: OwnerDep) -> dict[str, object]:
    row = db.scalar(
        select(MarketplaceVideoMapping).where(
            MarketplaceVideoMapping.id == mapping_id, MarketplaceVideoMapping.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Marketplace Video mapping was not found.")
    return mapping_response(row)


@router.post("/mappings/{mapping_id}/reconcile")
def reconcile_route(mapping_id: uuid.UUID, db: SessionDep, owner: OwnerDep) -> dict[str, object]:
    row = db.scalar(
        select(MarketplaceVideoMapping).where(
            MarketplaceVideoMapping.id == mapping_id, MarketplaceVideoMapping.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Marketplace Video mapping was not found.")
    return reconcile(db, owner, row)


@router.get("/product/{product_id}")
def product_channel(product_id: uuid.UUID, db: SessionDep, owner: OwnerDep) -> dict[str, object]:
    rows = list(
        db.scalars(
            select(MarketplaceVideoMapping)
            .where(
                MarketplaceVideoMapping.owner_id == owner.id,
                MarketplaceVideoMapping.product_id == product_id,
            )
            .order_by(
                MarketplaceVideoMapping.marketplace, MarketplaceVideoMapping.video_version.desc()
            )
        ).all()
    )
    result = []
    for marketplace in MARKETPLACES:
        current = next((row for row in rows if row.marketplace == marketplace), None)
        latest: MarketplaceVideoMapping | dict[str, object] | None = current
        update_available = False
        if current:
            candidates = db.scalars(
                select(VideoGeneration).where(
                    VideoGeneration.owner_id == owner.id,
                    VideoGeneration.product_id == product_id,
                    VideoGeneration.status == "succeeded",
                )
            ).all()
            for generation in candidates:
                output = db.scalar(
                    select(VideoOutput).where(
                        VideoOutput.generation_id == generation.id,
                        VideoOutput.status == "approved",
                    )
                )
                if (
                    output
                    and output.id != current.video_output_id
                    and _generation_version(db, generation) > current.video_version
                ):
                    update_available = True
                    latest = {
                        "id": None,
                        "owner_id": owner.id,
                        "product_id": product_id,
                        "account_id": current.account_id,
                        "listing_id": current.listing_id,
                        "marketplace": current.marketplace,
                        "video_generation_id": generation.id,
                        "video_output_id": output.id,
                        "video_media_id": output.media_id,
                        "video_version": _generation_version(db, generation),
                        "remote_video_id": current.remote_video_id,
                        "attachment_state": "approved_not_attached",
                        "reconciliation_state": current.reconciliation_state,
                        "drift_state": "none",
                        "readiness_fingerprint": current.readiness_fingerprint,
                        "mutation_fingerprint": current.mutation_fingerprint,
                        "correlation_id": current.correlation_id,
                        "operation": "replace",
                        "remote_state": current.remote_state_json,
                        "last_reconciled_at": current.last_reconciled_at,
                    }
                    break
        actions = (
            ["preview_video_update", "reconcile", "open_recovery"]
            if current
            else ["preview_video_attachment"]
        )
        result.append(
            {
                "marketplace": marketplace,
                "current": mapping_response(current) if current else None,
                "latest_approved_video": (
                    (
                        mapping_response(latest)
                        if isinstance(latest, MarketplaceVideoMapping)
                        else latest
                    )
                    if latest
                    else None
                ),
                "update_available": update_available,
                "actions": actions,
            }
        )
    return {"product_id": product_id, "channels": result}


@router.get("/history")
def history(db: SessionDep, owner: OwnerDep) -> list[dict[str, object]]:
    rows = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.actor_id == owner.id, AuditEvent.action.like("commerce.video.%"))
        .order_by(AuditEvent.occurred_at.desc())
    ).all()
    return [
        {
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "occurred_at": row.occurred_at,
            "metadata": row.metadata_json,
        }
        for row in rows
    ]


@router.get("/diagnostics")
def diagnostics(db: SessionDep, owner: OwnerDep) -> dict[str, object]:
    jobs_rows = list(
        db.scalars(
            select(MarketplaceVideoJob).where(MarketplaceVideoJob.owner_id == owner.id)
        ).all()
    )
    mappings_rows = list(
        db.scalars(
            select(MarketplaceVideoMapping).where(MarketplaceVideoMapping.owner_id == owner.id)
        ).all()
    )
    return {
        "ruleset": "LOCAL FAKE-CERTIFIED RULESET",
        "active_video_mappings": len(
            [row for row in mappings_rows if row.attachment_state == "active"]
        ),
        "pending_video_jobs": len(
            [row for row in jobs_rows if row.state in {"pending", "running"}]
        ),
        "failed_video_jobs": len([row for row in jobs_rows if row.state == "failed"]),
        "ambiguous_states": len(
            [row for row in mappings_rows if row.reconciliation_state == "ambiguous"]
        ),
        "reconciliation_lag": len(
            [row for row in mappings_rows if row.reconciliation_state != "reconciled"]
        ),
        "update_available_count": 0,
    }


class MarketplaceVideoRecoveryAction(BaseModel):
    job_id: uuid.UUID
    action: str
    confirm: bool = False


@router.get("/product/{product_id}/media-usage")
def product_media_usage(
    product_id: uuid.UUID, db: SessionDep, owner: OwnerDep
) -> list[dict[str, object]]:
    rows = db.scalars(
        select(MarketplaceVideoMapping).where(
            MarketplaceVideoMapping.owner_id == owner.id,
            MarketplaceVideoMapping.product_id == product_id,
        )
    ).all()
    result: list[dict[str, object]] = []
    generations = db.scalars(
        select(VideoGeneration).where(
            VideoGeneration.owner_id == owner.id,
            VideoGeneration.product_id == product_id,
            VideoGeneration.status == "succeeded",
        )
    ).all()
    for row in rows:
        latest_version = row.video_version
        latest_output_id = row.video_output_id
        for generation in generations:
            version = _generation_version(db, generation)
            output = db.scalar(
                select(VideoOutput).where(
                    VideoOutput.generation_id == generation.id,
                    VideoOutput.status == "approved",
                )
            )
            if output and version > latest_version:
                latest_version = version
                latest_output_id = output.id
        result.append(
            {
                "marketplace": row.marketplace,
                "listing_id": row.listing_id,
                "video_output_id": row.video_output_id,
                "video_version": row.video_version,
                "remote_video_id": row.remote_video_id,
                "latest_approved_video_output_id": latest_output_id,
                "latest_approved_video_version": latest_version,
                "update_available": latest_version > row.video_version,
            }
        )
    return result


@router.post("/recovery/actions")
def recovery_action(
    request: MarketplaceVideoRecoveryAction,
    db: SessionDep,
    owner: OwnerDep,
) -> dict[str, object]:
    job = db.scalar(
        select(MarketplaceVideoJob).where(
            MarketplaceVideoJob.id == request.job_id,
            MarketplaceVideoJob.owner_id == owner.id,
        )
    )
    if job is None:
        raise HTTPException(404, "Marketplace Video job was not found.")
    allowed = VIDEO_FAILURE_ACTIONS.get(
        job.last_error_code or "commerce.video.connector_unavailable",
        ["retry", "review_failure", "cancel"],
    )
    if request.action not in allowed:
        raise HTTPException(409, "That Marketplace Video recovery action is not available.")
    if not request.confirm:
        return {"status": "confirmation_required", "job_id": job.id, "available_actions": allowed}
    if request.action == "retry":
        job.state = "pending"
        job.last_error_code = None
        job.safe_error_message = None
    elif request.action == "cancel":
        job.state = "cancelled"
    db.commit()
    return {"status": job.state, "job_id": job.id, "available_actions": allowed}


@router.get("/recovery")
def recovery(db: SessionDep, owner: OwnerDep) -> list[dict[str, object]]:
    rows = db.scalars(
        select(MarketplaceVideoJob).where(
            MarketplaceVideoJob.owner_id == owner.id, MarketplaceVideoJob.state == "failed"
        )
    ).all()
    return [
        {
            "job_id": row.id,
            "marketplace": row.marketplace,
            "error_code": row.last_error_code,
            "safe_error_message": row.safe_error_message,
            "available_actions": VIDEO_FAILURE_ACTIONS.get(
                row.last_error_code or "commerce.video.connector_unavailable",
                ["retry", "review_failure", "cancel"],
            ),
        }
        for row in rows
    ]
