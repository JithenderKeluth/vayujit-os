"""Deterministic concentration, dependency, and alternate-readiness analysis for 8E.2."""

# ruff: noqa: E501, E701

from __future__ import annotations

import uuid
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.portfolio_models import (
    SupplierPortfolioAlternateReadiness,
    SupplierPortfolioAssessmentVersion,
    SupplierPortfolioConcentrationMetric,
    SupplierPortfolioContext,
    SupplierPortfolioDependencyFinding,
)

CONCENTRATION_CALCULATION_VERSION = "8E.2-concentration-v1"
DEPENDENCY_CALCULATION_VERSION = "8E.2-dependencies-v1"
READINESS_CALCULATION_VERSION = "8E.2-readiness-v1"
HHI_THRESHOLD_VERSION = "8E.2-hhi-thresholds-v1"
HHI_LOW_THRESHOLD = Decimal("0.15")
HHI_MODERATE_THRESHOLD = Decimal("0.25")
MISSING = "INSUFFICIENT_EVIDENCE"
DEPENDENCY_TYPES = (
    "ONLY_QUALIFIED_SUPPLIER",
    "ONLY_VERIFIED_SUPPLIER",
    "ONLY_LOW_RISK_SUPPLIER",
    "ONLY_SUPPLIER_FOR_PRODUCT",
    "ONLY_SUPPLIER_FOR_CRITICAL_CAPABILITY",
    "ONLY_COUNTRY_SOURCE",
    "ONLY_REGION_SOURCE",
    "ONLY_CURRENTLY_AVAILABLE_SOURCE",
    "ONLY_SUPPLIER_MEETING_MOQ",
    "ONLY_SUPPLIER_MEETING_LEAD_TIME",
    "ONLY_SUPPLIER_WITH_ACCEPTABLE_LANDED_COST",
)
READINESS_STATES = (
    "READY",
    "CONDITIONALLY_READY",
    "RESEARCH_REQUIRED",
    "DUE_DILIGENCE_REQUIRED",
    "COMMERCIAL_VALIDATION_REQUIRED",
    "NOT_READY",
    "BLOCKED",
    "UNKNOWN",
)


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() and parsed >= 0 else None


def _float(value: Decimal | None) -> float | None:
    return float(value.quantize(Decimal("0.0000000001"))) if value is not None else None


