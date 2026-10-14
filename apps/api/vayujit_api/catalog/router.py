from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.products.router import present_owned

from .models import (
    CatalogListingDraft,
    CatalogProductLineage,
    CatalogProductVariant,
    CatalogSupplierAssociation,
)
from .schemas import (
    CatalogEconomicsResponse,
    CatalogProductResponse,
    CatalogReadinessResponse,
    LineageResponse,
    ListingDraftCreate,
    ListingDraftResponse,
    ListingDraftUpdate,
    ListingReviewRequest,
    OpportunityConversionRequest,
    ProductImageCreate,
    ProductImageResponse,
    ProductImageUpdate,
    SupplierAssociationCreate,
    SupplierAssociationResponse,
    VariantCreate,
    VariantResponse,
    VariantUpdate,
)
from .service import (
    _image_response,
    _product,
    attach_product_image,
    catalog_economics,
    convert_opportunity,
    create_listing_draft,
    create_supplier_association,
    create_variant,
    lineage_for,
    list_product_images,
    readiness,
    remove_product_image,
    review_listing_draft,
    update_listing_draft,
    update_product_image,
    update_variant,
)

router = APIRouter(prefix="/api/v1/catalog", tags=["seller-catalog"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _lineage(row: CatalogProductLineage | None) -> LineageResponse | None:
    return LineageResponse.model_validate(row, from_attributes=True) if row else None


def _catalog_detail(db: Session, owner: User, product_id: uuid.UUID) -> CatalogProductResponse:
    product = _product(db, owner, product_id)
    variants = list(
        db.scalars(
            select(CatalogProductVariant)
            .where(
                CatalogProductVariant.owner_id == owner.id,
                CatalogProductVariant.product_id == product.id,
            )
            .order_by(CatalogProductVariant.variant_key)
        )
    )
    suppliers = list(
        db.scalars(
            select(CatalogSupplierAssociation)
            .where(
                CatalogSupplierAssociation.owner_id == owner.id,
                CatalogSupplierAssociation.product_id == product.id,
            )
            .order_by(CatalogSupplierAssociation.created_at)
        )
    )
    drafts = list(
        db.scalars(
            select(CatalogListingDraft)
            .where(
                CatalogListingDraft.owner_id == owner.id,
                CatalogListingDraft.product_id == product.id,
            )
            .order_by(CatalogListingDraft.channel)
        )
    )
    return CatalogProductResponse(
        product=present_owned(db, owner, product),
        lineage=_lineage(lineage_for(db, owner, product.id)),
        variants=[
            VariantResponse.model_validate(value, from_attributes=True) for value in variants
        ],
        images=[_image_response(db, value) for value in list_product_images(db, owner, product.id)],
        supplier_associations=[
            SupplierAssociationResponse.model_validate(value, from_attributes=True)
            for value in suppliers
        ],
        listing_drafts=[
            ListingDraftResponse.model_validate(value, from_attributes=True) for value in drafts
        ],
    )


@router.get("/products/{product_id}", response_model=CatalogProductResponse)
def get_catalog_product(product_id: uuid.UUID, db: DB, owner: Owner) -> CatalogProductResponse:
    return _catalog_detail(db, owner, product_id)


@router.post(
    "/opportunities/{opportunity_id}/convert",
    response_model=CatalogProductResponse,
    status_code=201,
)
def convert_catalog_opportunity(
    opportunity_id: uuid.UUID,
    data: OpportunityConversionRequest,
    db: DB,
    owner: Owner,
) -> CatalogProductResponse:
    product = convert_opportunity(db, owner, opportunity_id, data)
    return _catalog_detail(db, owner, product.id)


@router.get("/products/{product_id}/variants", response_model=list[VariantResponse])
def list_variants(product_id: uuid.UUID, db: DB, owner: Owner) -> list[VariantResponse]:
    product = _product(db, owner, product_id)
    rows = db.scalars(
        select(CatalogProductVariant)
        .where(
            CatalogProductVariant.owner_id == owner.id,
            CatalogProductVariant.product_id == product.id,
        )
        .order_by(CatalogProductVariant.variant_key)
    ).all()
    return [VariantResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/products/{product_id}/variants", response_model=VariantResponse, status_code=201)
def add_variant(
    product_id: uuid.UUID, data: VariantCreate, db: DB, owner: Owner
) -> VariantResponse:
    return VariantResponse.model_validate(
        create_variant(db, owner, product_id, data), from_attributes=True
    )


@router.patch("/variants/{variant_id}", response_model=VariantResponse)
def patch_variant(
    variant_id: uuid.UUID, data: VariantUpdate, db: DB, owner: Owner
) -> VariantResponse:
    return VariantResponse.model_validate(
        update_variant(db, owner, variant_id, data), from_attributes=True
    )


@router.get("/products/{product_id}/images", response_model=list[ProductImageResponse])
def get_product_images(product_id: uuid.UUID, db: DB, owner: Owner) -> list[ProductImageResponse]:
    return [_image_response(db, row) for row in list_product_images(db, owner, product_id)]


@router.post("/products/{product_id}/images", response_model=ProductImageResponse, status_code=201)
def add_product_image(
    product_id: uuid.UUID, data: ProductImageCreate, db: DB, owner: Owner
) -> ProductImageResponse:
    return _image_response(db, attach_product_image(db, owner, product_id, data))


@router.patch("/images/{image_id}", response_model=ProductImageResponse)
def patch_product_image(
    image_id: uuid.UUID, data: ProductImageUpdate, db: DB, owner: Owner
) -> ProductImageResponse:
    return _image_response(db, update_product_image(db, owner, image_id, data))


@router.delete("/images/{image_id}", status_code=204)
def delete_product_image(image_id: uuid.UUID, db: DB, owner: Owner) -> None:
    remove_product_image(db, owner, image_id)


@router.get("/products/{product_id}/economics", response_model=CatalogEconomicsResponse)
def product_economics(product_id: uuid.UUID, db: DB, owner: Owner) -> CatalogEconomicsResponse:
    return catalog_economics(db, owner, product_id)


@router.post(
    "/products/{product_id}/supplier-associations",
    response_model=SupplierAssociationResponse,
    status_code=201,
)
def associate_supplier(
    product_id: uuid.UUID,
    data: SupplierAssociationCreate,
    db: DB,
    owner: Owner,
) -> SupplierAssociationResponse:
    return SupplierAssociationResponse.model_validate(
        create_supplier_association(db, owner, product_id, data), from_attributes=True
    )


@router.get("/listing-drafts", response_model=list[ListingDraftResponse])
def list_listing_drafts(
    db: DB,
    owner: Owner,
    product_id: uuid.UUID | None = None,
    channel: str | None = Query(default=None, pattern="^(amazon_in|flipkart)$"),
) -> list[ListingDraftResponse]:
    query = select(CatalogListingDraft).where(CatalogListingDraft.owner_id == owner.id)
    if product_id is not None:
        _product(db, owner, product_id)
        query = query.where(CatalogListingDraft.product_id == product_id)
    if channel:
        query = query.where(CatalogListingDraft.channel == channel)
    rows = db.scalars(query.order_by(CatalogListingDraft.updated_at.desc())).all()
    return [ListingDraftResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post(
    "/products/{product_id}/listing-drafts", response_model=ListingDraftResponse, status_code=201
)
def add_listing_draft(
    product_id: uuid.UUID,
    data: ListingDraftCreate,
    db: DB,
    owner: Owner,
) -> ListingDraftResponse:
    return ListingDraftResponse.model_validate(
        create_listing_draft(db, owner, product_id, data), from_attributes=True
    )


@router.get("/listing-drafts/{draft_id}", response_model=ListingDraftResponse)
def get_listing_draft(draft_id: uuid.UUID, db: DB, owner: Owner) -> ListingDraftResponse:
    row = db.scalar(
        select(CatalogListingDraft).where(
            CatalogListingDraft.id == draft_id, CatalogListingDraft.owner_id == owner.id
        )
    )
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(404, "Listing draft not found.")
    return ListingDraftResponse.model_validate(row, from_attributes=True)


@router.patch("/listing-drafts/{draft_id}", response_model=ListingDraftResponse)
def patch_listing_draft(
    draft_id: uuid.UUID, data: ListingDraftUpdate, db: DB, owner: Owner
) -> ListingDraftResponse:
    return ListingDraftResponse.model_validate(
        update_listing_draft(db, owner, draft_id, data), from_attributes=True
    )


@router.post("/listing-drafts/{draft_id}/review", response_model=ListingDraftResponse)
def review_listing_draft_route(
    draft_id: uuid.UUID,
    data: ListingReviewRequest,
    db: DB,
    owner: Owner,
) -> ListingDraftResponse:
    return ListingDraftResponse.model_validate(
        review_listing_draft(db, owner, draft_id, data.version, data.decision),
        from_attributes=True,
    )


@router.get("/products/{product_id}/readiness", response_model=CatalogReadinessResponse)
def product_readiness(product_id: uuid.UUID, db: DB, owner: Owner) -> CatalogReadinessResponse:
    return CatalogReadinessResponse.model_validate(readiness(db, owner, product_id))
