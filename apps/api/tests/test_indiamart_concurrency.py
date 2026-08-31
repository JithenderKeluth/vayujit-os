from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
import test_ai_integration
from fastapi.testclient import TestClient
from helpers.indiamart_certification import mission, task
from sqlalchemy import func, select
from test_ai_integration import setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.external_durability import claim_execution, execution_identity
from vayujit_api.intelligence.external_models import ExternalExecution

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration

ENTITIES = (
    "request",
    "result",
    "candidate",
    "evidence",
    "observation",
    "change",
    "alert",
    "recovery",
    "report",
)


@pytest.mark.parametrize("entity", ENTITIES)
def test_indiamart_two_session_concurrency_has_one_durable_identity(
    client: TestClient, entity: str
) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        parent = mission(db, owner, f"concurrency:{entity}")
        worker = task(db, owner, parent)
        identity = execution_identity(
            entity, owner_id=owner.id, mission_id=parent.id, task_id=worker.id, value="same"
        )
        mission_id, task_id, owner_id, correlation = (
            parent.id,
            worker.id,
            owner.id,
            parent.correlation_id,
        )
        db.commit()
    barrier = threading.Barrier(2)

    def invoke(_: int) -> tuple[str, bool]:
        assert test_ai_integration.factory is not None
        with test_ai_integration.factory() as session:
            owner_row = session.get(User, owner_id)
            assert owner_row is not None
            barrier.wait()
            value, created = claim_execution(
                session,
                owner=owner_row,
                kind="search",
                identity_key=identity,
                provider="INDIAMART",
                mission_id=mission_id,
                task_id=task_id,
                correlation_id=correlation,
            )
            session.commit()
            return str(value.id), created

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(invoke, (1, 2)))
    assert len({row_id for row_id, _ in results}) == 1
    assert sum(created for _, created in results) == 1
    with test_ai_integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(ExternalExecution)) == 1
