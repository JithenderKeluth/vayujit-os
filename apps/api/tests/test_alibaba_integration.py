import uuid

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.config import Settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence.alibaba import provider_preflight
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchTask,
)

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)


def test_alibaba_local_discovery_uses_runtime_and_replays(client):
    context = setup_context(client)
    payload = {
        "query": "insulated bottle",
        "product_id": context["product"]["id"],
        "country_code": "CN",
        "result_limit": 2,
        "idempotency_key": "alibaba-cert-001",
    }
    first = client.post("/api/v1/intelligence/alibaba/discover", json=payload, headers=ORIGIN)
    assert first.status_code == 200, first.text
    body = first.json()
    assert len(body["results"]) == 2
    assert all(
        item["provider"] == "ALIBABA" and item["classification"] == "DISCOVERY_ONLY"
        for item in body["results"]
    )
    replay = client.post("/api/v1/intelligence/alibaba/discover", json=payload, headers=ORIGIN)
    assert replay.status_code == 200
    assert replay.json() == body
    assert client.get("/api/v1/intelligence/alibaba/discoveries", headers=ORIGIN).status_code == 200
    assert client.get("/api/v1/intelligence/alibaba/operations", headers=ORIGIN).status_code == 200
    assert client.get("/api/v1/intelligence/alibaba/integrity", headers=ORIGIN).status_code == 200


def test_alibaba_modes_are_fail_closed_without_external_calls():
    assert provider_preflight(Settings(alibaba_mode="DISABLED"))["status"] == "DISABLED"
    assert (
        provider_preflight(Settings(alibaba_enabled=True, alibaba_mode="LOCAL_FIXTURE"))["status"]
        == "READY"
    )
    assert (
        provider_preflight(
            Settings(
                alibaba_enabled=True,
                alibaba_mode="LIVE_READ_ONLY",
                alibaba_base_url="https://example.invalid",
            )
        )["status"]
        == "NOT_CONFIGURED"
    )


def test_alibaba_evidence_handoff_and_operational_projections(client):
    context = setup_context(client)
    discovery = client.post(
        "/api/v1/intelligence/alibaba/discover",
        json={"query": "handoff bottle", "product_id": context["product"]["id"], "result_limit": 1},
        headers=ORIGIN,
    )
    assert discovery.status_code == 200, discovery.text
    body = discovery.json()
    result_id = body["results"][0]["id"]
    for path in (
        "/api/v1/intelligence/alibaba/operations/summary",
        f"/api/v1/intelligence/alibaba/product-channel/{context['product']['id']}",
        "/api/v1/intelligence/alibaba/calendar",
        "/api/v1/intelligence/alibaba/report",
        "/api/v1/intelligence/alibaba/storage/inventory",
        "/api/v1/intelligence/alibaba/integrity",
        "/api/v1/operations/intelligence/projection",
        "/api/v1/intelligence/system-doctor",
    ):
        response = client.get(path, headers=ORIGIN)
        assert response.status_code == 200, f"{path}: {response.text}"
    assert (
        client.get("/api/v1/intelligence/system-doctor", headers=ORIGIN).json()["checks"][
            "alibaba"
        ]["provider"]
        == "ALIBABA"
    )

    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        mission = AutonomousResearchMission(
            owner_id=owner.id,
            mission_type="SUPPLIER_DISCOVERY",
            goal="Alibaba evidence handoff",
            market="CN",
            category="outdoors",
            provider_mode="LOCAL_DETERMINISTIC",
            correlation_id=uuid.uuid4().hex,
            idempotency_key="alibaba-handoff-mission",
            status="DRAFT",
        )
        db.add(mission)
        db.flush()
        task = AutonomousResearchTask(
            owner_id=owner.id,
            mission_id=mission.id,
            task_type="discover_suppliers",
            source_class="ALIBABA_DISCOVERY",
            idempotency_key="alibaba-handoff-task",
            correlation_id=mission.correlation_id,
        )
        db.add(task)
        db.commit()
        mission_id, task_id = str(mission.id), str(task.id)

    payload = {"mission_id": mission_id, "task_id": task_id}
    handoff = client.post(
        f"/api/v1/intelligence/alibaba/discoveries/{result_id}/evidence",
        json=payload,
        headers=ORIGIN,
    )
    assert handoff.status_code == 200, handoff.text
    handoff_body = handoff.json()
    assert handoff_body["provider"] == "ALIBABA"
    assert handoff_body["verification_status"] in {"SUPPORTED", "VERIFIED"}
    assert handoff_body["lineage"]["mission_id"] == mission_id
    replay = client.post(
        f"/api/v1/intelligence/alibaba/discoveries/{result_id}/evidence",
        json=payload,
        headers=ORIGIN,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["idempotent_reuse"] is True
    with test_ai_integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(AutonomousResearchEvidence)) == 1
        actions = set(db.scalars(select(AuditEvent.action)).all())
        assert "alibaba.discovery.evidence_handoff" in actions
