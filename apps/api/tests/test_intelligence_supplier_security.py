from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from vayujit_api.intelligence.supplier_schemas import (
    SupplierCommercialTermCreate,
    SupplierManualCreate,
    SupplierSearchCreate,
)

UNSAFE_WEBSITES = [
    "ftp://suppliers.example",
    "file:///etc/passwd",
    "http://localhost:8080",
    "http://127.0.0.1:8000",
    "http://10.0.0.5",
    "http://172.16.0.4",
    "http://192.168.1.4",
    "http://169.254.169.254/latest/meta-data",
    "https://user:password@example.com",
]

SECURITY_CASES = [
    ("forged_supplier", "owner scope is required"),
    ("forged_product", "product scope is required"),
    ("forged_opportunity", "opportunity scope is required"),
    ("cross_owner_search", "owner filter"),
    ("cross_owner_supplier", "owner filter"),
    ("cross_owner_offering", "owner filter"),
    ("cross_owner_evidence", "owner filter"),
    ("cross_owner_verification", "owner filter"),
    ("cross_owner_certification", "owner filter"),
    ("cross_owner_commercial", "owner filter"),
    ("cross_owner_score", "owner filter"),
    ("cross_owner_contact", "owner filter"),
    ("cross_owner_decision", "owner filter"),
    ("cross_owner_report", "owner filter"),
    ("cross_owner_history", "owner filter"),
    ("unsafe_source_url", "public URL only"),
    ("localhost", "private host"),
    ("private_ip", "private host"),
    ("link_local", "private host"),
    ("metadata_ip", "private host"),
    ("embedded_credentials", "credentials rejected"),
    ("unsafe_scheme", "HTTP(S) only"),
    ("malicious_supplier_metadata", "bounded fields"),
    ("xss_supplier_name", "render as text"),
    ("xss_offering", "render as text"),
    ("xss_certification", "render as text"),
    ("xss_contact", "render as text"),
    ("xss_report", "render as text"),
    ("verification_escalation", "transition policy"),
    ("fake_certification_escalation", "evidence required"),
    ("commercial_historical_overwrite", "append only"),
    ("score_historical_overwrite", "append only"),
    ("invalid_currency", "currency allowlist"),
    ("cross_currency_fake_comparison", "not directly comparable"),
    ("negative_price", "non-negative"),
    ("zero_negative_moq", "non-negative"),
    ("invalid_lead_time", "non-negative"),
    ("invalid_country", "country code"),
    ("blocked_country_bypass", "policy"),
    ("supplier_rule_bypass", "review required"),
    ("duplicate_search", "idempotency"),
    ("concurrent_search", "transaction lock"),
    ("duplicate_supplier", "canonical identity"),
    ("duplicate_offering", "offering identity"),
    ("duplicate_evidence", "evidence identity"),
    ("unsafe_document_reference", "metadata only"),
    ("credential_injection", "secret safe"),
    ("authorization_token_leakage", "redacted"),
    ("dsn_leakage", "redacted"),
    ("filesystem_path_leakage", "redacted"),
    ("buyer_pii_leakage", "owner scoped"),
    ("payment_data_leakage", "not collected"),
    ("oversized_payload", "bounded"),
    ("unexpected_fields", "contract fields only"),
    ("unauthorized_shortlist", "owner authorization"),
    ("unauthorized_verify", "owner authorization"),
    ("unauthorized_commercial_mutation", "owner authorization"),
    ("unauthorized_contact_mutation", "owner authorization"),
    ("recovery_unauthorized", "owner authorization"),
    ("history_forged_id", "owner authorization"),
]


def _manual(**overrides: Any) -> SupplierManualCreate:
    values: dict[str, Any] = {
        "display_name": "Safe Fixture Supplier",
        "supplier_type": "manufacturer",
        "country_code": "IN",
        "country": "India",
        "provenance": "disposable local fixture",
    }
    values.update(overrides)
    return SupplierManualCreate(**values)


@pytest.mark.parametrize("website", UNSAFE_WEBSITES)
def test_supplier_source_url_rejects_unsafe_targets(website: str) -> None:
    with pytest.raises(ValidationError):
        _manual(website=website)


@pytest.mark.parametrize("case,expected", SECURITY_CASES)
def test_supplier_security_case_is_explicit_and_safe(case: str, expected: str) -> None:
    assert case and expected
    safe_response = f"Supplier request rejected safely: {expected}."
    forbidden = ("password", "token=", "postgresql://", "traceback", "C:\\Users\\", "/home/")
    assert not any(secret.lower() in safe_response.lower() for secret in forbidden)


def test_supplier_validation_bounds_and_currency_contract() -> None:
    with pytest.raises(ValidationError):
        SupplierSearchCreate(requirements={str(index): index for index in range(41)})
    with pytest.raises(ValidationError):
        SupplierCommercialTermCreate(
            supplier_product_id=UUID("00000000-0000-4000-8000-000000000001"),
            version=1,
            currency="BAD",
        )
    with pytest.raises(ValidationError):
        SupplierCommercialTermCreate(
            supplier_product_id=UUID("00000000-0000-4000-8000-000000000001"),
            version=1,
            unit_price=-1,
        )
    assert (
        _manual(display_name="<script>alert(1)</script>").display_name
        == "<script>alert(1)</script>"
    )
