from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vayujit_api.intelligence.economic_freight_models import VOLUME_UNITS, WEIGHT_UNITS
from vayujit_api.intelligence.economic_models import COST_COMPONENT_CATEGORIES, PROVENANCE_CLASSES


class EconomicSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", hide_input_in_errors=True)


def _currency(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValueError("Currency must be a three-letter ISO-style code.")
    return normalized


class EconomicContextCreate(EconomicSchema):
    idempotency_key: str = Field(min_length=3, max_length=180)
    product_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    scenario_id: uuid.UUID | None = None
    source_marketplace: str | None = Field(default=None, max_length=120)
    origin_country: str | None = Field(default=None, max_length=80)
    destination_country: str | None = Field(default=None, max_length=80)
    target_channel: str | None = Field(default=None, max_length=120)
    target_quantity: Decimal | None = Field(default=None, gt=0)
    quantity_unit: str | None = Field(default=None, max_length=40)
    base_currency: str | None = None

    _normalize_currency = field_validator("base_currency")(_currency)


class EconomicContextUpdate(EconomicSchema):
    product_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    scenario_id: uuid.UUID | None = None
    source_marketplace: str | None = Field(default=None, max_length=120)
    origin_country: str | None = Field(default=None, max_length=80)
    destination_country: str | None = Field(default=None, max_length=80)
    target_channel: str | None = Field(default=None, max_length=120)
    target_quantity: Decimal | None = Field(default=None, gt=0)
    quantity_unit: str | None = Field(default=None, max_length=40)
    base_currency: str | None = None
    status: str | None = Field(default=None, pattern="^(DRAFT|CURRENT|ARCHIVED)$")

    _normalize_currency = field_validator("base_currency")(_currency)


class EconomicQuoteInputCreate(EconomicSchema):
    context_id: uuid.UUID
    idempotency_key: str = Field(min_length=3, max_length=180)
    supplier_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    supplier_quote_id: uuid.UUID | None = None
    quote_reference: str | None = Field(default=None, max_length=180)
    unit_price: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    unit_basis: str | None = Field(default=None, max_length=40)
    moq: Decimal | None = Field(default=None, gt=0)
    moq_unit: str | None = Field(default=None, max_length=40)
    quoted_lead_time_days: int | None = Field(default=None, ge=0)
    incoterm: str | None = Field(default=None, max_length=8)
    quote_date: datetime | None = None
    valid_until: datetime | None = None
    provenance: str = "QUOTED"
    freshness: str = "UNKNOWN"
    evidence_ref: uuid.UUID | None = None
    assumption_reason: str | None = Field(default=None, max_length=4000)
    notes: str = Field(default="", max_length=5000)
    metadata_json: dict[str, object] = Field(default_factory=dict)

    _normalize_currency = field_validator("currency")(_currency)

    @field_validator("provenance")
    @classmethod
    def valid_provenance(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in PROVENANCE_CLASSES:
            raise ValueError("Unsupported economic provenance.")
        return normalized

    @model_validator(mode="after")
    def money_requires_currency(self) -> EconomicQuoteInputCreate:
        if self.unit_price is not None and self.currency is None:
            raise ValueError("Currency is required when a monetary value is supplied.")
        if self.provenance == "ASSUMED" and not self.assumption_reason:
            raise ValueError("An assumption reason is required for ASSUMED input.")
        return self


class EconomicCostComponentCreate(EconomicSchema):
    context_id: uuid.UUID
    quote_input_id: uuid.UUID | None = None
    category: str
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    quantity_basis: Decimal | None = Field(default=None, gt=0)
    unit_basis: str | None = Field(default=None, max_length=40)
    provenance: str = "UNKNOWN"
    freshness: str = "UNKNOWN"
    effective_at: datetime | None = None
    valid_until: datetime | None = None
    evidence_ref: uuid.UUID | None = None
    assumption_reason: str | None = Field(default=None, max_length=4000)
    notes: str = Field(default="", max_length=5000)
    metadata_json: dict[str, object] = Field(default_factory=dict)

    _normalize_currency = field_validator("currency")(_currency)

    @field_validator("category")
    @classmethod
    def valid_category(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in COST_COMPONENT_CATEGORIES:
            raise ValueError("Unsupported economic cost component category.")
        return normalized

    @field_validator("provenance")
    @classmethod
    def valid_provenance(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in PROVENANCE_CLASSES:
            raise ValueError("Unsupported economic provenance.")
        return normalized

    @model_validator(mode="after")
    def money_requires_currency(self) -> EconomicCostComponentCreate:
        if self.amount is not None and self.currency is None:
            raise ValueError("Currency is required when a monetary value is supplied.")
        if self.provenance == "ASSUMED" and not self.assumption_reason:
            raise ValueError("An assumption reason is required for ASSUMED input.")
        return self


class EconomicAssumptionCreate(EconomicSchema):
    context_id: uuid.UUID
    key: str = Field(min_length=1, max_length=80)
    value: dict[str, object] = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=4000)
    freshness: str = "UNKNOWN"


class EconomicSnapshotCreate(EconomicSchema):
    context_id: uuid.UUID


class EconomicContextResponse(EconomicSchema):
    id: uuid.UUID
    owner_id: uuid.UUID
    product_id: uuid.UUID | None
    opportunity_id: uuid.UUID | None
    supplier_id: uuid.UUID | None
    scenario_id: uuid.UUID | None
    source_marketplace: str | None
    origin_country: str | None
    destination_country: str | None
    target_channel: str | None
    target_quantity: Decimal | None
    quantity_unit: str | None
    base_currency: str | None
    status: str
    version: int
    idempotency_key: str
    created_at: datetime
    updated_at: datetime


class EconomicInputResponse(EconomicSchema):
    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    category: str | None = None
    provenance: str
    freshness: str
    amount: Decimal | None = None
    unit_price: Decimal | None = None
    currency: str | None
    unit_basis: str | None
    assumption_reason: str | None
    created_at: datetime


class EconomicSnapshotResponse(EconomicSchema):
    id: uuid.UUID
    owner_id: uuid.UUID
    context_id: uuid.UUID
    version: int
    fingerprint: str
    completeness: str
    missing_inputs: list[object]
    payload: dict[str, object]
    created_at: datetime


def safe_metadata(value: dict[str, object]) -> dict[str, object]:
    """Keep provider metadata bounded and free of obvious secret fields."""
    if len(value) > 40:
        raise ValueError("Economic metadata is too large.")
    blocked = {"token", "secret", "password", "cookie", "authorization", "api_key"}
    if any(str(key).lower() in blocked for key in value):
        raise ValueError("Sensitive metadata is not allowed.")
    return value


class EconomicCalculationRequest(EconomicSchema):
    freight_snapshot_id: uuid.UUID | None = None
    fx_snapshot_id: uuid.UUID | None = None
    calculation_version: str = Field(default="landed-cost-v1", min_length=1, max_length=64)
    policy_version: str = Field(default="known-cost-v1", min_length=1, max_length=64)
    options: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bounded_options(self) -> EconomicCalculationRequest:
        safe_metadata(self.options)
        return self


class FXObservationCreate(EconomicSchema):
    idempotency_key: str = Field(min_length=3, max_length=180)
    base_currency: str
    quote_currency: str
    rate: Decimal = Field(gt=0)
    observed_at: datetime
    provider: str = Field(min_length=1, max_length=120)
    mode: Literal["LOCAL_FIXTURE", "MANUAL"] = "LOCAL_FIXTURE"
    provenance: Literal["OBSERVED", "QUOTED", "CONFIGURED", "ASSUMED", "LOCAL_FIXTURE"] = (
        "LOCAL_FIXTURE"
    )
    freshness: Literal["CURRENT", "STALE", "UNKNOWN"] = "UNKNOWN"
    evidence_ref: uuid.UUID | None = None
    assumption_reason: str | None = Field(default=None, max_length=4000)
    metadata_json: dict[str, object] = Field(default_factory=dict)

    _normalize_base = field_validator("base_currency")(_currency)
    _normalize_quote = field_validator("quote_currency")(_currency)

    @model_validator(mode="after")
    def validate_pair(self) -> FXObservationCreate:
        if self.base_currency == self.quote_currency:
            raise ValueError("FX base and quote currencies must differ.")
        if self.provenance == "ASSUMED" and not self.assumption_reason:
            raise ValueError("An assumption reason is required for ASSUMED FX.")
        safe_metadata(self.metadata_json)
        return self


class FXSnapshotCreate(EconomicSchema):
    observation_id: uuid.UUID
    base_currency: str
    quote_currency: str
    version: str = Field(default="fx-snapshot-v1", min_length=1, max_length=32)

    _normalize_base = field_validator("base_currency")(_currency)
    _normalize_quote = field_validator("quote_currency")(_currency)

    @model_validator(mode="after")
    def validate_pair(self) -> FXSnapshotCreate:
        if self.base_currency == self.quote_currency:
            raise ValueError("FX base and quote currencies must differ.")
        return self


class LogisticsContextCreate(EconomicSchema):
    economic_context_id: uuid.UUID
    idempotency_key: str = Field(min_length=3, max_length=180)
    origin_country: str | None = Field(default=None, max_length=80)
    origin_location: str | None = Field(default=None, max_length=160)
    destination_country: str | None = Field(default=None, max_length=80)
    destination_location: str | None = Field(default=None, max_length=160)
    transport_mode: Literal[
        "AIR", "SEA", "ROAD", "RAIL", "COURIER", "MULTIMODAL", "OTHER", "UNKNOWN"
    ] = "UNKNOWN"
    sea_freight_type: Literal["LCL", "FCL", "UNKNOWN"] = "UNKNOWN"
    container_type: str | None = Field(default=None, max_length=80)
    target_quantity: Decimal | None = Field(default=None, gt=0)
    quantity_unit: str | None = Field(default=None, max_length=40)
    total_weight: Decimal | None = Field(default=None, ge=0)
    weight_unit: str | None = None
    total_volume: Decimal | None = Field(default=None, ge=0)
    volume_unit: str | None = None
    package_count: int | None = Field(default=None, gt=0)
    container_count: int | None = Field(default=None, gt=0)
    incoterm: str | None = Field(default=None, max_length=8)
    requested_delivery_at: datetime | None = None
    status: Literal["DRAFT", "CURRENT", "ARCHIVED"] = "DRAFT"

    @field_validator("weight_unit")
    @classmethod
    def valid_weight_unit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.upper()
        if normalized not in WEIGHT_UNITS:
            raise ValueError("Unsupported weight unit.")
        return normalized

    @field_validator("volume_unit")
    @classmethod
    def valid_volume_unit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.upper()
        if normalized not in VOLUME_UNITS:
            raise ValueError("Unsupported volume unit.")
        return normalized

    @field_validator("incoterm")
    @classmethod
    def normalize_incoterm(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @model_validator(mode="after")
    def units_required(self) -> LogisticsContextCreate:
        if self.total_weight is not None and self.weight_unit is None:
            raise ValueError("Weight unit is required when weight is supplied.")
        if self.total_volume is not None and self.volume_unit is None:
            raise ValueError("Volume unit is required when volume is supplied.")
        return self


class FreightObservationCreate(EconomicSchema):
    logistics_context_id: uuid.UUID
    idempotency_key: str = Field(min_length=3, max_length=180)
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    basis: Literal[
        "PER_SHIPMENT", "PER_KG", "PER_CBM", "PER_CARTON", "PER_CONTAINER", "FIXED_QUOTE", "UNKNOWN"
    ] = "UNKNOWN"
    transport_mode: (
        Literal["AIR", "SEA", "ROAD", "RAIL", "COURIER", "MULTIMODAL", "OTHER", "UNKNOWN"] | None
    ) = None
    origin_country: str | None = Field(default=None, max_length=80)
    origin_location: str | None = Field(default=None, max_length=160)
    destination_country: str | None = Field(default=None, max_length=80)
    destination_location: str | None = Field(default=None, max_length=160)
    quoted_quantity: Decimal | None = Field(default=None, ge=0)
    quoted_quantity_unit: str | None = Field(default=None, max_length=40)
    quoted_weight: Decimal | None = Field(default=None, ge=0)
    quoted_weight_unit: str | None = None
    quoted_volume: Decimal | None = Field(default=None, ge=0)
    quoted_volume_unit: str | None = None
    quoted_package_count: int | None = Field(default=None, gt=0)
    quoted_container_count: int | None = Field(default=None, gt=0)
    incoterm: str | None = Field(default=None, max_length=8)
    quoted_at: datetime | None = None
    valid_until: datetime | None = None
    provider: str = Field(min_length=1, max_length=120)
    mode: Literal["LOCAL_FIXTURE", "MANUAL"] = "LOCAL_FIXTURE"
    provenance: Literal["OBSERVED", "QUOTED", "CONFIGURED", "ASSUMED", "CALCULATED", "UNKNOWN"] = (
        "UNKNOWN"
    )
    freshness: Literal["CURRENT", "STALE", "UNKNOWN"] = "UNKNOWN"
    evidence_ref: uuid.UUID | None = None
    assumption_reason: str | None = Field(default=None, max_length=4000)
    metadata_json: dict[str, object] = Field(default_factory=dict)
    version: str = Field(default="freight-observation-v1", min_length=1, max_length=32)

    _normalize_currency = field_validator("currency")(_currency)

    @field_validator("quoted_weight_unit")
    @classmethod
    def valid_quoted_weight_unit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.upper()
        if normalized not in WEIGHT_UNITS:
            raise ValueError("Unsupported quoted weight unit.")
        return normalized

    @field_validator("quoted_volume_unit")
    @classmethod
    def valid_quoted_volume_unit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.upper()
        if normalized not in VOLUME_UNITS:
            raise ValueError("Unsupported quoted volume unit.")
        return normalized

    @field_validator("incoterm")
    @classmethod
    def normalize_quote_incoterm(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @model_validator(mode="after")
    def validate_quote(self) -> FreightObservationCreate:
        if self.amount is not None and self.currency is None:
            raise ValueError("Currency is required when a freight amount is supplied.")
        if (
            self.valid_until is not None
            and self.quoted_at is not None
            and self.valid_until < self.quoted_at
        ):
            raise ValueError("Freight validity cannot end before the quote date.")
        if self.provenance == "ASSUMED" and not self.assumption_reason:
            raise ValueError("An assumption reason is required for ASSUMED freight.")
        safe_metadata(self.metadata_json)
        return self


class FreightSnapshotCreate(EconomicSchema):
    observation_id: uuid.UUID
    version: str = Field(default="freight-snapshot-v1", min_length=1, max_length=32)