def _assessment(
    db: Session, owner: User, portfolio: SupplierPortfolioContext, version_id: uuid.UUID | None
) -> SupplierPortfolioAssessmentVersion:
    target = version_id or portfolio.current_assessment_version_id
    if target is None:
        raise HTTPException(status_code=409, detail="Supplier portfolio has no assessment.")
    row = db.scalar(
        select(SupplierPortfolioAssessmentVersion).where(
            SupplierPortfolioAssessmentVersion.id == target,
            SupplierPortfolioAssessmentVersion.owner_id == owner.id,
            SupplierPortfolioAssessmentVersion.portfolio_id == portfolio.id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Supplier portfolio assessment not found.")
    return row


def _members(assessment: SupplierPortfolioAssessmentVersion) -> list[dict[str, Any]]:
    snapshot = assessment.input_snapshot if isinstance(assessment.input_snapshot, dict) else {}
    return [value for value in snapshot.get("memberships", []) if isinstance(value, dict)]


def _dedupe_members(members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for member in members:
        key = str(member.get("supplier_id", ""))
        if key and (
            key not in latest or int(member.get("version", 0)) >= int(latest[key].get("version", 0))
        ):
            latest[key] = member
    return [latest[key] for key in sorted(latest)]


def _supplier_map(
    db: Session, owner: User, members: list[dict[str, Any]]
) -> dict[str, CrossMarketplaceSupplier]:
    ids = [uuid.UUID(str(member["supplier_id"])) for member in members if member.get("supplier_id")]
    if not ids:
        return {}
    rows = db.scalars(
        select(CrossMarketplaceSupplier).where(
            CrossMarketplaceSupplier.owner_id == owner.id, CrossMarketplaceSupplier.id.in_(ids)
        )
    )
    return {str(row.id): row for row in rows}


def _geography(
    member: dict[str, Any], supplier: CrossMarketplaceSupplier | None
) -> tuple[str, str]:
    view = supplier.view_json if supplier and isinstance(supplier.view_json, dict) else {}
    country = (
        member.get("country")
        or view.get("country")
        or view.get("country_code")
        or member.get("country_region")
    )
    region = member.get("region") or view.get("region") or member.get("country_region")
    return (
        str(country).strip().upper() if country else "UNKNOWN",
        str(region).strip().upper() if region else "UNKNOWN",
    )


def _classification(hhi: Decimal | None) -> str:
    if hhi is None:
        return MISSING
    if hhi < HHI_LOW_THRESHOLD:
        return "LOW_CONCENTRATION"
    if hhi <= HHI_MODERATE_THRESHOLD:
        return "MODERATE_CONCENTRATION"
    return "HIGH_CONCENTRATION"


def _metric_payload(row: SupplierPortfolioConcentrationMetric) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "portfolio_id": str(row.portfolio_id),
        "assessment_version_id": str(row.assessment_version_id),
        "dimension": row.dimension,
        "metric_type": row.metric_type,
        "value": _float(_decimal(row.value)),
        "classification": row.classification,
        "denominator": _float(_decimal(row.denominator)),
        "contributors": row.contributors,
        "evidence_references": row.evidence_references,
        "calculation_version": row.calculation_version,
        "threshold_version": HHI_THRESHOLD_VERSION,
        "explanation": row.explanation,
        "missing_data": row.missing_data,
        "created_at": row.created_at.isoformat(),
    }


def _metric(
    assessment: SupplierPortfolioAssessmentVersion,
    portfolio: SupplierPortfolioContext,
    dimension: str,
    metric_type: str,
    value: Decimal | None,
    classification: str,
    denominator: Decimal | None,
    contributors: list[Any],
    evidence: list[str],
    explanation: str,
) -> SupplierPortfolioConcentrationMetric:
    return SupplierPortfolioConcentrationMetric(
        owner_id=assessment.owner_id,
        portfolio_id=portfolio.id,
        assessment_version_id=assessment.id,
        dimension=dimension,
        metric_type=metric_type,
        value=value,
        classification=classification,
        denominator=denominator,
        contributors=contributors,
        evidence_references=evidence,
        calculation_version=CONCENTRATION_CALCULATION_VERSION,
        threshold_version=HHI_THRESHOLD_VERSION,
        explanation=explanation,
        missing_data=value is None,
    )


def _group_shares(
    members: list[dict[str, Any]], suppliers: dict[str, CrossMarketplaceSupplier], dimension: str
) -> tuple[dict[str, Decimal], Decimal | None, bool]:
    groups: defaultdict[str, Decimal] = defaultdict(Decimal)
    total = Decimal("0")
    incomplete = not bool(members)
    for member in members:
        allocation = _decimal(member.get("allocation_percent"))
        if allocation is None:
            incomplete = True
            continue
        total += allocation
        if dimension == "supplier":
            key = str(member.get("supplier_id"))
        else:
            geography = _geography(member, suppliers.get(str(member.get("supplier_id"))))
            key = geography[0 if dimension == "country" else 1]
            incomplete = incomplete or key == "UNKNOWN"
        groups[key] += allocation
    return dict(groups), total if total else None, not incomplete and total == Decimal("100")


def _product_coverage(members: list[dict[str, Any]]) -> dict[str, int]:
    values: defaultdict[str, set[str]] = defaultdict(set)
    for member in members:
        allocation = _decimal(member.get("allocation_percent"))
        if allocation is None or allocation <= 0:
            continue
        for product in member.get("associated_products") or []:
            values[str(product)].add(str(member.get("supplier_id")))
    return {key: len(values[key]) for key in sorted(values)}


def calculate_concentration(
    db: Session,
    owner: User,
    portfolio: SupplierPortfolioContext,
    assessment_version_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    assessment = _assessment(db, owner, portfolio, assessment_version_id)
    existing: list[SupplierPortfolioConcentrationMetric] = list(
        db.scalars(
            select(SupplierPortfolioConcentrationMetric).where(
                SupplierPortfolioConcentrationMetric.owner_id == owner.id,
                SupplierPortfolioConcentrationMetric.portfolio_id == portfolio.id,
                SupplierPortfolioConcentrationMetric.assessment_version_id == assessment.id,
            )
        )
    )
    if not existing:
        members = _dedupe_members(_members(assessment))
        suppliers = _supplier_map(db, owner, members)
        rows: list[SupplierPortfolioConcentrationMetric] = []
        for dimension in ("supplier", "country", "region"):
            shares, denominator, complete = _group_shares(members, suppliers, dimension)
            if not complete:
                rows.extend(
                    (
                        _metric(
                            assessment,
                            portfolio,
                            dimension,
                            f"largest_{dimension}_share",
                            None,
                            MISSING,
                            None,
                            [],
                            [],
                            "Allocation or geography evidence is incomplete; concentration is not asserted.",
                        ),
                        _metric(
                            assessment,
                            portfolio,
                            dimension,
                            f"{dimension}_allocation_hhi",
                            None,
                            MISSING,
                            None,
                            [],
                            [],
                            "Allocation or geography evidence is incomplete; concentration is not asserted.",
                        ),
                    )
                )
                if dimension == "supplier":
                    rows.append(
                        _metric(
                            assessment,
                            portfolio,
                            dimension,
                            "top_3_supplier_share",
                            None,
                            MISSING,
                            None,
                            [],
                            [],
                            "Allocation evidence is incomplete; top-three concentration is not asserted.",
                        )
                    )
                continue
            ordered_shares = sorted(shares.items(), key=lambda item: (-item[1], item[0]))
            fractions = [share / denominator for share in shares.values()] if denominator else []
            hhi = sum((share * share for share in fractions), Decimal("0"))
            contributors = (
                [
                    {"supplier_id": key, "share_percent": float(value)}
                    for key, value in ordered_shares
                ]
                if dimension == "supplier"
                else [{"key": key, "share_percent": float(value)} for key, value in ordered_shares]
            )
            rows.append(
                _metric(
                    assessment,
                    portfolio,
                    dimension,
                    f"largest_{dimension}_share",
                    ordered_shares[0][1],
                    "OBSERVED",
                    denominator,
                    contributors,
                    ["portfolio_membership.allocation_percent"],
                    "Largest exposure is calculated from the immutable assessment membership snapshot.",
                )
            )
            rows.append(
                _metric(
                    assessment,
                    portfolio,
                    dimension,
                    f"{dimension}_allocation_hhi",
                    hhi,
                    _classification(hhi),
                    denominator,
                    contributors,
                    ["portfolio_membership.allocation_percent"],
                    "HHI is the sum of squared allocation fractions.",
                )
            )
            if dimension == "supplier":
                rows.append(
                    _metric(
                        assessment,
                        portfolio,
                        dimension,
                        "top_3_supplier_share",
                        sum((item[1] for item in ordered_shares[:3]), Decimal("0")),
                        "OBSERVED",
                        denominator,
                        contributors[:3],
                        ["portfolio_membership.allocation_percent"],
                        "Top-three supplier share is the sum of the three largest allocations.",
                    )
                )
        coverage = _product_coverage(members)
        if coverage:
            total = Decimal(len(coverage))
            counts = {
                "single_source_percentage": sum(value == 1 for value in coverage.values()),
                "dual_source_percentage": sum(value == 2 for value in coverage.values()),
                "multi_source_percentage": sum(value >= 3 for value in coverage.values()),
            }
            contributors = [
                {"product_id": key, "supplier_count": value} for key, value in coverage.items()
            ]
            for metric_type, count in counts.items():
                rows.append(
                    _metric(
                        assessment,
                        portfolio,
                        "product",
                        metric_type,
                        Decimal(count) / total * Decimal("100"),
                        "OBSERVED",
                        total,
                        contributors,
                        ["portfolio_membership.associated_products"],
                        "Product source coverage is calculated from positive-allocation suppliers in the immutable membership snapshot.",
                    )
                )
        else:
            rows.extend(
                _metric(
                    assessment,
                    portfolio,
                    "product",
                    key,
                    None,
                    MISSING,
                    None,
                    [],
                    [],
                    "No product associations with known positive allocation are available.",
                )
                for key in (
                    "single_source_percentage",
                    "dual_source_percentage",
                    "multi_source_percentage",
                )
            )
        alternates = [
            member
            for member in members
            if _decimal(member.get("allocation_percent")) == Decimal("0")
        ]
        rows.append(
            _metric(
                assessment,
                portfolio,
                "alternate_source",
                "alternate_supplier_count",
                Decimal(len(alternates)) if members else None,
                "OBSERVED" if members else MISSING,
                Decimal(len(members)) if members else None,
                [{"supplier_id": str(member.get("supplier_id"))} for member in alternates],
                ["portfolio_membership.allocation_percent"],
                "Alternate-source count includes members with an explicit zero allocation.",
            )
        )
        try:
            db.add_all(rows)
            db.commit()
        except IntegrityError:
            db.rollback()
            rows = list(
                db.scalars(
                    select(SupplierPortfolioConcentrationMetric).where(
                        SupplierPortfolioConcentrationMetric.owner_id == owner.id,
                        SupplierPortfolioConcentrationMetric.portfolio_id == portfolio.id,
                        SupplierPortfolioConcentrationMetric.assessment_version_id == assessment.id,
                    )
                )
            )
        existing = rows
    ordered = list(existing)
    ordered.sort(key=lambda row: f"{row.dimension}:{row.metric_type}")
    return {
        "assessment_version_id": str(assessment.id),
        "results": [_metric_payload(row) for row in ordered],
    }


def _severity(allocation: Decimal | None) -> str:
    if allocation is not None and allocation >= Decimal("50"):
        return "CRITICAL"
    if allocation is not None and allocation >= Decimal("25"):
        return "HIGH"
    return "MEDIUM"


def _finding_payload(row: SupplierPortfolioDependencyFinding) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "portfolio_id": str(row.portfolio_id),
        "assessment_version_id": str(row.assessment_version_id),
        "dependency_type": row.dependency_type,
        "affected_supplier_id": str(row.affected_supplier_id) if row.affected_supplier_id else None,
        "affected_product_id": str(row.affected_product_id) if row.affected_product_id else None,
        "affected_capability": row.affected_capability,
        "severity": row.severity,
        "confidence": _float(_decimal(row.confidence)),
        "supporting_evidence": row.supporting_evidence,
        "explanation": row.explanation,
        "missing_evidence": row.missing_evidence,
        "calculation_version": row.calculation_version,
        "detected_at": row.detected_at.isoformat(),
    }


def _add_finding(
    rows: list[SupplierPortfolioDependencyFinding],
    assessment: SupplierPortfolioAssessmentVersion,
    portfolio: SupplierPortfolioContext,
    dependency_type: str,
    member: dict[str, Any],
    *,
    product_id: str | None = None,
    capability: str | None = None,
) -> None:
    rows.append(
        SupplierPortfolioDependencyFinding(
            owner_id=assessment.owner_id,
            portfolio_id=portfolio.id,
            assessment_version_id=assessment.id,
            dependency_type=dependency_type,
            affected_supplier_id=(
                uuid.UUID(str(member["supplier_id"])) if member.get("supplier_id") else None
            ),
            affected_product_id=uuid.UUID(product_id) if product_id else None,
            affected_capability=capability,
            severity=_severity(_decimal(member.get("allocation_percent"))),
            confidence=100,
            supporting_evidence=["immutable_assessment.memberships"],
            explanation=f"{dependency_type.replace('_', ' ').title()} is supported by the immutable assessment snapshot.",
            missing_evidence=[],
            calculation_version=DEPENDENCY_CALCULATION_VERSION,
        )
    )


def calculate_dependencies(
    db: Session,
    owner: User,
    portfolio: SupplierPortfolioContext,
    assessment_version_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    assessment = _assessment(db, owner, portfolio, assessment_version_id)
    existing = list(
        db.scalars(
            select(SupplierPortfolioDependencyFinding).where(
                SupplierPortfolioDependencyFinding.owner_id == owner.id,
                SupplierPortfolioDependencyFinding.portfolio_id == portfolio.id,
                SupplierPortfolioDependencyFinding.assessment_version_id == assessment.id,
            )
        )
    )
    if not existing:
        members = _dedupe_members(_members(assessment))
        allocated = [
            member
            for member in members
            if (_decimal(member.get("allocation_percent")) or Decimal("0")) > 0
        ]
        rows: list[SupplierPortfolioDependencyFinding] = []
        products: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        capabilities: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for member in allocated:
            for product in member.get("associated_products") or []:
                products[str(product)].append(member)
            for capability in member.get("capabilities") or []:
                capabilities[str(capability).strip().upper()].append(member)
        for product, group in sorted(products.items()):
            if len({str(item.get("supplier_id")) for item in group}) == 1:
                _add_finding(
                    rows,
                    assessment,
                    portfolio,
                    "ONLY_SUPPLIER_FOR_PRODUCT",
                    group[0],
                    product_id=product,
                )
        for capability, group in sorted(capabilities.items()):
            if len({str(item.get("supplier_id")) for item in group}) == 1:
                _add_finding(
                    rows,
                    assessment,
                    portfolio,
                    "ONLY_SUPPLIER_FOR_CRITICAL_CAPABILITY",
                    group[0],
                    capability=capability,
                )
        suppliers = _supplier_map(db, owner, allocated)
        for dimension, dependency_type in (
            ("country", "ONLY_COUNTRY_SOURCE"),
            ("region", "ONLY_REGION_SOURCE"),
        ):
            groups = {
                _geography(member, suppliers.get(str(member.get("supplier_id"))))[
                    0 if dimension == "country" else 1
                ]
                for member in allocated
            }
            if len(groups) == 1 and "UNKNOWN" not in groups and allocated:
                _add_finding(rows, assessment, portfolio, dependency_type, allocated[0])
        for dependency_type, accepted in (
            ("ONLY_QUALIFIED_SUPPLIER", {"qualified", "eligible"}),
            ("ONLY_VERIFIED_SUPPLIER", {"verified"}),
            ("ONLY_LOW_RISK_SUPPLIER", {"low", "low_risk"}),
            ("ONLY_CURRENTLY_AVAILABLE_SOURCE", {"available", "ready"}),
        ):
            matching = [
                member
                for member in allocated
                if str(member.get("alternate_source_status", "")).strip().lower() in accepted
                or str(member.get("status", "")).strip().lower() in accepted
                or (
                    dependency_type == "ONLY_LOW_RISK_SUPPLIER"
                    and str(member.get("risk", "")).strip().lower() in accepted
                )
            ]
            if (
                matching
                and len({str(item.get("supplier_id")) for item in matching}) == 1
                and len(matching) < len(allocated)
            ):
                _add_finding(rows, assessment, portfolio, dependency_type, matching[0])
        if rows:
            try:
                db.add_all(rows)
                db.commit()
            except IntegrityError:
                db.rollback()
                rows = list(
                    db.scalars(
                        select(SupplierPortfolioDependencyFinding).where(
                            SupplierPortfolioDependencyFinding.owner_id == owner.id,
                            SupplierPortfolioDependencyFinding.portfolio_id == portfolio.id,
                            SupplierPortfolioDependencyFinding.assessment_version_id
                            == assessment.id,
                        )
                    )
                )
        existing = rows
    ordered = sorted(
        existing,
        key=lambda row: (
            row.dependency_type,
            str(row.affected_supplier_id or ""),
            str(row.affected_product_id or ""),
            row.affected_capability or "",
        ),
    )
    return {
        "assessment_version_id": str(assessment.id),
        "results": [_finding_payload(row) for row in ordered],
    }


def _readiness_payload(row: SupplierPortfolioAlternateReadiness) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "portfolio_id": str(row.portfolio_id),
        "assessment_version_id": str(row.assessment_version_id),
        "supplier_id": str(row.supplier_id),
        "product_id": str(row.product_id) if row.product_id else None,
        "readiness_state": row.readiness_state,
        "reasons": row.reasons,
        "satisfied_requirements": row.satisfied_requirements,
        "unmet_requirements": row.unmet_requirements,
        "missing_evidence": row.missing_evidence,
        "stale_evidence": row.stale_evidence,
        "contradictions": row.contradictions,
        "dd_gaps": row.dd_gaps,
        "commercial_gaps": row.commercial_gaps,
        "capability_gaps": row.capability_gaps,
        "confidence": _float(_decimal(row.confidence)),
        "next_evidence_action": row.next_evidence_action,
        "calculation_version": row.calculation_version,
        "created_at": row.created_at.isoformat(),
    }


def _readiness(member: dict[str, Any]) -> tuple[str, dict[str, list[str]]]:
    status = str(member.get("alternate_source_status", "")).strip().lower()
    freshness = str(member.get("evidence_freshness", "")).strip().lower()
    risk = str(member.get("risk", "")).strip().lower()
    details: dict[str, list[str]] = {
        "reasons": [],
        "satisfied": [],
        "unmet": [],
        "missing": [],
        "stale": [],
        "contradictions": [],
        "dd": [],
        "commercial": [],
        "capability": [],
    }
    if status in {"blocked", "suspended"}:
        return "BLOCKED", {
            **details,
            "reasons": ["Supplier membership is explicitly blocked."],
            "unmet": ["active supplier status"],
        }
    if status in {"not_ready", "rejected"}:
        return "NOT_READY", {
            **details,
            "reasons": ["Supplier membership is explicitly not ready."],
            "unmet": ["readiness requirement"],
        }
    if status in {"qualified", "eligible", "verified", "ready"}:
        details["satisfied"].append("supplier eligibility")
    else:
        details["unmet"].append("supplier eligibility")
    if member.get("capabilities"):
        details["satisfied"].append("declared capability")
    else:
        details["capability"].append("capability evidence")
    if member.get("due_diligence_lineage_id") is None and status in {
        "shortlisted",
        "candidate",
        "eligible",
        "qualified",
        "ready",
        "verified",
    }:
        details["dd"].append("due_diligence_assessment")
    if details["dd"]:
        return "DUE_DILIGENCE_REQUIRED", {
            **details,
            "reasons": ["Supplier is plausible but due diligence coverage is incomplete."],
        }
    if status == "commercial_validation_required":
        return "COMMERCIAL_VALIDATION_REQUIRED", {
            **details,
            "commercial": ["current commercial evidence"],
            "reasons": ["Commercial constraints require validation."],
        }
    if freshness in {"stale", "expired"}:
        details["stale"].append("supplier evidence")
    elif freshness in {"unknown", "missing", ""}:
        details["missing"].append("supplier evidence freshness")
    if risk in {"high", "critical"}:
        details["contradictions"].append("high supplier risk blocks a ready classification.")
    if details["missing"] or details["stale"]:
        return "RESEARCH_REQUIRED", {
            **details,
            "reasons": ["Evidence freshness is insufficient for an unconditional readiness claim."],
        }
    if (
        status in {"qualified", "eligible", "verified", "ready"}
        and not details["contradictions"]
        and not details["capability"]
    ):
        return "READY", {
            **details,
            "reasons": [
                "Eligibility, due diligence, capability, and fresh evidence requirements are satisfied."
            ],
        }
    if status:
        return "CONDITIONALLY_READY", {
            **details,
            "reasons": ["Most known requirements are satisfied but bounded gaps remain."],
        }
    return "UNKNOWN", {
        **details,
        "reasons": ["Evidence is too weak to classify this supplier safely."],
    }


def calculate_readiness(
    db: Session,
    owner: User,
    portfolio: SupplierPortfolioContext,
    assessment_version_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    assessment = _assessment(db, owner, portfolio, assessment_version_id)
    existing = list(
        db.scalars(
            select(SupplierPortfolioAlternateReadiness).where(
                SupplierPortfolioAlternateReadiness.owner_id == owner.id,
                SupplierPortfolioAlternateReadiness.portfolio_id == portfolio.id,
                SupplierPortfolioAlternateReadiness.assessment_version_id == assessment.id,
            )
        )
    )
    if not existing:
        rows: list[SupplierPortfolioAlternateReadiness] = []
        for member in _dedupe_members(_members(assessment)):
            state, details = _readiness(member)
            products: list[str | None] = [
                str(product) for product in (member.get("associated_products") or [])
            ] or [None]
            for product_id in products:
                rows.append(
                    SupplierPortfolioAlternateReadiness(
                        owner_id=assessment.owner_id,
                        portfolio_id=portfolio.id,
                        assessment_version_id=assessment.id,
                        supplier_id=uuid.UUID(str(member["supplier_id"])),
                        product_id=uuid.UUID(product_id) if product_id else None,
                        readiness_state=state,
                        reasons=details["reasons"],
                        satisfied_requirements=details["satisfied"],
                        unmet_requirements=details["unmet"],
                        missing_evidence=details["missing"],
                        stale_evidence=details["stale"],
                        contradictions=details["contradictions"],
                        dd_gaps=details["dd"],
                        commercial_gaps=details["commercial"],
                        capability_gaps=details["capability"],
                        confidence=_decimal(member.get("confidence")),
                        next_evidence_action={
                            "READY": "Continue periodic evidence refresh.",
                            "DUE_DILIGENCE_REQUIRED": "Complete due diligence assessment.",
                            "RESEARCH_REQUIRED": "Request fresh supplier evidence.",
                            "COMMERCIAL_VALIDATION_REQUIRED": "Validate MOQ, lead time, price, and availability.",
                            "BLOCKED": "Resolve the blocking supplier condition.",
                            "NOT_READY": "Do not use as an alternate until requirements are met.",
                        }.get(state, "Collect the missing evidence before making a decision."),
                        calculation_version=READINESS_CALCULATION_VERSION,
                    )
                )
        if rows:
            try:
                db.add_all(rows)
                db.commit()
            except IntegrityError:
                db.rollback()
                rows = list(
                    db.scalars(
                        select(SupplierPortfolioAlternateReadiness).where(
                            SupplierPortfolioAlternateReadiness.owner_id == owner.id,
                            SupplierPortfolioAlternateReadiness.portfolio_id == portfolio.id,
                            SupplierPortfolioAlternateReadiness.assessment_version_id
                            == assessment.id,
                        )
                    )
                )
        existing = rows
    ordered = sorted(existing, key=lambda row: (str(row.supplier_id), str(row.product_id or "")))
    return {
        "assessment_version_id": str(assessment.id),
        "results": [_readiness_payload(row) for row in ordered],
    }
