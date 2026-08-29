# ruff: noqa: E501,UP017
"""Deterministic local provider for autonomous research."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from vayujit_api.intelligence.policy import safe_external_content, validate_source_url

PROMPT_INJECTION_MARKERS = (
    "ignore previous instructions",
    "reveal api token",
    "run shell command",
    "send email",
    "change score",
    "approve supplier",
    "mark certification verified",
)


def classify_untrusted_content(value: str) -> dict[str, object]:
    lowered = value.lower()
    markers = [marker for marker in PROMPT_INJECTION_MARKERS if marker in lowered]
    return {
        "classification": "UNTRUSTED_EXTERNAL_DATA",
        "prompt_injection_detected": bool(markers),
        "markers": markers,
        "instructions_executable": False,
    }


def sanitize_untrusted_content(value: str, *, max_length: int = 20_000) -> str:
    safe = safe_external_content(value, max_length=max_length)
    return safe.replace("<script", "&lt;script").replace("</script>", "&lt;/script&gt;")


def validate_approved_fetch(url: str, *, allowed_domains: tuple[str, ...] = ()) -> str:
    value = validate_source_url(url)
    if value is None:
        raise ValueError("source URL is required")
    host = value.split("//", 1)[1].split("/", 1)[0].split(":", 1)[0].lower()
    if allowed_domains and not any(
        host == domain or host.endswith("." + domain) for domain in allowed_domains
    ):
        raise ValueError("source domain is not allowlisted")
    return value


@dataclass(frozen=True)
class LocalEvidence:
    source_class: str
    source_reference: str
    retrieval_identity: str
    evidence_class: str
    normalized_value: dict[str, object]
    confidence: float
    observed_at: datetime
    content_type: str = "application/json"


class LocalDeterministicResearchProvider:
    mode = "LOCAL_DETERMINISTIC"
    label = "LOCAL FIXTURE"

    def execute(self, task_type: str, mission: Any) -> dict[str, object]:
        scenario = str(dict(mission.scope).get("provider_scenario", "normal"))
        if scenario == "rate_limited" and task_type == "collect_pricing":
            raise RuntimeError("source_rate_limited")
        if scenario == "source_unavailable" and task_type in {
            "collect_trends",
            "discover_suppliers",
        }:
            raise RuntimeError("source_unavailable")
        if scenario == "unsafe_source":
            raise RuntimeError("unsafe_source")
        now = datetime.now(timezone.utc)
        base = str(mission.id)

        def ev(
            source: str, kind: str, value: dict[str, object], confidence: float = 0.82
        ) -> dict[str, object]:
            identity = f"local:{base}:{task_type}:{source}:{kind}"
            return {
                "source_class": source,
                "source_reference": f"LOCAL_FIXTURE/{source.lower()}/{kind}",
                "retrieval_identity": identity,
                "evidence_class": kind.upper(),
                "normalized_value": value,
                "confidence": confidence,
                "observed_at": now,
                "content_type": "application/json",
            }

        if task_type == "discover_candidates":
            return {
                "evidence": [
                    ev(
                        "MARKET",
                        "candidate",
                        {
                            "title": "Bamboo Drawer Organizer",
                            "category": mission.category or "home",
                            "market": mission.market or "IN",
                            "score_hint": 82,
                        },
                    ),
                    ev(
                        "MARKET",
                        "candidate",
                        {
                            "title": "Rechargeable Desk Lamp",
                            "category": mission.category or "electronics",
                            "market": mission.market or "IN",
                            "score_hint": 76,
                        },
                    ),
                ],
                "candidates": 2,
            }
        if task_type == "collect_trends":
            return {
                "evidence": [
                    ev(
                        "TREND",
                        "trend",
                        {
                            "trend_state": "growing",
                            "velocity": 0.72,
                            "acceleration": 0.18,
                            "seasonality": 0.12,
                        },
                    )
                ]
            }
        if task_type == "collect_competitors":
            return {
                "evidence": [
                    ev(
                        "COMPETITION",
                        "competitor",
                        {
                            "competitor": "Local Fixture Competitor",
                            "price": 1499,
                            "currency": "INR",
                            "rating": 4.3,
                            "review_count": 820,
                        },
                    ),
                    ev(
                        "COMPETITION",
                        "competitor",
                        {
                            "competitor": "Second Fixture Competitor",
                            "price": 1699,
                            "currency": "INR",
                            "rating": 4.4,
                            "review_count": 320,
                        },
                    ),
                ]
            }
        if task_type == "collect_reviews":
            text = sanitize_untrusted_content(
                "Packaging and size clarity are the leading fixture themes."
            )
            return {
                "evidence": [
                    ev(
                        "REVIEW",
                        "review",
                        {
                            "positive_themes": ["organization"],
                            "negative_themes": ["packaging damage"],
                            "pain_points": [text],
                        },
                    )
                ]
            }
        if task_type in {"collect_pricing", "collect_economics"}:
            first = ev(
                "PRICING", "price", {"value": 1499, "currency": "INR", "classification": "OBSERVED"}
            )
            if scenario == "conflicting":
                return {
                    "evidence": [
                        first,
                        ev(
                            "PRICING",
                            "price_listed",
                            {"value": 1899, "currency": "INR", "classification": "LISTED"},
                        ),
                    ]
                }
            return {"evidence": [first]}
        if task_type == "discover_suppliers":
            return {
                "evidence": [
                    ev(
                        "SUPPLIER",
                        "supplier",
                        {
                            "display_name": "Local Fixture Manufacturer",
                            "capabilities": ["cutting", "packaging"],
                            "verification": "REQUIRES_REVIEW",
                        },
                    )
                ]
            }
        if task_type == "verify_supplier":
            return {
                "evidence": [
                    ev(
                        "SUPPLIER",
                        "verification",
                        {
                            "identity": "fixture-supplier-001",
                            "capability": "observed",
                            "verification": "REQUIRES_REVIEW",
                        },
                        0.7,
                    )
                ]
            }
        if task_type == "risk_review":
            return {
                "evidence": [
                    ev(
                        "RISK",
                        "risk",
                        {"classification": "REQUIRES_REVIEW", "signals": ["evidence freshness"]},
                        0.76,
                    )
                ]
            }
        if task_type in {"refresh_evidence", "verify_evidence"}:
            return {
                "evidence": [
                    ev(
                        "INTERNAL",
                        "verification",
                        {"verified": True, "source_diversity": 1, "freshness": "FRESH"},
                        0.9,
                    )
                ]
            }
        if task_type in {"score_opportunities", "rerun_score"}:
            return {
                "evidence": [
                    ev(
                        "INTERNAL",
                        "score",
                        {
                            "scoring_model": "winning-product-local-v1",
                            "reuse_certified_engine": True,
                            "score": 82,
                        },
                        0.88,
                    )
                ],
                "score": 82,
            }
        if task_type in {"discover_manufacturer_website", "discover_supplier_website"}:
            source = (
                "MANUFACTURER_WEBSITE"
                if task_type.startswith("discover_manufacturer")
                else "SUPPLIER_WEBSITE"
            )
            return {
                "evidence": [
                    ev(
                        source,
                        "website",
                        {"domain": "example.org", "status": "LOCAL_FIXTURE", "read_only": True},
                    )
                ]
            }
        if task_type in {"extract_manufacturer_identity", "extract_supplier_identity"}:
            return {
                "evidence": [
                    ev(
                        "BUSINESS_IDENTITY",
                        "identity",
                        {"name": "Local Fixture Business", "state": "SOURCE_PROVIDED"},
                    )
                ]
            }
        if task_type in {"extract_manufacturer_offerings", "extract_supplier_offerings"}:
            return {
                "evidence": [
                    ev(
                        "PRODUCT_CATALOG",
                        "offering",
                        {
                            "product_name": "Fixture Offering",
                            "capabilities": ["OEM"],
                            "verification": "UNVERIFIED",
                        },
                    )
                ]
            }
        if task_type == "synthesize_report":
            return {
                "evidence": [
                    ev(
                        "INTERNAL",
                        "synthesis",
                        {
                            "findings": ["Evidence-backed local fixture result"],
                            "unknowns": [],
                            "recommendation": "REQUIRES_REVIEW",
                        },
                        0.84,
                    )
                ]
            }
        return {"evidence": [ev("INTERNAL", "general", {"status": "LOCAL_FIXTURE"})]}
