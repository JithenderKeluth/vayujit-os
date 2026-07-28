import csv
import io
import math
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from vayujit_api.ai.models import GeneratedArtifact, PromptTemplate
from vayujit_api.ai.service import artifact_details
from vayujit_api.audit.models import AuditEvent
from vayujit_api.brands.models import Brand
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.operations.schemas import (
    ApprovalComparisonVersion,
    ApprovalDetailsResponse,
    ApprovalPage,
    ApprovalQueueItem,
    DashboardMetrics,
    DashboardResponse,
    OperationalItem,
    OperationsPage,
)
from vayujit_api.products.models import Product
from vayujit_api.publishing.models import PublishingDestination, PublishingExecution
from vayujit_api.workflows.models import WorkflowInstance

dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
approval_router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])
operations_router = APIRouter(prefix="/api/v1/operations", tags=["operations"])
DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(current_user)]


def count(db: Session, model: type[Any], *conditions: ColumnElement[bool]) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)


def event_category(action: str) -> str:
    prefix = action.split(".", 1)[0]
    return {
        "ai": "AI Generation",
        "publishing": "Publishing",
        "workflow": "Workflow",
        "product": "Product",
        "settings": "System",
    }.get(prefix, "System")


def event_url(event: AuditEvent) -> str | None:
    routes = {
        "generated_artifact": "/approvals/",
        "publishing_execution": "/publishing/executions/",
        "workflow_instance": "/workflows/",
        "product": "/products/",
        "brand": "/brands/",
    }
    root = routes.get(event.entity_type)
    return f"{root}{event.entity_id}" if root else None


def safe_event(
    event: AuditEvent, products: dict[str, Product], brands: dict[str, Brand]
) -> OperationalItem:
    metadata = event.metadata_json
    product_id = str(metadata.get("product_id", ""))
    brand_id = str(metadata.get("brand_id", ""))
    product = products.get(product_id)
    brand = brands.get(brand_id) or (brands.get(str(product.brand_id)) if product else None)
    status = metadata.get("status") or metadata.get("to_status")
    summary = event.action.replace(".", " ").replace("_", " ").title()
    error = metadata.get("safe_error_message")
    if isinstance(error, str):
        summary = f"{summary}: {error[:160]}"
    return OperationalItem(
        id=event.id,
        timestamp=event.occurred_at,
        category=event_category(event.action),
        event_name=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        brand_id=brand.id if brand else None,
        brand_name=brand.name if brand else None,
        product_id=product.id if product else None,
        product_name=product.name if product else None,
        status=str(status) if status else None,
        safe_summary=summary,
        related_url=event_url(event),
    )


def operational_query(
    db: Session,
    owner_id: uuid.UUID,
    *,
    brand_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    category: str | None = None,
    event_name: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 1000,
) -> list[OperationalItem]:
    if date_from and date_to and date_to - date_from > timedelta(days=366):
        raise HTTPException(422, "Date range cannot exceed 366 days.")
    query = select(AuditEvent).where(AuditEvent.actor_id == owner_id)
    if event_name:
        query = query.where(AuditEvent.action == event_name)
    if date_from:
        query = query.where(AuditEvent.occurred_at >= date_from)
    if date_to:
        query = query.where(AuditEvent.occurred_at <= date_to)
    events = db.scalars(query.order_by(AuditEvent.occurred_at.desc()).limit(limit)).all()
    products = {
        str(x.id): x for x in db.scalars(select(Product).where(Product.owner_id == owner_id))
    }
    brands = {str(x.id): x for x in db.scalars(select(Brand).where(Brand.owner_id == owner_id))}
    values = [safe_event(item, products, brands) for item in events]
    if brand_id:
        values = [item for item in values if item.brand_id == brand_id]
    if product_id:
        values = [item for item in values if item.product_id == product_id]
    if category:
        values = [item for item in values if item.category == category]
    return values


