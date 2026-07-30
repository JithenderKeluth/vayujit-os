import math
import uuid
from datetime import datetime
from typing import Any, Literal, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.ai.schemas import CreateGenerationRequest
from vayujit_api.ai.service import generate
from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand, BrandStatus
from vayujit_api.core.observability import correlation_id
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.products.models import Product, ProductStatus
from vayujit_api.publishing.models import (
    PublishingDestination,
    PublishingExecution,
    PublishingJob,
)
from vayujit_api.publishing.scheduler_schemas import ScheduleCreate
from vayujit_api.publishing.scheduler_service import create_schedule, materialize_due_schedules
from vayujit_api.publishing.schemas import CreateExecution
from vayujit_api.publishing.service import create_execution, retry_execution
from vayujit_api.workflows.models import (
    WorkflowInstance,
    WorkflowPublishingWait,
    WorkflowStepExecution,
    WorkflowTemplate,
)
from vayujit_api.workflows.schemas import (
    CreateWorkflow,
    StepAttemptDetails,
    WorkflowDefinition,
    WorkflowDetails,
    WorkflowPage,
)

STEP_TYPES = {
    "generate_content": ("ai_generate", 1),
    "wait_for_approval": ("human_approval", 2),
    "publish_content": ("publish", 3),
}


def owned_workflow(
    db: Session, owner_id: uuid.UUID, workflow_id: uuid.UUID, *, lock: bool = False
) -> WorkflowInstance:
    query = select(WorkflowInstance).where(
        WorkflowInstance.id == workflow_id, WorkflowInstance.owner_id == owner_id
    )
    value = db.scalar(query.with_for_update() if lock else query)
    if value is None:
        raise HTTPException(404, "Workflow not found.")
    return value


def enabled_template(db: Session, template_id: uuid.UUID | None) -> WorkflowTemplate:
    query = select(WorkflowTemplate).where(WorkflowTemplate.status == "enabled")
    query = (
        query.where(WorkflowTemplate.id == template_id)
        if template_id
        else query.where(WorkflowTemplate.is_default.is_(True)).order_by(
            WorkflowTemplate.version.desc()
        )
    )
    value = db.scalar(query.limit(1))
    if value is None:
        raise HTTPException(404, "Workflow template not found.")
    WorkflowDefinition.model_validate(value.definition_json)
    return value


def latest_step(
    db: Session, workflow_id: uuid.UUID, step_key: str | None = None
) -> WorkflowStepExecution | None:
    query = select(WorkflowStepExecution).where(
        WorkflowStepExecution.workflow_instance_id == workflow_id
    )
    if step_key:
        query = query.where(WorkflowStepExecution.step_key == step_key)
    return db.scalar(
        query.order_by(
            WorkflowStepExecution.sequence_number.desc(),
            WorkflowStepExecution.attempt_number.desc(),
        ).limit(1)
    )


