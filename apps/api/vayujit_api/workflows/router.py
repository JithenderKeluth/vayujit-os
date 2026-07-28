import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.workflows.models import WorkflowTemplate
from vayujit_api.workflows.schemas import (
    CreateWorkflow,
    TemplateSummary,
    WorkflowDetails,
    WorkflowPage,
)
from vayujit_api.workflows.service import (
    cancel_workflow,
    continue_workflow,
    create_workflow,
    list_workflows,
    owned_workflow,
    retry_workflow,
    start_workflow,
    workflow_details,
)

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.get("/templates", response_model=list[TemplateSummary])
def templates(db: DB, owner: Owner) -> list[TemplateSummary]:
    values = db.scalars(
        select(WorkflowTemplate)
        .where(WorkflowTemplate.status == "enabled")
        .order_by(
            WorkflowTemplate.is_default.desc(),
            WorkflowTemplate.key,
            WorkflowTemplate.version.desc(),
        )
    )
    return [
        TemplateSummary(
            id=value.id,
            key=value.key,
            name=value.name,
            description=value.description,
            version=value.version,
            workflow_type=value.workflow_type,
            is_default=value.is_default,
        )
        for value in values
    ]


@router.post("", response_model=WorkflowDetails, status_code=201)
def create(data: CreateWorkflow, db: DB, owner: Owner) -> WorkflowDetails:
    return create_workflow(db, owner, data)


@router.get("", response_model=WorkflowPage)
def listing(
    db: DB,
    owner: Owner,
    brand_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    destination_id: uuid.UUID | None = None,
    status: str | None = None,
    current_step: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    retryable: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> WorkflowPage:
    return list_workflows(
        db,
        owner.id,
        brand_id=brand_id,
        product_id=product_id,
        destination_id=destination_id,
        status=status,
        current_step=current_step,
        date_from=date_from,
        date_to=date_to,
        retryable=retryable,
        page=page,
        page_size=page_size,
    )


@router.get("/{workflow_id}", response_model=WorkflowDetails)
def details(workflow_id: uuid.UUID, db: DB, owner: Owner) -> WorkflowDetails:
    return workflow_details(db, owned_workflow(db, owner.id, workflow_id))


@router.post("/{workflow_id}/start", response_model=WorkflowDetails)
def start(workflow_id: uuid.UUID, db: DB, owner: Owner) -> WorkflowDetails:
    return start_workflow(db, owner, workflow_id)


@router.post("/{workflow_id}/continue", response_model=WorkflowDetails)
def continue_after_approval(workflow_id: uuid.UUID, db: DB, owner: Owner) -> WorkflowDetails:
    return continue_workflow(db, owner, workflow_id)


@router.post("/{workflow_id}/retry", response_model=WorkflowDetails)
def retry(workflow_id: uuid.UUID, db: DB, owner: Owner) -> WorkflowDetails:
    return retry_workflow(db, owner, workflow_id)


@router.post("/{workflow_id}/cancel", response_model=WorkflowDetails)
def cancel(workflow_id: uuid.UUID, db: DB, owner: Owner) -> WorkflowDetails:
    return cancel_workflow(db, owner, workflow_id)