@dashboard_router.get("/summary", response_model=DashboardResponse)
def dashboard(
    db: DatabaseSession, user: CurrentUser, brand_id: uuid.UUID | None = None
) -> DashboardResponse:
    scope = [Product.owner_id == user.id]
    artifact_scope = [GeneratedArtifact.owner_id == user.id]
    execution_scope = [PublishingExecution.owner_id == user.id]
    workflow_scope = [WorkflowInstance.owner_id == user.id]
    destination_scope = [PublishingDestination.owner_id == user.id]
    if brand_id:
        scope.append(Product.brand_id == brand_id)
        artifact_scope.append(GeneratedArtifact.brand_id == brand_id)
        execution_scope.append(PublishingExecution.brand_id == brand_id)
        workflow_scope.append(WorkflowInstance.brand_id == brand_id)
        destination_scope.append(
            or_(
                PublishingDestination.brand_id == brand_id,
                PublishingDestination.brand_id.is_(None),
            )
        )
    metrics = DashboardMetrics(
        total_brands=count(db, Brand, Brand.owner_id == user.id),
        total_products=count(db, Product, *scope),
        active_products=count(db, Product, *scope, Product.status == "active"),
        pending_approvals=count(
            db, GeneratedArtifact, *artifact_scope, GeneratedArtifact.status == "pending_review"
        ),
        approved_artifacts=count(
            db, GeneratedArtifact, *artifact_scope, GeneratedArtifact.status == "approved"
        ),
        active_destinations=count(
            db, PublishingDestination, *destination_scope, PublishingDestination.status == "active"
        ),
        successful_executions=count(
            db, PublishingExecution, *execution_scope, PublishingExecution.status == "succeeded"
        ),
        failed_executions=count(
            db, PublishingExecution, *execution_scope, PublishingExecution.status == "failed"
        ),
        waiting_workflows=count(
            db,
            WorkflowInstance,
            *workflow_scope,
            WorkflowInstance.status == "waiting_for_approval",
        ),
        completed_workflows=count(
            db, WorkflowInstance, *workflow_scope, WorkflowInstance.status == "completed"
        ),
        failed_workflows=count(
            db, WorkflowInstance, *workflow_scope, WorkflowInstance.status == "failed"
        ),
        retryable_failures=count(
            db,
            PublishingExecution,
            *execution_scope,
            PublishingExecution.status == "failed",
            PublishingExecution.retryable.is_(True),
        ),
    )
    return DashboardResponse(
        metrics=metrics,
        activity=operational_query(db, user.id, brand_id=brand_id, limit=10),
    )


def approval_item(
    db: Session,
    owner_id: uuid.UUID,
    artifact: GeneratedArtifact,
    product: Product,
    brand: Brand,
    template: PromptTemplate,
) -> ApprovalQueueItem:
    content = artifact.content_json
    return ApprovalQueueItem(
        id=artifact.id,
        product_id=product.id,
        product_name=product.name,
        brand_id=brand.id,
        brand_name=brand.name,
        version_number=artifact.version_number,
        template_name=template.name,
        template_version=template.version,
        generated_title=str(content.get("product_title", ""))[:200],
        short_description=str(content.get("short_description", ""))[:500],
        status=artifact.status,
        generated_at=artifact.created_at,
        decided_at=artifact.approved_at or artifact.rejected_at,
        workflow_id=db.scalar(
            select(WorkflowInstance.id).where(
                WorkflowInstance.owner_id == owner_id,
                WorkflowInstance.context_json["artifact_id"].astext == str(artifact.id),
            )
        ),
    )