def new_step(
    db: Session,
    workflow: WorkflowInstance,
    step_key: str,
    *,
    status: str = "running",
    input_refs: dict[str, object] | None = None,
) -> WorkflowStepExecution:
    step_type, sequence = STEP_TYPES[step_key]
    previous = db.scalar(
        select(func.max(WorkflowStepExecution.attempt_number)).where(
            WorkflowStepExecution.workflow_instance_id == workflow.id,
            WorkflowStepExecution.step_key == step_key,
        )
    )
    stamp = now()
    value = WorkflowStepExecution(
        workflow_instance_id=workflow.id,
        step_key=step_key,
        step_type=step_type,
        sequence_number=sequence,
        attempt_number=(previous or 0) + 1,
        status=status,
        input_reference_json=input_refs or {},
        output_reference_json={},
        started_at=stamp if status == "running" else None,
        paused_at=stamp if status == "waiting" else None,
        retryable=False,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(value)
    db.flush()
    record_event(
        db,
        actor_id=workflow.owner_id,
        action="workflow.step_started",
        entity_type="workflow_instance",
        entity_id=workflow.id,
        metadata={
            "step_key": step_key,
            "step_type": step_type,
            "attempt_number": value.attempt_number,
        },
    )
    return value


def workflow_details(db: Session, workflow: WorkflowInstance) -> WorkflowDetails:
    template = db.get(WorkflowTemplate, workflow.workflow_template_id)
    brand = db.get(Brand, workflow.brand_id)
    product = db.get(Product, workflow.product_id)
    destination = db.get(PublishingDestination, workflow.destination_id)
    if not template or not brand or not product or not destination:
        raise HTTPException(409, "Workflow references are incomplete.")
    context = workflow.context_json
    artifact_id = uuid.UUID(str(context["artifact_id"])) if context.get("artifact_id") else None
    generation_id = (
        uuid.UUID(str(context["generation_request_id"]))
        if context.get("generation_request_id")
        else None
    )
    publishing_id = (
        uuid.UUID(str(context["publishing_execution_id"]))
        if context.get("publishing_execution_id")
        else None
    )
    artifact = db.get(GeneratedArtifact, artifact_id) if artifact_id else None
    publishing = db.get(PublishingExecution, publishing_id) if publishing_id else None
    wait = db.scalar(
        select(WorkflowPublishingWait)
        .where(WorkflowPublishingWait.workflow_instance_id == workflow.id)
        .order_by(WorkflowPublishingWait.created_at.desc())
        .limit(1)
    )
    values = db.scalars(
        select(WorkflowStepExecution)
        .where(WorkflowStepExecution.workflow_instance_id == workflow.id)
        .order_by(WorkflowStepExecution.sequence_number, WorkflowStepExecution.attempt_number)
    ).all()
    return WorkflowDetails(
        id=workflow.id,
        template_id=template.id,
        template_key=template.key,
        template_name=template.name,
        template_version=template.version,
        brand_id=brand.id,
        brand_name=brand.name,
        product_id=product.id,
        product_name=product.name,
        destination_id=destination.id,
        destination_name=destination.name,
        status=cast(
            Literal[
                "draft",
                "running",
                "waiting_for_approval",
                "waiting_for_publishing",
                "completed",
                "failed",
                "cancelled",
            ],
            workflow.status,
        ),
        current_step_key=workflow.current_step_key,
        artifact_id=artifact_id,
        artifact_status=artifact.status if artifact else None,
        generation_request_id=generation_id,
        publishing_execution_id=publishing_id,
        publishing_status=publishing.status if publishing else None,
        retryable=bool(
            workflow.status == "failed"
            and (step := latest_step(db, workflow.id))
            and step.retryable
        ),
        started_at=workflow.started_at,
        paused_at=workflow.paused_at,
        completed_at=workflow.completed_at,
        failed_at=workflow.failed_at,
        cancelled_at=workflow.cancelled_at,
        error_code=workflow.error_code,
        safe_error_message=workflow.safe_error_message,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        steps=[step_details(value) for value in values],
        publishing_schedule_id=wait.schedule_id if wait else None,
        publishing_job_id=wait.job_id if wait else None,
        publishing_wait_status=wait.status if wait else None,
    )


def step_details(value: WorkflowStepExecution) -> StepAttemptDetails:
    output = value.output_reference_json
    related_type: str | None = None
    related_id: uuid.UUID | None = None
    for key, kind in (
        ("artifact_id", "artifact"),
        ("generation_request_id", "generation"),
        ("publishing_execution_id", "publishing_execution"),
        ("publishing_job_id", "publishing_job"),
        ("publishing_schedule_id", "publishing_schedule"),
    ):
        if output.get(key):
            related_type = kind
            related_id = uuid.UUID(str(output[key]))
            break
    return StepAttemptDetails(
        id=value.id,
        step_key=value.step_key,
        step_type=value.step_type,
        sequence_number=value.sequence_number,
        attempt_number=value.attempt_number,
        status=value.status,
        related_id=related_id,
        related_type=related_type,
        started_at=value.started_at,
        paused_at=value.paused_at,
        completed_at=value.completed_at,
        failed_at=value.failed_at,
        cancelled_at=value.cancelled_at,
        error_code=value.error_code,
        safe_error_message=value.safe_error_message,
        retryable=value.retryable,
    )


def create_workflow(db: Session, owner: User, data: CreateWorkflow) -> WorkflowDetails:
    product = db.scalar(
        select(Product).where(Product.id == data.product_id, Product.owner_id == owner.id)
    )
    if product is None:
        raise HTTPException(404, "Product not found.")
    brand = db.scalar(select(Brand).where(Brand.id == product.brand_id, Brand.owner_id == owner.id))
    destination = db.scalar(
        select(PublishingDestination).where(
            PublishingDestination.id == data.destination_id,
            PublishingDestination.owner_id == owner.id,
        )
    )
    if not brand or not destination:
        raise HTTPException(404, "Workflow destination was not found.")
    if product.status != ProductStatus.ACTIVE.value:
        raise HTTPException(409, "Only active products may start a workflow.")
    if brand.status == BrandStatus.ARCHIVED.value:
        raise HTTPException(409, "Archived Brands cannot start workflows.")
    if destination.status != "active":
        raise HTTPException(409, "The publishing destination is disabled.")
    if destination.brand_id and destination.brand_id != brand.id:
        raise HTTPException(409, "Destination Brand scope does not match the Product.")
    template = enabled_template(db, data.workflow_template_id)
    stamp = now()
    workflow = WorkflowInstance(
        owner_id=owner.id,
        brand_id=brand.id,
        product_id=product.id,
        workflow_template_id=template.id,
        destination_id=destination.id,
        status="draft",
        input_json={
            "schema_version": 1,
            "additional_instructions": data.additional_instructions,
            "publishing_action": data.publishing_action,
            "schedule_at_local": (
                data.schedule_at_local.isoformat() if data.schedule_at_local else None
            ),
            "schedule_timezone": data.schedule_timezone,
        },
        context_json={"schema_version": 1},
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(workflow)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="workflow.created",
        entity_type="workflow_instance",
        entity_id=workflow.id,
        metadata={
            "template_key": template.key,
            "template_version": template.version,
            "product_id": str(product.id),
            "brand_id": str(brand.id),
            "destination_id": str(destination.id),
        },
    )
    db.commit()
    return workflow_details(db, workflow)


def run_generation(db: Session, owner: User, workflow: WorkflowInstance) -> WorkflowDetails:
    step = new_step(
        db,
        workflow,
        "generate_content",
        input_refs={"product_id": str(workflow.product_id)},
    )
    workflow.status = "running"
    workflow.current_step_key = "generate_content"
    workflow.started_at = workflow.started_at or now()
    workflow.paused_at = None
    workflow.updated_at = now()
    result = generate(
        db,
        owner,
        CreateGenerationRequest(
            product_id=workflow.product_id,
            additional_instructions=cast(
                str | None, workflow.input_json.get("additional_instructions")
            ),
        ),
    )
    stamp = now()
    workflow.context_json = {
        **workflow.context_json,
        "generation_request_id": str(result.id),
    }
    step.output_reference_json = {"generation_request_id": str(result.id)}
    if result.status != "completed" or result.artifact_id is None:
        step.status = "failed"
        step.failed_at = step.updated_at = stamp
        step.error_code = result.error_code
        step.safe_error_message = result.safe_error_message
        step.retryable = result.error_code == "mock_generation_failed"
        fail_workflow(
            db,
            workflow,
            result.error_code or "ai_generation_failed",
            result.safe_error_message or "AI generation failed.",
            retryable=step.retryable,
            step=step,
        )
        db.commit()
        return workflow_details(db, workflow)
    step.status = "succeeded"
    step.completed_at = step.updated_at = stamp
    step.output_reference_json = {
        "generation_request_id": str(result.id),
        "artifact_id": str(result.artifact_id),
    }
    record_step_success(db, workflow, step)
    approval = new_step(
        db,
        workflow,
        "wait_for_approval",
        status="waiting",
        input_refs={"artifact_id": str(result.artifact_id)},
    )
    approval.output_reference_json = {"artifact_id": str(result.artifact_id)}
    workflow.context_json = {
        **workflow.context_json,
        "artifact_id": str(result.artifact_id),
    }
    workflow.status = "waiting_for_approval"
    workflow.current_step_key = "wait_for_approval"
    workflow.paused_at = workflow.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action="workflow.waiting_for_approval",
        entity_type="workflow_instance",
        entity_id=workflow.id,
        metadata={"artifact_id": str(result.artifact_id)},
    )
    db.commit()
    return workflow_details(db, workflow)


