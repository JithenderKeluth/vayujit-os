# ruff: noqa
"""Explicit capability registry for the Business Agent boundary."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilitySpec:
    id: str
    version: str
    input_schema: str
    output_schema: str
    execution_class: str
    side_effect_class: str
    approval_required: bool
    provider_required: bool
    availability: str = "LOCAL"
    health: str = "HEALTHY"


CAPABILITY_REGISTRY: tuple[CapabilitySpec, ...] = (
    CapabilitySpec(
        "product_opportunity.create",
        "1",
        "BusinessGoal",
        "ProductOpportunity",
        "deterministic",
        "NONE",
        False,
        False,
    ),
    CapabilitySpec(
        "demand.intelligence",
        "1",
        "OpportunityRef",
        "DemandEvidence",
        "autonomous_research",
        "NONE",
        False,
        False,
    ),
    CapabilitySpec(
        "competition.intelligence",
        "1",
        "OpportunityRef",
        "CompetitionEvidence",
        "autonomous_research",
        "NONE",
        False,
        False,
    ),
    CapabilitySpec(
        "COMPETITOR_DISCOVERY",
        "1",
        "CompetitorContextRef",
        "DiscoverySnapshot",
        "autonomous_research",
        "INTERNAL_WRITE",
        False,
        False,
    ),
    CapabilitySpec(
        "COMPETITOR_ANALYSIS",
        "1",
        "CompetitorContextRef",
        "CommercialAnalysisProjection",
        "autonomous_research",
        "INTERNAL_WRITE",
        False,
        False,
    ),
    CapabilitySpec(
        "COMPETITOR_CHANGE_ANALYSIS",
        "1",
        "CompetitorContextRef",
        "ChangeComparison",
        "autonomous_research",
        "INTERNAL_WRITE",
        False,
        False,
    ),
    CapabilitySpec(
        "REVIEW_INGESTION",
        "1",
        "ReviewContextRef",
        "ReviewSnapshotRef",
        "autonomous_research",
        "INTERNAL_WRITE",
        False,
        False,
    ),
    CapabilitySpec(
        "REVIEW_ANALYSIS",
        "1",
        "ReviewContextRef",
        "ReviewAnalysisRef",
        "autonomous_research",
        "INTERNAL_WRITE",
        False,
        False,
    ),
    CapabilitySpec(
        "REVIEW_GAP_ANALYSIS",
        "1",
        "ReviewAnalysisRef",
        "ReviewGapAnalysisRef",
        "autonomous_research",
        "INTERNAL_WRITE",
        False,
        False,
    ),
    CapabilitySpec(
        "REVIEW_CHANGE_ANALYSIS",
        "1",
        "ReviewAnalysisPair",
        "ReviewChangeComparisonRef",
        "autonomous_research",
        "INTERNAL_WRITE",
        False,
        False,
    ),
    CapabilitySpec(
        "REVIEW_WINNING_PRODUCT_PROJECTION",
        "1",
        "ProductOpportunityAssessment",
        "ReviewWinningProductProjectionRef",
        "autonomous_research",
        "INTERNAL_WRITE",
        False,
        False,
    ),
    CapabilitySpec(
        "TREND_CONTEXT_RESOLUTION",
        "1",
        "OpportunityRef",
        "TrendContextRef",
        "deterministic",
        "INTERNAL_WRITE",
        False,
        False,
    ),
    CapabilitySpec(
        "TREND_INGESTION",
        "1",
        "TrendContextRef",
        "TrendEvidenceRef",
        "autonomous_research",
        "INTERNAL_WRITE",
        False,
        False,
    ),
    CapabilitySpec(
        "TREND_ANALYSIS",
        "1",
        "TrendContextRef",
        "TrendAnalysisRef",
        "deterministic",
        "INTERNAL_WRITE",
        False,
        False,
    ),
    CapabilitySpec(
        "TREND_CHANGE_ANALYSIS",
        "1",
        "TrendAnalysisRef",
        "TrendComparisonRef",
        "deterministic",
        "INTERNAL_WRITE",
        False,
        False,
    ),
    CapabilitySpec(
        "TREND_VALIDATION",
        "1",
        "TrendAnalysisRef",
        "TrendValidationRef",
        "deterministic",
        "INTERNAL_WRITE",
        False,
        False,
    ),
    CapabilitySpec(
        "TREND_WINNING_PRODUCT_PROJECTION",
        "1",
        "ProductOpportunityAssessment",
        "TrendWinningProductProjectionRef",
        "deterministic",
        "INTERNAL_WRITE",
        False,
        False,
    ),
    CapabilitySpec(
        "commercial.assessment",
        "1",
        "OpportunityRef",
        "CommercialAssessment",
        "product_opportunity",
        "NONE",
        False,
        False,
    ),
    CapabilitySpec(
        "supplier.discovery",
        "1",
        "OpportunityRef",
        "SupplierEvidence",
        "autonomous_research",
        "NONE",
        False,
        False,
    ),
    CapabilitySpec(
        "supplier.feasibility",
        "1",
        "OpportunityRef",
        "FeasibilityAssessment",
        "product_opportunity",
        "NONE",
        False,
        False,
    ),
    CapabilitySpec(
        "winning_product.score",
        "1",
        "OpportunityAssessment",
        "WinningProductScore",
        "product_opportunity",
        "NONE",
        False,
        False,
    ),
    CapabilitySpec(
        "winning_product.rank",
        "1",
        "ScoreSet",
        "RankedOpportunities",
        "deterministic",
        "NONE",
        False,
        False,
    ),
    CapabilitySpec(
        "sourcing_economics.inspect",
        "1",
        "EconomicContextRef",
        "EconomicProjection",
        "deterministic",
        "NONE",
        False,
        False,
    ),
    CapabilitySpec(
        "decision_brief.generate",
        "1",
        "AgentRun",
        "DecisionBrief",
        "deterministic",
        "NONE",
        True,
        False,
    ),
    CapabilitySpec(
        "external.write",
        "1",
        "Any",
        "None",
        "forbidden",
        "EXTERNAL_WRITE",
        True,
        False,
        "DISABLED",
        "DISABLED",
    ),
)


CAPABILITY_BUSINESS_COPY: dict[str, tuple[str, str]] = {
    "product_opportunity.create": (
        "Discover product opportunities",
        "Find product ideas that fit the stated goal and constraints.",
    ),
    "demand.intelligence": (
        "Review market activity evidence",
        "Inspect available market activity signals without turning them into sales claims.",
    ),
    "competition.intelligence": (
        "Analyze competing products",
        "Review observable assortment and competition evidence.",
    ),
    "commercial.assessment": (
        "Assess commercial considerations",
        "Identify commercial evidence and the information still needed.",
    ),
    "supplier.discovery": (
        "Research supplier options",
        "Prepare supplier research for the product opportunities under review.",
    ),
    "supplier.feasibility": (
        "Review sourcing feasibility",
        "Check sourcing evidence available for further investigation.",
    ),
    "winning_product.score": (
        "Assess product opportunities",
        "Explain the deterministic assessment while preserving score, risk, and confidence separately.",
    ),
    "winning_product.rank": (
        "Compare product opportunities",
        "Arrange authoritative product opportunity assessments for human comparison.",
    ),
    "decision_brief.generate": (
        "Prepare research findings",
        "Assemble an evidence-backed brief for human review.",
    ),
    "sourcing_economics.inspect": (
        "Review sourcing economics",
        "Show factual cost evidence and gaps without profitability claims.",
    ),
    "TREND_CONTEXT_RESOLUTION": (
        "Set up market trend research",
        "Connect the opportunity to the appropriate trend context.",
    ),
    "TREND_INGESTION": (
        "Collect trend evidence",
        "Gather observed signal evidence from the configured trend source.",
    ),
    "TREND_ANALYSIS": (
        "Analyze market trend signals",
        "Describe observed changes in external signals over time.",
    ),
    "TREND_CHANGE_ANALYSIS": (
        "Compare trend changes",
        "Compare observed trend periods without forecasting demand or sales.",
    ),
    "TREND_VALIDATION": (
        "Validate trend evidence",
        "Check freshness, agreement, and evidence gaps in trend observations.",
    ),
    "TREND_WINNING_PRODUCT_PROJECTION": (
        "Relate trend evidence to products",
        "Keep trend evidence descriptive and separate from product-success claims.",
    ),
    "COMPETITOR_DISCOVERY": (
        "Discover competing products",
        "Collect bounded competitor observations through the existing service boundary.",
    ),
    "COMPETITOR_ANALYSIS": (
        "Analyze competition",
        "Summarize assortment, pricing, positioning, and evidence quality where available.",
    ),
    "COMPETITOR_CHANGE_ANALYSIS": (
        "Review competitor changes",
        "Compare observed competitor changes without inferring revenue or sales volume.",
    ),
    "REVIEW_INGESTION": (
        "Collect customer feedback evidence",
        "Gather review observations through the existing Review Intelligence boundary.",
    ),
    "REVIEW_ANALYSIS": (
        "Understand customer feedback",
        "Summarize recurring themes, sentiment, and customer pain points.",
    ),
    "REVIEW_GAP_ANALYSIS": (
        "Identify feedback evidence gaps",
        "Show what customer-feedback evidence is still missing.",
    ),
    "REVIEW_CHANGE_ANALYSIS": (
        "Compare feedback changes",
        "Describe changes in customer feedback over time.",
    ),
    "REVIEW_WINNING_PRODUCT_PROJECTION": (
        "Relate feedback to opportunities",
        "Connect customer pain points to product gaps without claiming product success.",
    ),
}


def business_copy(capability_id: str) -> tuple[str, str]:
    return CAPABILITY_BUSINESS_COPY.get(capability_id, (capability_id, ""))


def capability_map() -> dict[str, CapabilitySpec]:
    return {item.id: item for item in CAPABILITY_REGISTRY}


def authorize_capability(capability_id: object, request: object | None = None) -> CapabilitySpec:
    """Resolve only explicitly registered local read-only capabilities."""
    if not isinstance(capability_id, str) or not capability_id.strip():
        raise ValueError("Malformed capability request.")
    if request is not None and not isinstance(request, dict):
        raise ValueError("Malformed capability request.")
    spec = capability_map().get(capability_id)
    if spec is None:
        raise ValueError("Unknown capability.")
    if spec.availability != "LOCAL" or spec.side_effect_class not in {
        "NONE",
        "READ_ONLY",
        "INTERNAL_WRITE",
    }:
        raise PermissionError("Capability is disabled for local certification.")
    return spec
