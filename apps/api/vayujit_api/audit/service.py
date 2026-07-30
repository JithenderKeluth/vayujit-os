import uuid

from sqlalchemy.orm import Session

from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.observability import correlation_id
from vayujit_api.identity.service import now


def record_event(
    db: Session,
    *,
    actor_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    metadata: dict[str, object] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=metadata or {},
        correlation_id=correlation_id(),
        occurred_at=now(),
    )
    db.add(event)
    return event