def start_workflow(db: Session, owner: User, workflow_id: uuid.UUID) -> WorkflowDetails:
    workflow = owned_workflow(db, owner.id, workflow_id, lock=True)
    if workflow.status != "draft":
        raise HTTPException(409, "Only a draft workflow may be started.")
    record_event(
        db,
        actor_id=owner.id,
        action="workflow.started",
        entity_type="workflow_instance",
        entity_id=workflow.id,
        metadata={"product_id": str(workflow.product_id)},
    )
    return run_generation(db, owner, workflow)


def continue_workflow(db: Session, owner: User, workflow_id: uuid.UUID) -> WorkflowDetails:
    workflow = owned_workflow(db, owner.id, workflow_id, lock=True)
    if workflow.status == "completed":
        return workflow_details(db, workflow)
    if workflow.status != "waiting_for_approval":
        raise HTTPException(409, "Workflow is not waiting for approval.")
    artifact_id = workflow.context_json.get("artifact_id")
    artifact = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == uuid.UUID(str(artifact_id)),
            GeneratedArtifact.owner_id == owner.id,
        )
    )
    if artifact is None:
        raise HTTPException(409, "Workflow Artifact is unavailable.")
    approval = latest_step(db, workflow.id, "wait_for_approval")
    if approval is None:
        raise HTTPException(409, "Workflow approval step is unavailable.")
    if artifact.status == "rejected":
        stamp = now()
        approval.status = "failed"
        approval.failed_at = approval.updated_at = stamp
        approval.error_code = "artifact_rejected"
        approval.safe_error_message = "The owner rejected the generated Artifact."
        fail_workflow(
            db,
            workflow,
            "artifact_rejected",
            approval.safe_error_message,
            retryable=False,
            step=approval,
        )
        record_event(
            db,
            actor_id=owner.id,
            action="workflow.artifact_rejected",
            entity_type="workflow_instance",
            entity_id=workflow.id,
            metadata={"artifact_id": str(artifact.id)},
        )
        db.commit()
        return workflow_details(db, workflow)
    if artifact.status != "approved":
        raise HTTPException(409, "Approve or reject the Artifact before continuing.")
    stamp = now()
    approval.status = "succeeded"
    approval.completed_at = approval.updated_at = stamp
    record_step_success(db, workflow, approval)
    workflow.status = "running"
    workflow.current_step_key = "publish_content"
    workflow.paused_at = None
    workflow.updated_at = stamp
    record_event(
        db,
        actor_id=owner.id,
        action="workflow.continued",
        entity_type="workflow_instance",
        entity_id=workflow.id,
        metadata={"artifact_id": str(artifact.id)},
    )
    step = new_step(
        db,
        workflow,
        "publish_content",
        input_refs={
            "artifact_id": str(artifact.id),
            "destination_id": str(workflow.destination_id),
        },
    )
    destination = db.get(PublishingDestination, workflow.destination_id)
    configured_action = str(workflow.input_json.get("publishing_action") or "default")
    schedule_actions = {
        "schedule_wordpress_draft": "create_draft",
        "schedule_wordpress_publish": "publish",
        "schedule_wordpress_update": "update",
        "schedule_shopify_draft": "create_draft",
        "schedule_shopify_update": "update_product",
        "schedule_shopify_activation": "activate_product",
        "schedule_shopify_archive": "archive_product",
    }
    schedule_at = workflow.input_json.get("schedule_at_local")
    if configured_action in schedule_actions:
        if not schedule_at or not workflow.input_json.get("schedule_timezone"):
            raise HTTPException(422, "Scheduled Workflow action requires local time and timezone.")
        expected_connector = (
            "wordpress" if configured_action.startswith("schedule_wordpress_") else "shopify"
        )
        if not destination or destination.connector_key != expected_connector:
            raise HTTPException(
                409,
                f"This Workflow action requires a {expected_connector.title()} destination.",
            )
        schedule = create_schedule(
            db,
            owner,
            ScheduleCreate(
                name=f"Workflow {workflow.id}",
                artifact_id=artifact.id,
                destination_id=workflow.destination_id,
                requested_action=cast(Any, schedule_actions[configured_action]),
                local_scheduled_at=datetime.fromisoformat(str(schedule_at)),
                timezone_name=str(workflow.input_json["schedule_timezone"]),
                schedule_type="one_time",
            ),
        )
        materialize_due_schedules(db)
        job = db.scalar(select(PublishingJob).where(PublishingJob.schedule_id == schedule.id))
        step.status = "waiting"
        step.paused_at = step.updated_at = now()
        step.output_reference_json = {
            "publishing_schedule_id": str(schedule.id),
            "publishing_job_id": str(job.id) if job else None,
        }
        wait = WorkflowPublishingWait(
            owner_id=owner.id,
            workflow_instance_id=workflow.id,
            workflow_step_execution_id=step.id,
            schedule_id=schedule.id,
            job_id=job.id if job else None,
            expected_terminal_state="succeeded",
            status="waiting",
            correlation_id=correlation_id(),
            created_at=now(),
            updated_at=now(),
        )
        db.add(wait)
        if job:
            job.workflow_instance_id = workflow.id
            job.correlation_id = wait.correlation_id
        workflow.status = "waiting_for_publishing"
        workflow.paused_at = workflow.updated_at = now()
        workflow.context_json = {
            **workflow.context_json,
            "publishing_schedule_id": str(schedule.id),
            "publishing_job_id": str(job.id) if job else None,
        }
        record_event(
            db,
            actor_id=owner.id,
            action="publishing.workflow_schedule_created",
            entity_type="workflow_instance",
            entity_id=workflow.id,
            metadata={"schedule_id": str(schedule.id), "job_id": str(job.id) if job else None},
        )
        record_event(
            db,
            actor_id=owner.id,
            action="publishing.workflow_wait_started",
            entity_type="workflow_instance",
            entity_id=workflow.id,
            metadata={"job_id": str(job.id) if job else None},
        )
        db.commit()
        return workflow_details(db, workflow)
    shopify_actions: dict[str, Literal["create_draft", "update", "activate", "archive"]] = {
        "default": "create_draft",
        "shopify_create_draft": "create_draft",
        "shopify_update_product": "update",
        "shopify_activate_product": "activate",
        "shopify_archive_product": "archive",
    }
    requested_action: Literal["create_draft", "publish", "update", "activate", "archive"] = (
        shopify_actions.get(configured_action, "create_draft")
        if destination and destination.connector_key == "shopify"
        else "publish"
    )
    result = create_execution(
        db,
        owner,
        CreateExecution(
            artifact_id=artifact.id,
            destination_id=workflow.destination_id,
            idempotency_key=f"wf:{workflow.id}:publish:{step.attempt_number}",
            action=requested_action,
        ),
    )
    workflow.context_json = {
        **workflow.context_json,
        "publishing_execution_id": str(result.id),
    }
    step.output_reference_json = {"publishing_execution_id": str(result.id)}
    finish_publish_step(
        db,
        owner,
        workflow,
        step,
        result.status,
        result.error_code,
        result.safe_error_message,
        result.retryable,
    )
    db.commit()
    return workflow_details(db, workflow)


