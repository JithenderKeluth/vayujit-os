# mypy: ignore-errors
from __future__ import annotations

import pytest
from sqlalchemy import select
from website_postgres_fixture import run_website_research

from vayujit_api.audit.models import AuditEvent
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchChange,
)
from vayujit_api.intelligence.website_models import WebsiteObservation

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_change_and_alert_e2e_replays_without_duplicates(client, db_session) -> None:
    run_website_research(
        client,
        content=(
            "Company Name: Alert Fixture. Address: 10 Factory Road. "
            "sales@alert.example.org Product: Fixture Tray. privacy terms shipping"
        ),
        key="alert-first",
    )
    prior = list(db_session.scalars(select(WebsiteObservation)))
    for item in prior:
        if item.observation_type == "RISK":
            item.verification = "SUPPORTED"
    db_session.commit()
    run_website_research(
        client,
        content="Company Name: Alert Fixture. Product: Fixture Tray.",
        key="alert-second",
    )
    changes = list(db_session.scalars(select(AutonomousResearchChange)))
    alerts = list(db_session.scalars(select(AutonomousResearchAlert)))
    assert len(changes) == 1
    assert changes[0].change_type == "risk"
    assert len(alerts) == 1
    assert alerts[0].severity == "REQUIRES_REVIEW"
    count = len(changes)
    run_website_research(
        client,
        content="Company Name: Alert Fixture. Product: Fixture Tray.",
        key="alert-second",
    )
    assert len(list(db_session.scalars(select(AutonomousResearchChange)))) == count
    assert len(list(db_session.scalars(select(AuditEvent)))) >= 1


def test_change_matrix_and_alert_matrix_are_idempotent(client, db_session, owner) -> None:
    from vayujit_api.intelligence.autonomous_models import (
        AutonomousResearchAlert,
        AutonomousResearchMission,
    )
    from vayujit_api.intelligence.autonomous_service import record_change

    seeded = run_website_research(
        client,
        content="Company Name: Matrix Change Fixture. Product: Fixture Tray.",
        key="matrix-change-seed",
    )
    mission = db_session.get(AutonomousResearchMission, seeded["mission_id"])
    assert mission is not None
    change_types = [
        "price",
        "moq",
        "lead_time",
        "certification",
        "business_identity",
        "capability",
        "facility",
        "availability",
        "risk",
    ]
    for index, change_type in enumerate(change_types, start=1):
        result = record_change(
            db_session,
            owner,
            mission,
            change_type=change_type,
            previous={"value": index},
            current={"value": index + 1},
            evidence_ids=[f"website-evidence-{index}"],
        )
        assert result is not None
    changes = list(
        db_session.scalars(
            select(AutonomousResearchChange).where(
                AutonomousResearchChange.mission_id == mission.id
            )
        )
    )
    assert len(changes) == 9
    assert {item.change_type for item in changes} == set(change_types)
    linked = list(
        db_session.scalars(
            select(AutonomousResearchAlert).where(
                AutonomousResearchAlert.mission_id == mission.id,
                AutonomousResearchAlert.lineage["change_id"].as_string().is_not(None),
            )
        )
    )
    assert all(item.lineage.get("correlation_id") == mission.correlation_id for item in linked)
    before = len(changes)
    for index, change_type in enumerate(change_types, start=1):
        record_change(
            db_session,
            owner,
            mission,
            change_type=change_type,
            previous={"value": index},
            current={"value": index + 1},
            evidence_ids=[f"website-evidence-{index}"],
        )
    assert (
        len(
            list(
                db_session.scalars(
                    select(AutonomousResearchChange).where(
                        AutonomousResearchChange.mission_id == mission.id
                    )
                )
            )
        )
        == before
    )
    for index, change_type in enumerate(change_types, start=1):
        db_session.add(
            AutonomousResearchAlert(
                owner_id=owner.id,
                mission_id=mission.id,
                alert_type=f"matrix_{change_type}",
                severity="REQUIRES_REVIEW",
                title=f"{change_type} review",
                detail="bounded fixture",
                identity_key=f"alert-matrix:{change_type}:{index}",
            )
        )
    db_session.commit()
    alerts = list(
        db_session.scalars(
            select(AutonomousResearchAlert).where(
                AutonomousResearchAlert.mission_id == mission.id,
                AutonomousResearchAlert.identity_key.like("alert-matrix:%"),
            )
        )
    )
    assert len(alerts) == 9
    before_alerts = len(alerts)
    for alert in alerts:
        assert (
            db_session.scalar(
                select(AutonomousResearchAlert).where(
                    AutonomousResearchAlert.identity_key == alert.identity_key
                )
            )
            is not None
        )
    assert (
        len(
            list(
                db_session.scalars(
                    select(AutonomousResearchAlert).where(
                        AutonomousResearchAlert.mission_id == mission.id,
                        AutonomousResearchAlert.identity_key.like("alert-matrix:%"),
                    )
                )
            )
        )
        == before_alerts
    )
