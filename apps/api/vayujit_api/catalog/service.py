from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.intelligence.business_agent_models import BusinessAgentGoal
from vayujit_api.intelligence.economic_integration_service import (
    project_economics_for_opportunity,
)
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.intelligence.product_opportunity_scoring_models import ProductOpportunityDecision
from vayujit_api.intelligence.supplier_models import Supplier
from vayujit_api.media.models import MediaAsset
from vayujit_api.media.service import response as media_response
from vayujit_api.products.models import Product
from vayujit_api.products.schemas import ProductCreate
from vayujit_api.products.service import create_product, owned_product

from .models import (
    CatalogListingDraft,
    CatalogProductImage,
    CatalogProductLineage,
    CatalogProductVariant,
    CatalogSupplierAssociation,
)
from .schemas import (
    CatalogEconomicsResponse,
    ListingDraftCreate,
    ListingDraftUpdate,
    OpportunityConversionRequest,
    ProductImageCreate,
    ProductImageResponse,
    ProductImageUpdate,
    SupplierAssociationCreate,
    VariantCreate,
    VariantUpdate,
)


def _product(db: Session, owner: User, product_id: uuid.UUID) -> Product:
    return owned_product(db, owner.id, product_id)


def _opportunity(db: Session, owner: User, opportunity_id: uuid.UUID) -> ProductOpportunity:
    row = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == opportunity_id, ProductOpportunity.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Product opportunity not found.")
    return row


