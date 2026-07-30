import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

WorkflowStatus = Literal[
    "draft", "running", "waiting_for_approval", "completed", "failed", "cancelled"
]


class WorkflowDefinitionStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Literal["generate_content", "wait_for_approval", "publish_content"]
    type: Literal["ai_generate", "human_approval", "publish"]
    depends_on: list[str] = Field(default_factory=list, max_length=1)


class WorkflowDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    steps: list[WorkflowDefinitionStep] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_system_sequence(self) -> "WorkflowDefinition":
        if [step.key for step in self.steps] != [
            "generate_content",
            "wait_for_approval",
            "publish_content",
        ]:
            raise ValueError("Unsupported workflow step sequence.")
        return self


class TemplateSummary(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    description: str
    version: int
    workflow_type: str
    is_default: bool


class CreateWorkflow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: uuid.UUID
    destination_id: uuid.UUID
    workflow_template_id: uuid.UUID | None = None
    additional_instructions: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None
    publishing_action: Literal[
        "default",
        "shopify_create_draft",
        "shopify_update_product",
        "shopify_activate_product",
        "shopify_archive_product",
    ] = "default"


class StepAttemptDetails(BaseModel):
    id: uuid.UUID
    step_key: str
    step_type: str
    sequence_number: int
    attempt_number: int
    status: str
    related_id: uuid.UUID | None
    related_type: str | None
    started_at: datetime | None
    paused_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    cancelled_at: datetime | None
    error_code: str | None
    safe_error_message: str | None
    retryable: bool


class WorkflowDetails(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    template_key: str
    template_name: str
    template_version: int
    brand_id: uuid.UUID
    brand_name: str
    product_id: uuid.UUID
    product_name: str
    destination_id: uuid.UUID
    destination_name: str
    status: WorkflowStatus
    current_step_key: str | None
    artifact_id: uuid.UUID | None
    artifact_status: str | None
    generation_request_id: uuid.UUID | None
    publishing_execution_id: uuid.UUID | None
    publishing_status: str | None
    retryable: bool
    started_at: datetime | None
    paused_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    cancelled_at: datetime | None
    error_code: str | None
    safe_error_message: str | None
    created_at: datetime
    updated_at: datetime
    steps: list[StepAttemptDetails] = Field(default_factory=list)


class WorkflowPage(BaseModel):
    items: list[WorkflowDetails]
    page: int
    page_size: int
    total: int
    pages: int
