import uuid
from datetime import datetime

from pydantic import BaseModel

from vayujit_api.ai.schemas import ArtifactDetails


class DashboardMetrics(BaseModel):
    total_brands: int
    total_products: int
    active_products: int
    pending_approvals: int
    approved_artifacts: int
    active_destinations: int
    successful_executions: int
    failed_executions: int
    waiting_workflows: int
    completed_workflows: int
    failed_workflows: int
    retryable_failures: int


class OperationalItem(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    category: str
    event_name: str
    entity_type: str
    entity_id: uuid.UUID
    brand_id: uuid.UUID | None = None
    brand_name: str | None = None
    product_id: uuid.UUID | None = None
    product_name: str | None = None
    status: str | None = None
    safe_summary: str
    related_url: str | None = None
    correlation_id: str | None = None


class DashboardResponse(BaseModel):
    metrics: DashboardMetrics
    activity: list[OperationalItem]


class OperationsPage(BaseModel):
    items: list[OperationalItem]
    page: int
    page_size: int
    total: int
    pages: int


class ApprovalQueueItem(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    brand_id: uuid.UUID
    brand_name: str
    version_number: int
    template_name: str
    template_version: int
    generated_title: str
    short_description: str
    status: str
    generated_at: datetime
    decided_at: datetime | None
    workflow_id: uuid.UUID | None


class ApprovalPage(BaseModel):
    items: list[ApprovalQueueItem]
    page: int
    page_size: int
    total: int
    pages: int


class ApprovalComparisonVersion(BaseModel):
    artifact: ArtifactDetails
    workflow_id: uuid.UUID | None


class ApprovalDetailsResponse(BaseModel):
    artifact: ArtifactDetails
    versions: list[ApprovalComparisonVersion]
