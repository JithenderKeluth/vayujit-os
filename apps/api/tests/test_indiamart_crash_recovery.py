from __future__ import annotations

import pytest
import test_ai_integration
from fastapi.testclient import TestClient
from helpers.indiamart_certification import mission, task
from sqlalchemy import func, select
from test_ai_integration import setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.external_durability import (
    checkpoint,
    claim_execution,
    execution_identity,
)
from vayujit_api.intelligence.external_models import ExternalExecution

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "stage",
    (
        "BEFORE_PROVIDER",
        "AFTER_PROVIDER",
        "AFTER_RESULT",
        "AFTER_EVIDENCE",
        "AFTER_CHANGE",
        "AFTER_ALERT",
    ),
)
def test_indiamart_crash_checkpoint_recovery_is_duplicate_free(
    client: TestClient, stage: str
) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        parent = mission(db, owner, f"crash:{stage}")
        worker = task(db, owner, parent)
        identity = execution_identity(
            "indiamart", owner_id=owner.id, mission_id=parent.id, task_id=worker.id, value=stage
        )
        first, created = claim_execution(
            db,
            owner=owner,
            kind="search",
            identity_key=identity,
            provider="INDIAMART",
            mission_id=parent.id,
            task_id=worker.id,
            correlation_id=parent.correlation_id,
        )
        assert created is True
        checkpoint(db, first, stage, status="CHECKPOINTED")
        db.commit()
        second, created_again = claim_execution(
            db,
            owner=owner,
            kind="search",
            identity_key=identity,
            provider="INDIAMART",
            mission_id=parent.id,
            task_id=worker.id,
            correlation_id=parent.correlation_id,
        )
        db.commit()
        assert created_again is False
        assert second.id == first.id
        assert second.checkpoint == stage
        assert db.scalar(select(func.count()).select_from(ExternalExecution)) == 1
