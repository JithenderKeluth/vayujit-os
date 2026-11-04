"""Real transactional PostgreSQL repair/upgrade/rollback; never ORM-create schema."""

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from vayujit_api.ads.models import AdAccount, AdCampaign
from vayujit_api.core.test_database import assert_safe_test_database
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.video.models import (
    VideoGeneration,
    VideoProject,
    VideoScene,
    VideoStoryboard,
    VideoStyle,
)

from qa.validate_postgres_instance import QaMigrationConfig

pytestmark = pytest.mark.integration
OLD = "20261204_0147"
NEW = "20261206_0149"
HEAD = "20261207_0150"
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def migration() -> Config:
    root = Path(__file__).resolve().parents[1]
    config = QaMigrationConfig(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    return config


@pytest.fixture
def engine():
    url = os.environ["VAYUJIT_TEST_DATABASE_URL"]
    value = create_engine(url, poolclass=NullPool)
    with value.connect() as c:
        assert_safe_test_database(c, database_url=url, environment="test")
    command.upgrade(migration(), "head")
    try:
        yield value
    finally:
        value.dispose()


def head(engine):
    with engine.connect() as c:
        return c.scalar(text("SELECT version_num FROM alembic_version"))


def test_fresh_install_matches_repaired_columns_and_index(engine):
    assert head(engine) == HEAD
    inspector = inspect(engine)
    video = {c["name"]: c for c in inspector.get_columns("video_generations")}
    ads = {c["name"]: c for c in inspector.get_columns("ad_campaigns")}
    for name in ("storyboard_version", "style_version"):
        assert name in video and video[name]["nullable"]
        assert name.replace("_", "") not in video
    for name in ("failure_category", "retry_after_seconds", "next_retry_at", "correlation_id"):
        assert ads[name]["nullable"] and ads[name]["default"] is None
    index = next(
        i
        for i in inspector.get_indexes("ad_campaigns")
        if i["name"] == "ix_ad_campaigns_correlation_id"
    )
    assert index["column_names"] == ["correlation_id"] and not index["unique"]
    assert next(c for c in inspector.get_columns("video_scenes") if c["name"] == "generation_id")[
        "nullable"
    ]
    command.upgrade(migration(), "head")
    assert head(engine) == HEAD


def seed(client, engine):
    response = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "[QA SYNTHETIC] Migration Owner",
            "email": "wp6a@example.com",
            "password": "SyntheticMigrationOnly123!",
            "password_confirmation": "SyntheticMigrationOnly123!",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201
    brand = client.post(
        "/api/v1/brands", json={"name": "[QA SYNTHETIC] Upgrade Brand"}, headers=ORIGIN
    ).json()
    product = client.post(
        "/api/v1/products",
        json={
            "brand_id": brand["id"],
            "name": "[QA SYNTHETIC] Upgrade Product",
            "product_type": "physical",
        },
        headers=ORIGIN,
    ).json()
    stamp = now()
    with Session(engine) as db:
        owner = db.scalar(select(User))
        project = VideoProject(
            owner_id=owner.id,
            brand_id=uuid.UUID(brand["id"]),
            product_id=uuid.UUID(product["id"]),
            name="[QA SYNTHETIC] Historical",
            created_at=stamp,
            updated_at=stamp,
        )
        board = VideoStoryboard(
            owner_id=owner.id,
            brand_id=project.brand_id,
            product_id=project.product_id,
            version=7,
            context_fingerprint="qa-historical-context",
            created_at=stamp,
            updated_at=stamp,
        )
        style = VideoStyle(
            owner_id=owner.id,
            brand_id=project.brand_id,
            name="[QA SYNTHETIC] Historical Style",
            version=3,
            created_at=stamp,
            updated_at=stamp,
        )
        account = AdAccount(
            owner_id=owner.id,
            provider="meta",
            external_account_id="qa-wp6a-historical",
            display_name="[QA SYNTHETIC] Disabled local",
            environment="local",
            created_at=stamp,
            updated_at=stamp,
        )
        db.add_all([project, board, style, account])
        db.flush()
        generation = VideoGeneration(
            owner_id=owner.id,
            project_id=project.id,
            brand_id=project.brand_id,
            product_id=project.product_id,
            storyboard_id=board.id,
            storyboard_version=7,
            style_id=style.id,
            style_version=3,
            video_type="slideshow",
            target_channel="youtube",
            aspect_ratio="16:9",
            resolution="320x240",
            status="failed",
            failure_code="qa_synthetic_historical",
            idempotency_key="qa-upgrade",
            correlation_id="qa-upgrade-correlation",
            available_at=stamp,
            created_at=stamp,
            updated_at=stamp,
        )
        campaign = AdCampaign(
            owner_id=owner.id,
            provider="meta",
            account_id=account.id,
            product_id=project.product_id,
            brand_id=project.brand_id,
            name="[QA SYNTHETIC] Historical draft",
            state="draft",
            idempotency_key="qa-historical",
            targeting_summary_json={"synthetic": True, "marker": "preserve"},
            created_at=stamp,
            updated_at=stamp,
        )
        db.add_all([generation, campaign])
        db.flush()
        db.add(
            VideoScene(
                generation_id=generation.id,
                storyboard_id=board.id,
                scene_order=1,
                duration_seconds=3,
                stable_key="qa-preserved-scene",
                scene_text="Synthetic preserved scene",
                transition="cut",
                version=1,
                status="draft",
                locale="en-IN",
            )
        )
        db.commit()
        return {
            "generation": str(generation.id),
            "campaign": str(campaign.id),
            "project": str(project.id),
            "board": str(board.id),
            "style": str(style.id),
            "account": str(account.id),
            "product": product["id"],
        }


def snapshot(engine, *, repaired):
    version_columns = (
        "storyboard_version,style_version" if repaired else "storyboardversion,styleversion"
    )
    with engine.connect() as c:
        return {
            "video": [
                tuple(r)
                for r in c.execute(
                    text(
                        "SELECT id,owner_id,project_id,product_id,storyboard_id,style_id,"
                        f"{version_columns},status,failure_code,idempotency_key,correlation_id,"
                        "created_at,updated_at FROM video_generations ORDER BY id"
                    )
                )
            ],
            "ads": [
                tuple(r)
                for r in c.execute(
                    text(
                        "SELECT id,owner_id,account_id,product_id,name,state,idempotency_key,"
                        "targeting_summary_json,created_at,updated_at FROM ad_campaigns ORDER BY id"
                    )
                )
            ],
            "scenes": [
                tuple(r)
                for r in c.execute(
                    text(
                        "SELECT id,generation_id,storyboard_id,scene_order,scene_text "
                        "FROM video_scenes ORDER BY id"
                    )
                )
            ],
            "counts": {
                t: c.scalar(text(f"SELECT count(*) FROM {t}"))
                for t in (
                    "users",
                    "brands",
                    "products",
                    "video_projects",
                    "video_storyboards",
                    "video_styles",
                    "video_generations",
                    "video_scenes",
                    "ad_accounts",
                    "ad_campaigns",
                )
            },
        }


def test_populated_representative_upgrade_roundtrip_preserves_data(pr56_client, engine):
    ids = seed(pr56_client, engine)
    original = snapshot(engine, repaired=True)
    command.downgrade(migration(), OLD)
    assert head(engine) == OLD
    assert snapshot(engine, repaired=False) == original
    command.upgrade(migration(), NEW)
    assert snapshot(engine, repaired=True) == original
    with engine.connect() as c:
        row = c.execute(
            text(
                "SELECT failure_category,retry_after_seconds,next_retry_at,correlation_id "
                "FROM ad_campaigns WHERE id=:id"
            ),
            {"id": ids["campaign"]},
        ).one()
        assert tuple(row) == (None, None, None, None)
    for path in (
        "/api/v1/ai/video/generations",
        "/api/v1/ads/overview",
        "/api/v1/ads/optimization/overview",
        "/api/v1/ads/anomalies",
        "/api/v1/ads/comparison",
    ):
        assert pr56_client.get(path).status_code == 200
    command.upgrade(migration(), "head")
    assert snapshot(engine, repaired=True) == original
    assert pr56_client.get("/api/v1/ai/video/generations").json()[0]["storyboard_version"] == 7


def test_downgrade_refuses_loss_of_new_recovery_values(pr56_client, engine):
    seed(pr56_client, engine)
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE ad_campaigns SET failure_category='qa_synthetic',retry_after_seconds=37,"
                "next_retry_at='2026-10-30T12:00:00Z',correlation_id='qa-preserve-new-values'"
            )
        )
    with pytest.raises(RuntimeError, match="WP6A_DOWNGRADE_WOULD_LOSE_RECOVERY_DATA"):
        command.downgrade(migration(), OLD)
    assert head(engine) == HEAD
    with engine.connect() as c:
        assert c.scalar(text("SELECT correlation_id FROM ad_campaigns")) == "qa-preserve-new-values"


