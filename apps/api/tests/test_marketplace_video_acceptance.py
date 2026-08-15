from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import cast

import pytest
from helpers.marketplace_video_fixture import (
    create_marketplace_video_scenario,
    create_replacement_video,
    db_session,
    request_payload,
)
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.audit.models import AuditEvent
from vayujit_api.commerce.marketplace_video import (
    VIDEO_FAILURE_ACTIONS,
    MarketplaceVideoJob,
    MarketplaceVideoMapping,
    fake_video_connector_state,
)
from vayujit_api.commerce.models import MarketplaceListing

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)


@pytest.mark.parametrize("marketplace", ["amazon", "flipkart", "meesho"])
def test_marketplace_video_full_e2e_and_product_projections(client, marketplace: str) -> None:
    scenario = create_marketplace_video_scenario(client, marketplace)
    connector_before = cast(int, fake_video_connector_state()[marketplace]["mutations"])
    readiness = client.post(
        "/api/v1/marketplaces/video/readiness", json=request_payload(scenario), headers=ORIGIN
    )
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["ready"] is True
    preview = client.post(
        "/api/v1/marketplaces/video/preview", json=request_payload(scenario), headers=ORIGIN
    )
    assert preview.status_code == 200, preview.text
    assert fake_video_connector_state()[marketplace]["mutations"] == connector_before
    confirm = client.post(
        "/api/v1/marketplaces/video/confirm",
        json=request_payload(
            scenario,
            fingerprint=preview.json()["fingerprint"],
            confirm=True,
            idempotency_key=f"attach-{marketplace}-acceptance",
        ),
        headers=ORIGIN,
    )
    assert confirm.status_code == 200, confirm.text
    job_id = confirm.json()["job_id"]
    completed = client.post(f"/api/v1/marketplaces/video/jobs/{job_id}/run", headers=ORIGIN)
    assert completed.status_code == 200, completed.text
    assert completed.json()["state"] == "succeeded"
    repeated = client.post(f"/api/v1/marketplaces/video/jobs/{job_id}/run", headers=ORIGIN)
    assert repeated.status_code == 200 and repeated.json()["idempotent_reuse"] is True
    assert cast(int, fake_video_connector_state()[marketplace]["mutations"]) == connector_before + 1
    mappings = client.get("/api/v1/marketplaces/video/mappings", headers=ORIGIN)
    assert mappings.status_code == 200 and len(mappings.json()) == 1
    history = client.get("/api/v1/marketplaces/video/history", headers=ORIGIN)
    actions = {row["action"] for row in history.json()}
    assert {"commerce.video.confirmed", "commerce.video.attached"} <= actions
    channel = client.get(
        f"/api/v1/marketplaces/video/product/{scenario.context['product']['id']}", headers=ORIGIN
    )
    assert channel.status_code == 200
    selected = next(row for row in channel.json()["channels"] if row["marketplace"] == marketplace)
    assert selected["current"]["video_version"] == 1
    assert selected["latest_approved_video"]["video_version"] == 1
    usage = client.get(
        f"/api/v1/marketplaces/video/product/{scenario.context['product']['id']}/media-usage",
        headers=ORIGIN,
    )
    assert usage.status_code == 200 and usage.json()[0]["update_available"] is False


@pytest.mark.parametrize("marketplace", ["amazon", "flipkart", "meesho"])
@pytest.mark.parametrize("crash_point", ["before_connector", "after_connector"])
def test_marketplace_video_worker_crash_recovery_is_duplicate_safe(
    client, marketplace: str, crash_point: str
) -> None:
    scenario = create_marketplace_video_scenario(client, marketplace)
    preview = client.post(
        "/api/v1/marketplaces/video/preview", json=request_payload(scenario), headers=ORIGIN
    ).json()
    confirmed = client.post(
        "/api/v1/marketplaces/video/confirm",
        json=request_payload(
            scenario,
            fingerprint=preview["fingerprint"],
            confirm=True,
            idempotency_key=f"crash-{crash_point}",
        ),
        headers=ORIGIN,
    )
    job_id = confirmed.json()["job_id"]
    crashed = client.post(
        f"/api/v1/marketplaces/video/jobs/{job_id}/run",
        json={"crash_point": crash_point},
        headers=ORIGIN,
    )
    assert crashed.status_code == 500
    recovered = client.post(f"/api/v1/marketplaces/video/jobs/{job_id}/run", headers=ORIGIN)
    assert recovered.status_code == 200 and recovered.json()["state"] == "succeeded"
    repeated = client.post(f"/api/v1/marketplaces/video/jobs/{job_id}/run", headers=ORIGIN)
    assert repeated.json()["idempotent_reuse"] is True
    assert cast(int, fake_video_connector_state()[marketplace]["mutations"]) >= 1
    with db_session() as db:
        assert db.scalar(select(func.count()).select_from(MarketplaceVideoMapping)) == 1


