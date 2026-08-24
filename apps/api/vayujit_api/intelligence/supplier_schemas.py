from __future__ import annotations

import ipaddress
import uuid
from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vayujit_api.intelligence.supplier_models import SUPPLIER_SOURCE_TYPES, SUPPLIER_TYPES


class SupplierModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


def _default_source_policy() -> dict[str, object]:
    return {"mode": "local_fixture"}


class SupplierSearchCreate(BaseModel):
    opportunity_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    requirements: dict[str, object] = Field(default_factory=dict)
    source_policy: dict[str, object] = Field(default_factory=_default_source_policy)
    ruleset_version: str = Field(default="supplier-default-v1", max_length=80)
    idempotency_key: str | None = Field(default=None, max_length=180)

    @field_validator("requirements")
    @classmethod
    def bounded_requirements(cls, value: dict[str, object]) -> dict[str, object]:
        if len(value) > 40:
            raise ValueError("Supplier requirements are too large.")
        return value


class SupplierSearchResponse(SupplierModel):
    id: uuid.UUID
    opportunity_id: uuid.UUID | None
    product_id: uuid.UUID | None
    requirements: dict[str, object]
    source_policy: dict[str, object]
    ruleset_version: str
    correlation_id: str
    status: str
    idempotency_key: str
    summary_json: dict[str, object]
    failure_classification: str | None
    provider_execution_id: str | None
    lease_expires_at: datetime | None
    checkpoint_state: dict[str, object]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SupplierResponse(SupplierModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    display_name: str
    legal_name: str | None
    supplier_type: str
    country_code: str | None
    country: str | None
    region: str | None
    city: str | None
    address: str | None
    website: str | None
    normalized_domain: str | None
    business_identifier: str | None
    source_identity: str
    normalized_identity: str
    is_offline: bool
    verification_state: str
    communication_status: str
    created_at: datetime
    updated_at: datetime
    score: float | None = None
    recommendation: str | None = None
    risk: dict[str, object] = Field(default_factory=dict)
    offering_count: int = 0
    evidence_count: int = 0
    shortlist_state: str | None = None
    comparison_status: str | None = None


class SupplierManualCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=200)
    legal_name: str | None = Field(default=None, max_length=240)
    supplier_type: str = "unknown"
    country_code: str = Field(min_length=2, max_length=2)
    country: str = Field(min_length=2, max_length=100)
    region: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=2000)
    website: str | None = Field(default=None, max_length=500)
    source_type: str = "manual_entry"
    provenance: str = Field(min_length=2, max_length=500)
    notes: str = Field(default="", max_length=5000)

    @field_validator("supplier_type")
    @classmethod
    def valid_type(cls, value: str) -> str:
        if value not in SUPPLIER_TYPES:
            raise ValueError("Unsupported supplier type.")
        return value

    @field_validator("source_type")
    @classmethod
    def valid_source(cls, value: str) -> str:
        if value not in SUPPLIER_SOURCE_TYPES:
            raise ValueError("Unsupported supplier source type.")
        return value

    @field_validator("country_code")
    @classmethod
    def valid_country_code(cls, value: str) -> str:
        normalized = value.upper()
        if not normalized.isalpha():
            raise ValueError("Country code must contain letters only.")
        return normalized

    @field_validator("website")
    @classmethod
    def safe_website(cls, value: str | None) -> str | None:
        if not value:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
            raise ValueError("Supplier website must be a public HTTP(S) URL without credentials.")
        host = (parsed.hostname or "").lower()
        if host in {"localhost", "localhost.localdomain"}:
            raise ValueError("Private supplier website hosts are not allowed.")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and (
            address.is_private or address.is_loopback or address.is_link_local
        ):
            raise ValueError("Private supplier website hosts are not allowed.")
        return value


class SupplierDecisionRequest(BaseModel):
    decision: Literal["shortlist", "reject", "review", "approve_for_rfq"]
    reason: str = Field(default="", max_length=2000)
    idempotency_key: str | None = Field(default=None, max_length=180)


