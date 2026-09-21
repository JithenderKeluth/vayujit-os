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
