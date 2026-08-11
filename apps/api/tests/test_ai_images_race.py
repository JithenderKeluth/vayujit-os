from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
import test_ai_integration
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.ai.bulk_models import AIStudioBulkOperation, AIStudioBulkOutput
from vayujit_api.ai.image_bulk_service import cancel_image_bulk, retry_image_bulk
from vayujit_api.ai.image_models import AIImageOutput
from vayujit_api.ai.studio_models import AIStudioJob
from vayujit_api.identity.models import User

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_bulk_retry_cancel_race_has_one_legal_durable_state(client) -> None:
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/images/bulk",
        json={
            "product_ids": [context["product"]["id"]],
            "channels": ["amazon"],
            "operation": "generate_product_image",
            "width": 64,
            "height": 64,
            "idempotency_key": "bulk-retry-cancel-race",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        operation = db.get(AIStudioBulkOperation, bulk_id)
        assert owner is not None and operation is not None
        output = db.scalar(
            select(AIStudioBulkOutput).where(AIStudioBulkOutput.bulk_operation_id == operation.id)
        )
        assert output is not None
        job = db.get(AIStudioJob, output.job_id)
        assert job is not None
        job.state = "failed"
        job.retryable = True
        job.failure_category = "provider_unavailable"
        job.last_error_code = "provider_unavailable"
        job.safe_error_message = "The local image provider is temporarily unavailable."
        db.commit()
        output_id = output.id

    def retry() -> tuple[int, int]:
        assert test_ai_integration.factory is not None
        with test_ai_integration.factory() as db:
            owner = db.scalar(select(User).where(User.email == "owner@example.com"))
            operation = db.get(AIStudioBulkOperation, bulk_id)
            assert owner is not None and operation is not None
            return retry_image_bulk(db, owner, bulk_id, [output_id])

    def cancel() -> int:
        assert test_ai_integration.factory is not None
        with test_ai_integration.factory() as db:
            owner = db.scalar(select(User).where(User.email == "owner@example.com"))
            operation = db.get(AIStudioBulkOperation, bulk_id)
            assert owner is not None and operation is not None
            return cancel_image_bulk(db, owner, bulk_id, [output_id])

    with ThreadPoolExecutor(max_workers=2) as pool:
        retry_result, cancel_result = list(pool.map(lambda task: task(), (retry, cancel)))
    assert retry_result[0] in {0, 1}
    assert cancel_result in {0, 1}

    with test_ai_integration.factory() as db:
        output = db.get(AIStudioBulkOutput, output_id)
        assert output is not None
        job = db.get(AIStudioJob, output.job_id)
        assert job is not None
        assert not (output.status == "cancelled" and job.state == "succeeded")
        assert output.status in {"cancelled", "retry_wait", "failed"}
        assert job.state in {"cancelled", "retry_wait", "failed"}
        assert (
            db.scalar(select(AIImageOutput.media_id).where(AIImageOutput.job_id == output.job_id))
            is None
        )
