from __future__ import annotations

import pytest
import test_ai_integration
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_ai_integration import setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchChange,
)
from vayujit_api.intelligence.external_intelligence import verify_external_evidence

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration

REJECTED_CASES = ("UNVERIFIED", "REJECTED", "STALE", "EXPIRED", "WRONG_OWNER", "DISCOVERY_ONLY")


@pytest.mark.parametrize("state", REJECTED_CASES)
def test_rejected_indiamart_data_has_zero_change_and_alert_delta(
    client: TestClient, state: str
) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        before_changes = db.scalar(select(func.count()).select_from(AutonomousResearchChange)) or 0
        before_alerts = db.scalar(select(func.count()).select_from(AutonomousResearchAlert)) or 0
        freshness = state if state in {"STALE", "EXPIRED"} else "FRESH"
        candidate: dict[str, object] = {
            "owner_id": "other-owner" if state == "WRONG_OWNER" else str(owner.id),
            "source_profile": "indiamart-local",
            "fetch_id": f"fetch-{state.lower()}",
            "search_result_id": f"result-{state.lower()}",
            "requested_url": "https://www.indiamart.com/disposable",
            "final_url": "https://www.indiamart.com/disposable",
            "content_hash": f"hash-{state.lower()}",
            "correlation_id": f"corr-{state.lower()}",
            "provider": "INDIAMART",
            "content": "normalized claim",
            "freshness_status": freshness,
            "verification_status": (
                "UNVERIFIED" if state in {"UNVERIFIED", "REJECTED"} else "SUPPORTED"
            ),
            "classification": "DISCOVERY_ONLY" if state == "DISCOVERY_ONLY" else "REJECTED",
        }
        if state in {"UNVERIFIED", "REJECTED"}:
            candidate["blocked"] = True
        decision = verify_external_evidence(candidate, expected_owner_id=str(owner.id))
        if state == "DISCOVERY_ONLY":
            assert decision["verification_state"] == "SUPPORTED"
        else:
            assert decision["verification_state"] == "REJECTED"
        db.commit()
        after_changes = db.scalar(select(func.count()).select_from(AutonomousResearchChange)) or 0
        after_alerts = db.scalar(select(func.count()).select_from(AutonomousResearchAlert)) or 0
        assert after_changes == before_changes
        assert after_alerts == before_alerts
