from __future__ import annotations

import os

os.environ["VAYUJIT_INTELLIGENCE_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_RESEARCH_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_SEARCH_PROVIDER_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_WEB_FETCH_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_PROVIDER_MODE"] = "LOCAL_FIXTURE"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_APPROVED_DOMAINS"] = "example.org"


import uuid

import pytest
import test_ai_integration as integration
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.external_durability import (
    checkpoint,
    claim_execution,
    execution_identity,
)
from vayujit_api.intelligence.external_models import ExternalExecution

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_execution_checkpoints_survive_replay(client) -> None:
    setup_context(client)
    first = client.post(
        "/api/v1/intelligence/external/search",
        json={"query": "checkpoint", "allowed_domains": ["example.org"]},
        headers=ORIGIN,
    )
    assert first.status_code == 200, first.text
    assert integration.factory is not None
    with integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        rows = list(
            db.scalars(select(ExternalExecution).where(ExternalExecution.owner_id == owner.id))
        )
        assert len(rows) == 1
        assert rows[0].checkpoint == "TERMINAL"
        assert rows[0].status == "COMPLETED"
        assert rows[0].provider_calls == 1
        checkpoint(db, rows[0], "TERMINAL", status="COMPLETED")
        db.commit()
        identity = execution_identity(
            "search", owner_id=owner.id, mission_id=None, task_id=None, value="replay"
        )
        claimed, created = claim_execution(
            db,
            owner=owner,
            kind="search",
            identity_key=identity,
            provider="fixture",
            mission_id=None,
            task_id=None,
            correlation_id=str(uuid.uuid4()),
        )
        assert created is True
        checkpoint(db, claimed, "BEFORE_PROVIDER")
        db.rollback()
