import re
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Slug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=160,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]
ProductTypeValue = Literal["physical", "digital", "service", "affiliate"]
ProductStatusValue = Literal["draft", "active", "archived"]
WeightUnitValue = Literal["g", "kg", "oz", "lb"]
MONEY_PATTERN = re.compile(r"^(?:0|[1-9]\d{0,9})(?:\.\d{1,2})?$")
WEIGHT_PATTERN = re.compile(r"^(?:0|[1-9]\d{0,8})(?:\.\d{1,3})?$")


def decimal_string(value: object, *, money: bool = True) -> Decimal | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("Decimal values must be JSON strings.")
    pattern = MONEY_PATTERN if money else WEIGHT_PATTERN
    if not pattern.fullmatch(value):
        raise ValueError("Invalid decimal format.")
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Invalid decimal value.") from error


class ProductData(BaseModel):
    brand_id: uuid.UUID | None = None
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    slug: Slug | None = None
    sku: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    product_type: ProductTypeValue
    short_description: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None
    ) = None
    description: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=10000)] | None
    ) = None
    category: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    tags: list[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    ] = Field(default_factory=list, max_length=20)
    price_amount: Decimal | None = None
    price_currency: Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$")] | None = None
    compare_at_price_amount: Decimal | None = None
    cost_amount: Decimal | None = None
    tax_code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)] | None = None
    barcode: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    weight_value: Decimal | None = None
    weight_unit: WeightUnitValue | None = None
    inventory_tracking_enabled: bool = False
    inventory_quantity: Annotated[int, Field(ge=0, le=2_000_000_000)] = 0
    low_stock_threshold: Annotated[int, Field(ge=0, le=2_000_000_000)] = 0
    is_featured: bool = False

    @field_validator("price_amount", "compare_at_price_amount", "cost_amount", mode="before")
    @classmethod
    def validate_money(cls, value: object) -> Decimal | None:
        return decimal_string(value)

    @field_validator("weight_value", mode="before")
    @classmethod
    def validate_weight(cls, value: object) -> Decimal | None:
        return decimal_string(value, money=False)

    @field_validator("price_currency")
    @classmethod
    def uppercase_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else None

    @field_validator("sku", "barcode")
    @classmethod
    def empty_to_none(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for tag in value:
            normalized = " ".join(tag.split())
            key = normalized.casefold()
            if key not in seen:
                seen.add(key)
                result.append(normalized)
        return result

    @model_validator(mode="after")
    def validate_combinations(self) -> "ProductData":
        if self.compare_at_price_amount is not None and self.price_amount is None:
            raise ValueError("Sale price is required when compare-at price is supplied.")
        if (
            self.compare_at_price_amount is not None
            and self.price_amount is not None
            and self.compare_at_price_amount < self.price_amount
        ):
            raise ValueError("Compare-at price cannot be lower than sale price.")
        if self.price_amount is not None and self.price_currency is None:
            raise ValueError("Currency is required when a price is supplied.")
        if self.weight_value is not None and self.weight_unit is None:
            raise ValueError("Weight unit is required when weight is supplied.")
        return self


class ProductCreate(ProductData):
    pass


class ProductUpdate(BaseModel):
    brand_id: uuid.UUID | None = None
    name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
        | None
    ) = None
    slug: Slug | None = None
    sku: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    product_type: ProductTypeValue | None = None
    short_description: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None
    ) = None
    description: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=10000)] | None
    ) = None
    category: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    tags: (
        list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]]
        | None
    ) = Field(default=None, max_length=20)
    price_amount: Decimal | None = None
    price_currency: Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$")] | None = None
    compare_at_price_amount: Decimal | None = None
    cost_amount: Decimal | None = None
    tax_code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)] | None = None
    barcode: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    weight_value: Decimal | None = None
    weight_unit: WeightUnitValue | None = None
    inventory_tracking_enabled: bool | None = None
    inventory_quantity: Annotated[int, Field(ge=0, le=2_000_000_000)] | None = None
    low_stock_threshold: Annotated[int, Field(ge=0, le=2_000_000_000)] | None = None
    is_featured: bool | None = None

    _money = field_validator(
        "price_amount", "compare_at_price_amount", "cost_amount", mode="before"
    )(lambda value: decimal_string(value))
    _weight = field_validator("weight_value", mode="before")(
        lambda value: decimal_string(value, money=False)
    )

    @field_validator("price_currency")
    @classmethod
    def uppercase_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        return ProductData.normalize_tags(value) if value is not None else None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_id: uuid.UUID
    brand_name: str
    name: str
    slug: str
    sku: str | None
    product_type: ProductTypeValue
    status: ProductStatusValue
    short_description: str | None
    description: str | None
    category: str | None
    tags: list[str]
    price_amount: Decimal | None
    price_currency: str | None
    compare_at_price_amount: Decimal | None
    cost_amount: Decimal | None
    tax_code: str | None
    barcode: str | None
    weight_value: Decimal | None
    weight_unit: WeightUnitValue | None
    inventory_tracking_enabled: bool
    inventory_quantity: int
    low_stock_threshold: int
    is_featured: bool
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    page: int
    page_size: int
    total: int
    pages: int


class ProductAuditSummary(BaseModel):
    action: str
    occurred_at: datetime


class ProductDetailsResponse(ProductResponse):
    recent_audit_events: list[ProductAuditSummary] = Field(default_factory=list)
