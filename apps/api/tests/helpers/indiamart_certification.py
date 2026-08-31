from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchTask,
)


def mission(
    db: Session, owner: User, key: str = "indiamart-certification"
) -> AutonomousResearchMission:
    value = AutonomousResearchMission(
        owner_id=owner.id,
        mission_type="SUPPLIER_DISCOVERY",
        goal="IndiaMART certification fixture",
        market="IN",
        category="outdoors",
        provider_mode="LOCAL_DETERMINISTIC",
        correlation_id=uuid.uuid4().hex,
        idempotency_key=key,
        status="DRAFT",
    )
    db.add(value)
    db.flush()
    return value


def task(db: Session, owner: User, parent: AutonomousResearchMission) -> AutonomousResearchTask:
    value = AutonomousResearchTask(
        owner_id=owner.id,
        mission_id=parent.id,
        task_type="discover_suppliers",
        source_class="SUPPLIER",
        idempotency_key=f"task:{parent.id}",
        correlation_id=parent.correlation_id,
    )
    db.add(value)
    db.flush()
    return value


def evidence(
    db: Session,
    owner: User,
    parent: AutonomousResearchMission,
    worker: AutonomousResearchTask,
    *,
    reference: str,
    value: object,
    verification: str = "SUPPORTED",
    freshness: str = "FRESH",
) -> AutonomousResearchEvidence:
    stamp = datetime.now(UTC)
    row = AutonomousResearchEvidence(
        owner_id=owner.id,
        mission_id=parent.id,
        task_id=worker.id,
        source_class="SUPPLIER",
        source_reference=reference,
        retrieval_identity=f"indiamart:{parent.id}:{reference}",
        content_type="application/json",
        normalized_value={"value": value},
        content_hash=uuid.uuid5(uuid.NAMESPACE_URL, reference).hex,
        verification_status=verification,
        freshness_status=freshness,
        verification_reason="deterministic certification fixture",
        source_profile="indiamart-local",
        provider="INDIAMART",
        canonical_url=f"https://www.indiamart.com/{reference}",
        domain="www.indiamart.com",
        lineage={
            "mission_id": str(parent.id),
            "task_id": str(worker.id),
            "correlation_id": parent.correlation_id,
        },
        confidence=0.8,
        evidence_class="SUPPLIER",
        observed_at=stamp,
        retrieved_at=stamp,
    )
    db.add(row)
    db.flush()
    return row
