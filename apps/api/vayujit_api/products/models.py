import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class ProductStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProductType(StrEnum):
    PHYSICAL = "physical"
    DIGITAL = "digital"
    SERVICE = "service"
    AFFILIATE = "affiliate"


class WeightUnit(StrEnum):
    G = "g"
    KG = "kg"
    OZ = "oz"
    LB = "lb"


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("brand_id", "normalized_name", name="uq_products_brand_normalized_name"),
        UniqueConstraint("brand_id", "slug", name="uq_products_brand_slug"),
        UniqueConstraint("owner_id", "sku", name="uq_products_owner_sku"),
        UniqueConstraint("owner_id", "barcode", name="uq_products_owner_barcode"),
        CheckConstraint("status IN ('draft', 'active', 'archived')", name="ck_products_status"),
        CheckConstraint(
            "product_type IN ('physical', 'digital', 'service', 'affiliate')",
            name="ck_products_type",
        ),
        CheckConstraint(
            "weight_unit IS NULL OR weight_unit IN ('g', 'kg', 'oz', 'lb')",
            name="ck_products_weight_unit",
        ),
        CheckConstraint("price_amount IS NULL OR price_amount >= 0", name="ck_products_price"),
        CheckConstraint(
            "compare_at_price_amount IS NULL OR compare_at_price_amount >= 0",
            name="ck_products_compare_price",
        ),
        CheckConstraint("cost_amount IS NULL OR cost_amount >= 0", name="ck_products_cost"),
        CheckConstraint(
            "compare_at_price_amount IS NULL OR price_amount IS NULL "
            "OR compare_at_price_amount >= price_amount",
            name="ck_products_compare_not_below_price",
        ),
        CheckConstraint("weight_value IS NULL OR weight_value >= 0", name="ck_products_weight"),
        CheckConstraint("inventory_quantity >= 0", name="ck_products_inventory_quantity"),
        CheckConstraint("low_stock_threshold >= 0", name="ck_products_low_stock_threshold"),
        CheckConstraint(
            "(status = 'archived' AND archived_at IS NOT NULL) "
            "OR (status <> 'archived' AND archived_at IS NULL)",
            name="ck_products_archive_timestamp",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    normalized_name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(160))
    sku: Mapped[str | None] = mapped_column(String(100))
    product_type: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default=ProductStatus.DRAFT.value, index=True)
    short_description: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(120), index=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list)
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    price_currency: Mapped[str | None] = mapped_column(String(3))
    compare_at_price_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cost_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    tax_code: Mapped[str | None] = mapped_column(String(50))
    barcode: Mapped[str | None] = mapped_column(String(100))
    weight_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    weight_unit: Mapped[str | None] = mapped_column(String(4))
    inventory_tracking_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    inventory_quantity: Mapped[int] = mapped_column(Integer, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=0)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
