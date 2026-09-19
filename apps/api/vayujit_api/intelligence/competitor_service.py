"""Synchronous owner-scoped services for Competitor Intelligence 10A."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand
from vayujit_api.identity.models import User
from vayujit_api.intelligence.competitor_models import (
    AVAILABILITY_STATES,
    CONTEXT_STATUSES,
    ENTITY_TYPES,
    EVIDENCE_STATES,
    FRESHNESS_STATES,
    IDENTITY_STATES,
    CompetitorContext,
    CompetitorEntity,
    CompetitorObservation,
    CompetitorProduct,
    CompetitorSnapshot,
)
from vayujit_api.intelligence.competitor_schemas import (
    CompetitorProductCreate,
    CompetitorProductIdentityUpdate,
    ContextCreate,
    EntityCreate,
    ObservationCreate,
    SnapshotCreate,
)
from vayujit_api.intelligence.models import IntelligenceEvidence, IntelligenceSource
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.products.models import Product


def _now() -> datetime:
    return datetime.now(UTC)


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


def get_context(db: Session, owner: User, context_id: uuid.UUID) -> CompetitorContext:
    value = db.scalar(
        select(CompetitorContext).where(
            CompetitorContext.id == context_id, CompetitorContext.owner_id == owner.id
        )
    )
    if value is None:
        raise HTTPException(404, "Competitor context not found.")
    return value


def get_entity(db: Session, owner: User, entity_id: uuid.UUID) -> CompetitorEntity:
    value = db.scalar(
        select(CompetitorEntity).where(
            CompetitorEntity.id == entity_id, CompetitorEntity.owner_id == owner.id
        )
    )
    if value is None:
        raise HTTPException(404, "Competitor entity not found.")
    return value


def get_competitor_product(db: Session, owner: User, product_id: uuid.UUID) -> CompetitorProduct:
    value = db.scalar(
        select(CompetitorProduct).where(
            CompetitorProduct.id == product_id, CompetitorProduct.owner_id == owner.id
        )
    )
    if value is None:
        raise HTTPException(404, "Competitor product not found.")
    return value


def _existing_by_key[T](db: Session, model: type[T], owner: User, key: str) -> T | None:
    return db.scalar(select(model).where(model.owner_id == owner.id, model.idempotency_key == key))  # type: ignore[attr-defined, no-any-return]


def create_context(db: Session, owner: User, data: ContextCreate) -> CompetitorContext:
    key = data.idempotency_key or (
        f"competitor-context:{data.subject_type}:{data.subject_reference}:"
        f"{data.marketplace}:{data.market}"
    )
    existing = _existing_by_key(db, CompetitorContext, owner, key)
    if existing is not None:
        return existing
    context_ids: dict[str, uuid.UUID | None] = {
        "product_opportunity_id": None,
        "product_id": None,
        "brand_id": None,
    }
    if data.subject_type == "PRODUCT_OPPORTUNITY":
        if (
            db.scalar(
                select(ProductOpportunity.id).where(
                    ProductOpportunity.id == data.subject_reference,
                    ProductOpportunity.owner_id == owner.id,
                )
            )
            is None
        ):
            raise HTTPException(404, "Product opportunity not found.")
        context_ids["product_opportunity_id"] = data.subject_reference
    elif data.subject_type == "PRODUCT":
        if (
            db.scalar(
                select(Product.id).where(
                    Product.id == data.subject_reference, Product.owner_id == owner.id
                )
            )
            is None
        ):
            raise HTTPException(404, "Product not found.")
        context_ids["product_id"] = data.subject_reference
    elif (
        db.scalar(
            select(Brand.id).where(Brand.id == data.subject_reference, Brand.owner_id == owner.id)
        )
        is None
    ):
        raise HTTPException(404, "Brand not found.")
    else:
        context_ids["brand_id"] = data.subject_reference
    value = CompetitorContext(
        owner_id=owner.id,
        created_by=owner.id,
        subject_type=data.subject_type,
        subject_reference=data.subject_reference,
        marketplace=data.marketplace.strip(),
        market=data.market.strip(),
        category=data.category.strip(),
        currency=data.currency,
        status=data.status,
        idempotency_key=key,
        **context_ids,
    )
    db.add(value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(CompetitorContext).where(
                CompetitorContext.owner_id == owner.id, CompetitorContext.idempotency_key == key
            )
        )
        if existing is not None:
            return existing
        raise
    _audit(
        db,
        owner,
        "COMPETITOR_CONTEXT_CREATED",
        "competitor_context",
        value.id,
        f"competitor-context-created:{value.id}",
    )
    db.commit()
    db.refresh(value)
    return value


def archive_context(db: Session, owner: User, context: CompetitorContext) -> CompetitorContext:
    if context.status != "ARCHIVED":
        context.status = "ARCHIVED"
        context.archived_at = _now()
        context.version += 1
        context.updated_at = _now()
        _audit(
            db,
            owner,
            "COMPETITOR_CONTEXT_ARCHIVED",
            "competitor_context",
            context.id,
            f"competitor-context-archived:{context.id}:{context.version}",
        )
        db.commit()
        db.refresh(context)
    return context


def create_entity(db: Session, owner: User, data: EntityCreate) -> CompetitorEntity:
    key = (
        data.idempotency_key
        or f"competitor-entity:{data.entity_type}:{data.canonical_name.casefold()}"
    )
    existing = _existing_by_key(db, CompetitorEntity, owner, key)
    if existing is not None:
        return existing
    value = CompetitorEntity(
        owner_id=owner.id, idempotency_key=key, **data.model_dump(exclude={"idempotency_key"})
    )
    value.canonical_name = value.canonical_name.strip().casefold()
    db.add(value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(CompetitorEntity).where(
                CompetitorEntity.owner_id == owner.id,
                CompetitorEntity.canonical_name == value.canonical_name,
                CompetitorEntity.entity_type == value.entity_type,
            )
        )
        if existing is not None:
            return existing
        raise
    _audit(
        db,
        owner,
        "COMPETITOR_ENTITY_CREATED",
        "competitor_entity",
        value.id,
        f"competitor-entity-created:{value.id}",
    )
    db.commit()
    db.refresh(value)
    return value


def create_product(
    db: Session, owner: User, context: CompetitorContext, data: CompetitorProductCreate
) -> CompetitorProduct:
    if data.entity_id is not None:
        get_entity(db, owner, data.entity_id)
    if (
        data.canonical_product_id is not None
        and db.scalar(
            select(Product.id).where(
                Product.id == data.canonical_product_id, Product.owner_id == owner.id
            )
        )
        is None
    ):
        raise HTTPException(404, "Canonical product not found.")
    key = (
        data.idempotency_key
        or f"competitor-product:{context.id}:{data.marketplace}:{data.external_identifier}"
    )
    existing = _existing_by_key(db, CompetitorProduct, owner, key)
    if existing is not None:
        if existing.context_id != context.id:
            raise HTTPException(409, "Idempotency key belongs to another competitor context.")
        return existing
    value = CompetitorProduct(
        owner_id=owner.id,
        context_id=context.id,
        idempotency_key=key,
        **data.model_dump(exclude={"idempotency_key"}),
    )
    db.add(value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(CompetitorProduct).where(
                CompetitorProduct.owner_id == owner.id,
                CompetitorProduct.context_id == context.id,
                CompetitorProduct.marketplace == data.marketplace,
                CompetitorProduct.external_identifier == data.external_identifier,
            )
        )
        if existing is not None:
            return existing
        raise
    _audit(
        db,
        owner,
        "COMPETITOR_PRODUCT_ADDED",
        "competitor_product",
        value.id,
        f"competitor-product-added:{value.id}",
    )
    db.commit()
    db.refresh(value)
    return value


def update_identity(
    db: Session, owner: User, product: CompetitorProduct, data: CompetitorProductIdentityUpdate
) -> CompetitorProduct:
    if product.identity_state != data.identity_state:
        product.identity_state = data.identity_state
        product.updated_at = _now()
        _audit(
            db,
            owner,
            "COMPETITOR_IDENTITY_STATE_CHANGED",
            "competitor_product",
            product.id,
            f"competitor-identity:{product.id}:{data.identity_state}",
        )
        db.commit()
        db.refresh(product)
    return product


def create_observation(
    db: Session, owner: User, product: CompetitorProduct, data: ObservationCreate
) -> CompetitorObservation:
    if (
        data.source_id is not None
        and db.scalar(
            select(IntelligenceSource.id).where(
                IntelligenceSource.id == data.source_id, IntelligenceSource.owner_id == owner.id
            )
        )
        is None
    ):
        raise HTTPException(404, "Source not found.")
    if (
        data.evidence_id is not None
        and db.scalar(
            select(IntelligenceEvidence.id).where(
                IntelligenceEvidence.id == data.evidence_id,
                IntelligenceEvidence.owner_id == owner.id,
            )
        )
        is None
    ):
        raise HTTPException(404, "Evidence not found.")
    lowered = data.observation_type.casefold()
    if "rating" in lowered and data.numeric_value is not None and not 0 <= data.numeric_value <= 5:
        raise HTTPException(422, "Rating must be between 0 and 5.")
    if "review" in lowered and data.numeric_value is not None and data.numeric_value < 0:
        raise HTTPException(422, "Review count must be non-negative.")
    existing = db.scalar(
        select(CompetitorObservation).where(
            CompetitorObservation.owner_id == owner.id,
            CompetitorObservation.competitor_product_id == product.id,
            CompetitorObservation.observation_key == data.observation_key,
        )
    )
    if existing is not None:
        return existing
    value = CompetitorObservation(
        owner_id=owner.id, competitor_product_id=product.id, **data.model_dump()
    )
    db.add(value)
    product.last_observed = data.observed_at
    product.updated_at = _now()
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(CompetitorObservation).where(
                CompetitorObservation.owner_id == owner.id,
                CompetitorObservation.competitor_product_id == product.id,
                CompetitorObservation.observation_key == data.observation_key,
            )
        )
        if existing is not None:
            return existing
        raise
    _audit(
        db,
        owner,
        "COMPETITOR_OBSERVATION_PERSISTED",
        "competitor_observation",
        value.id,
        f"competitor-observation:{value.id}",
    )
    db.commit()
    db.refresh(value)
    return value


def create_snapshot(
    db: Session, owner: User, context: CompetitorContext, data: SnapshotCreate
) -> CompetitorSnapshot:
    product = None
    if data.product_id is not None:
        product = get_competitor_product(db, owner, data.product_id)
        if product.context_id != context.id:
            raise HTTPException(404, "Competitor product not found in context.")
    observation_ids = list(data.observation_references)
    if observation_ids:
        observations = list(
            db.scalars(
                select(CompetitorObservation).where(
                    CompetitorObservation.owner_id == owner.id,
                    CompetitorObservation.id.in_(observation_ids),
                )
            )
        )
        if len(observations) != len(set(observation_ids)) or any(
            item.competitor_product_id != data.product_id for item in observations
        ):
            raise HTTPException(
                422, "Snapshot observations do not match the selected competitor product."
            )
    key = (
        data.idempotency_key
        or f"competitor-snapshot:{context.id}:{data.product_id}:{data.input_fingerprint}"
    )
    existing = _existing_by_key(db, CompetitorSnapshot, owner, key)
    if existing is not None:
        return existing
    value = CompetitorSnapshot(
        owner_id=owner.id,
        context_id=context.id,
        product_id=data.product_id,
        idempotency_key=key,
        observation_references=[str(item) for item in observation_ids],
        **data.model_dump(exclude={"product_id", "observation_references", "idempotency_key"}),
    )
    db.add(value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(CompetitorSnapshot).where(
                CompetitorSnapshot.owner_id == owner.id,
                CompetitorSnapshot.context_id == context.id,
                CompetitorSnapshot.product_id == data.product_id,
                CompetitorSnapshot.input_fingerprint == data.input_fingerprint,
            )
        )
        if existing is not None:
            return existing
        raise
    _audit(
        db,
        owner,
        "COMPETITOR_SNAPSHOT_CREATED",
        "competitor_snapshot",
        value.id,
        f"competitor-snapshot:{value.id}",
    )
    db.commit()
    db.refresh(value)
    return value


def integrity_report(db: Session, owner: User) -> dict[str, object]:
    contexts = select(CompetitorContext.id).where(CompetitorContext.owner_id == owner.id)
    products = select(CompetitorProduct.id).where(CompetitorProduct.owner_id == owner.id)
    entities = select(CompetitorEntity.id).where(CompetitorEntity.owner_id == owner.id)
    counts = {
        "orphan_contexts": int(
            db.scalar(
                select(func.count())
                .select_from(CompetitorContext)
                .where(
                    CompetitorContext.owner_id == owner.id, CompetitorContext.created_by != owner.id
                )
            )
            or 0
        ),
        "orphan_products": int(
            db.scalar(
                select(func.count())
                .select_from(CompetitorProduct)
                .where(
                    CompetitorProduct.owner_id == owner.id,
                    ~CompetitorProduct.context_id.in_(contexts),
                )
            )
            or 0
        ),
        "orphan_observations": int(
            db.scalar(
                select(func.count())
                .select_from(CompetitorObservation)
                .where(
                    CompetitorObservation.owner_id == owner.id,
                    ~CompetitorObservation.competitor_product_id.in_(products),
                )
            )
            or 0
        ),
        "orphan_snapshots": int(
            db.scalar(
                select(func.count())
                .select_from(CompetitorSnapshot)
                .where(
                    CompetitorSnapshot.owner_id == owner.id,
                    ~CompetitorSnapshot.context_id.in_(contexts),
                )
            )
            or 0
        ),
        "broken_entity_lineage": int(
            db.scalar(
                select(func.count())
                .select_from(CompetitorProduct)
                .where(
                    CompetitorProduct.owner_id == owner.id,
                    CompetitorProduct.entity_id.is_not(None),
                    ~CompetitorProduct.entity_id.in_(entities),
                )
            )
            or 0
        ),
    }
    duplicate_counts = {
        "duplicate_logical_contexts": int(
            db.scalar(
                select(func.count()).select_from(
                    select(
                        CompetitorContext.subject_type,
                        CompetitorContext.subject_reference,
                        CompetitorContext.marketplace,
                        CompetitorContext.market,
                        func.count().label("n"),
                    )
                    .where(CompetitorContext.owner_id == owner.id)
                    .group_by(
                        CompetitorContext.subject_type,
                        CompetitorContext.subject_reference,
                        CompetitorContext.marketplace,
                        CompetitorContext.market,
                    )
                    .having(func.count() > 1)
                    .subquery()
                )
            )
            or 0
        ),
        "duplicate_logical_products": int(
            db.scalar(
                select(func.count()).select_from(
                    select(
                        CompetitorProduct.context_id,
                        CompetitorProduct.marketplace,
                        CompetitorProduct.external_identifier,
                        func.count().label("n"),
                    )
                    .where(CompetitorProduct.owner_id == owner.id)
                    .group_by(
                        CompetitorProduct.context_id,
                        CompetitorProduct.marketplace,
                        CompetitorProduct.external_identifier,
                    )
                    .having(func.count() > 1)
                    .subquery()
                )
            )
            or 0
        ),
        "duplicate_observations": int(
            db.scalar(
                select(func.count()).select_from(
                    select(
                        CompetitorObservation.competitor_product_id,
                        CompetitorObservation.observation_key,
                        func.count().label("n"),
                    )
                    .where(CompetitorObservation.owner_id == owner.id)
                    .group_by(
                        CompetitorObservation.competitor_product_id,
                        CompetitorObservation.observation_key,
                    )
                    .having(func.count() > 1)
                    .subquery()
                )
            )
            or 0
        ),
        "duplicate_snapshot_fingerprints": int(
            db.scalar(
                select(func.count()).select_from(
                    select(
                        CompetitorSnapshot.context_id,
                        CompetitorSnapshot.product_id,
                        CompetitorSnapshot.input_fingerprint,
                        func.count().label("n"),
                    )
                    .where(CompetitorSnapshot.owner_id == owner.id)
                    .group_by(
                        CompetitorSnapshot.context_id,
                        CompetitorSnapshot.product_id,
                        CompetitorSnapshot.input_fingerprint,
                    )
                    .having(func.count() > 1)
                    .subquery()
                )
            )
            or 0
        ),
    }
    opportunities = select(ProductOpportunity.id).where(ProductOpportunity.owner_id == owner.id)
    canonical_products = select(Product.id).where(Product.owner_id == owner.id)
    brands = select(Brand.id).where(Brand.owner_id == owner.id)
    sources = select(IntelligenceSource.id).where(IntelligenceSource.owner_id == owner.id)
    evidence = select(IntelligenceEvidence.id).where(IntelligenceEvidence.owner_id == owner.id)
    subject_lineage_broken = or_(
        and_(
            CompetitorContext.subject_type == "PRODUCT_OPPORTUNITY",
            or_(
                CompetitorContext.product_opportunity_id.is_(None),
                CompetitorContext.product_opportunity_id != CompetitorContext.subject_reference,
                ~CompetitorContext.product_opportunity_id.in_(opportunities),
            ),
        ),
        and_(
            CompetitorContext.subject_type == "PRODUCT",
            or_(
                CompetitorContext.product_id.is_(None),
                CompetitorContext.product_id != CompetitorContext.subject_reference,
                ~CompetitorContext.product_id.in_(canonical_products),
            ),
        ),
        and_(
            CompetitorContext.subject_type == "BRAND",
            or_(
                CompetitorContext.brand_id.is_(None),
                CompetitorContext.brand_id != CompetitorContext.subject_reference,
                ~CompetitorContext.brand_id.in_(brands),
            ),
        ),
    )
    invalid_observation_type = func.lower(CompetitorObservation.observation_type)
    invalid_currency = or_(
        func.length(CompetitorObservation.currency) != 3,
        CompetitorObservation.currency != func.upper(CompetitorObservation.currency),
    )
    counts.update(
        {
            "broken_subject_lineage": int(
                db.scalar(
                    select(func.count())
                    .select_from(CompetitorContext)
                    .where(CompetitorContext.owner_id == owner.id, subject_lineage_broken)
                )
                or 0
            ),
            "broken_source_lineage": int(
                db.scalar(
                    select(func.count())
                    .select_from(CompetitorObservation)
                    .where(
                        CompetitorObservation.owner_id == owner.id,
                        CompetitorObservation.source_id.is_not(None),
                        ~CompetitorObservation.source_id.in_(sources),
                    )
                )
                or 0
            ),
            "broken_evidence_lineage": int(
                db.scalar(
                    select(func.count())
                    .select_from(CompetitorObservation)
                    .where(
                        CompetitorObservation.owner_id == owner.id,
                        CompetitorObservation.evidence_id.is_not(None),
                        ~CompetitorObservation.evidence_id.in_(evidence),
                    )
                )
                or 0
            ),
            "invalid_context_values": int(
                db.scalar(
                    select(func.count())
                    .select_from(CompetitorContext)
                    .where(
                        CompetitorContext.owner_id == owner.id,
                        or_(
                            ~CompetitorContext.subject_type.in_(
                                ("PRODUCT_OPPORTUNITY", "PRODUCT", "BRAND")
                            ),
                            ~CompetitorContext.status.in_(CONTEXT_STATUSES),
                            CompetitorContext.version < 1,
                        ),
                    )
                )
                or 0
            ),
            "invalid_entity_values": int(
                db.scalar(
                    select(func.count())
                    .select_from(CompetitorEntity)
                    .where(
                        CompetitorEntity.owner_id == owner.id,
                        or_(
                            ~CompetitorEntity.entity_type.in_(ENTITY_TYPES),
                            ~CompetitorEntity.evidence_state.in_(EVIDENCE_STATES),
                        ),
                    )
                )
                or 0
            ),
            "invalid_product_values": int(
                db.scalar(
                    select(func.count())
                    .select_from(CompetitorProduct)
                    .where(
                        CompetitorProduct.owner_id == owner.id,
                        or_(
                            ~CompetitorProduct.availability_state.in_(AVAILABILITY_STATES),
                            ~CompetitorProduct.identity_state.in_(IDENTITY_STATES),
                            ~CompetitorProduct.evidence_state.in_(EVIDENCE_STATES),
                        ),
                    )
                )
                or 0
            ),
            "invalid_freshness_values": int(
                db.scalar(
                    select(func.count())
                    .select_from(CompetitorObservation)
                    .where(
                        CompetitorObservation.owner_id == owner.id,
                        ~CompetitorObservation.freshness_state.in_(FRESHNESS_STATES),
                    )
                )
                or 0
            ),
            "invalid_price_values": int(
                db.scalar(
                    select(func.count())
                    .select_from(CompetitorObservation)
                    .where(
                        CompetitorObservation.owner_id == owner.id,
                        invalid_observation_type.in_(
                            ("price", "listed_price", "sale_price", "unit_price")
                        ),
                        CompetitorObservation.numeric_value.is_not(None),
                        CompetitorObservation.numeric_value < 0,
                    )
                )
                or 0
            ),
            "invalid_rating_values": int(
                db.scalar(
                    select(func.count())
                    .select_from(CompetitorObservation)
                    .where(
                        CompetitorObservation.owner_id == owner.id,
                        invalid_observation_type.in_(("rating", "product_rating")),
                        CompetitorObservation.numeric_value.is_not(None),
                        or_(
                            CompetitorObservation.numeric_value < 0,
                            CompetitorObservation.numeric_value > 5,
                        ),
                    )
                )
                or 0
            ),
            "invalid_review_counts": int(
                db.scalar(
                    select(func.count())
                    .select_from(CompetitorObservation)
                    .where(
                        CompetitorObservation.owner_id == owner.id,
                        invalid_observation_type.in_(
                            ("review", "reviews", "review_count", "reviews_count")
                        ),
                        CompetitorObservation.numeric_value.is_not(None),
                        CompetitorObservation.numeric_value < 0,
                    )
                )
                or 0
            ),
            "invalid_currencies": int(
                (
                    db.scalar(
                        select(func.count())
                        .select_from(CompetitorContext)
                        .where(
                            CompetitorContext.owner_id == owner.id,
                            CompetitorContext.currency.is_not(None),
                            or_(
                                func.length(CompetitorContext.currency) != 3,
                                CompetitorContext.currency
                                != func.upper(CompetitorContext.currency),
                            ),
                        )
                    )
                    or 0
                )
                + (
                    db.scalar(
                        select(func.count())
                        .select_from(CompetitorObservation)
                        .where(
                            CompetitorObservation.owner_id == owner.id,
                            CompetitorObservation.currency.is_not(None),
                            invalid_currency,
                        )
                    )
                    or 0
                )
            ),
            "invalid_snapshot_versions": int(
                db.scalar(
                    select(func.count())
                    .select_from(CompetitorSnapshot)
                    .where(
                        CompetitorSnapshot.owner_id == owner.id,
                        CompetitorSnapshot.snapshot_version < 1,
                    )
                )
                or 0
            ),
        }
    )
    total = sum(counts.values()) + sum(duplicate_counts.values())
    return {
        "status": "PASS" if total == 0 else "FAIL",
        "counts": counts,
        "duplicate_counts": duplicate_counts,
    }