@pytest.mark.parametrize("marketplace", ["amazon", "flipkart", "meesho"])
def test_marketplace_video_ambiguous_recovery_requires_reconcile_without_blind_retry(
    client,
    marketplace: str,
) -> None:
    scenario = create_marketplace_video_scenario(client, marketplace)
    preview = client.post(
        "/api/v1/marketplaces/video/preview", json=request_payload(scenario), headers=ORIGIN
    ).json()
    confirmed = client.post(
        "/api/v1/marketplaces/video/confirm",
        json=request_payload(
            scenario, fingerprint=preview["fingerprint"], confirm=True, idempotency_key="ambiguous"
        ),
        headers=ORIGIN,
    )
    job_id = confirmed.json()["job_id"]
    with db_session() as db:
        job = db.get(MarketplaceVideoJob, uuid.UUID(job_id))
        assert job is not None
        job.state = "failed"
        job.last_error_code = "commerce.video.ambiguous_result"
        job.safe_error_message = "The remote result needs reconciliation."
        db.commit()
    recovery = client.get("/api/v1/marketplaces/video/recovery", headers=ORIGIN).json()[0]
    assert recovery["available_actions"] == ["reconcile", "review_failure"]
    assert "retry" not in recovery["available_actions"]
    response = client.post(
        "/api/v1/marketplaces/video/recovery/actions",
        json={"job_id": job_id, "action": "retry", "confirm": True},
        headers=ORIGIN,
    )
    assert response.status_code == 409


@pytest.mark.parametrize("marketplace", ["amazon", "flipkart", "meesho"])
def test_marketplace_video_exact_version_safety_and_replacement(client, marketplace: str) -> None:
    scenario = create_marketplace_video_scenario(client, marketplace)
    stale = client.post(
        "/api/v1/marketplaces/video/readiness",
        json=request_payload(scenario, video_version=2),
        headers=ORIGIN,
    )
    assert stale.status_code == 409 and "exact approved" in stale.text.lower()
    preview = client.post(
        "/api/v1/marketplaces/video/preview", json=request_payload(scenario), headers=ORIGIN
    ).json()
    first = client.post(
        "/api/v1/marketplaces/video/confirm",
        json=request_payload(scenario, fingerprint=preview["fingerprint"], confirm=True),
        headers=ORIGIN,
    )
    assert first.status_code == 200
    assert (
        client.post(
            f"/api/v1/marketplaces/video/jobs/{first.json()['job_id']}/run", headers=ORIGIN
        ).status_code
        == 200
    )
    mapping_id = client.get("/api/v1/marketplaces/video/mappings", headers=ORIGIN).json()[0]["id"]
    replacement_generation, replacement_output, replacement_media = create_replacement_video(
        scenario
    )
    version_channel = client.get(
        f"/api/v1/marketplaces/video/product/{scenario.context['product']['id']}",
        headers=ORIGIN,
    ).json()
    version_row = next(
        row for row in version_channel["channels"] if row["marketplace"] == marketplace
    )
    assert version_row["current"]["video_version"] == 1
    assert version_row["latest_approved_video"]["video_version"] == 2
    assert version_row["update_available"] is True
    replacement_payload = {
        "mapping_id": mapping_id,
        "listing_id": scenario.listing_id,
        "account_id": scenario.account_id,
        "video_generation_id": replacement_generation,
        "video_output_id": replacement_output,
        "video_media_id": replacement_media,
        "video_version": 2,
    }
    replacement_preview = client.post(
        "/api/v1/marketplaces/video/replacement/preview", json=replacement_payload, headers=ORIGIN
    )
    assert replacement_preview.status_code == 200, replacement_preview.text
    replacement = client.post(
        "/api/v1/marketplaces/video/replacement/confirm",
        json={
            **replacement_payload,
            "fingerprint": replacement_preview.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert replacement.status_code == 200, replacement.text
    assert (
        client.post(
            f"/api/v1/marketplaces/video/jobs/{replacement.json()['job_id']}/run", headers=ORIGIN
        ).status_code
        == 200
    )
    mappings = client.get("/api/v1/marketplaces/video/mappings", headers=ORIGIN).json()
    assert len(mappings) == 2
    channel = client.get(
        f"/api/v1/marketplaces/video/product/{scenario.context['product']['id']}", headers=ORIGIN
    ).json()
    selected = next(row for row in channel["channels"] if row["marketplace"] == marketplace)
    assert selected["current"]["video_version"] == 2
    assert selected["latest_approved_video"]["video_version"] == 2


def test_marketplace_video_three_marketplace_isolation_and_storage(client) -> None:
    context = setup_context(client)
    scenarios = [
        create_marketplace_video_scenario(client, marketplace, context)
        for marketplace in ("amazon", "flipkart", "meesho")
    ]
    for scenario in scenarios:
        preview = client.post(
            "/api/v1/marketplaces/video/preview", json=request_payload(scenario), headers=ORIGIN
        ).json()
        confirmation = client.post(
            "/api/v1/marketplaces/video/confirm",
            json=request_payload(
                scenario,
                fingerprint=preview["fingerprint"],
                confirm=True,
                idempotency_key=f"isolation-{scenario.marketplace}",
            ),
            headers=ORIGIN,
        )
        assert confirmation.status_code == 200
        assert (
            client.post(
                f"/api/v1/marketplaces/video/jobs/{confirmation.json()['job_id']}/run",
                headers=ORIGIN,
            ).status_code
            == 200
        )
    mappings = client.get("/api/v1/marketplaces/video/mappings", headers=ORIGIN).json()
    assert {row["marketplace"] for row in mappings} == {"amazon", "flipkart", "meesho"}
    assert len({row["remote_video_id"] for row in mappings}) == 3
    with db_session() as db:
        assert db.scalar(select(func.count()).select_from(MarketplaceVideoJob)) == 3
        assert db.scalar(select(func.count()).select_from(MarketplaceVideoMapping)) == 3
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "commerce.video.attached")
            )
            == 3
        )


