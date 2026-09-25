from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from vayujit_api.intelligence.economic_models import PROVENANCE_CLASSES
from vayujit_api.intelligence.economic_schemas import EconomicSchema, safe_metadata


def _currency(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.upper()
    if len(value) != 3 or not value.isalpha():
        raise ValueError("Currency must be a three-letter ISO-style code.")
    return value


def _prov(value: str) -> str:
    value = value.upper()
    if value not in (*PROVENANCE_CLASSES, "USER_PROVIDED"):
        raise ValueError("Unsupported economic provenance.")
    return value


class CustomsTaxContextCreate(EconomicSchema):
    economic_context_id: uuid.UUID
    idempotency_key: str = Field(min_length=3, max_length=180)
    origin_country: str | None = Field(default=None, max_length=80)
    destination_country: str | None = Field(default=None, max_length=80)
    reporting_currency: str | None = None
    classification_code: str | None = Field(default=None, min_length=1, max_length=64)
    classification_scheme: str | None = Field(default=None, max_length=64)
    classification_version: str | None = Field(default=None, max_length=64)
    classification_provenance: Literal["UNKNOWN", "USER_PROVIDED", "SOURCE_OBSERVED"] = "UNKNOWN"
    evidence_ref: uuid.UUID | None = None
    status: Literal["DRAFT", "CURRENT", "ARCHIVED"] = "DRAFT"
    _currency = field_validator("reporting_currency")(_currency)


class ClassificationEvidenceCreate(EconomicSchema):
    context_id: uuid.UUID
    idempotency_key: str = Field(min_length=3, max_length=180)
    classification_code: str = Field(min_length=1, max_length=64)
    classification_scheme: str = Field(min_length=1, max_length=64)
    jurisdiction: str = Field(min_length=1, max_length=80)
    supplied_description: str | None = Field(default=None, max_length=5000)
    source: str = Field(min_length=1, max_length=120)
    provider: str | None = Field(default=None, max_length=120)
    source_reference: str | None = Field(default=None, max_length=500)
    provenance: str = "UNKNOWN"
    freshness: Literal["CURRENT", "STALE", "UNKNOWN"] = "UNKNOWN"
    effective_at: datetime | None = None
    valid_until: datetime | None = None
    notes: str = Field(default="", max_length=5000)
    metadata_json: dict[str, object] = Field(default_factory=dict)
    version: str = Field(default="classification-evidence-v1", max_length=32)
    _prov = field_validator("provenance")(_prov)

    @model_validator(mode="after")
    def validate_classification(self) -> ClassificationEvidenceCreate:
        if self.provenance == "VERIFIED":
            raise ValueError("Verification is not supported; preserve source evidence instead.")
        safe_metadata(self.metadata_json)
        return self


class CustomsRateEvidenceCreate(EconomicSchema):
    context_id: uuid.UUID
    classification_evidence_id: uuid.UUID | None = None
    idempotency_key: str = Field(min_length=3, max_length=180)
    rate_kind: Literal["DUTY", "IMPORT_TAX", "SURCHARGE", "CESS", "LEVY"]
    category: Literal["CUSTOMS_DUTY", "IMPORT_TAX", "OTHER"]
    tax_type: str | None = Field(default=None, max_length=120)
    rate: Decimal = Field(ge=0, le=1)
    rate_scale: Literal["FRACTION_OF_ONE"] = "FRACTION_OF_ONE"
    basis: Literal[
        "PRODUCT_VALUE",
        "PRODUCT_PLUS_FREIGHT",
        "EXPLICIT_CUSTOMS_VALUE",
        "EXPLICIT_TAXABLE_VALUE",
        "UNKNOWN",
    ] = "UNKNOWN"
    jurisdiction: str = Field(min_length=1, max_length=80)
    origin_country: str | None = Field(default=None, max_length=80)
    destination_country: str | None = Field(default=None, max_length=80)
    effective_at: datetime | None = None
    valid_until: datetime | None = None
    source: str = Field(min_length=1, max_length=120)
    provenance: str = "UNKNOWN"
    freshness: Literal["CURRENT", "STALE", "UNKNOWN"] = "UNKNOWN"
    evidence_ref: uuid.UUID | None = None
    assumption_reason: str | None = Field(default=None, max_length=4000)
    metadata_json: dict[str, object] = Field(default_factory=dict)
    version: str = Field(default="customs-rate-v1", max_length=32)
    _prov = field_validator("provenance")(_prov)

    @model_validator(mode="after")
    def validate_rate(self) -> CustomsRateEvidenceCreate:
        if self.provenance == "ASSUMED" and not self.assumption_reason:
            raise ValueError("An assumption reason is required for ASSUMED rates.")
        safe_metadata(self.metadata_json)
        return self


class RegulatoryCostEvidenceCreate(EconomicSchema):
    context_id: uuid.UUID
    idempotency_key: str = Field(min_length=3, max_length=180)
    cost_category: Literal["BROKERAGE", "INSPECTION", "OTHER"]
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    requirement_type: Literal[
        "BIS", "FSSAI", "WPC", "CDSCO", "LEGAL_METROLOGY", "OTHER", "UNKNOWN"
    ] = "UNKNOWN"
    requirement_state: Literal["OBSERVED_REQUIREMENT", "USER_CONFIGURED", "UNKNOWN"] = "UNKNOWN"
    source: str = Field(min_length=1, max_length=120)
    provenance: str = "UNKNOWN"
    freshness: Literal["CURRENT", "STALE", "UNKNOWN"] = "UNKNOWN"
    effective_at: datetime | None = None
    valid_until: datetime | None = None
    evidence_ref: uuid.UUID | None = None
    assumption_reason: str | None = Field(default=None, max_length=4000)
    metadata_json: dict[str, object] = Field(default_factory=dict)
    version: str = Field(default="regulatory-cost-v1", max_length=32)
    _currency = field_validator("currency")(_currency)
    _prov = field_validator("provenance")(_prov)

    @model_validator(mode="after")
    def validate_regulatory_cost(self) -> RegulatoryCostEvidenceCreate:
        if self.amount is not None and self.currency is None:
            raise ValueError("Currency is required when a regulatory cost amount is supplied.")
        if self.provenance == "ASSUMED" and not self.assumption_reason:
            raise ValueError("An assumption reason is required for ASSUMED costs.")
        safe_metadata(self.metadata_json)
        return self


class BasisInput(EconomicSchema):
    basis_type: Literal[
        "PRODUCT_VALUE",
        "PRODUCT_PLUS_FREIGHT",
        "EXPLICIT_CUSTOMS_VALUE",
        "EXPLICIT_TAXABLE_VALUE",
        "UNKNOWN",
    ]
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    freight_snapshot_id: uuid.UUID | None = None
    _currency = field_validator("currency")(_currency)

    @model_validator(mode="after")
    def validate_basis(self) -> BasisInput:
        if self.basis_type == "PRODUCT_PLUS_FREIGHT" and self.freight_snapshot_id is None:
            raise ValueError(
                "PRODUCT_PLUS_FREIGHT requires an explicit freight snapshot reference."
            )
        if self.basis_type != "UNKNOWN" and (self.amount is None or self.currency is None):
            raise ValueError(
                "An explicit amount and currency are required for a known customs basis."
            )
        return self


class CustomsTaxSnapshotCreate(EconomicSchema):
    context_id: uuid.UUID
    version: str = Field(default="customs-tax-snapshot-v1", min_length=1, max_length=32)
    basis_inputs: dict[str, BasisInput] = Field(default_factory=dict)
    classification_evidence_ids: list[uuid.UUID] | None = None
    rate_evidence_ids: list[uuid.UUID] | None = None
    regulatory_cost_evidence_ids: list[uuid.UUID] | None = None

    @model_validator(mode="after")
    def validate_snapshot(self) -> CustomsTaxSnapshotCreate:
        if len(self.basis_inputs) > 20:
            raise ValueError("Too many customs basis inputs.")
        return self