class SupplierVerificationRequest(BaseModel):
    state: Literal[
        "unverified",
        "self_reported",
        "partially_verified",
        "verified",
        "high_confidence",
        "suspended",
        "blocked",
    ]
    reason: str = Field(default="", max_length=2000)
    evidence_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)


class SupplierComparisonRequest(BaseModel):
    supplier_ids: list[uuid.UUID] = Field(min_length=2, max_length=5)


class SupplierReportResponse(BaseModel):
    supplier: SupplierResponse
    report_version: str
    generated_at: datetime
    sections: dict[str, object]


class SupplierOverviewResponse(BaseModel):
    supplier_count: int
    verified_count: int
    unverified_count: int
    shortlisted_count: int
    high_risk_count: int
    stale_count: int
    recent_searches: int
    recent_failures: int
    provider_mode: str = "local_fixture"
    external_connectors: dict[str, str] = Field(default_factory=dict)


class SupplierSourceRegistryResponse(BaseModel):
    source_type: str
    access_modes: list[str]
    status: str
    notes: str


class SupplierDetailResponse(SupplierResponse):
    sources: list[dict[str, object]] = Field(default_factory=list)
    contacts: list[dict[str, object]] = Field(default_factory=list)
    offerings: list[dict[str, object]] = Field(default_factory=list)
    capabilities: list[dict[str, object]] = Field(default_factory=list)
    commercial_terms: list[dict[str, object]] = Field(default_factory=list)
    verifications: list[dict[str, object]] = Field(default_factory=list)
    certifications: list[dict[str, object]] = Field(default_factory=list)
    risk_assessments: list[dict[str, object]] = Field(default_factory=list)
    score_evaluations: list[dict[str, object]] = Field(default_factory=list)
    matches: list[dict[str, object]] = Field(default_factory=list)
    decisions: list[dict[str, object]] = Field(default_factory=list)
    evidence: list[dict[str, object]] = Field(default_factory=list)
    documents: list[dict[str, object]] = Field(default_factory=list)
    history: list[dict[str, object]] = Field(default_factory=list)


class SupplierRuleResponse(BaseModel):
    key: str
    label: str
    action: str
    hard_block: bool
    description: str


class SupplierCommercialTermCreate(BaseModel):
    supplier_product_id: uuid.UUID
    version: int = Field(ge=1)
    unit_price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    price_tiers: list[dict[str, object]] = Field(default_factory=list, max_length=50)
    moq: float | None = Field(default=None, ge=0)
    sample_price: float | None = Field(default=None, ge=0)
    tooling_fee: float | None = Field(default=None, ge=0)
    packaging_fee: float | None = Field(default=None, ge=0)
    branding_fee: float | None = Field(default=None, ge=0)
    payment_terms: str | None = Field(default=None, max_length=160)
    deposit_percent: float | None = Field(default=None, ge=0, le=100)
    balance_percent: float | None = Field(default=None, ge=0, le=100)
    incoterm: str | None = Field(default=None, max_length=20)
    valid_until: datetime | None = None
    lead_time_days: int | None = Field(default=None, ge=0)
    sample_lead_days: int | None = Field(default=None, ge=0)
    production_lead_days: int | None = Field(default=None, ge=0)
    dispatch_lead_days: int | None = Field(default=None, ge=0)
    source_evidence_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    idempotency_key: str | None = Field(default=None, max_length=180)

    @field_validator("currency")
    @classmethod
    def valid_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.upper()
        if normalized not in {"INR", "USD", "CNY", "EUR", "GBP", "AED", "JPY"}:
            raise ValueError("Unsupported currency code.")
        return normalized

    @model_validator(mode="after")
    def valid_payment_split(self) -> SupplierCommercialTermCreate:
        if (self.deposit_percent or 0) + (self.balance_percent or 0) > 100:
            raise ValueError("Deposit and balance percentages cannot exceed 100.")
        return self


class SupplierContactCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    role: str | None = Field(default=None, max_length=120)
    business_email: str | None = Field(default=None, max_length=240)
    business_phone: str | None = Field(default=None, max_length=80)
    whatsapp: str | None = Field(default=None, max_length=80)
    preferred_method: Literal["email", "phone", "whatsapp", "other"] | None = None
    source: str = Field(min_length=2, max_length=500)
    verification: Literal["unverified", "self_reported", "verified"] = "unverified"
    communication_status: Literal[
        "not_contacted",
        "contact_drafted",
        "contact_approved",
        "contacted_manually",
        "responded",
        "no_response",
    ] = "not_contacted"


class SupplierContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    role: str | None = Field(default=None, max_length=120)
    business_email: str | None = Field(default=None, max_length=240)
    business_phone: str | None = Field(default=None, max_length=80)
    whatsapp: str | None = Field(default=None, max_length=80)
    preferred_method: Literal["email", "phone", "whatsapp", "other"] | None = None
    verification: Literal["unverified", "self_reported", "verified"] | None = None
    communication_status: (
        Literal[
            "not_contacted",
            "contact_drafted",
            "contact_approved",
            "contacted_manually",
            "responded",
            "no_response",
        ]
        | None
    ) = None
    archived: bool | None = None


class SupplierDocumentReferenceCreate(BaseModel):
    reference_id: str = Field(min_length=1, max_length=180)
    document_type: Literal[
        "catalog",
        "certificate",
        "quotation",
        "business_registration",
        "inspection_report",
        "sample_evidence",
    ]
    display_name: str = Field(min_length=1, max_length=240)
    mime_type: str | None = Field(default=None, max_length=120)
    size_bytes: int | None = Field(default=None, ge=0, le=50_000_000)
    content_hash: str | None = Field(default=None, max_length=128)
    source_reference: str = Field(min_length=2, max_length=500)
    verification_state: Literal["unverified", "self_reported", "verified"] = "unverified"
    observed_at: datetime | None = None


class SupplierCertificationClaimCreate(BaseModel):
    claim: str = Field(min_length=2, max_length=120)
    source_reference: str = Field(min_length=2, max_length=500)
    document_reference: str | None = Field(default=None, max_length=500)
    observed_at: datetime | None = None
    expires_at: datetime | None = None
    verification_state: Literal["unverified", "self_reported", "verified"] = "unverified"
    evidence_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    version: int | None = Field(default=None, ge=1)


class SupplierScoreCreate(BaseModel):
    model_version: str = Field(min_length=1, max_length=80)
    weights: dict[str, float]
    inputs: dict[str, object] = Field(default_factory=dict)
    dimensions: dict[str, dict[str, object]]
    final_score: float = Field(ge=0, le=100)
    recommendation: str = Field(min_length=1, max_length=32)
    evidence_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)


class SupplierRecoveryRequest(BaseModel):
    action: Literal[
        "retry",
        "reconcile",
        "review_source",
        "review_supplier",
        "refresh_evidence",
        "review_verification",
        "review_rules",
        "cancel",
    ]
    idempotency_key: str = Field(min_length=2, max_length=180)
    reason: str = Field(default="", max_length=2000)


class SupplierFreshnessResponse(BaseModel):
    price: str
    moq: str
    lead_time: str
    contact: str
    certification: str
    verification: str
    capability: str
    offering: str


class SupplierSourceDiversityResponse(BaseModel):
    independent_source_count: int
    supplier_profile_source_count: int
    commercial_source_count: int
    verification_source_count: int
    source_diversity_score: float
    missing_source_types: list[str]


class SupplierHistoryResponse(BaseModel):
    events: list[dict[str, object]]


class SupplierRiskMatrixResponse(BaseModel):
    dimensions: list[dict[str, object]]
    warnings: list[str]


class SupplierStorageInventoryResponse(BaseModel):
    tables: list[dict[str, object]]


class SupplierRecoveryResponse(BaseModel):
    id: uuid.UUID
    search_id: uuid.UUID
    action: str
    status: str
    idempotent_reuse: bool = False
    reason_code: str | None = None
    correlation_id: str