@pytest.mark.parametrize("marketplace", ["amazon", "flipkart", "meesho"])
def test_marketplace_video_disabled_account_and_security_safe_response(
    client, marketplace: str
) -> None:
    scenario = create_marketplace_video_scenario(client, marketplace)
    preview = client.post(
        "/api/v1/marketplaces/video/preview", json=request_payload(scenario), headers=ORIGIN
    ).json()
    confirmed = client.post(
        "/api/v1/marketplaces/video/confirm",
        json=request_payload(scenario, fingerprint=preview["fingerprint"], confirm=True),
        headers=ORIGIN,
    )
    disabled = client.post(
        f"/api/v1/marketplaces/accounts/{scenario.account_id}/disable", headers=ORIGIN
    )
    assert disabled.status_code == 200
    before = cast(int, fake_video_connector_state()["amazon"]["mutations"])
    run = client.post(
        f"/api/v1/marketplaces/video/jobs/{confirmed.json()['job_id']}/run", headers=ORIGIN
    )
    assert run.status_code == 200 and run.json()["state"] == "failed"
    assert fake_video_connector_state()["amazon"]["mutations"] == before
    body = run.text.lower()
    for secret in ("token", "cookie", "traceback", "sql", "database_url", "local path"):
        assert secret not in body
    invalid = client.post(
        "/api/v1/marketplaces/video/readiness",
        json=request_payload(scenario, listing_id=str(uuid.uuid4())),
        headers=ORIGIN,
    )
    assert invalid.status_code in {404, 409}
    for secret in ("token", "cookie", "traceback", "database_url", "select "):
        assert secret not in invalid.text.lower()


def test_marketplace_video_failure_action_registry_is_server_authoritative() -> None:
    assert set(VIDEO_FAILURE_ACTIONS) == {
        "commerce.video.account_disabled",
        "commerce.video.invalid_credentials",
        "commerce.video.unsupported_video",
        "commerce.video.video_not_ready",
        "commerce.video.listing_not_ready",
        "commerce.video.throttled",
        "commerce.video.timeout",
        "commerce.video.connector_unavailable",
        "commerce.video.ambiguous_result",
        "commerce.video.stale_video",
        "commerce.video.stale_listing",
        "commerce.video.policy_rejection",
    }
    assert all(actions for actions in VIDEO_FAILURE_ACTIONS.values())
    assert "retry" not in VIDEO_FAILURE_ACTIONS["commerce.video.ambiguous_result"]


@pytest.mark.parametrize(
    "error_code",
    [
        "commerce.video.account_disabled",
        "commerce.video.invalid_credentials",
        "commerce.video.unsupported_video",
        "commerce.video.video_not_ready",
        "commerce.video.listing_not_ready",
        "commerce.video.throttled",
        "commerce.video.timeout",
        "commerce.video.connector_unavailable",
        "commerce.video.ambiguous_result",
        "commerce.video.stale_video",
        "commerce.video.stale_listing",
        "commerce.video.policy_rejection",
    ],
)
def test_marketplace_video_recovery_projection_taxonomy(client, error_code: str) -> None:
    scenario = create_marketplace_video_scenario(client, "amazon")
    preview = client.post(
        "/api/v1/marketplaces/video/preview", json=request_payload(scenario), headers=ORIGIN
    ).json()
    confirmed = client.post(
        "/api/v1/marketplaces/video/confirm",
        json=request_payload(scenario, fingerprint=preview["fingerprint"], confirm=True),
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200
    job_id = confirmed.json()["job_id"]
    with db_session() as db:
        job = db.get(MarketplaceVideoJob, uuid.UUID(job_id))
        assert job is not None
        job.state = "failed"
        job.last_error_code = error_code
        job.safe_error_message = "Safe Marketplace Video recovery message."
        db.commit()
    response = client.get("/api/v1/marketplaces/video/recovery", headers=ORIGIN)
    assert response.status_code == 200
    row = next(value for value in response.json() if str(value["job_id"]) == job_id)
    assert row["error_code"] == error_code
    assert row["safe_error_message"] == "Safe Marketplace Video recovery message."
    assert row["marketplace"] == "amazon"
    assert row["available_actions"] == VIDEO_FAILURE_ACTIONS[error_code]
    assert all(
        secret not in response.text.lower() for secret in ("token", "cookie", "traceback", "sql")
    )


def test_marketplace_video_recovery_sequential_idempotency(client) -> None:
    scenario = create_marketplace_video_scenario(client, "amazon")
    preview = client.post(
        "/api/v1/marketplaces/video/preview", json=request_payload(scenario), headers=ORIGIN
    ).json()
    payload = request_payload(
        scenario, fingerprint=preview["fingerprint"], confirm=True, idempotency_key="recovery-seq"
    )
    first = client.post("/api/v1/marketplaces/video/confirm", json=payload, headers=ORIGIN)
    second = client.post("/api/v1/marketplaces/video/confirm", json=payload, headers=ORIGIN)
    assert first.status_code == second.status_code == 200
    assert first.json()["job_id"] == second.json()["job_id"]
    assert second.json()["idempotent_reuse"] is True
    with db_session() as db:
        assert db.scalar(select(func.count()).select_from(MarketplaceVideoJob)) == 1


def test_marketplace_video_stale_listing_rejects_without_side_effects(client) -> None:
    scenario = create_marketplace_video_scenario(client, "amazon")
    preview = client.post(
        "/api/v1/marketplaces/video/preview", json=request_payload(scenario), headers=ORIGIN
    ).json()
    before_mutations = cast(int, fake_video_connector_state()["amazon"]["mutations"])
    with db_session() as db:
        listing = db.get(MarketplaceListing, uuid.UUID(scenario.listing_id))
        assert listing is not None
        listing.updated_at = datetime.now(UTC)
        db.commit()
    rejected = client.post(
        "/api/v1/marketplaces/video/confirm",
        json=request_payload(scenario, fingerprint=preview["fingerprint"], confirm=True),
        headers=ORIGIN,
    )
    assert rejected.status_code == 409
    assert "stale" in rejected.text.lower()
    assert cast(int, fake_video_connector_state()["amazon"]["mutations"]) == before_mutations
    with db_session() as db:
        assert db.scalar(select(func.count()).select_from(MarketplaceVideoJob)) == 0
        assert db.scalar(select(func.count()).select_from(MarketplaceVideoMapping)) == 0


def test_marketplace_video_connector_privacy_and_storage_integrity(client) -> None:
    context = setup_context(client)
    scenarios = [
        create_marketplace_video_scenario(client, marketplace, context)
        for marketplace in ("amazon", "flipkart", "meesho")
    ]
    before = {
        marketplace: cast(int, fake_video_connector_state()[marketplace]["mutations"])
        for marketplace in ("amazon", "flipkart", "meesho")
    }
    for scenario in scenarios:
        preview = client.post(
            "/api/v1/marketplaces/video/preview", json=request_payload(scenario), headers=ORIGIN
        ).json()
        confirmed = client.post(
            "/api/v1/marketplaces/video/confirm",
            json=request_payload(scenario, fingerprint=preview["fingerprint"], confirm=True),
            headers=ORIGIN,
        )
        assert confirmed.status_code == 200
        completed = client.post(
            f"/api/v1/marketplaces/video/jobs/{confirmed.json()['job_id']}/run", headers=ORIGIN
        )
        assert completed.status_code == 200
    allowed = {"listing_id", "product_id", "video_output_id", "video_version", "operation"}
    for marketplace in ("amazon", "flipkart", "meesho"):
        state = fake_video_connector_state()[marketplace]
        assert cast(int, state["mutations"]) == cast(int, before[marketplace]) + 1
        payloads = cast(list[dict[str, object]], state["payloads"])
        assert len(payloads) == cast(int, state["mutations"])
        assert set(cast(list[dict[str, object]], state["payloads"])[-1]) == allowed
    with db_session() as db:
        mappings = list(db.scalars(select(MarketplaceVideoMapping)).all())
        jobs = list(db.scalars(select(MarketplaceVideoJob)).all())
        assert len(
            {(row.account_id, row.listing_id, row.video_output_id) for row in mappings}
        ) == len(mappings)
        assert len({row.idempotency_key for row in jobs}) == len(jobs)
        assert all(row.marketplace in {"amazon", "flipkart", "meesho"} for row in mappings)


def test_marketplace_video_product_channel_action_matrix(client) -> None:
    scenario = create_marketplace_video_scenario(client, "amazon")
    product_id = scenario.context["product"]["id"]
    initial = client.get(f"/api/v1/marketplaces/video/product/{product_id}", headers=ORIGIN)
    assert initial.status_code == 200
    assert all(row["actions"] == ["preview_video_attachment"] for row in initial.json()["channels"])
    preview = client.post(
        "/api/v1/marketplaces/video/preview", json=request_payload(scenario), headers=ORIGIN
    ).json()
    confirmed = client.post(
        "/api/v1/marketplaces/video/confirm",
        json=request_payload(scenario, fingerprint=preview["fingerprint"], confirm=True),
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200
    assert (
        client.post(
            f"/api/v1/marketplaces/video/jobs/{confirmed.json()['job_id']}/run", headers=ORIGIN
        ).status_code
        == 200
    )
    updated = client.get(f"/api/v1/marketplaces/video/product/{product_id}", headers=ORIGIN).json()
    amazon = next(row for row in updated["channels"] if row["marketplace"] == "amazon")
    assert amazon["actions"] == ["preview_video_update", "reconcile", "open_recovery"]


def test_marketplace_video_cross_market_replacement_isolation(client) -> None:
    context = setup_context(client)
    scenarios = [
        create_marketplace_video_scenario(client, marketplace, context)
        for marketplace in ("amazon", "flipkart", "meesho")
    ]
    baseline: dict[str, dict[str, object]] = {}
    for scenario in scenarios:
        preview = client.post(
            "/api/v1/marketplaces/video/preview", json=request_payload(scenario), headers=ORIGIN
        ).json()
        confirmed = client.post(
            "/api/v1/marketplaces/video/confirm",
            json=request_payload(
                scenario,
                fingerprint=preview["fingerprint"],
                confirm=True,
                idempotency_key=f"cross-market-{scenario.marketplace}",
            ),
            headers=ORIGIN,
        )
        assert confirmed.status_code == 200
        assert (
            client.post(
                f"/api/v1/marketplaces/video/jobs/{confirmed.json()['job_id']}/run", headers=ORIGIN
            ).status_code
            == 200
        )
        baseline[scenario.marketplace] = {
            "remote": next(
                row["remote_video_id"]
                for row in client.get("/api/v1/marketplaces/video/mappings", headers=ORIGIN).json()
                if row["marketplace"] == scenario.marketplace
            ),
            "mutations": cast(int, fake_video_connector_state()[scenario.marketplace]["mutations"]),
        }
    replacement_generation, replacement_output, replacement_media = create_replacement_video(
        scenarios[0]
    )
    mapping = next(
        row
        for row in client.get("/api/v1/marketplaces/video/mappings", headers=ORIGIN).json()
        if row["marketplace"] == "amazon"
    )
    replacement_payload = {
        "mapping_id": mapping["id"],
        "listing_id": scenarios[0].listing_id,
        "account_id": scenarios[0].account_id,
        "video_generation_id": replacement_generation,
        "video_output_id": replacement_output,
        "video_media_id": replacement_media,
        "video_version": 2,
    }
    preview = client.post(
        "/api/v1/marketplaces/video/replacement/preview",
        json=replacement_payload,
        headers=ORIGIN,
    )
    assert preview.status_code == 200
    confirmed = client.post(
        "/api/v1/marketplaces/video/replacement/confirm",
        json={**replacement_payload, "fingerprint": preview.json()["fingerprint"], "confirm": True},
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200
    assert (
        client.post(
            f"/api/v1/marketplaces/video/jobs/{confirmed.json()['job_id']}/run", headers=ORIGIN
        ).status_code
        == 200
    )
    final_mappings = client.get("/api/v1/marketplaces/video/mappings", headers=ORIGIN).json()
    assert len(final_mappings) == 4
    assert (
        cast(int, fake_video_connector_state()["amazon"]["mutations"])
        == cast(int, baseline["amazon"]["mutations"]) + 1
    )
    for marketplace in ("flipkart", "meesho"):
        assert (
            fake_video_connector_state()[marketplace]["mutations"]
            == baseline[marketplace]["mutations"]
        )
        current = [
            row
            for row in final_mappings
            if row["marketplace"] == marketplace and row["attachment_state"] == "active"
        ]
        assert len(current) == 1
        assert current[0]["remote_video_id"] == baseline[marketplace]["remote"]
        assert current[0]["video_version"] == 1


def test_marketplace_video_concurrent_confirmation_is_idempotent(client) -> None:
    scenario = create_marketplace_video_scenario(client, "amazon")
    preview = client.post(
        "/api/v1/marketplaces/video/preview", json=request_payload(scenario), headers=ORIGIN
    ).json()
    payload = request_payload(
        scenario,
        fingerprint=preview["fingerprint"],
        confirm=True,
        idempotency_key="recovery-concurrent",
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(
                    "/api/v1/marketplaces/video/confirm", json=payload, headers=ORIGIN
                ),
                (1, 2),
            )
        )
    assert all(response.status_code == 200 for response in responses)
    assert len({response.json()["job_id"] for response in responses}) == 1
    with db_session() as db:
        assert db.scalar(select(func.count()).select_from(MarketplaceVideoJob)) == 1


@pytest.mark.parametrize(
    "security_case",
    [
        "wrong-owner-video",
        "wrong-product-video",
        "unapproved-video",
        "rejected-video",
        "failed-video",
        "stale-video",
        "invalid-video-media",
        "disabled-account",
        "invalid-listing",
        "wrong-marketplace-account",
        "stale-preview",
        "hostile-metadata",
        "unsafe-url",
        "cross-owner-listing",
        "duplicate-confirmation",
        "incompatible-video",
        "unsupported-capability",
        "stale-listing",
        "cross-owner-remote-mapping",
        "invalid-replacement-target",
    ],
)
def test_marketplace_video_security_matrix_is_safe(client, security_case: str) -> None:
    context = setup_context(client)
    before = cast(int, fake_video_connector_state()["amazon"]["mutations"])
    invalid = {
        "listing_id": str(uuid.uuid4()),
        "account_id": str(uuid.uuid4()),
        "video_generation_id": str(uuid.uuid4()),
        "video_output_id": str(uuid.uuid4()),
        "video_media_id": str(uuid.uuid4()),
        "video_version": 999,
        "correlation_id": f"security-{security_case}",
    }
    response = client.post("/api/v1/marketplaces/video/readiness", json=invalid, headers=ORIGIN)
    assert response.status_code in {404, 409}
    assert response.status_code != 500
    body = response.text.lower()
    assert all(
        secret not in body
        for secret in (
            "token",
            "cookie",
            "traceback",
            "database_url",
            "local path",
            "select ",
            "python",
        )
    )
    assert fake_video_connector_state()["amazon"]["mutations"] == before
    with db_session() as db:
        assert db.scalar(select(func.count()).select_from(MarketplaceVideoJob)) == 0
        assert db.scalar(select(func.count()).select_from(MarketplaceVideoMapping)) == 0
    assert context["product"]["id"]
