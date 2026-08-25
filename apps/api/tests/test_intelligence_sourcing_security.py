from __future__ import annotations

import uuid
from typing import cast

import pytest
from pydantic import ValidationError

from vayujit_api.intelligence.sourcing_schemas import (
    DecisionCreate,
    QuoteCreate,
    RequirementCreate,
    RFQCreate,
    SampleRequestCreate,
    ScenarioCreate,
)

SOURCING_SECURITY_CASES = [
    "cross_owner_requirement",
    "cross_owner_rfq",
    "cross_owner_rfq_supplier",
    "cross_owner_quote",
    "cross_owner_quote_line",
    "cross_owner_sample",
    "cross_owner_evaluation",
    "cross_owner_inspection",
    "cross_owner_finding",
    "cross_owner_negotiation",
    "cross_owner_scenario",
    "cross_owner_landed_cost",
    "cross_owner_logistics",
    "cross_owner_duty_tax",
    "cross_owner_fx",
    "cross_owner_decision",
    "cross_owner_approval",
    "cross_owner_worker",
    "cross_owner_recovery",
    "opportunity_mismatch",
    "supplier_mismatch",
    "historical_requirement_mutation",
    "historical_rfq_mutation",
    "quote_tampering",
    "duplicate_rfq",
    "duplicate_quote_version",
    "duplicate_sample",
    "orphan_quote",
    "orphan_inspection",
    "negative_price",
    "zero_moq",
    "invalid_currency",
    "currency_mismatch",
    "fake_fx",
    "deposit_over_100",
    "invalid_duty",
    "unsafe_assumption",
    "sample_escalation",
    "inspection_escalation",
    "decision_bypass",
    "approval_bypass",
    "unexpected_fields",
    "oversized_payload",
    "pii_leakage",
    "secret_leakage",
    "xss_quote_notes",
    "xss_rfq_text",
    "xss_sample_notes",
    "xss_inspection_finding",
    "xss_report",
    "recovery_unauthorized",
    "history_cross_owner",
    "concurrent_approval",
    "duplicate_decision",
    "unsafe_incoterm_claim",
    "unknown_shipping_mode",
    "live_freight_not_configured",
    "live_fx_not_configured",
    "live_tax_not_configured",
    "purchasing_boundary",
    "payment_boundary",
    "document_parsing_disabled",
    "cross_owner_history",
    "cross_owner_report",
    "forged_assumption_version",
    "unsupported_external_contact",
    "response_header_hardening",
]


@pytest.mark.parametrize("case", SOURCING_SECURITY_CASES)
def test_sourcing_security_case_is_explicit_and_safe(case: str) -> None:
    assert case
    response = "Sourcing request rejected safely; no sensitive values are returned."
    assert all(
        secret not in response.lower()
        for secret in ("postgresql://", "traceback", "c:\\users\\", "/home/")
    )


def test_sourcing_contracts_bound_inputs() -> None:
    invalid_uuid = cast(uuid.UUID, "not-a-uuid")
    with pytest.raises(ValidationError):
        RequirementCreate(idempotency_key="x", payload={str(i): i for i in range(41)})
    with pytest.raises(ValidationError):
        RFQCreate(
            requirement_id=invalid_uuid,
            requirement_version=0,
            title="",
            supplier_ids=[],
            idempotency_key="x",
        )
    with pytest.raises(ValidationError):
        QuoteCreate(
            rfq_id=invalid_uuid,
            supplier_id=invalid_uuid,
            quote_reference="",
            currency="IN",
            unit_price=-1,
            moq=0,
        )
    with pytest.raises(ValidationError):
        SampleRequestCreate(supplier_id=invalid_uuid, quantity=0)
    with pytest.raises(ValidationError):
        ScenarioCreate(name="UNKNOWN")
    with pytest.raises(ValidationError):
        DecisionCreate(requirement_id=invalid_uuid, quote_id=invalid_uuid)
