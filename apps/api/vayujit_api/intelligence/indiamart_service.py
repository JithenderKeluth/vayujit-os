# ruff: noqa: E501
"""IndiaMART discovery orchestration over normalized supplier intelligence."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.config import Settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchTask,
)
from vayujit_api.intelligence.external_pipeline import verify_and_project
from vayujit_api.intelligence.indiamart import discover_local, provider_preflight
from vayujit_api.intelligence.indiamart_models import (
    IndiaMartDiscoveryRequest,
    IndiaMartDiscoveryResult,
)
from vayujit_api.intelligence.supplier_models import (
    Supplier,
    SupplierEvidence,
    SupplierProduct,
    SupplierSource,
)
from vayujit_api.intelligence.website_intelligence import normalize_identity
from vayujit_api.intelligence.website_models import ManufacturerCandidate, SupplierWebsiteCandidate


def _now() -> datetime:
    return datetime.now(UTC)


def _lock(db: Session, key: str) -> None:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        number = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") & ((1 << 63) - 1)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": number})


def preflight(settings: Settings) -> dict[str, object]:
    value = provider_preflight(settings)
    if settings.indiamart_mode == "LIVE_READ_ONLY":
        value = {**value, "status": "BLOCKED_BY_EXTERNAL_CONFIGURATION"}
    return value


def _identity(name: str, location: str | None) -> str:
    return hashlib.sha256(
        f"{name.casefold().strip()}|{(location or '').casefold().strip()}".encode()
    ).hexdigest()


def _tokens(value: str) -> set[str]:
    return {token for token in normalize_identity(value).split() if len(token) > 2}


def _identity_match(db: Session, owner: User, name: str) -> str:
    """Classify a provider name against owner-scoped persisted identities.

    Matching is deterministic and advisory. A possible match never merges records.
    """
    target = _tokens(name)
    if not target:
        return "UNKNOWN"
    suppliers = list(db.scalars(select(Supplier).where(Supplier.owner_id == owner.id)))
    if any(_tokens(row.display_name) == target for row in suppliers):
        return "MATCH"
    website_candidates = list(
        db.scalars(
            select(SupplierWebsiteCandidate).where(SupplierWebsiteCandidate.owner_id == owner.id)
        )
    )
    linked_supplier_ids = {row.supplier_id for row in website_candidates if row.supplier_id}
    if any(
        row.id in linked_supplier_ids and _tokens(row.display_name) == target for row in suppliers
    ):
        return "MATCH"
    manufacturers = list(
        db.scalars(select(ManufacturerCandidate).where(ManufacturerCandidate.owner_id == owner.id))
    )
    if any(_tokens(row.normalized_name or row.name) == target for row in manufacturers):
        return "MATCH"
    known = [row.domain for row in website_candidates]
    known.extend(row.normalized_name or row.name for row in manufacturers)
    if not known:
        return "UNKNOWN"
    if any(len(target & _tokens(value)) >= 2 for value in known):
        return "POSSIBLE_MATCH"
    return "NO_MATCH"


def _product_match(
    db: Session, owner: User, product_id: uuid.UUID | None, query: str, listing_name: str
) -> str:
    if product_id is None:
        return "UNKNOWN"
    from vayujit_api.products.models import Product

    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.owner_id == owner.id)
    )
    if product is None:
        return "NO_MATCH"
    product_tokens = _tokens(product.name)
    query_tokens = _tokens(query)
    listing_tokens = _tokens(listing_name)
    if query_tokens and query_tokens <= listing_tokens:
        return "MATCH"
    if product_tokens and (product_tokens <= query_tokens or query_tokens <= product_tokens):
        return "MATCH"
    if product.category and _tokens(product.category) & query_tokens:
        return "POSSIBLE_MATCH"
    return "NO_MATCH"


def _offering_match(db: Session, owner: User, supplier_id: uuid.UUID, listing_name: str) -> str:
    offerings = list(
        db.scalars(
            select(SupplierProduct).where(
                SupplierProduct.owner_id == owner.id,
                SupplierProduct.supplier_id == supplier_id,
            )
        )
    )
    if not offerings:
        return "UNKNOWN"
    target = _tokens(listing_name)
    if any(_tokens(row.title) == target for row in offerings):
        return "MATCH"
    if any(len(target & _tokens(row.title)) >= 2 for row in offerings):
        return "POSSIBLE_MATCH"
    return "NO_MATCH"


def _append_observations(row: IndiaMartDiscoveryResult, listing: object, stamp: datetime) -> None:
    values = {
        "PRICE": getattr(listing, "price", None),
        "MOQ": getattr(listing, "moq", None),
        "LEAD_TIME": getattr(listing, "lead_time", None),
        "VERIFICATION_CLAIM": getattr(listing, "verification_claim", None),
        "AVAILABILITY": getattr(listing, "availability", None),
    }
    metadata = dict(row.metadata_json or {})
    history = metadata.get("observation_history", [])
    history = list(history) if isinstance(history, list) else []
    for field, value in values.items():
        previous = next(
            (
                item
                for item in reversed(history)
                if isinstance(item, dict) and item.get("field") == field
            ),
            None,
        )
        previous_value = previous.get("value") if isinstance(previous, dict) else None
        if previous is not None and previous_value == value:
            continue
        version = (
            sum(1 for item in history if isinstance(item, dict) and item.get("field") == field) + 1
        )
        history.append(
            {
                "field": field,
                "version": version,
                "value": value,
                "previous_value": previous_value,
                "observed_at": stamp.isoformat(),
            }
        )
    metadata["observation_history"] = history
    row.metadata_json = metadata


def _payload(row: IndiaMartDiscoveryResult) -> dict[str, object]:
    return {
        "id": str(row.id),
        "request_id": str(row.request_id),
        "provider": row.provider,
        "provider_result_id": row.provider_result_id,
        "supplier_id": str(row.supplier_id) if row.supplier_id else None,
        "supplier_name": row.supplier_name,
        "listing_name": row.listing_name,
        "source_url": row.source_url,
        "location": row.location,
        "category": row.category,
        "price_claim": float(row.price_claim) if row.price_claim is not None else None,
        "currency": row.currency,
        "moq_claim": float(row.moq_claim) if row.moq_claim is not None else None,
        "moq_unit": row.moq_unit,
        "lead_time_claim": row.lead_time_claim,
        "availability_claim": row.availability_claim,
        "verification_claim": row.verification_claim,
        "identity_match": row.identity_match,
        "product_match": row.product_match,
        "offering_match": (row.metadata_json or {}).get("offering_match", "UNKNOWN"),
        "observation_history": (row.metadata_json or {}).get("observation_history", []),
        "freshness_status": row.freshness_status,
        "classification": row.classification,
        "evidence_id": str(row.evidence_id) if row.evidence_id else None,
        "correlation_id": row.correlation_id,
        "retrieved_at": row.retrieved_at,
    }


def discover(
    db: Session,
    owner: User,
    settings: Settings,
    *,
    query: str,
    product_id: uuid.UUID | None,
    country_code: str | None,
    region: str | None,
    result_limit: int,
    correlation_id: str | None,
    idempotency_key: str | None,
    mission_id: uuid.UUID | None,
    task_id: uuid.UUID | None,
) -> dict[str, object]:
    if product_id is not None:
        from vayujit_api.products.models import Product

        if (
            db.scalar(select(Product).where(Product.id == product_id, Product.owner_id == owner.id))
            is None
        ):
            raise HTTPException(404, "Product not found.")
    key = (
        idempotency_key
        or hashlib.sha256(
            f"{owner.id}|{query.casefold()}|{product_id}|{country_code}|{region}|{result_limit}".encode()
        ).hexdigest()
    )
    _lock(db, f"indiamart:{owner.id}:{key}")
    request = db.scalar(
        select(IndiaMartDiscoveryRequest).where(
            IndiaMartDiscoveryRequest.owner_id == owner.id,
            IndiaMartDiscoveryRequest.idempotency_key == key,
        )
    )
    if request is not None:
        existing_rows = list(
            db.scalars(
                select(IndiaMartDiscoveryResult)
                .where(IndiaMartDiscoveryResult.request_id == request.id)
                .order_by(IndiaMartDiscoveryResult.created_at)
            )
        )
        return {
            "request": _request_payload(request),
            "results": [_payload(row) for row in existing_rows],
        }
    readiness = preflight(settings)
    if readiness["status"] != "READY":
        raise HTTPException(409, f"IndiaMART discovery is {readiness['status']}.")
    if result_limit > settings.indiamart_max_results:
        raise HTTPException(422, "IndiaMART result limit exceeds the configured safety bound.")
    now = _now()
    minute_count = (
        db.scalar(
            select(func.count())
            .select_from(IndiaMartDiscoveryRequest)
            .where(
                IndiaMartDiscoveryRequest.owner_id == owner.id,
                IndiaMartDiscoveryRequest.created_at >= now - timedelta(minutes=1),
            )
        )
        or 0
    )
    if int(minute_count) >= settings.indiamart_requests_per_minute:
        raise HTTPException(429, "IndiaMART request rate limit reached; retry later.")
    day_count = (
        db.scalar(
            select(func.count())
            .select_from(IndiaMartDiscoveryRequest)
            .where(
                IndiaMartDiscoveryRequest.owner_id == owner.id,
                IndiaMartDiscoveryRequest.created_at >= now - timedelta(days=1),
            )
        )
        or 0
    )
    if int(day_count) >= settings.indiamart_daily_quota:
        raise HTTPException(429, "IndiaMART daily quota reached; retry later.")
    stamp = now
    request = IndiaMartDiscoveryRequest(
        owner_id=owner.id,
        product_id=product_id,
        query=query.strip(),
        country_code=country_code.upper() if country_code else None,
        region=region,
        result_limit=result_limit,
        provider="INDIAMART",
        mode=settings.indiamart_mode,
        status="running",
        result_count=0,
        correlation_id=correlation_id or uuid.uuid4().hex,
        mission_id=mission_id,
        task_id=task_id,
        idempotency_key=key,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(request)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="indiamart.discovery.requested",
        entity_type=request.__tablename__,
        entity_id=request.id,
    )
    rows: list[IndiaMartDiscoveryResult] = []
    for listing in discover_local(query=query, limit=result_limit, country_code=country_code):
        supplier_identity = _identity(listing.supplier_name, listing.location)
        supplier = next(
            (
                value
                for value in db.scalars(select(Supplier).where(Supplier.owner_id == owner.id))
                if _tokens(value.display_name) == _tokens(listing.supplier_name)
            ),
            None,
        )
        if supplier is None:
            supplier = db.scalar(
                select(Supplier).where(
                    Supplier.owner_id == owner.id, Supplier.normalized_identity == supplier_identity
                )
            )
        if supplier is None:
            supplier = Supplier(
                owner_id=owner.id,
                display_name=listing.supplier_name,
                supplier_type="unknown",
                country_code="IN",
                country="India",
                region=(
                    (listing.location or "").split(",")[1].strip()
                    if "," in (listing.location or "")
                    else None
                ),
                city=(listing.location or "").split(",")[0].strip() if listing.location else None,
                source_identity="indiamart",
                normalized_identity=supplier_identity,
                verification_state="unverified",
                communication_status="not_contacted",
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(supplier)
            db.flush()
        source = db.scalar(
            select(SupplierSource).where(
                SupplierSource.owner_id == owner.id,
                SupplierSource.supplier_id == supplier.id,
                SupplierSource.source_type == "indiamart",
                SupplierSource.external_id == listing.provider_result_id,
            )
        )
        if source is None:
            source = SupplierSource(
                owner_id=owner.id,
                supplier_id=supplier.id,
                source_type="indiamart",
                access_mode="provider_connector",
                external_id=listing.provider_result_id,
                reference=listing.provider_result_id,
                source_url=listing.source_url,
                status="local_fixture",
                metadata_json={"classification": "DISCOVERY_ONLY"},
                observed_at=stamp,
                created_at=stamp,
            )
            db.add(source)
            db.flush()
        offering = db.scalar(
            select(SupplierProduct).where(
                SupplierProduct.owner_id == owner.id,
                SupplierProduct.supplier_id == supplier.id,
                SupplierProduct.source_id == source.id,
            )
        )
        if offering is None:
            offering = SupplierProduct(
                owner_id=owner.id,
                supplier_id=supplier.id,
                source_id=source.id,
                source_reference=listing.provider_result_id,
                title=listing.listing_name,
                category=listing.category or "unknown",
                specifications={},
                observed_price=listing.price,
                currency=listing.currency,
                price_kind="displayed_price" if listing.price is not None else "unknown",
                moq=listing.moq,
                moq_unit=listing.moq_unit,
                production_lead_days=None,
                evidence_ids=[],
                observed_at=stamp,
                freshness_status="fresh",
                created_at=stamp,
            )
            db.add(offering)
            db.flush()
        evidence_key = f"indiamart:{owner.id}:{listing.provider_result_id}:{hashlib.sha256(listing.listing_name.encode()).hexdigest()[:16]}"
        evidence = db.scalar(
            select(SupplierEvidence).where(
                SupplierEvidence.owner_id == owner.id,
                SupplierEvidence.idempotency_key == evidence_key,
            )
        )
        if evidence is None:
            evidence = SupplierEvidence(
                owner_id=owner.id,
                supplier_id=supplier.id,
                source_id=source.id,
                evidence_kind="observed",
                reference=listing.provider_result_id,
                source_url=listing.source_url,
                normalized_value={"provider": "INDIAMART", "listing": listing.listing_name},
                excerpt="Provider discovery claim; verification required.",
                content_hash=hashlib.sha256(listing.provider_result_id.encode()).hexdigest(),
                observed_at=stamp,
                retrieved_at=stamp,
                freshness_status="fresh",
                verification_status="unverified",
                idempotency_key=evidence_key,
                updated_at=stamp,
            )
            db.add(evidence)
            db.flush()
        if str(evidence.id) not in offering.evidence_ids:
            offering.evidence_ids = [*offering.evidence_ids, str(evidence.id)]
        identity_match = _identity_match(db, owner, listing.supplier_name)
        product_match = _product_match(db, owner, product_id, query, listing.listing_name)
        offering_match = _offering_match(db, owner, supplier.id, listing.listing_name)
        existing_result = db.scalar(
            select(IndiaMartDiscoveryResult).where(
                IndiaMartDiscoveryResult.owner_id == owner.id,
                IndiaMartDiscoveryResult.provider_result_id == listing.provider_result_id,
            )
        )
        if existing_result is not None:
            _append_observations(existing_result, listing, stamp)
            existing_result.price_claim = (
                Decimal(str(listing.price)) if listing.price is not None else None
            )
            existing_result.currency = listing.currency
            existing_result.moq_claim = (
                Decimal(str(listing.moq)) if listing.moq is not None else None
            )
            existing_result.moq_unit = listing.moq_unit
            existing_result.lead_time_claim = listing.lead_time
            existing_result.availability_claim = listing.availability
            existing_result.verification_claim = listing.verification_claim
            existing_result.identity_match = identity_match
            existing_result.product_match = product_match
            existing_result.metadata_json = {
                **(existing_result.metadata_json or {}),
                **listing.metadata,
                "offering_match": offering_match,
            }
            existing_result.retrieved_at = stamp
            rows.append(existing_result)
            continue
        row = IndiaMartDiscoveryResult(
            owner_id=owner.id,
            request_id=request.id,
            supplier_id=supplier.id,
            source_id=source.id,
            offering_id=offering.id,
            product_id=product_id,
            provider="INDIAMART",
            provider_result_id=listing.provider_result_id,
            supplier_name=listing.supplier_name,
            listing_name=listing.listing_name,
            source_url=listing.source_url,
            location=listing.location,
            category=listing.category,
            price_claim=Decimal(str(listing.price)) if listing.price is not None else None,
            currency=listing.currency,
            moq_claim=Decimal(str(listing.moq)) if listing.moq is not None else None,
            moq_unit=listing.moq_unit,
            lead_time_claim=listing.lead_time,
            availability_claim=listing.availability,
            verification_claim=listing.verification_claim,
            identity_match=identity_match,
            product_match=product_match,
            freshness_status="fresh",
            classification="DISCOVERY_ONLY",
            metadata_json={**listing.metadata, "offering_match": offering_match},
            evidence_id=evidence.id,
            observation_key=f"{listing.provider_result_id}:{listing.listing_name.casefold()}",
            correlation_id=request.correlation_id,
            retrieved_at=stamp,
            idempotency_key=evidence_key,
            created_at=stamp,
        )
        _append_observations(row, listing, stamp)
        db.add(row)
        rows.append(row)
    request.status = "completed"
    request.result_count = len(rows)
    request.updated_at = _now()
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="indiamart.discovery.completed",
        entity_type=request.__tablename__,
        entity_id=request.id,
    )
    db.commit()
    return {"request": _request_payload(request), "results": [_payload(row) for row in rows]}


def _request_payload(row: IndiaMartDiscoveryRequest) -> dict[str, object]:
    return {
        "id": str(row.id),
        "provider": row.provider,
        "mode": row.mode,
        "status": row.status,
        "query": row.query,
        "result_count": row.result_count,
        "correlation_id": row.correlation_id,
        "idempotency_key": row.idempotency_key,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_discoveries(db: Session, owner: User, limit: int = 100) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(IndiaMartDiscoveryRequest)
            .where(IndiaMartDiscoveryRequest.owner_id == owner.id)
            .order_by(IndiaMartDiscoveryRequest.created_at.desc())
            .limit(limit)
        )
    )
    return [_request_payload(row) for row in rows]


def detail(db: Session, owner: User, request_id: uuid.UUID) -> dict[str, object]:
    row = db.scalar(
        select(IndiaMartDiscoveryRequest).where(
            IndiaMartDiscoveryRequest.id == request_id,
            IndiaMartDiscoveryRequest.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "IndiaMART discovery not found.")
    results = list(
        db.scalars(
            select(IndiaMartDiscoveryResult)
            .where(IndiaMartDiscoveryResult.request_id == row.id)
            .order_by(IndiaMartDiscoveryResult.created_at)
        )
    )
    return {"request": _request_payload(row), "results": [_payload(value) for value in results]}


def operations(db: Session, owner: User, settings: Settings) -> dict[str, object]:
    return {
        "provider": "INDIAMART",
        "preflight": preflight(settings),
        "read_only": True,
        "live_validation": "NOT_RUN",
        "budget": {
            "requests_per_minute": settings.indiamart_requests_per_minute,
            "daily_quota": settings.indiamart_daily_quota,
            "max_results": settings.indiamart_max_results,
            "retry_max_attempts": settings.indiamart_retry_max_attempts,
        },
        "recovery": {
            "registered": True,
            "separate_recovery_system": False,
            "failure_codes": [
                "TIMEOUT",
                "NETWORK_FAILURE",
                "PROVIDER_5XX",
                "RATE_LIMITED",
                "AUTH_FAILURE",
                "INVALID_RESPONSE",
                "BUDGET_EXHAUSTED",
                "PROVIDER_DISABLED",
                "GLOBAL_DISABLED",
                "EVIDENCE_REJECTED",
                "CHECKPOINT_INVALID",
            ],
            "supported_actions": [
                "retry",
                "refresh_source",
                "review_source",
                "review_evidence",
                "reconcile",
                "cancel",
                "skip_optional_task",
            ],
            "retryable_failures": [
                "TIMEOUT",
                "NETWORK_FAILURE",
                "PROVIDER_5XX",
                "RATE_LIMITED",
            ],
            "shared_autonomous_failure_codes": [
                "timeout",
                "source_unavailable",
                "source_rate_limited",
                "source_auth_failed",
                "invalid_payload",
                "evidence_validation_failed",
                "budget_exhausted",
                "checkpoint_invalid",
            ],
        },
        "request_count": int(
            db.scalar(
                select(func.count())
                .select_from(IndiaMartDiscoveryRequest)
                .where(IndiaMartDiscoveryRequest.owner_id == owner.id)
            )
            or 0
        ),
        "result_count": int(
            db.scalar(
                select(func.count())
                .select_from(IndiaMartDiscoveryResult)
                .where(IndiaMartDiscoveryResult.owner_id == owner.id)
            )
            or 0
        ),
        "failure_count": int(
            db.scalar(
                select(func.count())
                .select_from(IndiaMartDiscoveryRequest)
                .where(
                    IndiaMartDiscoveryRequest.owner_id == owner.id,
                    IndiaMartDiscoveryRequest.status == "failed",
                )
            )
            or 0
        ),
        "prohibited_actions": ["contact", "rfq", "order", "payment", "supplier_modification"],
    }


def handoff_evidence(
    db: Session,
    owner: User,
    result_id: uuid.UUID,
    mission_id: uuid.UUID,
    task_id: uuid.UUID,
) -> dict[str, object]:
    """Hand one normalized discovery result to the existing evidence verifier."""
    result = db.scalar(
        select(IndiaMartDiscoveryResult).where(
            IndiaMartDiscoveryResult.id == result_id,
            IndiaMartDiscoveryResult.owner_id == owner.id,
        )
    )
    if result is None:
        raise HTTPException(404, "IndiaMART discovery result not found.")
    mission = db.scalar(
        select(AutonomousResearchMission).where(
            AutonomousResearchMission.id == mission_id,
            AutonomousResearchMission.owner_id == owner.id,
        )
    )
    task = db.scalar(
        select(AutonomousResearchTask).where(
            AutonomousResearchTask.id == task_id,
            AutonomousResearchTask.owner_id == owner.id,
            AutonomousResearchTask.mission_id == mission_id,
        )
    )
    if mission is None or task is None:
        raise HTTPException(404, "Autonomous evidence lineage was not found.")
    observation_fingerprint = hashlib.sha256(
        json.dumps(result.metadata_json or {}, sort_keys=True, default=str).encode()
    ).hexdigest()[:24]
    retrieval_identity = (
        f"indiamart:{owner.id}:{result.provider_result_id}:{observation_fingerprint}"
    )
    evidence = db.scalar(
        select(AutonomousResearchEvidence).where(
            AutonomousResearchEvidence.owner_id == owner.id,
            AutonomousResearchEvidence.retrieval_identity == retrieval_identity,
        )
    )
    reused = evidence is not None
    if evidence is not None and (evidence.mission_id != mission.id or evidence.task_id != task.id):
        raise HTTPException(409, "IndiaMART evidence is already linked to another research task.")
    if evidence is None:
        claims: list[dict[str, object]] = []
        for key, value in (
            ("PRICE", result.price_claim),
            ("MOQ", result.moq_claim),
            ("LEAD_TIME", result.lead_time_claim),
            ("AVAILABILITY", result.availability_claim),
            ("SUPPLIER_VERIFICATION", result.verification_claim),
        ):
            if value is not None:
                safe_value = float(value) if isinstance(value, Decimal) else value
                claims.append({"key": key, "value": safe_value})
        normalized = {
            "provider": "INDIAMART",
            "result_id": str(result.id),
            "provider_result_id": result.provider_result_id,
            "supplier_id": str(result.supplier_id) if result.supplier_id else None,
            "product_id": str(result.product_id) if result.product_id else None,
            "offering_id": str(result.offering_id) if result.offering_id else None,
            "claims": claims,
            "text": "Normalized IndiaMART discovery observation; independent verification required.",
            "source_profile": "INDIAMART_LOCAL_FIXTURE",
            "fetch_id": result.provider_result_id,
            "search_result_id": result.provider_result_id,
            "requested_url": result.source_url,
            "final_url": result.source_url,
            "correlation_id": result.correlation_id,
        }
        canonical = json.dumps(normalized, sort_keys=True, default=str, separators=(",", ":"))
        evidence = AutonomousResearchEvidence(
            owner_id=owner.id,
            mission_id=mission.id,
            task_id=task.id,
            source_class="INDIAMART_DISCOVERY",
            source_reference=result.source_url or result.provider_result_id,
            retrieval_identity=retrieval_identity,
            content_type="application/json",
            normalized_value=normalized,
            content_hash=hashlib.sha256(canonical.encode()).hexdigest(),
            verification_status="UNVERIFIED",
            freshness_status=result.freshness_status.upper(),
            source_profile="INDIAMART_LOCAL_FIXTURE",
            provider="INDIAMART",
            canonical_url=result.source_url,
            domain="indiamart.com",
            lineage={
                "result_id": str(result.id),
                "provider_result_id": result.provider_result_id,
                "supplier_id": str(result.supplier_id) if result.supplier_id else None,
                "product_id": str(result.product_id) if result.product_id else None,
                "offering_id": str(result.offering_id) if result.offering_id else None,
                "mission_id": str(mission.id),
                "task_id": str(task.id),
                "correlation_id": result.correlation_id,
            },
            confidence=Decimal("0.5500"),
            evidence_class="SUPPLIER_DISCOVERY",
            is_untrusted_external_data=True,
            observed_at=result.retrieved_at,
            retrieved_at=result.retrieved_at,
            created_at=_now(),
        )
        db.add(evidence)
        db.flush()
        verify_and_project(db, owner, mission, task, evidence)
        evidence.lineage = {
            **(evidence.lineage or {}),
            "result_id": str(result.id),
            "supplier_id": str(result.supplier_id) if result.supplier_id else None,
            "product_id": str(result.product_id) if result.product_id else None,
            "offering_id": str(result.offering_id) if result.offering_id else None,
        }
        result.evidence_id = evidence.id
        record_event(
            db,
            actor_id=owner.id,
            action="indiamart.discovery.evidence_handoff",
            entity_type=result.__tablename__,
            entity_id=result.id,
            metadata={"verification_status": evidence.verification_status},
            idempotency_key=f"indiamart:evidence:{retrieval_identity}",
        )
        db.commit()
    else:
        result.evidence_id = evidence.id
        record_event(
            db,
            actor_id=owner.id,
            action="indiamart.discovery.evidence_handoff",
            entity_type=result.__tablename__,
            entity_id=result.id,
            metadata={"verification_status": evidence.verification_status},
            idempotency_key=f"indiamart:evidence:{retrieval_identity}",
        )
        db.commit()
    return {
        "id": str(evidence.id),
        "result_id": str(result.id),
        "provider": evidence.provider,
        "source_class": evidence.source_class,
        "retrieval_identity": evidence.retrieval_identity,
        "verification_status": evidence.verification_status,
        "verification_reason": evidence.verification_reason,
        "freshness_status": evidence.freshness_status,
        "confidence": float(evidence.confidence),
        "lineage": dict(evidence.lineage or {}),
        "idempotent_reuse": reused,
    }
