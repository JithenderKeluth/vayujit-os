from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Protocol

from fastapi import HTTPException

from vayujit_api.intelligence.review_service import _safe_metadata

ADAPTER_VERSION = "review-adapter-v1"
NORMALIZATION_VERSION = "review-normalization-v1"
MAX_BATCH_SIZE = 500
MAX_METADATA_KEYS = 64
MAX_VARIANT_KEYS = 24


@dataclass(frozen=True)
class ReviewIngestionCandidate:
    provider: str
    provider_review_id: str | None
    external_product_id: str | None
    rating: Decimal | None
    rating_scale: Decimal | None
    title: str | None
    body: str | None
    reviewer_display_id: str | None
    verified_purchase: str
    review_date: datetime | None
    review_date_precision: str
    observed_at: datetime | None
    language: str | None
    locale: str | None
    helpful_count: int | None
    variant_info: dict[str, object]
    source_reference: str | None
    source_url: str | None
    raw_payload: dict[str, object]
    normalized_payload: dict[str, object]


class ReviewIngestionAdapter(Protocol):
    provider: str
    version: str

    def adapt(self, payload: dict[str, object]) -> ReviewIngestionCandidate: ...


def _text(value: object, limit: int, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    if len(value) > limit:
        raise ValueError(f"OVERSIZED_{field.upper()}")
    return value


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[ \t]+", " ", value).strip()


def _datetime(value: object) -> tuple[datetime | None, str]:
    if value is None or value == "":
        return None, "unknown"
    if isinstance(value, datetime):
        return value, "timestamp"
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=UTC), "date"
    if not isinstance(value, str):
        raise ValueError("INVALID_DATE")
    raw = value.strip()
    try:
        if len(raw) == 10:
            parsed = date.fromisoformat(raw)
            return datetime.combine(parsed, time.min, tzinfo=UTC), "date"
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_DATE") from exc
    return parsed, "timestamp"


def _decimal(value: object, field: str) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"INVALID_{field.upper()}") from exc


def _verified(value: object) -> str:
    if value is None or value == "":
        return "UNKNOWN"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    normalized = str(value).strip().upper().replace("-", "_").replace(" ", "_")
    if normalized in {"TRUE", "VERIFIED", "YES", "Y", "1"}:
        return "TRUE"
    if normalized in {"FALSE", "NOT_VERIFIED", "NO", "N", "0"}:
        return "FALSE"
    return "UNKNOWN"


def _helpful(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("INVALID_HELPFUL_COUNT")
    if isinstance(value, int) and not isinstance(value, bool):
        result = value
    elif isinstance(value, str):
        try:
            result = int(value)
        except ValueError as exc:
            raise ValueError("INVALID_HELPFUL_COUNT") from exc
    else:
        raise ValueError("INVALID_HELPFUL_COUNT")
    if result < 0:
        raise ValueError("INVALID_HELPFUL_COUNT")
    return result


def _safe_dict(value: object) -> dict[str, object]:
    safe = _safe_metadata(value)
    return dict(safe) if isinstance(safe, dict) else {}


def _bounded_mapping(value: object, limit: int, field: str) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"MALFORMED_{field.upper()}")
    if len(value) > limit:
        raise ValueError(f"OVERSIZED_{field.upper()}")
    safe = _safe_metadata(value)
    return dict(safe) if isinstance(safe, dict) else {}


