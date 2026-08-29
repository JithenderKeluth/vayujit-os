# mypy: ignore-errors
from __future__ import annotations

import pytest
from sqlalchemy import select
from website_postgres_fixture import run_website_research

from vayujit_api.intelligence.website_models import WebsiteObservation

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_risk_observation_history_is_append_only(client, db_session) -> None:
    run_website_research(
        client,
        content=(
            "Company Name: Risk Fixture. Address: 10 Factory Road. "
            "sales@risk.example.org Product: Fixture Tray."
        ),
    )
    run_website_research(client, content="Company Name: Risk Fixture. Product: Fixture Tray.")
    risks = [
        item
        for item in db_session.scalars(select(WebsiteObservation))
        if item.observation_type == "RISK"
    ]
    assert len(risks) == 2
    assert risks[1].previous_observation_id == risks[0].id
    assert risks[1].normalized_value != risks[0].normalized_value


def test_risk_severity_lifecycle_preserves_four_states(db_session, owner) -> None:
    import uuid

    from vayujit_api.intelligence.website_models import WebsiteObservation

    previous = None
    for step, (severity, status) in enumerate(
        [("LOW", "ACTIVE"), ("MEDIUM", "ACTIVE"), ("HIGH", "ACTIVE"), ("HIGH", "RESOLVED")],
        start=1,
    ):
        row = WebsiteObservation(
            owner_id=owner.id,
            observation_type="RISK",
            claim_type="UNDOCUMENTED_CERTIFICATION",
            normalized_value={
                "risk": "UNDOCUMENTED_CERTIFICATION",
                "severity": severity,
                "status": status,
            },
            source_provided_state="SOURCE_PROVIDED",
            verification="SUPPORTED",
            freshness="FRESH",
            confidence=0.9,
            content_hash=str(uuid.uuid4()),
            evidence_ids=[],
            previous_observation_id=previous.id if previous else None,
            observation_identity=f"risk-lifecycle:undocumented-certification:{step}",
            domain="example.org",
            page_url="https://example.org",
            correlation_id="risk-lifecycle",
        )
        db_session.add(row)
        db_session.flush()
        previous = row
    rows = list(
        db_session.scalars(
            select(WebsiteObservation)
            .where(WebsiteObservation.claim_type == "UNDOCUMENTED_CERTIFICATION")
            .order_by(WebsiteObservation.created_at)
        )
    )
    assert len(rows) == 4
    assert rows[-1].normalized_value["status"] == "RESOLVED"
    assert rows[-1].normalized_value["severity"] == "HIGH"
    assert all(rows[index].previous_observation_id == rows[index - 1].id for index in range(1, 4))
