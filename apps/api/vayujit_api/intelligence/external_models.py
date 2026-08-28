# ruff: noqa: E501
"""Owner-scoped ledgers for controlled external research."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ExternalSearchRequest(Base):
    __tablename__ = "intelligence_external_search_requests"
    __table_args__ = (
        UniqueConstraint("owner_id", "identity_key", name="uq_external_search_identity"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    query: Mapped[str] = mapped_column(String(500))
    market: Mapped[str] = mapped_column(String(120), default="")
    language: Mapped[str] = mapped_column(String(32), default="en")
    max_results: Mapped[int] = mapped_column(Integer, default=10)
    safe_search: Mapped[bool] = mapped_column(default=True)
    source_categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    allowed_domains: Mapped[list[str]] = mapped_column(JSONB, default=list)
    excluded_domains: Mapped[list[str]] = mapped_column(JSONB, default=list)
    provider: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    identity_key: Mapped[str] = mapped_column(String(300))
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExternalSearchResult(Base):
    __tablename__ = "intelligence_external_search_results"
    __table_args__ = (
        UniqueConstraint("owner_id", "identity_key", name="uq_external_search_result_identity"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    search_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_external_search_requests.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    snippet: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    provider: Mapped[str] = mapped_column(String(64))
    provider_result_id: Mapped[str] = mapped_column(String(300))
    rank: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    source_classification: Mapped[str] = mapped_column(
        String(64), default="SEARCH_DISCOVERY_RESULT"
    )
    raw_payload_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(128))
    identity_key: Mapped[str] = mapped_column(String(300))


class ExternalFetch(Base):
    __tablename__ = "intelligence_external_fetches"
    __table_args__ = (
        UniqueConstraint("owner_id", "identity_key", name="uq_external_fetch_identity"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    search_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_external_search_results.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requested_url: Mapped[str] = mapped_column(Text)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    content_length: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_profile: Mapped[str] = mapped_column(String(120), default="default")
    provider_mode: Mapped[str] = mapped_column(String(32))
    redirect_count: Mapped[int] = mapped_column(Integer, default=0)
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    identity_key: Mapped[str] = mapped_column(String(300))
    freshness: Mapped[str] = mapped_column(String(24), default="unknown")
    extracted: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExternalSourceProfile(Base):
    __tablename__ = "intelligence_external_source_profiles"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_external_source_profile"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    approved_domains: Mapped[list[str]] = mapped_column(JSONB, default=list)
    blocked_domains: Mapped[list[str]] = mapped_column(JSONB, default=list)
    robots_policy: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    terms_status: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    access_classification: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    enabled: Mapped[bool] = mapped_column(default=False)


class ExternalProviderState(Base):
    __tablename__ = "intelligence_external_provider_states"
    __table_args__ = (UniqueConstraint("owner_id", "provider", name="uq_external_provider_state"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="DISABLED")
    requests_minute: Mapped[int] = mapped_column(Integer, default=0)
    requests_hour: Mapped[int] = mapped_column(Integer, default=0)
    requests_day: Mapped[int] = mapped_column(Integer, default=0)
    last_failure: Mapped[str | None] = mapped_column(String(80), nullable=True)
    disabled: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ExternalResearchBudget(Base):
    """Atomic, mission-scoped resource ledger for external work."""

    __tablename__ = "intelligence_external_budgets"
    __table_args__ = (
        UniqueConstraint("owner_id", "mission_id", name="uq_external_budget_mission"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="CASCADE"),
        index=True,
    )
    max_searches: Mapped[int] = mapped_column(Integer, default=10)
    max_fetches: Mapped[int] = mapped_column(Integer, default=10)
    max_domains: Mapped[int] = mapped_column(Integer, default=10)
    max_results: Mapped[int] = mapped_column(Integer, default=100)
    max_response_bytes: Mapped[int] = mapped_column(Integer, default=1_000_000)
    max_total_bytes: Mapped[int] = mapped_column(Integer, default=10_000_000)
    max_elapsed_seconds: Mapped[int] = mapped_column(Integer, default=300)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    max_provider_requests: Mapped[int] = mapped_column(Integer, default=20)
    searches_used: Mapped[int] = mapped_column(Integer, default=0)
    fetches_used: Mapped[int] = mapped_column(Integer, default=0)
    domains_used: Mapped[int] = mapped_column(Integer, default=0)
    domains_seen: Mapped[list[str]] = mapped_column(JSONB, default=list)
    results_used: Mapped[int] = mapped_column(Integer, default=0)
    bytes_used: Mapped[int] = mapped_column(Integer, default=0)
    retries_used: Mapped[int] = mapped_column(Integer, default=0)
    provider_requests_used: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    elapsed_seconds: Mapped[float] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ExternalExecution(Base):
    """Durable logical execution/checkpoint ledger shared by search and fetch."""

    __tablename__ = "intelligence_external_executions"
    __table_args__ = (
        UniqueConstraint("owner_id", "identity_key", name="uq_external_execution_identity"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(16), index=True)
    identity_key: Mapped[str] = mapped_column(String(300))
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    checkpoint: Mapped[str] = mapped_column(String(40), default="CLAIMED")
    provider: Mapped[str] = mapped_column(String(64))
    provider_calls: Mapped[int] = mapped_column(Integer, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    result_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    safe_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ExternalRecoveryAction(Base):
    """Idempotent, owner-scoped execution record for external recovery."""

    __tablename__ = "intelligence_external_recovery"
    __table_args__ = (
        UniqueConstraint("owner_id", "identity_key", name="uq_external_recovery_identity"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_missions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_autonomous_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    failure_code: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED")
    safe_reason_code: Mapped[str] = mapped_column(String(120))
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    identity_key: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
