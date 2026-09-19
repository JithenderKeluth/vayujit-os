"""Deterministic, read-only competitor discovery and identity resolution."""

from __future__ import annotations

import hashlib
import json
import string
import unicodedata
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.commerce.models import MarketplaceListing
from vayujit_api.identity.models import User
from vayujit_api.intelligence.competitor_discovery_models import (
    CompetitorDiscoveryCandidate,
    CompetitorDiscoveryRequest,
    CompetitorDiscoverySnapshot,
)
from vayujit_api.intelligence.competitor_discovery_schemas import DiscoveryRequestCreate
from vayujit_api.intelligence.competitor_models import (
    CompetitorContext,
    CompetitorObservation,
    CompetitorProduct,
)
from vayujit_api.intelligence.competitor_service import get_context
from vayujit_api.intelligence.models import IntelligenceEvidence, IntelligenceSource

RULE_VERSION = "competitor-match-v1"


def _now() -> datetime:
    return datetime.now(UTC)


def normalize_identity_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value).casefold()
    text = "".join(" " if char in string.punctuation else char for char in text)
    return " ".join(text.split())


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _audit(
    db: Session, owner: User, action: str, entity_type: str, entity_id: uuid.UUID, key: str
) -> None:
    record_event(
        db,
        actor_id=owner.id,
        action=f"intelligence.{action.casefold()}",
        entity_type=entity_type,
        entity_id=entity_id,
        metadata={"event_type": action, "entity_id": str(entity_id)},
        idempotency_key=key,
    )


def get_request(db: Session, owner: User, request_id: uuid.UUID) -> CompetitorDiscoveryRequest:
    value = db.scalar(
        select(CompetitorDiscoveryRequest).where(
            CompetitorDiscoveryRequest.id == request_id,
            CompetitorDiscoveryRequest.owner_id == owner.id,
        )
    )
    if value is None:
        raise HTTPException(404, "Discovery request not found.")
    return value


def get_candidate(
    db: Session, owner: User, candidate_id: uuid.UUID
) -> CompetitorDiscoveryCandidate:
    value = db.scalar(
        select(CompetitorDiscoveryCandidate).where(
            CompetitorDiscoveryCandidate.id == candidate_id,
            CompetitorDiscoveryCandidate.owner_id == owner.id,
        )
    )
    if value is None:
        raise HTTPException(404, "Discovery candidate not found.")
    return value