def test_downgrade_refuses_to_delete_or_orphan_storyboard_only_scene(pr56_client, engine):
    ids = seed(pr56_client, engine)
    with Session(engine) as db:
        row = VideoScene(
            storyboard_id=uuid.UUID(ids["board"]),
            scene_order=2,
            duration_seconds=3,
            stable_key="qa-storyboard-only",
            scene_text="Synthetic unrendered scene",
            transition="cut",
            version=1,
            status="draft",
            locale="en-IN",
        )
        db.add(row)
        db.commit()
        scene_id = row.id
    with pytest.raises(RuntimeError, match="WP6A_DOWNGRADE_WOULD_ORPHAN_STORYBOARD_SCENES"):
        command.downgrade(migration(), OLD)
    assert head(engine) == HEAD
    with Session(engine) as db:
        assert db.get(VideoScene, scene_id).generation_id is None


@pytest.mark.parametrize("state", ["both_names", "wrong_type", "missing_name", "partial_ads"])
def test_unsupported_upgrade_refuses_without_partial_ddl(engine, state):
    command.downgrade(migration(), OLD)
    try:
        with engine.begin() as c:
            if state == "both_names":
                c.exec_driver_sql(
                    "ALTER TABLE video_generations ADD COLUMN storyboard_version integer"
                )
            elif state == "wrong_type":
                c.exec_driver_sql(
                    "ALTER TABLE video_generations ALTER COLUMN storyboardversion TYPE text "
                    "USING storyboardversion::text"
                )
            elif state == "missing_name":
                c.exec_driver_sql(
                    "ALTER TABLE video_generations RENAME COLUMN storyboardversion "
                    "TO qa_test_version"
                )
            else:
                c.exec_driver_sql(
                    "ALTER TABLE ad_campaigns ADD COLUMN failure_category varchar(80)"
                )
        before = {
            t: {v["name"]: str(v["type"]) for v in inspect(engine).get_columns(t)}
            for t in ("video_generations", "ad_campaigns")
        }
        with pytest.raises(RuntimeError, match="WP6A_"):
            command.upgrade(migration(), NEW)
        assert head(engine) == OLD
        assert {
            t: {v["name"]: str(v["type"]) for v in inspect(engine).get_columns(t)} for t in before
        } == before
    finally:
        with engine.begin() as c:
            if state == "both_names":
                c.exec_driver_sql("ALTER TABLE video_generations DROP COLUMN storyboard_version")
            elif state == "wrong_type":
                c.exec_driver_sql(
                    "ALTER TABLE video_generations ALTER COLUMN storyboardversion TYPE integer "
                    "USING storyboardversion::integer"
                )
            elif state == "missing_name":
                c.exec_driver_sql(
                    "ALTER TABLE video_generations RENAME COLUMN qa_test_version "
                    "TO storyboardversion"
                )
            else:
                c.exec_driver_sql("ALTER TABLE ad_campaigns DROP COLUMN failure_category")
        command.upgrade(migration(), NEW)
