import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from typing import cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.seo_models import SEOAnalysis, TagSet
from vayujit_api.ai.seo_schemas import (
    KeywordSetDetail,
    KeywordSetUpsert,
    SEOAnalysisResponse,
    SEOFinding,
    SEORequest,
    TagScope,
    TagSetResponse,
)
from vayujit_api.ai.studio_models import KeywordSet
from vayujit_api.audit.service import record_event
from vayujit_api.products.models import Product

RULE_VERSION = "seo-rules-v1"
CHANNEL_RULES: dict[str, dict[str, object]] = {
    "canonical": {"type": "website", "title": 60, "description": 160},
    "wordpress": {"type": "website", "title": 60, "description": 160},
    "shopify": {"type": "website", "title": 70, "description": 320},
    "amazon": {
        "type": "marketplace",
        "title": 200,
        "description": 2000,
        "required": ["title", "bullets", "description"],
    },
    "flipkart": {
        "type": "marketplace",
        "title": 150,
        "description": 2000,
        "required": ["title", "highlights", "description"],
    },
    "meesho": {
        "type": "marketplace",
        "title": 150,
        "description": 2000,
        "required": ["title", "description"],
    },
}


def _terms(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        term = " ".join(str(value).strip().split())
        if term and term.casefold() not in seen:
            seen.add(term.casefold())
            result.append(term)
    return result


def _product(db: Session, owner_id: uuid.UUID, product_id: uuid.UUID) -> Product:
    row = db.scalar(select(Product).where(Product.id == product_id, Product.owner_id == owner_id))
    if row is None:
        raise HTTPException(404, "Product not found.")
    return row


def _keyword_set(
    db: Session, owner_id: uuid.UUID, key_id: uuid.UUID | None, locale: str
) -> KeywordSet | None:
    if key_id:
        row = db.scalar(
            select(KeywordSet).where(
                KeywordSet.id == key_id,
                KeywordSet.owner_id == owner_id,
                KeywordSet.archived.is_(False),
            )
        )
        if row is None:
            raise HTTPException(404, "Keyword Set not found.")
        if row.locale != locale:
            raise HTTPException(
                422, "Keyword Set locale does not match the requested analysis locale."
            )
        return row
    return None


def _artifact(db: Session, owner_id: uuid.UUID, data: SEORequest, product: Product):
    from vayujit_api.ai.models import GeneratedArtifact

    if data.artifact_id:
        row = db.scalar(
            select(GeneratedArtifact).where(
                GeneratedArtifact.id == data.artifact_id, GeneratedArtifact.owner_id == owner_id
            )
        )
        if row is None or row.product_id != product.id:
            raise HTTPException(404, "Artifact not found for this Product.")
        if row.locale != data.locale:
            raise HTTPException(
                422, "Artifact locale does not match the requested analysis locale."
            )
        if row.channel != data.channel:
            raise HTTPException(
                422, "Artifact channel does not match the requested analysis channel."
            )
        return row
    return db.scalar(
        select(GeneratedArtifact)
        .where(
            GeneratedArtifact.owner_id == owner_id,
            GeneratedArtifact.product_id == product.id,
            GeneratedArtifact.channel == data.channel,
            GeneratedArtifact.locale == data.locale,
            GeneratedArtifact.status == "approved",
        )
        .order_by(GeneratedArtifact.version_number.desc())
    )


def _finding_response(item: dict[str, object], row: SEOAnalysis) -> SEOFinding:
    payload = dict(item)
    severity = str(payload.get("severity") or "information")
    actions = (
        ["reanalyze"]
        if row.status == "stale"
        else (
            ["edit", "regenerate"] if severity in {"warning", "recommendation", "blocker"} else []
        )
    )
    if str(payload.get("field")) == "keywords":
        actions = ["open_keywords", *actions]
    payload["actions"] = list(dict.fromkeys(actions))
    return SEOFinding.model_validate(payload)


def _analysis_response(row: SEOAnalysis) -> SEOAnalysisResponse:
    return SEOAnalysisResponse(
        id=row.id,
        product_id=row.product_id,
        artifact_id=row.artifact_id,
        artifact_version=row.artifact_version,
        keyword_set_id=row.keyword_set_id,
        keyword_set_version=row.keyword_set_version,
        channel=row.channel,
        seo_type=row.seo_type,
        locale=row.locale,
        intent=row.intent,
        overall_score=row.overall_score,
        dimensions=cast(dict[str, dict[str, object]], row.dimensions_json),
        findings=[_finding_response(item, row) for item in row.findings_json],
        recommendations=[_finding_response(item, row) for item in row.recommendations_json],
        keyword_coverage=row.keyword_coverage_json,
        metrics=row.metrics_json,
        fingerprint=row.fingerprint,
        rule_version=row.rule_version,
        status=row.status,
        analyzed_at=row.analyzed_at,
    )


def analyze(db: Session, owner_id: uuid.UUID, data: SEORequest) -> SEOAnalysisResponse:
    product = _product(db, owner_id, data.product_id)
    keyset = _keyword_set(db, owner_id, data.keyword_set_id, data.locale)
    artifact = _artifact(db, owner_id, data, product)
    content = (
        dict(artifact.content_json)
        if artifact
        else {
            "title": product.name,
            "description": product.description or "",
            "tags": product.tags or [],
        }
    )
    text = json.dumps(content, ensure_ascii=False)
    primary = data.primary_keyword or (
        list(keyset.primary_keywords_json or [])[0]
        if keyset and keyset.primary_keywords_json
        else None
    )
    secondary = _terms(
        data.secondary_keywords + (list(keyset.secondary_keywords_json or []) if keyset else [])
    )
    requested = _terms(([primary] if primary else []) + secondary)
    lowered = text.casefold()
    hits = [term for term in requested if term.casefold() in lowered]
    rules = CHANNEL_RULES[data.channel]
    findings: list[SEOFinding] = []
    title = str(content.get("title") or content.get("seo_title") or "")
    description = str(content.get("description") or content.get("seo_description") or "")
    if not artifact:
        findings.append(
            SEOFinding(
                severity="information",
                field="artifact",
                code="no_approved_artifact",
                explanation="Generate or approve content before running full SEO/Search analysis.",
                suggested_action="Generate content",
            )
        )
    if not title:
        findings.append(
            SEOFinding(
                severity="blocker",
                field="title",
                code="missing_title",
                explanation="Required title content is missing.",
                suggested_action="Edit content",
            )
        )
    if not description:
        findings.append(
            SEOFinding(
                severity=(
                    "blocker" if data.channel in {"amazon", "flipkart", "meesho"} else "warning"
                ),
                field="description",
                code="missing_description",
                explanation="Description content is missing.",
                suggested_action="Edit content",
            )
        )
    if primary and primary.casefold() not in title.casefold():
        findings.append(
            SEOFinding(
                severity="warning",
                field="title",
                code="primary_keyword_missing",
                explanation=f'Primary keyword "{primary}" is not present in the title.',
                suggested_action="Edit or regenerate",
            )
        )
    title_limit = int(cast(int, rules["title"]))
    if len(title) > title_limit:
        findings.append(
            SEOFinding(
                severity="warning",
                field="title",
                code="title_length",
                explanation="Title exceeds the configured channel guidance.",
                suggested_action="Shorten title",
            )
        )
    excluded = (
        set(
            (keyset.negative_keywords_json or [])
            + (getattr(keyset, "excluded_keywords_json", []) or [])
        )
        if keyset
        else set()
    )
    for term in excluded:
        if str(term).casefold() in lowered:
            findings.append(
                SEOFinding(
                    severity="blocker",
                    field="content",
                    code="excluded_term_used",
                    explanation="An excluded term appears in the content.",
                    suggested_action="Edit content",
                )
            )
    repetitions = [term for term in requested if len(re.findall(re.escape(term), lowered)) > 4]
    if repetitions:
        findings.append(
            SEOFinding(
                severity="warning",
                field="keywords",
                code="keyword_stuffing",
                explanation="Repeated terms may reduce content quality; avoid stuffing.",
                suggested_action="Edit naturally",
            )
        )
    completeness = 100 if title and description else 50 if title else 0
    coverage = round(100 * len(hits) / max(1, len(requested)))
    readability = max(0, min(100, 100 - max(0, len(text.split()) - 250) // 10))
    dimensions: dict[str, dict[str, object]] = {}
    for name, score, explanation in (
        ("Completeness", completeness, "Required content fields are present."),
        ("Keyword Coverage", coverage, "Requested terms found in the Artifact content."),
        (
            "Title Quality",
            100 if title and len(title) <= title_limit else 60,
            "Title length and presence checks.",
        ),
        (
            "Metadata Quality",
            90 if content.get("seo") or content.get("seo_title") else 65,
            "SEO metadata fields are evaluated when available.",
        ),
        ("Readability", readability, "Deterministic length-based readability guidance."),
        (
            "Structure",
            90 if any(key in content for key in ("headings", "bullets", "highlights")) else 65,
            "Structured fields are checked when provided.",
        ),
        ("Fact Consistency", 100, "No unsupported Product facts were introduced by this analysis."),
        (
            "Channel Compliance",
            max(0, 100 - sum(1 for item in findings if item.severity == "blocker") * 40),
            "Configured channel capability checks only.",
        ),
    ):
        related = [
            item.model_dump()
            for item in findings
            if item.field.casefold() in name.casefold() or name.casefold() in item.field.casefold()
        ]
        dimensions[name] = {
            "score": score,
            "explanation": explanation,
            "checks": [{"result": "pass" if score >= 80 else "review", "score": score}],
            "recommendations": related,
        }
    overall = round(
        sum(int(cast(int, item["score"])) for item in dimensions.values()) / len(dimensions)
    )
    now = datetime.now(UTC)
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "product": str(product.id),
                "artifact": str(artifact.id) if artifact else None,
                "version": artifact.version_number if artifact else None,
                "keywords": requested,
                "keyword_version": keyset.version if keyset else None,
                "channel": data.channel,
                "locale": data.locale,
                "rule": RULE_VERSION,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    existing = db.scalar(
        select(SEOAnalysis).where(
            SEOAnalysis.owner_id == owner_id,
            SEOAnalysis.artifact_id == (artifact.id if artifact else None),
            SEOAnalysis.channel == data.channel,
            SEOAnalysis.locale == data.locale,
            SEOAnalysis.fingerprint == fingerprint,
        )
    )
    if existing and not data.force:
        existing.status = "current"
        return _analysis_response(existing)
    if existing is None:
        prior_rows = db.scalars(
            select(SEOAnalysis).where(
                SEOAnalysis.owner_id == owner_id,
                SEOAnalysis.product_id == product.id,
                SEOAnalysis.channel == data.channel,
                SEOAnalysis.locale == data.locale,
                SEOAnalysis.status == "current",
            )
        ).all()
        for prior in prior_rows:
            prior.status = "stale"
    if existing:
        row = existing
        row.analyzed_at = now
    else:
        row = SEOAnalysis(
            owner_id=owner_id,
            product_id=product.id,
            artifact_id=artifact.id if artifact else None,
            artifact_version=artifact.version_number if artifact else None,
            keyword_set_id=keyset.id if keyset else None,
            keyword_set_version=keyset.version if keyset else None,
            channel=data.channel,
            locale=data.locale,
            intent=data.intent,
            seo_type=str(rules["type"]),
            fingerprint=fingerprint,
            rule_version=RULE_VERSION,
            overall_score=overall,
            dimensions_json=dimensions,
            findings_json=[item.model_dump() for item in findings],
            recommendations_json=[
                item.model_dump()
                for item in findings
                if item.severity in {"recommendation", "warning"}
            ],
            keyword_coverage_json={
                "requested": requested,
                "covered": hits,
                "missing": [term for term in requested if term not in hits],
            },
            metrics_json={
                "search_volume": "unavailable",
                "keyword_difficulty": "unavailable",
                "cpc": "unavailable",
                "ranking_position": "unavailable",
            },
            analyzed_at=now,
        )
        db.add(row)
    row.overall_score = overall
    row.dimensions_json = cast(dict[str, object], dimensions)
    row.findings_json = [item.model_dump() for item in findings]
    row.recommendations_json = [
        item.model_dump() for item in findings if item.severity in {"recommendation", "warning"}
    ]
    row.keyword_coverage_json = {
        "requested": requested,
        "covered": hits,
        "missing": [term for term in requested if term not in hits],
    }
    row.status = "current"
    row.fingerprint = fingerprint
    row.keyword_set_id = keyset.id if keyset else None
    row.keyword_set_version = keyset.version if keyset else None
    row.intent = data.intent
    row.analyzed_at = now
    db.flush()
    record_event(
        db,
        actor_id=owner_id,
        action="ai.seo_reanalyzed" if existing else "ai.seo_analyzed",
        entity_type="ai_seo_analysis",
        entity_id=row.id,
        metadata={
            "channel": data.channel,
            "locale": data.locale,
            "artifact_version": row.artifact_version,
        },
    )
    db.flush()
    db.commit()
    db.refresh(row)
    return _analysis_response(row)


def keyword_response(row: KeywordSet) -> KeywordSetDetail:
    return KeywordSetDetail(
        id=row.id,
        name=row.name,
        description=row.description,
        brand_id=row.brand_id,
        product_id=row.product_id,
        locale=row.locale,
        primary=list(row.primary_keywords_json or []),
        secondary=list(row.secondary_keywords_json or []),
        marketplace=list(row.marketplace_keywords_json or []),
        website=list(row.website_keywords_json or []),
        campaign=list(row.campaign_keywords_json or []),
        excluded=list(getattr(row, "excluded_keywords_json", []) or []),
        negative=list(row.negative_keywords_json or []),
        competitor_reference=list(getattr(row, "competitor_references_json", []) or []),
        source=row.source,
        notes=row.notes,
        is_default=row.is_default,
        version=row.version,
        archived=row.archived,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def normalize_keyword_groups(data: KeywordSetUpsert) -> dict[str, list[str]]:
    groups = {
        "primary": data.primary,
        "secondary": data.secondary,
        "marketplace": data.marketplace,
        "website": data.website,
        "campaign": data.campaign,
        "excluded": data.excluded,
        "negative": data.negative,
        "competitor_reference": data.competitor_reference,
    }
    normalized = {key: _terms(value) for key, value in groups.items()}
    primary = {value.casefold() for value in normalized["primary"]}
    excluded = {value.casefold() for value in normalized["excluded"]}
    negative = {value.casefold() for value in normalized["negative"]}
    conflicts = primary & (excluded | negative)
    if conflicts:
        raise HTTPException(
            422, {"code": "keyword_conflict", "field": "primary", "conflicts": sorted(conflicts)}
        )
    return normalized


def tag_response(row: TagSet) -> TagSetResponse:
    return TagSetResponse(
        id=row.id,
        name=row.name,
        product_id=row.product_id,
        scope=cast(TagScope, row.scope),
        locale=row.locale,
        tags=[
            str(item.get("label", "")) if isinstance(item, dict) else str(item)
            for item in row.tags_json
        ],
        archived=row.archived,
        created_at=row.created_at,
        updated_at=row.updated_at,
        tag_details=[item for item in row.tags_json if isinstance(item, dict)],
    )
