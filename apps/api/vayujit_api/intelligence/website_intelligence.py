"""Bounded deterministic intelligence helpers for public manufacturer/supplier websites."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

from vayujit_api.intelligence.external_provider import sanitize_text, validate_external_url

WEBSITE_SOURCE_TYPES = (
    "MANUFACTURER_WEBSITE",
    "SUPPLIER_WEBSITE",
    "DISTRIBUTOR_WEBSITE",
    "WHOLESALER_WEBSITE",
    "EXPORTER_WEBSITE",
    "BRAND_WEBSITE",
    "PUBLIC_BUSINESS_DIRECTORY",
    "PUBLIC_DOCUMENTATION",
)
CERTIFICATION_STATES = (
    "CLAIMED",
    "DOCUMENT_REFERENCED",
    "SUPPORTED",
    "VERIFIED",
    "EXPIRED",
    "UNKNOWN",
)
CAPABILITY_TERMS = (
    "OEM",
    "ODM",
    "PRIVATE_LABEL",
    "CUSTOM_PACKAGING",
    "CUSTOM_DESIGN",
    "SAMPLE_AVAILABILITY",
    "LOW_MOQ",
    "BULK_PRODUCTION",
    "EXPORT_CAPABILITY",
    "QUALITY_INSPECTION",
    "DESIGN_SUPPORT",
    "TOOLING_MOLD",
)
FACILITY_PATTERNS = {
    "FACTORY_OWNED": r"(?:factory[- ]owned|own factory|manufacturer[- ]owned)",
    "FACTORY_AREA": r"factory area\s*[:=-]?\s*([^\n.;]{1,80})",
    "PRODUCTION_LINES": r"production lines?\s*[:=-]?\s*([^\n.;]{1,80})",
    "EMPLOYEE_COUNT": r"(?:employees?|workforce)\s*[:=-]?\s*([^\n.;]{1,80})",
    "MONTHLY_CAPACITY": r"(?:monthly capacity|capacity per month)\s*[:=-]?\s*([^\n.;]{1,80})",
    "WAREHOUSE": r"warehouse\s*[:=-]?\s*([^\n.;]{1,80})",
    "LABORATORY": r"laboratory|lab facility",
    "QC_FACILITY": r"(?:quality control|qc) facility",
}


@dataclass(frozen=True)
class WebsiteSourceProfile:
    domain: str
    display_name: str
    source_type: str
    country_region: str = ""
    approved_status: str = "UNKNOWN"
    fetch_permission: str = "READ_ONLY"
    freshness_policy: str = "manual"
    verification_policy: str = "evidence_required"
    robots_terms: str = "UNKNOWN"
    known_mirror_domains: tuple[str, ...] = ()
    business_identity_hints: tuple[str, ...] = ()
    notes: str = ""
    enabled: bool = False


def normalize_domain(value: str) -> str:
    parsed = urlparse(value if "://" in value else "https://" + value)
    return (parsed.hostname or "").lower().rstrip(".").removeprefix("www.")


def normalize_identity(name: str, domain: str = "") -> str:
    value = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    value = re.sub(r"\b(inc|llc|ltd|limited|co|company|corp|corporation)\b", "", value)
    return " ".join(value.split()) or normalize_domain(domain)


def _first(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return sanitize_text(match.group(1), max_length=500) if match else None


def extract_website_intelligence(
    *, url: str, text: str, source_type: str = "SUPPLIER_WEBSITE"
) -> dict[str, object]:
    """Extract explicit, source-provided claims without AI or network access."""
    safe_url = validate_external_url(url)
    bounded = sanitize_text(text, max_length=50_000)
    lower = bounded.lower()
    emails = sorted(set(re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", bounded, re.I)))[:10]
    phones = sorted(set(re.findall(r"(?:\+?\d[\d ()-]{7,}\d)", bounded)))[:10]
    certifications: list[dict[str, object]] = []
    for cert in ("ISO", "CE", "RoHS", "FCC", "BIS", "UL", "FDA", "GMP", "BSCI", "SEDEX", "SA8000"):
        if re.search(rf"\b{re.escape(cert)}\b", bounded, re.I):
            state = (
                "DOCUMENT_REFERENCED"
                if re.search(
                    rf"{cert}[^.\n]{{0,100}}(?:certificate|document|report)", bounded, re.I
                )
                else "CLAIMED"
            )
            certifications.append({"name": cert, "state": state, "source_provided": True})
    capabilities = [
        term
        for term in CAPABILITY_TERMS
        if term.replace("_", " ").lower() in lower or term.replace("_", "/").lower() in lower
    ]
    facilities: list[dict[str, object]] = []
    for facility_type, pattern in FACILITY_PATTERNS.items():
        match = re.search(pattern, bounded, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip() if match.lastindex else True
            facilities.append(
                {
                    "type": facility_type,
                    "value": sanitize_text(str(value), max_length=200),
                    "status": "CLAIMED",
                }
            )

    moq = _first(r"(?:MOQ|minimum order quantity)\s*[:=-]?\s*([\d,]+\s*[A-Za-z]+)", bounded)
    price = _first(
        r"(?:price|from)\s*[:=-]?\s*([$Ã¢â€šÂ¬Ã‚Â£Ã¢â€šÂ¹]?\s*[\d,.]+(?:\s*[A-Z]{3})?)", bounded
    )
    lead_time = _first(r"(?:lead time|production time)\s*[:=-]?\s*([\w\s-]{2,40})", bounded)
    company = _first(r"(?:company name|legal name|about)\s*[:=-]?\s*([^\n.;]{2,120})", bounded)
    address = _first(r"(?:address|located at)\s*[:=-]?\s*([^\n.;]{5,240})", bounded)
    products = [
        sanitize_text(item, max_length=180)
        for item in re.findall(r"(?:product|catalog)\s*[:=-]\s*([^\n.;]{2,180})", bounded, re.I)[
            :25
        ]
    ]
    risks: list[str] = []
    if not company:
        risks.append("missing_legal_identity")
    if not address:
        risks.append("missing_physical_address")
    if not emails and not phones:
        risks.append("generic_contact_missing")
    if certifications and all(item["state"] == "CLAIMED" for item in certifications):
        risks.append("certification_claim_without_document")
    if not re.search(r"privacy|terms|shipping", lower):
        risks.append("missing_policy_pages")
    now = datetime.now(UTC)
    commercial_terms = {"moq": moq, "price": price, "lead_time": lead_time}
    for key, pattern in {
        "shipping": r"shipping(?: claim)?\s*[:=-]?\s*([^\n.;]{2,80})",
        "incoterm": r"\b(EXW|FOB|CIF|DDP|DAP)\b",
        "availability": r"availability\s*[:=-]?\s*([^\n.;]{2,80})",
        "price_range": r"price range\s*[:=-]?\s*([^\n.;]{2,80})",
        "quantity_tier": r"(?:quantity tier|tier pricing)\s*[:=-]?\s*([^\n.;]{2,80})",
        "sample_moq": r"sample MOQ\s*[:=-]?\s*([^\n.;]{1,40})",
        "sample_price": r"sample price\s*[:=-]?\s*([^\n.;]{1,40})",
    }.items():
        value = _first(pattern, bounded)
        if value:
            commercial_terms[key] = value

    return {
        "source_type": source_type,
        "source_reference": safe_url,
        "domain": normalize_domain(safe_url),
        "retrieved_at": now.isoformat(),
        "freshness": "FRESH",
        "business_identity": {
            "name": company,
            "address": address,
            "emails": emails,
            "phones": phones,
            "state": "SOURCE_PROVIDED",
        },
        "products": products,
        "capabilities": capabilities,
        "commercial_terms": commercial_terms,
        "facilities": facilities,
        "certifications": certifications,
        "contacts": {
            "business_email": emails,
            "business_phone": phones,
            "business_address": address,
        },
        "risk_signals": risks,
        "quality_signals": {
            "https": urlparse(safe_url).scheme == "https",
            "domain_consistent": True,
            "contact_complete": bool(emails or phones),
            "product_detail_complete": bool(products),
        },
        "verification_state": "UNVERIFIED",
        "confidence": 0.35 if company else 0.15,
        "unknowns": ["independent_verification", "ownership", "certification_validity"],
        "content_hash": hashlib.sha256(bounded.encode()).hexdigest(),
        "classification": "UNTRUSTED_EXTERNAL_DATA",
    }


def match_offering(*, website_name: str, product_name: str) -> dict[str, object]:
    left = normalize_identity(website_name)
    right = normalize_identity(product_name)
    left_tokens, right_tokens = set(left.split()), set(right.split())
    overlap = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
    state = "MATCH" if overlap >= 0.6 else "POSSIBLE_MATCH" if overlap >= 0.25 else "NO_MATCH"
    return {
        "state": state,
        "confidence": round(overlap, 4),
        "reason": "normalized token overlap",
        "requires_review": state == "POSSIBLE_MATCH",
    }


def classify_identity(*, left: dict[str, object], right: dict[str, object]) -> str:
    keys = ("domain", "business_name", "address", "phone", "email", "registration_id")
    matches = sum(
        bool(left.get(k) and right.get(k) and str(left[k]).lower() == str(right[k]).lower())
        for k in keys
    )
    return "MATCH" if matches >= 2 else "POSSIBLE_MATCH" if matches == 1 else "NO_MATCH"


def materiality(change_type: str, previous: object, current: object) -> str:
    if previous == current:
        return "NON_MATERIAL"
    if change_type in {
        "business_address",
        "certification",
        "lead_time",
        "product_availability",
        "identity",
    }:
        return "REQUIRES_REVIEW"
    if change_type == "price":
        return (
            "MATERIAL"
            if isinstance(previous, (int, float))
            and isinstance(current, (int, float))
            and abs(current - previous) / max(1, abs(previous)) >= 0.15
            else "NON_MATERIAL"
        )
    if change_type == "moq":
        return (
            "MATERIAL"
            if isinstance(previous, (int, float))
            and isinstance(current, (int, float))
            and current >= previous * 2
            else "NON_MATERIAL"
        )
    return "NON_MATERIAL"
