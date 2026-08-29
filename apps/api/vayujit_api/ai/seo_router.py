import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.image_models import AIImageOutput
from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.ai.seo_models import SEOAnalysis, TagSet
from vayujit_api.ai.seo_schemas import (
    KeywordSetDetail,
    KeywordSetUpsert,
    KeywordSuggestion,
    KeywordSuggestionRequest,
    ProductChannelIntelligence,
    SEOAnalysisComparison,
    SEOAnalysisResponse,
    SEOChannel,
    SEOIntent,
    SEORequest,
    TagSetResponse,
    TagSetUpsert,
    TagSuggestion,
)
from vayujit_api.ai.seo_service import (
    _analysis_response,
    _product,
    analyze,
    keyword_response,
    normalize_keyword_groups,
    tag_response,
)
from vayujit_api.ai.studio_models import KeywordSet
from vayujit_api.audit.service import record_event
from vayujit_api.commerce.models import MarketplaceListing, MarketplaceMediaMapping
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.website_models import (
    ManufacturerCandidate,
    SupplierWebsiteCandidate,
    WebsiteOffering,
)

router = APIRouter(prefix="/api/v1/ai/seo", tags=["ai-seo"])
DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(current_user)]


@router.post("/analyze", response_model=SEOAnalysisResponse, status_code=201)
def analyze_route(data: SEORequest, db: DatabaseSession, owner: CurrentUser) -> SEOAnalysisResponse:
    return analyze(db, owner.id, data)


