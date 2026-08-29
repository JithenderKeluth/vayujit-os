# mypy: ignore-errors
from __future__ import annotations

import pytest
from sqlalchemy import select
from website_postgres_fixture import run_website_research

from vayujit_api.intelligence.website_models import WebsiteObservation

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_postgres_t1_t2_append_and_replay(client, db_session) -> None:
    replay_key = "matrix-replay"
    first = run_website_research(
        client, content="Company Name: Matrix Fixture. Product: Fixture Tray. MOQ: 100 units."
    )
    before = list(db_session.scalars(select(WebsiteObservation)))
    second = run_website_research(
        client,
        content="Company Name: Matrix Fixture. Product: Fixture Tray. MOQ: 1000 units.",
        key=replay_key,
    )
    after = list(db_session.scalars(select(WebsiteObservation)))
    assert first["mission_id"] != second["mission_id"]
    assert len(after) > len(before)
    t2 = [item for item in after if str(item.mission_id) == second["mission_id"]]
    assert any(item.previous_observation_id is not None for item in t2)

    count_before_replay = len(after)
    replay = run_website_research(
        client,
        content="Company Name: Matrix Fixture. Product: Fixture Tray. MOQ: 1000 units.",
        key=replay_key,
    )
    assert replay["mission_id"] == second["mission_id"]
    assert len(list(db_session.scalars(select(WebsiteObservation)))) == count_before_replay


def test_all_ten_observation_types_append_and_replay(client, db_session, owner) -> None:
    run_website_research(client, content="Company Name: Ten Type Fixture. Product: Fixture Tray.")
    seed = db_session.scalar(select(WebsiteObservation))
    assert seed is not None
    types = [
        "PRICE",
        "MOQ",
        "LEAD_TIME",
        "BUSINESS_IDENTITY",
        "CONTACT",
        "CAPABILITY",
        "FACILITY",
        "CERTIFICATION",
        "AVAILABILITY",
        "RISK",
    ]
    for observation_type in types:
        first = WebsiteObservation(
            owner_id=owner.id,
            candidate_id=seed.candidate_id,
            observation_type=observation_type,
            claim_type=observation_type.lower(),
            normalized_value={"value": f"{observation_type}-T1"},
            source_provided_state="SOURCE_PROVIDED",
            verification="SUPPORTED",
            freshness="FRESH",
            confidence=0.9,
            content_hash=f"{observation_type}-T1",
            evidence_ids=[f"{observation_type}-T1"],
            observation_identity=f"matrix:{observation_type}:T1",
            domain="example.org",
            page_url="https://example.org",
            correlation_id="matrix",
        )
        db_session.add(first)
        db_session.flush()
        second = WebsiteObservation(
            owner_id=owner.id,
            candidate_id=seed.candidate_id,
            observation_type=observation_type,
            claim_type=observation_type.lower(),
            normalized_value={"value": f"{observation_type}-T2"},
            source_provided_state="SOURCE_PROVIDED",
            verification="SUPPORTED",
            freshness="FRESH",
            confidence=0.9,
            content_hash=f"{observation_type}-T2",
            evidence_ids=[f"{observation_type}-T2"],
            previous_observation_id=first.id,
            observation_identity=f"matrix:{observation_type}:T2",
            domain="example.org",
            page_url="https://example.org",
            correlation_id="matrix",
        )
        db_session.add(second)
        db_session.flush()
    before_replay = len(list(db_session.scalars(select(WebsiteObservation))))
    for observation_type in types:
        assert (
            len(
                list(
                    db_session.scalars(
                        select(WebsiteObservation).where(
                            WebsiteObservation.observation_type == observation_type,
                            WebsiteObservation.observation_identity.like(
                                f"matrix:{observation_type}:%"
                            ),
                        )
                    )
                )
            )
            == 2
        )
        current = db_session.scalar(
            select(WebsiteObservation).where(
                WebsiteObservation.observation_type == observation_type,
                WebsiteObservation.observation_identity == f"matrix:{observation_type}:T2",
            )
        )
        assert current is not None and current.previous_observation_id is not None
    after_replay = len(list(db_session.scalars(select(WebsiteObservation))))
    assert after_replay - before_replay == 0
