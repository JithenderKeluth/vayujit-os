# ruff: noqa: E501,UP017
"""Deterministic autonomous research planning and bounded agent contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

AGENT_ROLES = (
    "Research Planner",
    "Market Researcher",
    "Trend Researcher",
    "Competition Researcher",
    "Review Researcher",
    "Supplier Researcher",
    "Supplier Verification Researcher",
    "Pricing Researcher",
    "Economics Researcher",
    "Risk Researcher",
    "Evidence Verifier",
    "Research Critic",
    "Research Synthesizer",
)

TASK_PLAN: dict[str, tuple[tuple[str, str, str], ...]] = {
    "PRODUCT_DISCOVERY": (
        ("discover_candidates", "MARKET", "Market Researcher"),
        ("collect_trends", "TREND", "Trend Researcher"),
        ("collect_competitors", "COMPETITION", "Competition Researcher"),
        ("verify_evidence", "INTERNAL", "Evidence Verifier"),
        ("score_opportunities", "INTERNAL", "Research Critic"),
        ("synthesize_report", "INTERNAL", "Research Synthesizer"),
    ),
    "PRODUCT_VALIDATION": (
        ("refresh_evidence", "INTERNAL", "Evidence Verifier"),
        ("collect_reviews", "REVIEW", "Review Researcher"),
        ("rerun_score", "INTERNAL", "Research Critic"),
        ("synthesize_report", "INTERNAL", "Research Synthesizer"),
    ),
    "TREND_RESEARCH": (
        ("collect_trends", "TREND", "Trend Researcher"),
        ("verify_evidence", "INTERNAL", "Evidence Verifier"),
        ("synthesize_report", "INTERNAL", "Research Synthesizer"),
    ),
    "COMPETITOR_RESEARCH": (
        ("collect_competitors", "COMPETITION", "Competition Researcher"),
        ("verify_evidence", "INTERNAL", "Evidence Verifier"),
        ("synthesize_report", "INTERNAL", "Research Synthesizer"),
    ),
    "REVIEW_RESEARCH": (
        ("collect_reviews", "REVIEW", "Review Researcher"),
        ("verify_evidence", "INTERNAL", "Evidence Verifier"),
        ("synthesize_report", "INTERNAL", "Research Synthesizer"),
    ),
    "SUPPLIER_DISCOVERY": (
        ("discover_suppliers", "SUPPLIER", "Supplier Researcher"),
        ("verify_evidence", "INTERNAL", "Evidence Verifier"),
        ("synthesize_report", "INTERNAL", "Research Synthesizer"),
    ),
    "SUPPLIER_VERIFICATION": (
        ("verify_supplier", "SUPPLIER", "Supplier Verification Researcher"),
        ("verify_evidence", "INTERNAL", "Evidence Verifier"),
        ("risk_review", "INTERNAL", "Risk Researcher"),
        ("synthesize_report", "INTERNAL", "Research Synthesizer"),
    ),
    "PRICING_RESEARCH": (
        ("collect_pricing", "PRICING", "Pricing Researcher"),
        ("verify_evidence", "INTERNAL", "Evidence Verifier"),
        ("synthesize_report", "INTERNAL", "Research Synthesizer"),
    ),
    "ECONOMICS_RESEARCH": (
        ("collect_pricing", "PRICING", "Pricing Researcher"),
        ("collect_economics", "ECONOMICS", "Economics Researcher"),
        ("verify_evidence", "INTERNAL", "Evidence Verifier"),
        ("synthesize_report", "INTERNAL", "Research Synthesizer"),
    ),
    "RISK_RESEARCH": (
        ("risk_review", "RISK", "Risk Researcher"),
        ("verify_evidence", "INTERNAL", "Evidence Verifier"),
        ("synthesize_report", "INTERNAL", "Research Synthesizer"),
    ),
    "SOURCE_REFRESH": (
        ("refresh_evidence", "INTERNAL", "Evidence Verifier"),
        ("synthesize_report", "INTERNAL", "Research Synthesizer"),
    ),
    "FULL_OPPORTUNITY_RESEARCH": (
        ("discover_candidates", "MARKET", "Market Researcher"),
        ("collect_trends", "TREND", "Trend Researcher"),
        ("collect_competitors", "COMPETITION", "Competition Researcher"),
        ("collect_reviews", "REVIEW", "Review Researcher"),
        ("discover_suppliers", "SUPPLIER", "Supplier Researcher"),
        ("collect_pricing", "PRICING", "Pricing Researcher"),
        ("collect_economics", "ECONOMICS", "Economics Researcher"),
        ("risk_review", "RISK", "Risk Researcher"),
        ("verify_evidence", "INTERNAL", "Evidence Verifier"),
        ("score_opportunities", "INTERNAL", "Research Critic"),
        ("synthesize_report", "INTERNAL", "Research Synthesizer"),
    ),
    "MANUFACTURER_RESEARCH": (
        ("discover_manufacturer_website", "MANUFACTURER_WEBSITE", "Market Researcher"),
        ("extract_manufacturer_identity", "BUSINESS_IDENTITY", "Evidence Verifier"),
        ("extract_manufacturer_offerings", "PRODUCT_CATALOG", "Supplier Researcher"),
        ("verify_evidence", "INTERNAL", "Evidence Verifier"),
        ("risk_review", "RISK", "Risk Researcher"),
        ("synthesize_report", "INTERNAL", "Research Synthesizer"),
    ),
    "SUPPLIER_WEBSITE_RESEARCH": (
        ("discover_supplier_website", "SUPPLIER_WEBSITE", "Supplier Researcher"),
        ("extract_supplier_identity", "BUSINESS_IDENTITY", "Evidence Verifier"),
        ("extract_supplier_offerings", "PRODUCT_CATALOG", "Supplier Researcher"),
        ("verify_evidence", "INTERNAL", "Evidence Verifier"),
        ("risk_review", "RISK", "Risk Researcher"),
        ("synthesize_report", "INTERNAL", "Research Synthesizer"),
    ),
}

STOP_CONDITIONS = (
    "required_confidence_reached",
    "required_evidence_classes_complete",
    "hard_rule_blocked",
    "maximum_task_count",
    "maximum_retry_reached",
    "external_source_unavailable",
    "human_review_required",
)
RECOVERY_FAILURE_CODES = (
    "source_unavailable",
    "source_rate_limited",
    "source_auth_failed",
    "unsafe_source",
    "invalid_payload",
    "evidence_validation_failed",
    "contradiction_unresolved",
    "budget_exhausted",
    "timeout",
    "checkpoint_invalid",
    "scoring_failed",
    "dependency_failed",
)
RECOVERY_ACTIONS = (
    "retry",
    "reconcile",
    "refresh_source",
    "review_source",
    "review_evidence",
    "resolve_contradiction",
    "skip_optional_task",
    "cancel",
)
SOURCE_REGISTRY = (
    ("IndiaMART", "NOT_CONFIGURED"),
    ("Alibaba", "NOT_CONFIGURED"),
    ("TradeIndia", "NOT_CONFIGURED"),
    ("Global Sources", "NOT_CONFIGURED"),
    ("Manufacturer sites", "MANUAL_ONLY"),
    ("Marketplace research", "LOCAL_FIXTURE"),
    ("Trend/search sources", "LOCAL_FIXTURE"),
)


@dataclass(frozen=True)
class AgentContract:
    role: str
    goal: str
    scope: dict[str, object]
    allowed_sources: tuple[str, ...]
    forbidden_sources: tuple[str, ...]
    existing_evidence: tuple[str, ...]
    required_output_schema: str
    max_elapsed_seconds: int
    max_provider_calls: int
    correlation_id: str


def build_plan(mission_type: str, *, max_tasks: int, correlation_id: str) -> list[dict[str, Any]]:
    planned = TASK_PLAN.get(mission_type)
    if planned is None:
        raise ValueError("Unsupported autonomous mission type")
    if len(planned) > max_tasks:
        planned = planned[:max_tasks]
    tasks: list[dict[str, Any]] = []
    previous: list[str] = []
    for position, (task_type, source_class, role) in enumerate(planned):
        dependencies = list(previous[-1:])
        task = {
            "task_type": task_type,
            "source_class": source_class,
            "role": role,
            "priority": position * 10 + 10,
            "dependency_ids": dependencies,
            "required_evidence_classes": [source_class],
            "stop_conditions": list(STOP_CONDITIONS),
            "fallback": "mark_partial_and_continue_independent_tasks",
        }
        tasks.append(task)
        previous.append(task_type)
    return tasks


def contract_for(
    task: dict[str, Any], *, mission: Any, existing_evidence: tuple[str, ...] = ()
) -> AgentContract:
    return AgentContract(
        role=str(task["role"]),
        goal=str(mission.goal),
        scope=dict(mission.scope),
        allowed_sources=(str(task["source_class"]), "INTERNAL"),
        forbidden_sources=(
            "ARBITRARY_SCRAPER",
            "PRIVATE_IP",
            "METADATA_ENDPOINT",
            "UNAPPROVED_BROWSER",
        ),
        existing_evidence=existing_evidence,
        required_output_schema="structured_evidence_v1",
        max_elapsed_seconds=mission.max_elapsed_seconds,
        max_provider_calls=mission.max_provider_calls,
        correlation_id=mission.correlation_id,
    )