def _source(db: Session, owner: User, mode: str) -> IntelligenceSource:
    provider = "canonical_listings" if mode == "CANONICAL_LISTINGS" else "local_fixture"
    display = f"Competitor discovery ({mode})"
    value = db.scalar(
        select(IntelligenceSource).where(
            IntelligenceSource.owner_id == owner.id,
            IntelligenceSource.provider == provider,
            IntelligenceSource.display_name == display,
        )
    )
    if value is not None:
        return value
    value = IntelligenceSource(
        owner_id=owner.id,
        source_type="internal_marketplace_data",
        display_name=display,
        provider=provider,
        enabled=True,
        trust_classification="trusted_internal",
        access_method="internal",
        configuration_status="configured",
        terms_policy_status="accepted",
        metadata_json={"read_only": True, "mode": mode},
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(value)
    db.flush()
    return value


def _evidence(
    db: Session,
    owner: User,
    source: IntelligenceSource,
    request: CompetitorDiscoveryRequest,
    row: dict[str, Any],
    key: str,
) -> IntelligenceEvidence:
    existing = db.scalar(
        select(IntelligenceEvidence).where(
            IntelligenceEvidence.owner_id == owner.id, IntelligenceEvidence.idempotency_key == key
        )
    )
    if existing is not None:
        return existing
    observed = _now()
    value = IntelligenceEvidence(
        owner_id=owner.id,
        source_id=source.id,
        source_reference=str(
            row.get("source_reference") or row.get("source_identifier") or request.id
        ),
        source_url=row.get("canonical_url"),
        observed_at=observed,
        retrieved_at=observed,
        content_type="application/json",
        normalized_value={"title": row.get("title", ""), "marketplace": row.get("marketplace", "")},
        excerpt_summary="Deterministic read-only discovery observation.",
        content_hash=_fingerprint(row),
        trust_classification=(
            "trusted_internal" if request.provider_mode == "CANONICAL_LISTINGS" else "fixture"
        ),
        verification_status="verified",
        freshness_status="fresh",
        freshness_ttl_seconds=3600,
        metadata_json={"request_id": str(request.id), "provider_mode": request.provider_mode},
        correlation_id=str(request.id)[:64],
        idempotency_key=key,
        created_at=observed,
    )
    db.add(value)
    db.flush()
    return value


def _canonical_rows(
    db: Session, owner: User, request: CompetitorDiscoveryRequest
) -> list[dict[str, Any]]:
    query = (
        select(MarketplaceListing)
        .where(
            MarketplaceListing.owner_id == owner.id,
            MarketplaceListing.status.in_(("ready", "active", "paused")),
        )
        .order_by(MarketplaceListing.updated_at.desc())
        .limit(request.maximum_candidates)
    )
    if request.marketplace:
        query = query.where(MarketplaceListing.marketplace == request.marketplace)
    return [
        {
            "source_mode": "CANONICAL_LISTINGS",
            "source_identifier": f"listing:{listing.id}",
            "listing_identifier": listing.remote_listing_id or listing.local_listing_id,
            "canonical_url": listing.external_url,
            "title": listing.title,
            "brand": str(listing.brand_id),
            "seller": None,
            "category": listing.category,
            "marketplace": listing.marketplace,
            "availability_state": "AVAILABLE" if listing.status == "active" else "UNKNOWN",
            "canonical_product_id": str(listing.product_id),
        }
        for listing in db.scalars(query)
    ]


def _fixture_rows(request: CompetitorDiscoveryRequest) -> list[dict[str, Any]]:
    fixture = request.filters.get("fixture_candidates", [])
    if not isinstance(fixture, list):
        raise HTTPException(422, "LOCAL_FIXTURE requires filters.fixture_candidates.")
    return [item for item in fixture if isinstance(item, dict)][: request.maximum_candidates]


def _rows(db: Session, owner: User, request: CompetitorDiscoveryRequest) -> list[dict[str, Any]]:
    if request.provider_mode == "DISABLED":
        raise HTTPException(409, "Competitor discovery provider is disabled.")
    if request.provider_mode == "LIVE_READ_ONLY":
        raise HTTPException(503, "Live read-only discovery provider is not configured.")
    if request.provider_mode == "LOCAL_FIXTURE":
        return _fixture_rows(request)
    return _canonical_rows(db, owner, request)


def _match(
    db: Session, owner: User, context: CompetitorContext, row: dict[str, Any]
) -> tuple[str, str, Decimal, list[str], list[str], list[str], uuid.UUID | None]:
    title = normalize_identity_text(str(row.get("title") or ""))
    brand = normalize_identity_text(str(row.get("brand") or ""))
    marketplace = str(row.get("marketplace") or context.marketplace)
    identifier = str(row.get("listing_identifier") or row.get("source_identifier") or "")
    existing = db.scalar(
        select(CompetitorProduct).where(
            CompetitorProduct.owner_id == owner.id,
            CompetitorProduct.context_id == context.id,
            CompetitorProduct.marketplace == marketplace,
            CompetitorProduct.external_identifier == identifier,
        )
    )
    if existing is not None:
        return (
            "CONFIRMED",
            "AUTHORITATIVE_IDENTIFIER",
            Decimal("1.0000"),
            ["existing_competitor_identifier"],
            [],
            [],
            existing.id,
        )
    canonical = row.get("canonical_product_id")
    if canonical:
        try:
            value = db.scalar(
                select(CompetitorProduct).where(
                    CompetitorProduct.owner_id == owner.id,
                    CompetitorProduct.context_id == context.id,
                    CompetitorProduct.canonical_product_id == uuid.UUID(str(canonical)),
                )
            )
        except ValueError:
            value = None
        if value is not None:
            return (
                "PROBABLE",
                "CANONICAL_PRODUCT",
                Decimal("0.9000"),
                ["canonical_product_id"],
                [],
                [],
                value.id,
            )
    matching = list(
        db.scalars(
            select(CompetitorProduct).where(
                CompetitorProduct.owner_id == owner.id, CompetitorProduct.context_id == context.id
            )
        )
    )
    matching = [item for item in matching if normalize_identity_text(item.title) == title]
    conflicts = [
        "brand_conflict"
        for item in matching
        if brand and item.brand_reference and normalize_identity_text(item.brand_reference) != brand
    ]
    if conflicts:
        return "AMBIGUOUS", "STRUCTURED_MATCH", Decimal("0.5000"), [], conflicts, ["seller"], None
    if matching:
        return (
            "PROBABLE",
            "STRUCTURED_MATCH",
            Decimal("0.8500"),
            ["normalized_title"],
            [],
            [],
            matching[0].id,
        )
    missing = ["brand"] if not brand else []
    if not row.get("seller"):
        missing.append("seller")
    return "CANDIDATE", "WEAK_CANDIDATE", Decimal("0.2500"), [], [], missing, None


def _product(
    db: Session,
    owner: User,
    context: CompetitorContext,
    candidate: CompetitorDiscoveryCandidate,
    canonical_product_id: uuid.UUID | None = None,
) -> CompetitorProduct:
    if candidate.competitor_product_id:
        value = db.scalar(
            select(CompetitorProduct).where(CompetitorProduct.id == candidate.competitor_product_id)
        )
        if value is not None:
            return value
    identifier = candidate.listing_identifier or candidate.source_identifier
    value = db.scalar(
        select(CompetitorProduct).where(
            CompetitorProduct.owner_id == owner.id,
            CompetitorProduct.context_id == context.id,
            CompetitorProduct.marketplace == candidate.marketplace,
            CompetitorProduct.external_identifier == identifier,
        )
    )
    if value is None:
        value = CompetitorProduct(
            owner_id=owner.id,
            context_id=context.id,
            title=candidate.raw_title,
            brand_reference=candidate.brand_claim,
            seller_reference=candidate.seller_claim,
            marketplace=candidate.marketplace,
            external_identifier=identifier,
            canonical_url=candidate.canonical_url,
            category=candidate.category,
            availability_state=candidate.availability_state,
            identity_state=candidate.identity_state,
            evidence_state="AVAILABLE",
            canonical_product_id=canonical_product_id,
            idempotency_key=f"competitor-discovery-product:{context.id}:{candidate.source_mode}:{identifier}",
            first_observed=_now(),
            last_observed=_now(),
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(value)
        db.flush()
    candidate.competitor_product_id = value.id
    return value


def _observation(
    db: Session,
    owner: User,
    product: CompetitorProduct,
    candidate: CompetitorDiscoveryCandidate,
    key: str,
    value: object,
    numeric: Decimal | None = None,
) -> None:
    existing = db.scalar(
        select(CompetitorObservation).where(
            CompetitorObservation.owner_id == owner.id,
            CompetitorObservation.competitor_product_id == product.id,
            CompetitorObservation.observation_key == key,
        )
    )
    if existing is not None:
        existing.observed_value = {"value": value}
        existing.observed_at = _now()
        existing.retrieved_at = _now()
        return
    db.add(
        CompetitorObservation(
            owner_id=owner.id,
            competitor_product_id=product.id,
            observation_type=key,
            observed_value={"value": value},
            numeric_value=numeric,
            source_id=candidate.source_id,
            source_reference=candidate.source_identifier,
            source_url=candidate.canonical_url,
            observed_at=_now(),
            retrieved_at=_now(),
            evidence_id=candidate.evidence_id,
            freshness_state="CURRENT",
            verification_state="OBSERVED",
            observation_key=key,
            created_at=_now(),
        )
    )


def create_request(
    db: Session, owner: User, context_id: uuid.UUID, data: DiscoveryRequestCreate
) -> CompetitorDiscoveryRequest:
    context = get_context(db, owner, context_id)
    if context.status == "ARCHIVED":
        raise HTTPException(409, "Archived competitor contexts cannot run discovery.")
    payload = data.model_dump(mode="json")
    fingerprint = _fingerprint({"context": str(context.id), **payload})
    key = data.idempotency_key or f"competitor-discovery:{context.id}:{fingerprint}"
    existing = db.scalar(
        select(CompetitorDiscoveryRequest).where(
            CompetitorDiscoveryRequest.owner_id == owner.id,
            CompetitorDiscoveryRequest.idempotency_key == key,
        )
    )
    if existing is not None:
        return existing
    value = CompetitorDiscoveryRequest(
        owner_id=owner.id,
        context_id=context.id,
        marketplace=data.marketplace or context.marketplace,
        market=data.market or context.market,
        category=data.category or context.category,
        query_inputs=data.query_inputs,
        filters=data.filters,
        source_selection=data.source_selection,
        maximum_candidates=data.maximum_candidates,
        provider_mode=data.provider_mode,
        input_fingerprint=fingerprint,
        status="PENDING",
        version=1,
        created_by=owner.id,
        idempotency_key=key,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(value)
    db.flush()
    _audit(
        db,
        owner,
        "COMPETITOR_DISCOVERY_REQUEST_CREATED",
        "discovery_request",
        value.id,
        f"discovery-request-created:{value.id}",
    )
    db.commit()
    db.refresh(value)
    return value


def _snapshot(
    db: Session,
    owner: User,
    request: CompetitorDiscoveryRequest,
    candidates: list[CompetitorDiscoveryCandidate],
) -> CompetitorDiscoverySnapshot:
    previous = db.scalar(
        select(CompetitorDiscoverySnapshot)
        .where(
            CompetitorDiscoverySnapshot.owner_id == owner.id,
            CompetitorDiscoverySnapshot.request_id == request.id,
        )
        .order_by(CompetitorDiscoverySnapshot.snapshot_version.desc())
    )
    version = previous.snapshot_version + 1 if previous else 1
    counts: dict[str, int] = {}
    for candidate in candidates:
        counts[candidate.source_mode] = counts.get(candidate.source_mode, 0) + 1
    evidence = sum(1 for value in candidates if value.evidence_id)
    value = CompetitorDiscoverySnapshot(
        owner_id=owner.id,
        request_id=request.id,
        context_id=request.context_id,
        snapshot_version=version,
        candidate_count=len(candidates),
        accepted_candidate_count=sum(
            value.identity_state in ("PROBABLE", "CONFIRMED") for value in candidates
        ),
        ambiguous_count=sum(value.identity_state == "AMBIGUOUS" for value in candidates),
        rejected_count=sum(value.identity_state == "REJECTED" for value in candidates),
        source_counts=counts,
        source_diversity=len(counts),
        evidence_coverage=Decimal(evidence / len(candidates)) if candidates else Decimal("0"),
        competitor_product_references=[
            str(value.competitor_product_id) for value in candidates if value.competitor_product_id
        ],
        input_fingerprint=request.input_fingerprint,
        previous_snapshot_id=previous.id if previous else None,
        source_freshness={mode: "CURRENT" for mode in counts},
        captured_at=_now(),
        idempotency_key=f"discovery-snapshot:{request.id}:{version}:{request.input_fingerprint}",
        created_at=_now(),
    )
    db.add(value)
    db.flush()
    return value


def execute_request(
    db: Session, owner: User, request: CompetitorDiscoveryRequest, *, refresh: bool = False
) -> tuple[
    CompetitorDiscoveryRequest, list[CompetitorDiscoveryCandidate], CompetitorDiscoverySnapshot
]:
    if request.status in ("COMPLETED", "PARTIALLY_COMPLETED") and not refresh:
        cached_candidates = list(
            db.scalars(
                select(CompetitorDiscoveryCandidate)
                .where(
                    CompetitorDiscoveryCandidate.owner_id == owner.id,
                    CompetitorDiscoveryCandidate.request_id == request.id,
                )
                .order_by(CompetitorDiscoveryCandidate.created_at.asc())
            )
        )
        snapshot = db.scalar(
            select(CompetitorDiscoverySnapshot)
            .where(
                CompetitorDiscoverySnapshot.owner_id == owner.id,
                CompetitorDiscoverySnapshot.request_id == request.id,
            )
            .order_by(CompetitorDiscoverySnapshot.snapshot_version.desc())
        )
        if snapshot is None:
            raise HTTPException(409, "Discovery request has no snapshot.")
        return request, cached_candidates, snapshot
    context = get_context(db, owner, request.context_id)
    request.status = "RUNNING"
    request.started_at = _now()
    request.updated_at = _now()
    db.flush()
    rows = _rows(db, owner, request)
    candidates: list[CompetitorDiscoveryCandidate] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        mode = str(row.get("source_mode") or request.provider_mode)
        identifier = str(
            row.get("source_identifier") or row.get("listing_identifier") or f"row:{index}"
        )
        dedupe_key = f"{mode}:{identifier}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        title = str(row.get("title") or "")
        source = _source(db, owner, mode)
        evidence = _evidence(
            db,
            owner,
            source,
            request,
            {**row, "source_identifier": identifier},
            f"discovery-evidence:{request.id}:{dedupe_key}",
        )
        state, level, score, supporting, conflicts, missing, product_id = _match(
            db, owner, context, row
        )
        candidate = db.scalar(
            select(CompetitorDiscoveryCandidate).where(
                CompetitorDiscoveryCandidate.owner_id == owner.id,
                CompetitorDiscoveryCandidate.request_id == request.id,
                CompetitorDiscoveryCandidate.source_mode == mode,
                CompetitorDiscoveryCandidate.source_identifier == identifier,
            )
        )
        values: dict[str, Any] = {
            "owner_id": owner.id,
            "request_id": request.id,
            "context_id": context.id,
            "source_mode": mode,
            "source_identifier": identifier,
            "listing_identifier": row.get("listing_identifier"),
            "canonical_url": row.get("canonical_url"),
            "raw_title": title[:500],
            "normalized_title": normalize_identity_text(title)[:500],
            "brand_claim": row.get("brand"),
            "seller_claim": row.get("seller"),
            "category": row.get("category"),
            "marketplace": str(row.get("marketplace") or request.marketplace),
            "price_amount": row.get("price_amount"),
            "currency": row.get("currency"),
            "rating": row.get("rating"),
            "review_count": row.get("review_count"),
            "availability_state": str(row.get("availability_state") or "UNKNOWN").upper(),
            "structured_attributes": (
                row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
            ),
            "identity_state": state,
            "match_level": level,
            "match_score": score,
            "supporting_signals": supporting,
            "conflicting_signals": conflicts,
            "missing_signals": missing,
            "rule_version": RULE_VERSION,
            "input_fingerprint": request.input_fingerprint,
            "evidence_state": "AVAILABLE",
            "freshness_state": "CURRENT",
            "source_id": source.id,
            "evidence_id": evidence.id,
            "competitor_product_id": product_id,
            "updated_at": _now(),
        }
        if candidate is None:
            candidate = CompetitorDiscoveryCandidate(
                **values,
                discovered_at=_now(),
                idempotency_key=f"discovery-candidate:{request.id}:{dedupe_key}",
                created_at=_now(),
            )
            db.add(candidate)
            db.flush()
        else:
            for key, item in values.items():
                if key not in {"owner_id", "request_id", "context_id"}:
                    setattr(candidate, key, item)
        if state in ("CONFIRMED", "PROBABLE") and candidate.competitor_product_id is None:
            canonical_id = None
            if row.get("canonical_product_id"):
                try:
                    canonical_id = uuid.UUID(str(row["canonical_product_id"]))
                except ValueError:
                    canonical_id = None
            candidate.competitor_product_id = _product(
                db, owner, context, candidate, canonical_id
            ).id
        if candidate.competitor_product_id:
            product = db.scalar(
                select(CompetitorProduct).where(
                    CompetitorProduct.id == candidate.competitor_product_id
                )
            )
            if product:
                _observation(db, owner, product, candidate, "title", candidate.raw_title)
                if candidate.price_amount is not None:
                    _observation(
                        db,
                        owner,
                        product,
                        candidate,
                        "price",
                        str(candidate.price_amount),
                        Decimal(str(candidate.price_amount)),
                    )
        candidates.append(candidate)
    request.status = "COMPLETED" if candidates else "PARTIALLY_COMPLETED"
    request.version += 1
    request.completed_at = _now()
    request.updated_at = _now()
    snapshot = _snapshot(db, owner, request, candidates)
    _audit(
        db,
        owner,
        "COMPETITOR_DISCOVERY_EXECUTED",
        "discovery_request",
        request.id,
        f"discovery-executed:{request.id}:{snapshot.snapshot_version}",
    )
    db.commit()
    db.refresh(request)
    db.refresh(snapshot)
    return request, candidates, snapshot


def resolve_candidate(
    db: Session,
    owner: User,
    candidate: CompetitorDiscoveryCandidate,
    *,
    state: str,
    reason: str,
    confirm: bool,
) -> CompetitorDiscoveryCandidate:
    if state == "CONFIRMED" and not confirm:
        raise HTTPException(422, "Confirmation is required to confirm a candidate.")
    if state not in {"CONFIRMED", "REJECTED", "AMBIGUOUS"}:
        raise HTTPException(422, "Unsupported resolution state.")
    context = get_context(db, owner, candidate.context_id)
    candidate.identity_state = state
    candidate.match_level = "HUMAN_CONFIRMED" if state == "CONFIRMED" else "STRUCTURED_MATCH"
    candidate.supporting_signals = [
        *candidate.supporting_signals,
        {"human_resolution": reason or state},
    ]
    if state == "CONFIRMED":
        candidate.competitor_product_id = _product(db, owner, context, candidate).id
    candidate.updated_at = _now()
    _audit(
        db,
        owner,
        f"COMPETITOR_DISCOVERY_CANDIDATE_{state}",
        "discovery_candidate",
        candidate.id,
        f"discovery-candidate:{candidate.id}:{state}:{candidate.updated_at.timestamp()}",
    )
    db.commit()
    db.refresh(candidate)
    return candidate


def integrity_report(db: Session, owner: User) -> dict[str, object]:
    request_count = (
        db.scalar(
            select(func.count())
            .select_from(CompetitorDiscoveryRequest)
            .where(CompetitorDiscoveryRequest.owner_id == owner.id)
        )
        or 0
    )
    candidate_count = (
        db.scalar(
            select(func.count())
            .select_from(CompetitorDiscoveryCandidate)
            .where(CompetitorDiscoveryCandidate.owner_id == owner.id)
        )
        or 0
    )
    snapshot_count = (
        db.scalar(
            select(func.count())
            .select_from(CompetitorDiscoverySnapshot)
            .where(CompetitorDiscoverySnapshot.owner_id == owner.id)
        )
        or 0
    )
    orphan = (
        db.scalar(
            select(func.count())
            .select_from(CompetitorDiscoveryCandidate)
            .where(
                CompetitorDiscoveryCandidate.owner_id == owner.id,
                ~select(CompetitorDiscoveryRequest.id)
                .where(CompetitorDiscoveryRequest.id == CompetitorDiscoveryCandidate.request_id)
                .exists(),
            )
        )
        or 0
    )
    return {
        "status": "healthy" if not orphan else "attention_required",
        "counts": {
            "requests": int(request_count),
            "candidates": int(candidate_count),
            "snapshots": int(snapshot_count),
        },
        "duplicate_counts": {"orphan_candidates": int(orphan)},
        "provider_modes": {
            "DISABLED": "fail_closed",
            "LOCAL_FIXTURE": "enabled",
            "LIVE_READ_ONLY": "not_configured",
        },
    }
