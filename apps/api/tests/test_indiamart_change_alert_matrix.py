from __future__ import annotations

import pytest
import test_ai_integration
from fastapi.testclient import TestClient
from helpers.indiamart_certification import evidence, mission, task
from sqlalchemy import func, select
from test_ai_integration import setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchChange,
)
from vayujit_api.intelligence.autonomous_service import record_change
from vayujit_api.intelligence.external_intelligence import (
    record_external_alert,
    record_external_change,
)

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration

CHANGE_FIELDS = (
    "PRICE",
    "MOQ",
    "LEAD_TIME",
    "AVAILABILITY",
    "BUSINESS_IDENTITY",
    "VERIFICATION_CLAIM",
    "LISTING_STATUS",
)


@pytest.mark.parametrize("field", CHANGE_FIELDS)
def test_indiamart_change_matrix_persists_one_replay_safe_change(
    client: TestClient, field: str
) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        parent = mission(db, owner, f"change:{field}")
        worker = task(db, owner, parent)
        accepted = evidence(db, owner, parent, worker, reference=f"change-{field}", value=field)
        previous = {"value": f"{field}-T1"}
        current = {"value": f"{field}-T2"}
        before = db.scalar(select(func.count()).select_from(AutonomousResearchChange)) or 0
        row = record_external_change(
            db,
            parent,
            change_type=field,
            entity_id=f"listing-{field}",
            field_key=field,
            previous=previous,
            current=current,
            evidence_ids=[str(accepted.id)],
        )
        assert row is not None
        assert row.owner_id == owner.id
        assert row.correlation_id == parent.correlation_id
        assert row.previous_value == previous
        assert row.current_value == current
        assert row.evidence_ids == [str(accepted.id)]
        db.commit()
        replay = record_external_change(
            db,
            parent,
            change_type=field,
            entity_id=f"listing-{field}",
            field_key=field,
            previous=previous,
            current=current,
            evidence_ids=[str(accepted.id)],
        )
        db.commit()
        after = db.scalar(select(func.count()).select_from(AutonomousResearchChange)) or 0
        assert replay is not None and replay.id == row.id
        assert after - before == 1


@pytest.mark.parametrize(
    "alert_type",
    (
        "material_price_change",
        "material_moq_change",
        "material_lead_time_change",
        "listing_removed",
        "verification_claim_changed",
        "business_identity_conflict",
    ),
)
def test_indiamart_alert_matrix_replays_without_duplicates(
    client: TestClient, alert_type: str
) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        parent = mission(db, owner, f"alert:{alert_type}")
        before = db.scalar(select(func.count()).select_from(AutonomousResearchAlert)) or 0
        first = record_external_alert(
            db,
            parent,
            alert_type=alert_type,
            title=f"IndiaMART {alert_type}",
            detail="Deterministic evidence requires human review.",
            identity=f"listing:{alert_type}",
            severity="REQUIRES_REVIEW",
            lineage={"correlation_id": parent.correlation_id},
        )
        db.commit()
        replay = record_external_alert(
            db,
            parent,
            alert_type=alert_type,
            title=f"IndiaMART {alert_type}",
            detail="Deterministic evidence requires human review.",
            identity=f"listing:{alert_type}",
            severity="REQUIRES_REVIEW",
            lineage={"correlation_id": parent.correlation_id},
        )
        db.commit()
        later = record_external_alert(
            db,
            parent,
            alert_type=alert_type,
            title=f"IndiaMART {alert_type}",
            detail="A distinct later observation requires review.",
            identity=f"listing:{alert_type}:later",
            severity="REQUIRES_REVIEW",
        )
        db.commit()
        after = db.scalar(select(func.count()).select_from(AutonomousResearchAlert)) or 0
        assert first.id == replay.id
        assert later.id != first.id
        assert after - before == 2


def test_change_service_emits_material_alert_and_replays(client: TestClient) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        parent = mission(db, owner, "change-service-alert")
        worker = task(db, owner, parent)
        accepted = evidence(db, owner, parent, worker, reference="material-price", value=100)
        row = record_change(
            db,
            owner,
            parent,
            change_type="price",
            previous={"value": 100},
            current={"value": 130},
            evidence_ids=[str(accepted.id)],
        )
        assert row is not None and row.material is True
        alerts = list(
            db.scalars(
                select(AutonomousResearchAlert).where(
                    AutonomousResearchAlert.mission_id == parent.id
                )
            )
        )
        assert len(alerts) == 1
