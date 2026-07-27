import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class BrandStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Brand(Base):
    __tablename__ = "brands"
    __table_args__ = (
        UniqueConstraint("owner_id", "normalized_name", name="uq_brands_owner_normalized_name"),
        UniqueConstraint("owner_id", "slug", name="uq_brands_owner_slug"),
        CheckConstraint("status IN ('active', 'archived')", name="ck_brands_status"),
        CheckConstraint(
            "(status = 'active') OR (is_active_context = false)",
            name="ck_archived_brand_not_active",
        ),
        Index(
            "uq_brands_one_active_context_per_owner",
            "owner_id",
            unique=True,
            postgresql_where=text("is_active_context = true"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    normalized_name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    tagline: Mapped[str | None] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(16), default=BrandStatus.ACTIVE.value, index=True)
    website_url: Mapped[str | None] = mapped_column(String(2048))
    primary_color: Mapped[str | None] = mapped_column(String(7))
    secondary_color: Mapped[str | None] = mapped_column(String(7))
    logo_asset_path: Mapped[str | None] = mapped_column(String(512))
    is_active_context: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