class LocalFixtureReviewAdapter:
    provider = "LOCAL_FIXTURE"
    version = ADAPTER_VERSION

    def __init__(self, provider: str) -> None:
        self.provider = provider

    def adapt(self, payload: dict[str, object]) -> ReviewIngestionCandidate:
        raw_title = _text(payload.get("title", payload.get("review_title")), 1000, "title")
        raw_body = _text(payload.get("body", payload.get("review_body")), 100_000, "body")
        title = normalize_text(raw_title)
        body = normalize_text(raw_body)
        review_date, review_date_precision = _datetime(
            payload.get("review_date", payload.get("date"))
        )
        observed_at, _ = _datetime(payload.get("observed_at"))
        rating = _decimal(payload.get("rating"), "rating")
        rating_scale = _decimal(payload.get("rating_scale", payload.get("scale")), "scale")
        if rating is not None and (rating_scale is None or rating < 0 or rating > rating_scale):
            raise ValueError("INVALID_RATING")
        if rating_scale is not None and rating_scale <= 0:
            raise ValueError("INVALID_SCALE")
        provider_review_id = _text(
            payload.get("provider_review_id", payload.get("review_id", payload.get("id"))),
            240,
            "provider_review_id",
        )
        external_product_id = _text(
            payload.get("external_product_id", payload.get("product_id")),
            240,
            "external_product_id",
        )
        reviewer = _text(
            payload.get("reviewer_display_id", payload.get("reviewer")), 240, "reviewer"
        )
        language = _text(payload.get("language"), 40, "language")
        locale = _text(payload.get("locale"), 40, "locale")
        source_reference = _text(
            payload.get("source_reference", payload.get("reference")), 500, "source_reference"
        )
        source_url = _text(payload.get("source_url", payload.get("url")), 1000, "source_url")
        variant_info = _bounded_mapping(
            payload.get("variant", payload.get("variant_info")), MAX_VARIANT_KEYS, "variant"
        )
        helpful_count = _helpful(payload.get("helpful_count", payload.get("helpful")))
        metadata = _bounded_mapping(
            payload.get("provider_metadata", payload.get("metadata")), MAX_METADATA_KEYS, "metadata"
        )
        raw_payload = _safe_dict(
            {
                "provider_review_id": provider_review_id,
                "external_product_id": external_product_id,
                "rating": str(rating) if rating is not None else None,
                "rating_scale": str(rating_scale) if rating_scale is not None else None,
                "title": raw_title,
                "body": raw_body,
                "reviewer_display_id": reviewer,
                "verified_purchase": payload.get("verified_purchase"),
                "review_date": payload.get("review_date", payload.get("date")),
                "observed_at": payload.get("observed_at"),
                "language": language,
                "locale": locale,
                "helpful_count": payload.get("helpful_count", payload.get("helpful")),
                "variant": variant_info,
                "source_reference": source_reference,
                "source_url": source_url,
                "provider_metadata": metadata,
            }
        )
        normalized_payload: dict[str, object] = {
            "provider": self.provider,
            "provider_review_id": provider_review_id,
            "external_product_id": external_product_id,
            "rating": str(rating) if rating is not None else None,
            "rating_scale": str(rating_scale) if rating_scale is not None else None,
            "title": title,
            "body": body,
            "review_date": review_date.isoformat() if review_date else None,
            "review_date_precision": review_date_precision,
            "verified_purchase": _verified(payload.get("verified_purchase")),
            "helpful_count": helpful_count,
            "variant_info": variant_info,
            "language": language,
            "locale": locale,
        }
        return ReviewIngestionCandidate(
            provider=self.provider,
            provider_review_id=provider_review_id,
            external_product_id=external_product_id,
            rating=rating,
            rating_scale=rating_scale,
            title=title,
            body=body,
            reviewer_display_id=reviewer,
            verified_purchase=_verified(payload.get("verified_purchase")),
            review_date=review_date,
            review_date_precision=review_date_precision,
            observed_at=observed_at,
            language=language,
            locale=locale,
            helpful_count=helpful_count,
            variant_info=variant_info,
            source_reference=source_reference,
            source_url=source_url,
            raw_payload=raw_payload,
            normalized_payload=normalized_payload,
        )


def adapter_for(provider: str, mode: str) -> ReviewIngestionAdapter:
    if provider not in {"LOCAL_FIXTURE", "manual", "amazon", "flipkart", "meesho", "website"}:
        raise HTTPException(status_code=422, detail="UNSUPPORTED_PROVIDER")
    if mode == "DISABLED":
        raise HTTPException(status_code=409, detail="Review ingestion provider is disabled.")
    if mode == "LIVE_READ_ONLY":
        raise HTTPException(
            status_code=503, detail="Live read-only review ingestion is not configured."
        )
    return LocalFixtureReviewAdapter(provider)