def _supplier(db: Session, owner: User, supplier_id: uuid.UUID) -> Supplier:
    row = db.scalar(
        select(Supplier).where(Supplier.id == supplier_id, Supplier.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Supplier not found.")
    return row


def _record(
    db: Session,
    owner: User,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    **metadata: object,
) -> None:
    record_event(
        db,
        actor_id=owner.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata={str(key): value for key, value in metadata.items()},
        idempotency_key=f"catalog:{entity_type}:{entity_id}:{action}:{uuid.uuid4()}",
    )


def lineage_for(db: Session, owner: User, product_id: uuid.UUID) -> CatalogProductLineage | None:
    return db.scalar(
        select(CatalogProductLineage).where(
            CatalogProductLineage.owner_id == owner.id,
            CatalogProductLineage.product_id == product_id,
        )
    )


def latest_shortlist(
    db: Session, owner: User, opportunity_id: uuid.UUID
) -> ProductOpportunityDecision | None:
    return db.scalar(
        select(ProductOpportunityDecision)
        .where(
            ProductOpportunityDecision.owner_id == owner.id,
            ProductOpportunityDecision.opportunity_id == opportunity_id,
            ProductOpportunityDecision.action == "shortlist",
        )
        .order_by(ProductOpportunityDecision.created_at.desc())
        .limit(1)
    )


def _variant_option_fingerprint(option_values: dict[str, object]) -> str:
    return json.dumps(option_values, sort_keys=True, separators=(",", ":"), default=str)


def _validate_variant_values(variant_key: str, option_values: dict[str, object]) -> None:
    if not variant_key.strip():
        raise HTTPException(422, "Variant key cannot be blank.")
    for key, value in option_values.items():
        if not str(key).strip() or value is None or not str(value).strip():
            raise HTTPException(422, "Variant option names and values must not be blank.")


def _ensure_unique_option_combination(
    db: Session,
    owner: User,
    product_id: uuid.UUID,
    option_values: dict[str, object],
    *,
    exclude_id: uuid.UUID | None = None,
) -> None:
    fingerprint = _variant_option_fingerprint(option_values)
    rows = db.scalars(
        select(CatalogProductVariant).where(
            CatalogProductVariant.owner_id == owner.id,
            CatalogProductVariant.product_id == product_id,
            CatalogProductVariant.status != "archived",
        )
    ).all()
    for row in rows:
        if exclude_id is not None and row.id == exclude_id:
            continue
        if row.option_values and _variant_option_fingerprint(row.option_values) == fingerprint:
            raise HTTPException(409, "This option combination already exists for the product.")


def convert_opportunity(
    db: Session, owner: User, opportunity_id: uuid.UUID, data: OpportunityConversionRequest
) -> Product:
    opportunity = _opportunity(db, owner, opportunity_id)
    decision = latest_shortlist(db, owner, opportunity.id)
    if decision is None:
        raise HTTPException(
            409,
            detail={
                "code": "PRODUCT_SELECTION_REQUIRED",
                "message": "Select this opportunity explicitly before creating a catalog product.",
            },
        )
    if data.goal_id is not None:
        goal = db.scalar(
            select(BusinessAgentGoal).where(
                BusinessAgentGoal.id == data.goal_id, BusinessAgentGoal.owner_id == owner.id
            )
        )
        if goal is None:
            raise HTTPException(404, "Business goal not found.")

    # ProductOpportunity.product_id is the canonical product identity already
    # established by research.  It is not proof that the seller has selected
    # or converted it into the Seller Catalog.  Require the HUMAN shortlist
    # above, then create durable lineage around that existing product.  A
    # replay after conversion is safe because the lineage is authoritative.
    existing = (
        db.scalar(
            select(Product).where(
                Product.id == opportunity.product_id, Product.owner_id == owner.id
            )
        )
        if opportunity.product_id
        else None
    )
    if existing is not None:
        lineage = lineage_for(db, owner, existing.id)
        if lineage is not None:
            return existing
        stamp = now()
        lineage = CatalogProductLineage(
            owner_id=owner.id,
            product_id=existing.id,
            opportunity_id=opportunity.id,
            goal_id=data.goal_id,
            assessment_id=decision.assessment_id,
            source_kind="opportunity",
            provenance_json={
                "source": "ProductOpportunity",
                "selection_decision_id": str(decision.id),
                "selection_action": decision.action,
                "claims_are_unverified": True,
                "commercial_values": "UNKNOWN_UNLESS_EXPLICITLY_ENTERED",
            },
            created_at=stamp,
            updated_at=stamp,
        )
        opportunity.brand_id = existing.brand_id
        opportunity.updated_at = stamp
        db.add(lineage)
        _record(
            db,
            owner,
            "catalog.product_linked_from_opportunity",
            "product",
            existing.id,
            opportunity_id=str(opportunity.id),
            decision_id=str(decision.id),
        )
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            raise HTTPException(
                409, "This opportunity was converted by another request."
            ) from error
        db.refresh(existing)
        return existing
    product_data = ProductCreate(
        brand_id=data.brand_id,
        name=opportunity.name.strip(),
        sku=data.sku,
        product_type=data.product_type,
        short_description=opportunity.description[:500] or None,
        description=opportunity.description or opportunity.product_concept,
        category=opportunity.category or None,
        tags=list(opportunity.tags or []),
        price_amount=None,
        price_currency=None,
        inventory_tracking_enabled=False,
        inventory_quantity=0,
        low_stock_threshold=0,
    )
    product = create_product(db, owner, product_data)
    stamp = now()
    lineage = CatalogProductLineage(
        owner_id=owner.id,
        product_id=product.id,
        opportunity_id=opportunity.id,
        goal_id=data.goal_id,
        assessment_id=decision.assessment_id,
        source_kind="opportunity",
        provenance_json={
            "source": "ProductOpportunity",
            "selection_decision_id": str(decision.id),
            "selection_action": decision.action,
            "claims_are_unverified": True,
            "commercial_values": "UNKNOWN_UNLESS_EXPLICITLY_ENTERED",
        },
        created_at=stamp,
        updated_at=stamp,
    )
    opportunity.product_id = product.id
    opportunity.brand_id = product.brand_id
    opportunity.updated_at = stamp
    db.add(lineage)
    _record(
        db,
        owner,
        "catalog.product_converted_from_opportunity",
        "product",
        product.id,
        opportunity_id=str(opportunity.id),
        decision_id=str(decision.id),
    )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "This opportunity was converted by another request.") from error
    db.refresh(product)
    return product


def create_variant(
    db: Session, owner: User, product_id: uuid.UUID, data: VariantCreate
) -> CatalogProductVariant:
    product = _product(db, owner, product_id)
    if product.status == "archived":
        raise HTTPException(409, "Archived products cannot receive variants.")
    _validate_variant_values(data.variant_key, data.option_values)
    if data.option_values:
        _ensure_unique_option_combination(db, owner, product.id, data.option_values)
    row = CatalogProductVariant(
        owner_id=owner.id,
        product_id=product.id,
        variant_key=data.variant_key.strip(),
        title=data.title.strip(),
        sku=data.sku,
        option_values=data.option_values,
        attributes=data.attributes,
        image_refs=data.image_refs,
        price_amount=data.price_amount,
        currency=data.currency,
        status="draft",
        version=1,
        created_at=now(),
        updated_at=now(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Variant key or SKU is already used by this owner.") from error
    db.refresh(row)
    _record(db, owner, "catalog.variant_created", "catalog_product_variant", row.id)
    db.commit()
    return row


def update_variant(
    db: Session, owner: User, variant_id: uuid.UUID, data: VariantUpdate
) -> CatalogProductVariant:
    row = db.scalar(
        select(CatalogProductVariant).where(
            CatalogProductVariant.id == variant_id, CatalogProductVariant.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Variant not found.")
    if row.version != data.version:
        raise HTTPException(409, "Variant is stale; refresh before saving.")
    _validate_variant_values(data.variant_key, data.option_values)
    if data.option_values:
        _ensure_unique_option_combination(
            db, owner, row.product_id, data.option_values, exclude_id=row.id
        )
    for key, value in data.model_dump(exclude={"version", "status"}, exclude_unset=True).items():
        setattr(row, key, value)
    if data.status is not None:
        row.status = data.status
    row.version += 1
    row.updated_at = now()
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Variant key or SKU is already used by this owner.") from error
    db.refresh(row)
    _record(
        db,
        owner,
        "catalog.variant_updated",
        "catalog_product_variant",
        row.id,
        version=row.version,
    )
    db.commit()
    return row


def _image_response(db: Session, row: CatalogProductImage) -> ProductImageResponse:
    media = db.scalar(
        select(MediaAsset).where(MediaAsset.id == row.media_id, MediaAsset.owner_id == row.owner_id)
    )
    if media is None:
        raise HTTPException(409, "The selected media asset is no longer available.")
    preview = media_response(db, media)
    return ProductImageResponse(
        id=row.id,
        product_id=row.product_id,
        media_id=row.media_id,
        alt_text=row.alt_text,
        position=row.position,
        is_primary=row.is_primary,
        version=row.version,
        preview_url=preview.preview_url,
        mime_type=media.mime_type,
        size_bytes=media.size_bytes,
        width=media.width,
        height=media.height,
        status=media.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_product_images(
    db: Session, owner: User, product_id: uuid.UUID
) -> list[CatalogProductImage]:
    product = _product(db, owner, product_id)
    return list(
        db.scalars(
            select(CatalogProductImage)
            .where(
                CatalogProductImage.owner_id == owner.id,
                CatalogProductImage.product_id == product.id,
            )
            .order_by(CatalogProductImage.position, CatalogProductImage.created_at)
        )
    )


def attach_product_image(
    db: Session, owner: User, product_id: uuid.UUID, data: ProductImageCreate
) -> CatalogProductImage:
    product = _product(db, owner, product_id)
    media = db.scalar(
        select(MediaAsset).where(
            MediaAsset.id == data.media_id,
            MediaAsset.owner_id == owner.id,
            MediaAsset.status == "ready",
        )
    )
    if media is None:
        raise HTTPException(404, "Ready image asset not found in this owner scope.")
    existing = db.scalar(
        select(CatalogProductImage).where(
            CatalogProductImage.owner_id == owner.id,
            CatalogProductImage.product_id == product.id,
            CatalogProductImage.media_id == media.id,
        )
    )
    if existing is not None:
        return existing
    if data.is_primary:
        db.query(CatalogProductImage).filter(
            CatalogProductImage.owner_id == owner.id,
            CatalogProductImage.product_id == product.id,
        ).update({CatalogProductImage.is_primary: False}, synchronize_session=False)
    row = CatalogProductImage(
        owner_id=owner.id,
        product_id=product.id,
        media_id=media.id,
        alt_text=data.alt_text.strip() if data.alt_text else None,
        position=data.position,
        is_primary=data.is_primary,
        version=1,
        created_at=now(),
        updated_at=now(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "This image is already selected for the product.") from error
    db.refresh(row)
    _record(
        db,
        owner,
        "catalog.product_image_attached",
        "catalog_product_image",
        row.id,
        media_id=str(media.id),
    )
    db.commit()
    return row


def update_product_image(
    db: Session, owner: User, image_id: uuid.UUID, data: ProductImageUpdate
) -> CatalogProductImage:
    row = db.scalar(
        select(CatalogProductImage).where(
            CatalogProductImage.id == image_id, CatalogProductImage.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Product image selection not found.")
    if row.version != data.version:
        raise HTTPException(409, "Product image selection is stale; refresh before saving.")
    if data.alt_text is not None:
        row.alt_text = data.alt_text.strip() or None
    if data.position is not None:
        row.position = data.position
    if data.is_primary is not None:
        if data.is_primary:
            db.query(CatalogProductImage).filter(
                CatalogProductImage.owner_id == owner.id,
                CatalogProductImage.product_id == row.product_id,
                CatalogProductImage.id != row.id,
            ).update({CatalogProductImage.is_primary: False}, synchronize_session=False)
        row.is_primary = data.is_primary
    row.version += 1
    row.updated_at = now()
    db.commit()
    db.refresh(row)
    _record(
        db,
        owner,
        "catalog.product_image_updated",
        "catalog_product_image",
        row.id,
        version=row.version,
    )
    db.commit()
    return row


def remove_product_image(db: Session, owner: User, image_id: uuid.UUID) -> None:
    row = db.scalar(
        select(CatalogProductImage).where(
            CatalogProductImage.id == image_id, CatalogProductImage.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Product image selection not found.")
    db.delete(row)
    db.commit()
    _record(db, owner, "catalog.product_image_removed", "catalog_product_image", image_id)
    db.commit()


def catalog_economics(db: Session, owner: User, product_id: uuid.UUID) -> CatalogEconomicsResponse:
    product = _product(db, owner, product_id)
    lineage = lineage_for(db, owner, product.id)
    if lineage is None or lineage.opportunity_id is None:
        return CatalogEconomicsResponse(
            product_id=product.id,
            available=False,
            reason=(
                "Canonical sourcing economics are unavailable until this product has "
                "Product Opportunity lineage."
            ),
        )
    projection = project_economics_for_opportunity(db, owner, lineage.opportunity_id)
    status = str(projection.get("status", "NOT_EVALUATED"))
    assessment_id = projection.get("assessment_id")
    return CatalogEconomicsResponse(
        product_id=product.id,
        available=status not in {"NOT_EVALUATED", "UNKNOWN"},
        opportunity_id=lineage.opportunity_id,
        assessment_id=uuid.UUID(str(assessment_id)) if assessment_id else lineage.assessment_id,
        projection=projection,
        reason=(
            None
            if status not in {"NOT_EVALUATED", "UNKNOWN"}
            else "No complete canonical economics calculation is available yet."
        ),
    )


def create_supplier_association(
    db: Session, owner: User, product_id: uuid.UUID, data: SupplierAssociationCreate
) -> CatalogSupplierAssociation:
    product = _product(db, owner, product_id)
    _supplier(db, owner, data.supplier_id)
    if data.status == "accepted":
        raise HTTPException(
            409,
            "Supplier associations remain review-required; supplier approval is a separate "
            "HUMAN decision.",
        )
    opportunity_id = data.opportunity_id
    if opportunity_id is not None:
        opportunity = _opportunity(db, owner, opportunity_id)
        if opportunity.product_id not in {None, product.id}:
            raise HTTPException(
                409, "Supplier association opportunity is not linked to this product."
            )
    existing = db.scalar(
        select(CatalogSupplierAssociation).where(
            CatalogSupplierAssociation.owner_id == owner.id,
            CatalogSupplierAssociation.product_id == product.id,
            CatalogSupplierAssociation.supplier_id == data.supplier_id,
        )
    )
    if existing is not None:
        return existing
    row = CatalogSupplierAssociation(
        owner_id=owner.id,
        product_id=product.id,
        supplier_id=data.supplier_id,
        opportunity_id=opportunity_id,
        status=data.status,
        provenance_json={**data.provenance_json, "supplier_approval": "NOT_IMPLIED"},
        created_at=now(),
        updated_at=now(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Supplier is already associated with this product.") from error
    db.refresh(row)
    return row


def listing_missing_fields(db: Session, draft: CatalogListingDraft, product: Product) -> list[str]:
    missing: list[str] = []
    if not draft.title.strip():
        missing.append("title")
    if not draft.description.strip():
        missing.append("description")
    if not (draft.category or product.category):
        missing.append("category")
    if not product.sku and not db.scalar(
        select(CatalogProductVariant.id).where(
            CatalogProductVariant.owner_id == draft.owner_id,
            CatalogProductVariant.product_id == product.id,
            CatalogProductVariant.sku.is_not(None),
            CatalogProductVariant.status != "archived",
        )
    ):
        missing.append("sku")
    if not draft.image_refs:
        missing.append("images")
    if not draft.intended_price_amount:
        missing.append("intended_price")
    if not draft.intended_currency:
        missing.append("currency")
    if not draft.compliance:
        missing.append("compliance_information")
    claims = (
        draft.attributes.get("unverified_claims") if isinstance(draft.attributes, dict) else None
    )
    if isinstance(claims, list) and claims:
        missing.append("unverified_claims_review")
    return missing


def refresh_listing_readiness(db: Session, draft: CatalogListingDraft, product: Product) -> None:
    missing = listing_missing_fields(db, draft, product)
    draft.missing_fields = missing
    draft.validation_state = "valid" if not missing else "incomplete"
    if product.status == "archived":
        draft.readiness_state = "BLOCKED"
        draft.status = "blocked"
    elif missing:
        draft.readiness_state = "BLOCKED"
        draft.status = "incomplete"
    elif draft.human_review_state == "approved":
        draft.readiness_state = "APPROVED_FOR_FUTURE_SUBMISSION"
        draft.status = "approved_for_future_submission"
    else:
        draft.readiness_state = "READY_FOR_HUMAN_REVIEW"
        draft.status = "needs_review"


def create_listing_draft(
    db: Session, owner: User, product_id: uuid.UUID, data: ListingDraftCreate
) -> CatalogListingDraft:
    product = _product(db, owner, product_id)
    existing = db.scalar(
        select(CatalogListingDraft).where(
            CatalogListingDraft.owner_id == owner.id,
            CatalogListingDraft.product_id == product.id,
            CatalogListingDraft.channel == data.channel,
        )
    )
    if existing is not None:
        return existing
    row = CatalogListingDraft(
        owner_id=owner.id,
        product_id=product.id,
        channel=data.channel,
        title=data.title.strip(),
        description=data.description.strip(),
        bullets=list(data.bullets),
        category=data.category.strip() if data.category else product.category,
        attributes=data.attributes,
        image_refs=data.image_refs,
        intended_price_amount=data.intended_price_amount,
        intended_currency=data.intended_currency,
        compliance=data.compliance,
        provenance_json={
            "source": "seller_catalog",
            "marketplace_publication": "DISABLED",
            "claims_require_human_review": True,
        },
        idempotency_key=data.idempotency_key,
        created_at=now(),
        updated_at=now(),
    )
    refresh_listing_readiness(db, row, product)
    db.add(row)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            409, "A listing draft already exists for this product and channel."
        ) from error
    db.refresh(row)
    return row


def update_listing_draft(
    db: Session, owner: User, draft_id: uuid.UUID, data: ListingDraftUpdate
) -> CatalogListingDraft:
    row = db.scalar(
        select(CatalogListingDraft).where(
            CatalogListingDraft.id == draft_id, CatalogListingDraft.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Listing draft not found.")
    if row.version != data.version:
        raise HTTPException(409, "Listing draft is stale; refresh before saving.")
    product = _product(db, owner, row.product_id)
    for key, value in data.model_dump(exclude={"version"}, exclude_unset=True).items():
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    row.version += 1
    row.human_review_state = "not_reviewed"
    row.updated_at = now()
    refresh_listing_readiness(db, row, product)
    db.commit()
    db.refresh(row)
    return row


def review_listing_draft(
    db: Session, owner: User, draft_id: uuid.UUID, version: int, decision: str
) -> CatalogListingDraft:
    row = db.scalar(
        select(CatalogListingDraft).where(
            CatalogListingDraft.id == draft_id, CatalogListingDraft.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Listing draft not found.")
    if row.version != version:
        raise HTTPException(409, "Listing draft is stale; refresh before reviewing.")
    product = _product(db, owner, row.product_id)
    refresh_listing_readiness(db, row, product)
    if decision == "approve":
        if row.missing_fields:
            raise HTTPException(
                409,
                detail={
                    "code": "LISTING_DRAFT_INCOMPLETE",
                    "message": "Complete required listing fields before HUMAN approval.",
                    "fields": row.missing_fields,
                },
            )
        row.human_review_state = "approved"
    else:
        row.human_review_state = "needs_review"
    row.version += 1
    row.updated_at = now()
    refresh_listing_readiness(db, row, product)
    _record(
        db,
        owner,
        "catalog.listing_draft_reviewed",
        "catalog_listing_draft",
        row.id,
        decision=decision,
        version=row.version,
    )
    db.commit()
    db.refresh(row)
    return row


def readiness(db: Session, owner: User, product_id: uuid.UUID) -> dict[str, Any]:
    product = _product(db, owner, product_id)
    drafts = list(
        db.scalars(
            select(CatalogListingDraft).where(
                CatalogListingDraft.owner_id == owner.id,
                CatalogListingDraft.product_id == product.id,
                CatalogListingDraft.status != "archived",
            )
        )
    )
    blockers: list[str] = []
    if product.status == "archived":
        blockers.append("product_archived")
    if not drafts:
        blockers.append("listing_draft_required")
    for draft in drafts:
        blockers.extend(f"{draft.channel}:{field}" for field in draft.missing_fields)
        if draft.human_review_state != "approved":
            blockers.append(f"{draft.channel}:human_review_required")
    return {
        "product_id": product.id,
        "readiness": "READY_FOR_FUTURE_SUBMISSION" if not blockers else "BLOCKED",
        "blockers": sorted(set(blockers)),
        "next_actions": [
            "Create or complete a channel listing draft.",
            "Review all evidence-backed claims and compliance fields.",
            "Approve the draft explicitly as HUMAN before any future submission.",
        ],
        "external_publication": "DISABLED_IN_PR_SOS_01",
    }