def resume_publishing_waits(db: Session, job_id: uuid.UUID) -> int:
    job = db.get(PublishingJob, job_id)
    if not job or job.state not in {
        "succeeded",
        "failed",
        "dead_letter",
        "cancelled",
        "expired",
    }:
        return 0
    waits = list(
        db.scalars(
            select(WorkflowPublishingWait)
            .where(
                WorkflowPublishingWait.job_id == job_id,
                WorkflowPublishingWait.status.in_(["scheduled", "waiting", "running", "retrying"]),
            )
            .with_for_update(skip_locked=True)
        )
    )
    stamp = now()
    for wait in waits:
        workflow = db.get(WorkflowInstance, wait.workflow_instance_id)
        step = db.get(WorkflowStepExecution, wait.workflow_step_execution_id)
        if not workflow or not step:
            continue
        wait.completed_at = wait.updated_at = stamp
        if job.state == "succeeded":
            wait.status = "succeeded"
            step.status = "succeeded"
            step.completed_at = step.updated_at = stamp
            workflow.status = "completed"
            workflow.current_step_key = None
            workflow.completed_at = workflow.updated_at = stamp
            workflow.paused_at = None
            action = "publishing.workflow_wait_completed"
        else:
            wait.status = "dead_letter" if job.state == "dead_letter" else "failed"
            step.status = "failed"
            step.failed_at = step.updated_at = stamp
            step.error_code = job.last_error_code or f"publishing_job_{job.state}"
            step.safe_error_message = job.last_error_message or "Scheduled publishing failed."
            step.retryable = job.retryable
            workflow.status = "failed"
            workflow.failed_at = workflow.updated_at = stamp
            workflow.error_code = step.error_code
            workflow.safe_error_message = step.safe_error_message
            action = "publishing.workflow_wait_failed"
        record_event(
            db,
            actor_id=wait.owner_id,
            action=action,
            entity_type="workflow_instance",
            entity_id=workflow.id,
            metadata={"job_id": str(job.id), "state": job.state},
        )
    db.commit()
    return len(waits)