@router.get("/analyses/{analysis_id}/compare/{against_id}", response_model=SEOAnalysisComparison)
def compare_analyses(
    analysis_id: uuid.UUID, against_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> SEOAnalysisComparison:
    current = db.scalar(
        select(SEOAnalysis).where(SEOAnalysis.id == analysis_id, SEOAnalysis.owner_id == owner.id)
    )
    previous = db.scalar(
        select(SEOAnalysis).where(SEOAnalysis.id == against_id, SEOAnalysis.owner_id == owner.id)
    )
    if current is None or previous is None:
        raise HTTPException(404, "SEO analysis not found.")
    current_response = _analysis_response(current)
    previous_response = _analysis_response(previous)
    names = set(current_response.dimensions) | set(previous_response.dimensions)
    deltas = {
        name: int(cast(int, current_response.dimensions.get(name, {}).get("score", 0)))
        - int(cast(int, previous_response.dimensions.get(name, {}).get("score", 0)))
        for name in names
    }
    changes: list[str] = []
    if current_response.overall_score != previous_response.overall_score:
        delta = current_response.overall_score - previous_response.overall_score
        changes.append(f"Overall score changed by {delta} points.")
    if current_response.keyword_coverage != previous_response.keyword_coverage:
        changes.append("Keyword coverage changed.")
    if not changes:
        changes.append("No material SEO changes detected.")
    return SEOAnalysisComparison(
        current=current_response,
        previous=previous_response,
        score_delta=current_response.overall_score - previous_response.overall_score,
        dimension_deltas=deltas,
        changes=changes,
    )


@router.get("/products/{product_id}/channels", response_model=list[ProductChannelIntelligence])
def product_channel_intelligence(
    product_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> list[ProductChannelIntelligence]:
    product = _product(db, owner.id, product_id)
    output: list[ProductChannelIntelligence] = []
    website_candidates = list(
        db.scalars(select(ManufacturerCandidate).where(ManufacturerCandidate.owner_id == owner.id))
    )
    website_supplier_candidates = list(
        db.scalars(
            select(SupplierWebsiteCandidate).where(SupplierWebsiteCandidate.owner_id == owner.id)
        )
    )
    website_offerings = list(
        db.scalars(
            select(WebsiteOffering).where(
                WebsiteOffering.owner_id == owner.id, WebsiteOffering.product_id == product.id
            )
        )
    )
    for channel in ("canonical", "wordpress", "shopify", "amazon", "flipkart", "meesho"):
        artifact = db.scalar(
            select(GeneratedArtifact)
            .where(
                GeneratedArtifact.owner_id == owner.id,
                GeneratedArtifact.product_id == product.id,
                GeneratedArtifact.channel == channel,
                GeneratedArtifact.status == "approved",
            )
            .order_by(GeneratedArtifact.version_number.desc())
        )
        listing = None
        if channel in {"amazon", "flipkart", "meesho"}:
            listing = db.scalar(
                select(MarketplaceListing)
                .where(
                    MarketplaceListing.owner_id == owner.id,
                    MarketplaceListing.product_id == product.id,
                    MarketplaceListing.marketplace == channel,
                )
                .order_by(MarketplaceListing.updated_at.desc())
            )
        analysis = None
        if artifact is not None:
            analysis = db.scalar(
                select(SEOAnalysis)
                .where(
                    SEOAnalysis.owner_id == owner.id,
                    SEOAnalysis.product_id == product.id,
                    SEOAnalysis.artifact_id == artifact.id,
                    SEOAnalysis.channel == channel,
                )
                .order_by(SEOAnalysis.analyzed_at.desc())
            )
        image_outputs = list(
            db.scalars(
                select(AIImageOutput)
                .where(
                    AIImageOutput.owner_id == owner.id,
                    AIImageOutput.product_id == product.id,
                    AIImageOutput.channel == channel,
                )
                .order_by(AIImageOutput.created_at.desc())
            )
        )
        approved_images = [item for item in image_outputs if item.status == "approved"]
        image_mappings = (
            list(
                db.scalars(
                    select(MarketplaceMediaMapping).where(
                        MarketplaceMediaMapping.owner_id == owner.id,
                        MarketplaceMediaMapping.listing_id == listing.id,
                    )
                )
            )
            if listing
            else []
        )
        listing_main = next((item for item in image_mappings if item.position == 0), None)
        latest_approved = approved_images[0] if approved_images else None
        image_readiness = (
            "not_generated"
            if not image_outputs
            else ("ready" if latest_approved else "needs_review")
        )
        image_update_available = bool(
            latest_approved and listing_main and listing_main.image_output_id != latest_approved.id
        )
        findings = analysis.findings_json if analysis else []
        blockers = [
            f"{item.get('code')}: {item.get('explanation')}"
            for item in findings
            if item.get("severity") == "blocker"
        ]
        warnings = [
            f"{item.get('code')}: {item.get('explanation')}"
            for item in findings
            if item.get("severity") in {"warning", "recommendation"}
        ]
        stale = bool(analysis and analysis.analyzed_at < product.updated_at)
        used_version = listing.content_artifact_version if listing else None
        update_available = bool(
            artifact and used_version is not None and used_version < artifact.version_number
        )
        readiness = (
            "not_generated"
            if artifact is None
            else (
                "blocked"
                if blockers
                else (
                    "update_available"
                    if (update_available or stale)
                    else "needs_review" if analysis is None else "ready"
                )
            )
        )
        output.append(
            ProductChannelIntelligence(
                channel=channel,
                approved_artifact_id=artifact.id if artifact else None,
                approved_version=artifact.version_number if artifact else None,
                locale=artifact.locale if artifact else None,
                content_quality_score=analysis.overall_score if analysis else None,
                search_score=analysis.overall_score if analysis else None,
                listing_used_version=used_version,
                last_generated=artifact.created_at if artifact else None,
                last_approved=artifact.approved_at if artifact else None,
                blockers=blockers,
                warnings=warnings,
                analysis_stale=stale,
                update_available=update_available,
                image_readiness=image_readiness,
                approved_main_image=(
                    {
                        "output_id": str(latest_approved.id),
                        "media_id": str(latest_approved.media_id),
                        "version": latest_approved.created_at.isoformat(),
                    }
                    if latest_approved
                    else None
                ),
                approved_gallery_count=max(0, len(approved_images) - 1),
                listing_main_image=(
                    {
                        "output_id": str(listing_main.image_output_id),
                        "media_id": str(listing_main.media_id),
                    }
                    if listing_main and listing_main.image_output_id
                    else None
                ),
                listing_gallery_count=max(0, len(image_mappings) - 1),
                image_update_available=image_update_available,
                website_candidate_count=len(website_candidates),
                supplier_website_candidate_count=len(website_supplier_candidates),
                website_offering_count=len(website_offerings),
                website_follow_up_required=any(
                    item.verification_state != "VERIFIED" for item in website_candidates
                ),
                readiness=cast(
                    Literal[
                        "not_generated",
                        "draft",
                        "needs_review",
                        "approved",
                        "update_available",
                        "blocked",
                        "ready",
                    ],
                    readiness,
                ),
            )
        )
    return output


@router.get("/analyses", response_model=list[SEOAnalysisResponse])
def list_analyses(
    db: DatabaseSession,
    owner: CurrentUser,
    product_id: uuid.UUID | None = None,
    channel: str | None = None,
    locale: str | None = None,
    status: str | None = None,
) -> list[SEOAnalysisResponse]:
    query = select(SEOAnalysis).where(SEOAnalysis.owner_id == owner.id)
    if product_id:
        query = query.where(SEOAnalysis.product_id == product_id)
    if channel:
        query = query.where(SEOAnalysis.channel == channel)
    if locale:
        query = query.where(SEOAnalysis.locale == locale)
    if status:
        query = query.where(SEOAnalysis.status == status)
    return [
        _analysis_response(row)
        for row in db.scalars(query.order_by(SEOAnalysis.analyzed_at.desc()).limit(100))
    ]


@router.get("/analyses/{analysis_id}", response_model=SEOAnalysisResponse)
def get_analysis(
    analysis_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> SEOAnalysisResponse:
    row = db.scalar(
        select(SEOAnalysis).where(SEOAnalysis.id == analysis_id, SEOAnalysis.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "SEO analysis not found.")
    return _analysis_response(row)


@router.post("/analyses/{analysis_id}/reanalyze", response_model=SEOAnalysisResponse)
def reanalyze(
    analysis_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> SEOAnalysisResponse:
    row = db.scalar(
        select(SEOAnalysis).where(SEOAnalysis.id == analysis_id, SEOAnalysis.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "SEO analysis not found.")
    return analyze(
        db,
        owner.id,
        SEORequest(
            product_id=row.product_id,
            artifact_id=row.artifact_id,
            keyword_set_id=row.keyword_set_id,
            channel=cast(SEOChannel, row.channel),
            locale=row.locale,
            intent=cast(SEOIntent, row.intent),
            force=True,
        ),
    )


@router.get("/keywords", response_model=list[KeywordSetDetail])
def list_keyword_sets(
    db: DatabaseSession, owner: CurrentUser, include_archived: bool = False
) -> list[KeywordSetDetail]:
    query = select(KeywordSet).where(KeywordSet.owner_id == owner.id)
    if not include_archived:
        query = query.where(KeywordSet.archived.is_(False))
    return [keyword_response(row) for row in db.scalars(query.order_by(KeywordSet.name))]


@router.post("/keywords", response_model=KeywordSetDetail, status_code=201)
def create_keyword_set(
    data: KeywordSetUpsert, db: DatabaseSession, owner: CurrentUser
) -> KeywordSetDetail:
    groups = normalize_keyword_groups(data)
    now = datetime.now(UTC)
    if data.is_default:
        db.query(KeywordSet).filter(
            KeywordSet.owner_id == owner.id, KeywordSet.locale == data.locale
        ).update({KeywordSet.is_default: False})
    row = KeywordSet(
        owner_id=owner.id,
        name=data.name,
        description=data.description,
        brand_id=data.brand_id,
        product_id=data.product_id,
        primary_keywords_json=groups["primary"],
        secondary_keywords_json=groups["secondary"],
        marketplace_keywords_json=groups["marketplace"],
        website_keywords_json=groups["website"],
        campaign_keywords_json=groups["campaign"],
        negative_keywords_json=groups["negative"],
        excluded_keywords_json=groups["excluded"],
        competitor_references_json=groups["competitor_reference"],
        source=data.source,
        notes=data.notes,
        locale=data.locale,
        version=1,
        is_default=data.is_default,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    record_event(
        db,
        actor_id=owner.id,
        action="ai.keyword_set_created",
        entity_type="ai_keyword_set",
        entity_id=row.id,
        metadata={"locale": row.locale, "version": row.version},
    )
    db.commit()
    return keyword_response(row)


@router.post("/keywords/suggestions", response_model=list[KeywordSuggestion])
def keyword_suggestions(
    data: KeywordSuggestionRequest, db: DatabaseSession, owner: CurrentUser
) -> list[KeywordSuggestion]:
    product = _product(db, owner.id, data.product_id)
    candidates = [product.name, product.category or "", *(product.tags or [])]
    result = [
        KeywordSuggestion(keyword=item, category="primary" if item == product.name else "secondary")
        for item in dict.fromkeys(" ".join(item.split()) for item in candidates if item.strip())
    ]
    record_event(
        db,
        actor_id=owner.id,
        action="ai.keyword_suggestions_generated",
        entity_type="product",
        entity_id=product.id,
        metadata={"locale": data.locale, "channel": data.channel, "count": len(result)},
    )
    db.commit()
    return result


@router.get("/keywords/{keyword_set_id}", response_model=KeywordSetDetail)
def get_keyword_set(
    keyword_set_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> KeywordSetDetail:
    row = db.scalar(
        select(KeywordSet).where(KeywordSet.id == keyword_set_id, KeywordSet.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Keyword Set not found.")
    return keyword_response(row)


@router.put("/keywords/{keyword_set_id}", response_model=KeywordSetDetail)
def update_keyword_set(
    keyword_set_id: uuid.UUID, data: KeywordSetUpsert, db: DatabaseSession, owner: CurrentUser
) -> KeywordSetDetail:
    row = db.scalar(
        select(KeywordSet).where(
            KeywordSet.id == keyword_set_id,
            KeywordSet.owner_id == owner.id,
            KeywordSet.archived.is_(False),
        )
    )
    if row is None:
        raise HTTPException(404, "Keyword Set not found.")
    groups = normalize_keyword_groups(data)
    now = datetime.now(UTC)
    row.name = data.name
    row.description = data.description
    row.primary_keywords_json = groups["primary"]
    row.secondary_keywords_json = groups["secondary"]
    row.marketplace_keywords_json = groups["marketplace"]
    row.website_keywords_json = groups["website"]
    row.campaign_keywords_json = groups["campaign"]
    row.negative_keywords_json = groups["negative"]
    row.excluded_keywords_json = groups["excluded"]
    row.competitor_references_json = groups["competitor_reference"]
    row.source = data.source
    row.notes = data.notes
    row.locale = data.locale
    row.version += 1
    row.is_default = data.is_default
    row.updated_at = now
    db.commit()
    db.refresh(row)
    record_event(
        db,
        actor_id=owner.id,
        action="ai.keyword_set_updated",
        entity_type="ai_keyword_set",
        entity_id=row.id,
        metadata={"version": row.version},
    )
    db.commit()
    return keyword_response(row)


@router.post(
    "/keywords/{keyword_set_id}/duplicate", response_model=KeywordSetDetail, status_code=201
)
def duplicate_keyword_set(
    keyword_set_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> KeywordSetDetail:
    source = db.scalar(
        select(KeywordSet).where(KeywordSet.id == keyword_set_id, KeywordSet.owner_id == owner.id)
    )
    if source is None:
        raise HTTPException(404, "Keyword Set not found.")
    now = datetime.now(UTC)
    row = KeywordSet(
        owner_id=owner.id,
        name=f"{source.name} copy",
        description=source.description,
        brand_id=source.brand_id,
        product_id=source.product_id,
        primary_keywords_json=list(source.primary_keywords_json or []),
        secondary_keywords_json=list(source.secondary_keywords_json or []),
        marketplace_keywords_json=list(source.marketplace_keywords_json or []),
        website_keywords_json=list(source.website_keywords_json or []),
        campaign_keywords_json=list(source.campaign_keywords_json or []),
        negative_keywords_json=list(source.negative_keywords_json or []),
        excluded_keywords_json=list(source.excluded_keywords_json or []),
        competitor_references_json=list(source.competitor_references_json or []),
        source=source.source,
        notes=source.notes,
        locale=source.locale,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return keyword_response(row)


@router.post("/keywords/{keyword_set_id}/archive", response_model=KeywordSetDetail)
def archive_keyword_set(
    keyword_set_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> KeywordSetDetail:
    row = db.scalar(
        select(KeywordSet).where(KeywordSet.id == keyword_set_id, KeywordSet.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Keyword Set not found.")
    row.archived = True
    row.is_default = False
    db.commit()
    db.refresh(row)
    record_event(
        db,
        actor_id=owner.id,
        action="ai.keyword_set_archived",
        entity_type="ai_keyword_set",
        entity_id=row.id,
        metadata={},
    )
    db.commit()
    return keyword_response(row)


@router.post("/keywords/{keyword_set_id}/restore", response_model=KeywordSetDetail)
def restore_keyword_set(
    keyword_set_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> KeywordSetDetail:
    row = db.scalar(
        select(KeywordSet).where(KeywordSet.id == keyword_set_id, KeywordSet.owner_id == owner.id)
    )
    if row is None:
        raise HTTPException(404, "Keyword Set not found.")
    row.archived = False
    db.commit()
    db.refresh(row)
    return keyword_response(row)


@router.get("/tags", response_model=list[TagSetResponse])
def list_tags(
    db: DatabaseSession, owner: CurrentUser, product_id: uuid.UUID | None = None
) -> list[TagSetResponse]:
    query = select(TagSet).where(TagSet.owner_id == owner.id, TagSet.archived.is_(False))
    if product_id:
        query = query.where(TagSet.product_id == product_id)
    return [tag_response(row) for row in db.scalars(query.order_by(TagSet.name))]


@router.post("/tags/suggestions", response_model=list[TagSuggestion])
def tag_suggestions(
    data: KeywordSuggestionRequest, db: DatabaseSession, owner: CurrentUser
) -> list[TagSuggestion]:
    product = _product(db, owner.id, data.product_id)
    candidates = [product.name, product.category or "", *(product.tags or [])]
    result = [
        TagSuggestion(tag=item)
        for item in dict.fromkeys(" ".join(item.split()) for item in candidates if item.strip())
    ]
    record_event(
        db,
        actor_id=owner.id,
        action="ai.tag_suggestions_generated",
        entity_type="product",
        entity_id=product.id,
        metadata={"locale": data.locale, "channel": data.channel, "count": len(result)},
    )
    db.commit()
    return result


@router.post("/tags", response_model=TagSetResponse, status_code=201)
def create_tag_set(data: TagSetUpsert, db: DatabaseSession, owner: CurrentUser) -> TagSetResponse:
    now = datetime.now(UTC)
    row = TagSet(
        owner_id=owner.id,
        product_id=data.product_id,
        name=data.name,
        scope=data.scope,
        locale=data.locale,
        tags_json=[{"label": tag, "source": "manual"} for tag in data.tags],
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    record_event(
        db,
        actor_id=owner.id,
        action="ai.tag_set_updated",
        entity_type="ai_tag_set",
        entity_id=row.id,
        metadata={"scope": row.scope, "locale": row.locale},
    )
    db.commit()
    return tag_response(row)


@router.put("/tags/{tag_set_id}", response_model=TagSetResponse)
def update_tag_set(
    tag_set_id: uuid.UUID, data: TagSetUpsert, db: DatabaseSession, owner: CurrentUser
) -> TagSetResponse:
    row = db.scalar(
        select(TagSet).where(
            TagSet.id == tag_set_id, TagSet.owner_id == owner.id, TagSet.archived.is_(False)
        )
    )
    if row is None:
        raise HTTPException(404, "Tag Set not found.")
    row.name = data.name
    row.product_id = data.product_id
    row.scope = data.scope
    row.locale = data.locale
    row.tags_json = [{"label": tag, "source": "manual"} for tag in data.tags]
    row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return tag_response(row)


@router.post("/tags/{tag_set_id}/archive", response_model=TagSetResponse)
def archive_tag_set(
    tag_set_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> TagSetResponse:
    row = db.scalar(select(TagSet).where(TagSet.id == tag_set_id, TagSet.owner_id == owner.id))
    if row is None:
        raise HTTPException(404, "Tag Set not found.")
    row.archived = True
    db.commit()
    db.refresh(row)
    return tag_response(row)
