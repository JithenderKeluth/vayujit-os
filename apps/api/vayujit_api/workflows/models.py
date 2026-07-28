import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_workflow_template_key_version"),
        CheckConstraint("status IN ('enabled','disabled')", name="ck_workflow_template_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    key: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer)
    workflow_type: Mapped[str] = mapped_column(String(80), index=True)
    definition_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), index=True)
    is_default: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','running','waiting_for_approval','completed','failed','cancelled')",
            name="ck_workflow_instance_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), index=True
    )
    workflow_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_templates.id")
    )
    destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_destinations.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), index=True)
    current_step_key: Mapped[str | None] = mapped_column(String(80), index=True)
    input_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    context_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkflowStepExecution(Base):
    __tablename__ = "workflow_step_executions"
    __table_args__ = (
        UniqueConstraint(
            "workflow_instance_id", "step_key", "attempt_number", name="uq_workflow_step_attempt"
        ),
        CheckConstraint(
            "status IN ('pending','running','waiting','succeeded','failed','skipped','cancelled')",
            name="ck_workflow_step_status",
        ),
        CheckConstraint("sequence_number BETWEEN 1 AND 3", name="ck_workflow_step_sequence"),
        CheckConstraint("attempt_number > 0", name="ck_workflow_step_attempt_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_instances.id"), index=True
    )
    step_key: Mapped[str] = mapped_column(String(80), index=True)
    step_type: Mapped[str] = mapped_column(String(40))
    sequence_number: Mapped[int] = mapped_column(Integer)
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), index=True)
    input_reference_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    output_reference_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    retryable: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