def resume_terminal_publishing_waits(db: Session) -> int:
    job_ids = [
        job_id
        for job_id in db.scalars(
            select(WorkflowPublishingWait.job_id)
            .join(PublishingJob, PublishingJob.id == WorkflowPublishingWait.job_id)
            .where(
                WorkflowPublishingWait.status.in_(["scheduled", "waiting", "running", "retrying"]),
                PublishingJob.state.in_(
                    ["succeeded", "failed", "dead_letter", "cancelled", "expired"]
                ),
            )
            .distinct()
        )
        if job_id is not None
    ]
    resumed = 0
    for job_id in job_ids:
        resumed += resume_publishing_waits(db, job_id)
    return resumed


def retry_workflow(db: Session, owner: User, workflow_id: uuid.UUID) -> WorkflowDetails:
    workflow = owned_workflow(db, owner.id, workflow_id, lock=True)
    step = latest_step(db, workflow.id)
    if workflow.status != "failed" or step is None or not step.retryable:
        raise HTTPException(409, "Workflow is not eligible for retry.")
    record_event(
        db,
        actor_id=owner.id,
        action="workflow.retry_requested",
        entity_type="workflow_instance",
        entity_id=workflow.id,
        metadata={"step_key": step.step_key, "attempt_number": step.attempt_number + 1},
    )
    if step.step_key == "generate_content":
        workflow.error_code = workflow.safe_error_message = None
        workflow.failed_at = None
        return run_generation(db, owner, workflow)
    if step.step_key != "publish_content":
        raise HTTPException(409, "Human approval cannot be mechanically retried.")
    publishing_id = workflow.context_json.get("publishing_execution_id")
    if not publishing_id:
        raise HTTPException(409, "Publishing execution reference is unavailable.")
    next_step = new_step(
        db,
        workflow,
        "publish_content",
        input_refs={"publishing_execution_id": str(publishing_id)},
    )
    workflow.status = "running"
    workflow.current_step_key = "publish_content"
    workflow.failed_at = None
    workflow.error_code = workflow.safe_error_message = None
    workflow.updated_at = now()
    result = retry_execution(db, owner, uuid.UUID(str(publishing_id)))
    next_step.output_reference_json = {"publishing_execution_id": str(result.id)}
    finish_publish_step(
        db,
        owner,
        workflow,
        next_step,
        result.status,
        result.error_code,
        result.safe_error_message,
        result.retryable,
    )
    db.commit()
    return workflow_details(db, workflow)