@approval_router.get("", response_model=ApprovalPage)
def approvals(
    db: DatabaseSession,
    user: CurrentUser,
    status: (
        Literal["pending_review", "approved", "rejected", "superseded"] | None
    ) = "pending_review",
    brand_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    template_id: uuid.UUID | None = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ApprovalPage:
    filters: list[ColumnElement[bool]] = [GeneratedArtifact.owner_id == user.id]
    for column, value in (
        (GeneratedArtifact.status, status),
        (GeneratedArtifact.brand_id, brand_id),
        (GeneratedArtifact.product_id, product_id),
        (GeneratedArtifact.prompt_template_id, template_id),
    ):
        if value is not None:
            filters.append(column == value)
    query = (
        select(GeneratedArtifact, Product, Brand, PromptTemplate)
        .join(Product, Product.id == GeneratedArtifact.product_id)
        .join(Brand, Brand.id == GeneratedArtifact.brand_id)
        .join(PromptTemplate, PromptTemplate.id == GeneratedArtifact.prompt_template_id)
        .where(*filters)
    )
    if search:
        query = query.where(
            or_(
                Product.normalized_name.contains(search.strip().casefold()),
                GeneratedArtifact.content_json["product_title"].astext.ilike(f"%{search.strip()}%"),
            )
        )
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = db.execute(
        query.order_by(GeneratedArtifact.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ApprovalPage(
        items=[approval_item(db, user.id, *row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


@approval_router.get("/{artifact_id}", response_model=ApprovalDetailsResponse)
def approval_details(
    artifact_id: uuid.UUID, db: DatabaseSession, user: CurrentUser
) -> ApprovalDetailsResponse:
    details = artifact_details(db, user.id, artifact_id)
    rows = db.execute(
        select(GeneratedArtifact, Product, Brand, PromptTemplate)
        .join(Product, Product.id == GeneratedArtifact.product_id)
        .join(Brand, Brand.id == GeneratedArtifact.brand_id)
        .join(PromptTemplate, PromptTemplate.id == GeneratedArtifact.prompt_template_id)
        .where(
            GeneratedArtifact.owner_id == user.id,
            GeneratedArtifact.product_id == details.product_id,
            GeneratedArtifact.prompt_template_id == details.template_id,
        )
        .order_by(GeneratedArtifact.version_number.desc())
    ).all()
    return ApprovalDetailsResponse(
        artifact=details,
        versions=[
            ApprovalComparisonVersion(
                artifact=artifact_details(db, user.id, row[0].id),
                workflow_id=approval_item(db, user.id, *row).workflow_id,
            )
            for row in rows
        ],
    )


@operations_router.get("/history", response_model=OperationsPage)
def history(
    db: DatabaseSession,
    user: CurrentUser,
    brand_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    category: str | None = None,
    event_name: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> OperationsPage:
    values = operational_query(
        db,
        user.id,
        brand_id=brand_id,
        product_id=product_id,
        category=category,
        event_name=event_name,
        date_from=date_from,
        date_to=date_to,
    )
    total = len(values)
    return OperationsPage(
        items=values[(page - 1) * page_size : page * page_size],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


def csv_safe(value: object) -> str:
    text_value = str(value or "")
    return f"'{text_value}" if text_value.startswith(("=", "+", "-", "@")) else text_value


@operations_router.get("/history/export")
def export_history(
    db: DatabaseSession,
    user: CurrentUser,
    brand_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    category: str | None = None,
) -> Response:
    values = operational_query(
        db, user.id, brand_id=brand_id, product_id=product_id, category=category, limit=5000
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "timestamp",
            "category",
            "event",
            "brand",
            "product",
            "entity_type",
            "entity_id",
            "status",
            "summary",
        ]
    )
    for item in values:
        writer.writerow(
            [
                csv_safe(item.timestamp.isoformat()),
                csv_safe(item.category),
                csv_safe(item.event_name),
                csv_safe(item.brand_name),
                csv_safe(item.product_name),
                csv_safe(item.entity_type),
                csv_safe(item.entity_id),
                csv_safe(item.status),
                csv_safe(item.safe_summary),
            ]
        )
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=vayujit-operations.csv"},
    )
