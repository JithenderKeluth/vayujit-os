import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class OwnerPreference(Base):
    __tablename__ = "owner_preferences"
    __table_args__ = (
        CheckConstraint("default_page_size IN (10,25,50,100)", name="ck_preferences_page_size"),
        CheckConstraint(
            "execution_history_page_size IN (10,25,50,100)",
            name="ck_preferences_history_page_size",
        ),
        CheckConstraint(
            "date_format IN ('medium','short','iso')", name="ck_preferences_date_format"
        ),
        CheckConstraint(
            "theme_preference IN ('system','light','dark')", name="ck_preferences_theme"
        ),
        CheckConstraint(
            "density_preference IN ('comfortable','compact')", name="ck_preferences_density"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")
    date_format: Mapped[str] = mapped_column(String(20), default="medium")
    default_page_size: Mapped[int] = mapped_column(Integer, default=25)
    execution_history_page_size: Mapped[int] = mapped_column(Integer, default=25)
    default_brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL")
    )
    default_prompt_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_templates.id", ondelete="SET NULL")
    )
    default_publishing_destination_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_destinations.id", ondelete="SET NULL")
    )
    confirm_before_publish: Mapped[bool] = mapped_column(Boolean, default=True)
    confirm_before_retry: Mapped[bool] = mapped_column(Boolean, default=True)
    theme_preference: Mapped[str] = mapped_column(String(20), default="system")
    density_preference: Mapped[str] = mapped_column(String(20), default="comfortable")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