def cancel_workflow(db: Session, owner: User, workflow_id: uuid.UUID) -> WorkflowDetails:
    workflow = owned_workflow(db, owner.id, workflow_id, lock=True)
    if workflow.status not in {
        "draft",
        "waiting_for_approval",
        "waiting_for_publishing",
        "failed",
    }:
        raise HTTPException(409, "Workflow cannot be cancelled in its current state.")
    stamp = now()
    if workflow.status == "waiting_for_publishing":
        waits = list(
            db.scalars(
                select(WorkflowPublishingWait).where(
                    WorkflowPublishingWait.workflow_instance_id == workflow.id,
                    WorkflowPublishingWait.status.in_(
                        ["scheduled", "waiting", "running", "retrying"]
                    ),
                )
            )
        )
        for wait in waits:
            job = db.get(PublishingJob, wait.job_id)
            if job and job.state not in {
                "succeeded",
                "failed",
                "cancelled",
                "expired",
                "dead_letter",
            }:
                job.state = (
                    "cancel_requested" if job.state in {"claimed", "running"} else "cancelled"
                )
                if job.state == "cancelled":
                    job.completed_at = stamp
                job.updated_at = stamp
            wait.status = "cancelled"
            wait.completed_at = wait.updated_at = stamp
    for step in db.scalars(
        select(WorkflowStepExecution).where(
            WorkflowStepExecution.workflow_instance_id == workflow.id,
            WorkflowStepExecution.status.in_(["pending", "waiting"]),
        )
    ):
        step.status = "cancelled"
        step.cancelled_at = step.updated_at = stamp
    workflow.status = "cancelled"
    workflow.cancelled_at = workflow.updated_at = stamp
    workflow.current_step_key = None
    record_event(
        db,
        actor_id=owner.id,
        action="workflow.cancelled",
        entity_type="workflow_instance",
        entity_id=workflow.id,
        metadata={"product_id": str(workflow.product_id)},
    )
    db.commit()
    return workflow_details(db, workflow)


