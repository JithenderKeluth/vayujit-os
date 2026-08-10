import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class SEOAnalysis(Base):
    __tablename__ = "ai_seo_analyses"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "artifact_id",
            "artifact_version",
            "channel",
            "locale",
            "fingerprint",
            name="uq_ai_seo_analysis_context",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="CASCADE"), index=True
    )
    artifact_version: Mapped[int | None] = mapped_column(Integer)
    keyword_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_keyword_sets.id", ondelete="SET NULL"), index=True
    )
    keyword_set_version: Mapped[int | None] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(40), index=True)
    locale: Mapped[str] = mapped_column(String(16), index=True)
    intent: Mapped[str] = mapped_column(String(32), default="unknown")
    seo_type: Mapped[str] = mapped_column(String(32), default="website")
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    rule_version: Mapped[str] = mapped_column(String(40), default="seo-rules-v1")
    status: Mapped[str] = mapped_column(String(24), default="current")
    overall_score: Mapped[int] = mapped_column(Integer)
    dimensions_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    findings_json: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    recommendations_json: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    keyword_coverage_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    metrics_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TagSet(Base):
    __tablename__ = "ai_tag_sets"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", "scope", "locale", name="uq_ai_tag_set_identity"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    scope: Mapped[str] = mapped_column(String(32), default="product")
    locale: Mapped[str] = mapped_column(String(16), default="en-IN")
    tags_json: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