def fail_workflow(
    db: Session,
    workflow: WorkflowInstance,
    code: str,
    message: str,
    *,
    retryable: bool,
    step: WorkflowStepExecution,
) -> None:
    workflow.status = "failed"
    workflow.current_step_key = step.step_key
    workflow.failed_at = workflow.updated_at = now()
    workflow.error_code = code
    workflow.safe_error_message = message
    record_event(
        db,
        actor_id=workflow.owner_id,
        action="workflow.step_failed",
        entity_type="workflow_instance",
        entity_id=workflow.id,
        metadata={
            "step_key": step.step_key,
            "attempt_number": step.attempt_number,
            "retryable": retryable,
        },
    )


def record_step_success(
    db: Session, workflow: WorkflowInstance, step: WorkflowStepExecution
) -> None:
    record_event(
        db,
        actor_id=workflow.owner_id,
        action="workflow.step_succeeded",
        entity_type="workflow_instance",
        entity_id=workflow.id,
        metadata={"step_key": step.step_key, "attempt_number": step.attempt_number},
    )


def finish_publish_step(
    db: Session,
    owner: User,
    workflow: WorkflowInstance,
    step: WorkflowStepExecution,
    status: str,
    error_code: str | None,
    safe_message: str | None,
    retryable: bool,
) -> None:
    stamp = now()
    if status == "succeeded":
        step.status = "succeeded"
        step.completed_at = step.updated_at = stamp
        record_step_success(db, workflow, step)
        workflow.status = "completed"
        workflow.current_step_key = None
        workflow.completed_at = workflow.updated_at = stamp
        workflow.error_code = workflow.safe_error_message = None
        record_event(
            db,
            actor_id=owner.id,
            action="workflow.completed",
            entity_type="workflow_instance",
            entity_id=workflow.id,
            metadata={
                "publishing_execution_id": str(workflow.context_json["publishing_execution_id"])
            },
        )
        return
    step.status = "failed"
    step.failed_at = step.updated_at = stamp
    step.error_code = error_code
    step.safe_error_message = safe_message
    step.retryable = retryable
    fail_workflow(
        db,
        workflow,
        error_code or "publishing_failed",
        safe_message or "Publishing failed.",
        retryable=retryable,
        step=step,
    )


def list_workflows(
    db: Session,
    owner_id: uuid.UUID,
    *,
    brand_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    destination_id: uuid.UUID | None = None,
    status: str | None = None,
    current_step: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    retryable: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> WorkflowPage:
    filters = [WorkflowInstance.owner_id == owner_id]
    for column, value in (
        (WorkflowInstance.brand_id, brand_id),
        (WorkflowInstance.product_id, product_id),
        (WorkflowInstance.destination_id, destination_id),
        (WorkflowInstance.status, status),
        (WorkflowInstance.current_step_key, current_step),
    ):
        if value is not None:
            filters.append(column == value)
    if date_from:
        filters.append(WorkflowInstance.created_at >= date_from)
    if date_to:
        filters.append(WorkflowInstance.created_at <= date_to)
    base = select(WorkflowInstance).where(*filters)
    if retryable is not None:
        values = db.scalars(
            base.order_by(WorkflowInstance.created_at.desc(), WorkflowInstance.id.desc())
        ).all()
        matching = [
            value
            for value in (workflow_details(db, item) for item in values)
            if value.retryable is retryable
        ]
        total = len(matching)
        details = matching[(page - 1) * page_size : page * page_size]
    else:
        values = db.scalars(
            base.order_by(WorkflowInstance.created_at.desc(), WorkflowInstance.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        details = [workflow_details(db, value) for value in values]
        total = db.scalar(select(func.count()).select_from(WorkflowInstance).where(*filters)) or 0
    return WorkflowPage(
        items=details,
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )
