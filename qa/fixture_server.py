"""QA-only disposable installation. Never import this module from production."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import threading
import traceback
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


def require_target(name: str, token: str) -> None:
    if not re.fullmatch(r"[a-f0-9]{16}", token) or name != f"vayujit_qa{token}_test":
        raise ValueError("QA_DATABASE_TARGET_DENIED")


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--migrate", action="store_true")
    parser.add_argument(
        "--pytest",
        nargs="+",
        choices=[
            "test_pr5b_landed_cost.py",
            "test_pr5c_unit_economics.py",
            "test_pr6a_decision_readiness.py",
            "test_pr6c_decision_workflow.py",
            "test_pr_sos_04_inventory_orders.py",
            "test_pr_sos_05_financials.py",
            "test_pr_sos_06_action_center.py",
            "test_qa_phase3a_remediation.py",
            "test_qa_phase3b_remediation.py",
            "test_qa_phase4b_opening_stock.py",
            "test_seller_wp1.py",
            "test_seller_wp2.py",
            "test_seller_wp3.py",
            "test_seller_wp4.py",
            "test_seller_wp5.py",
            "test_seller_wp6.py",
            "test_seller_wp6a.py",
            "test_seller_wp6b.py",
            "test_seller_wp6a_migration.py",
            "test_product_opportunity_scoring.py",
            "test_pr_sos_01_catalog.py",
            "test_business_agent_orchestration.py",
            "test_product_source_review_integration.py",
            "test_intelligence_economic_foundation.py",
            "test_intelligence_economic_calculation.py",
            "test_supplier_due_diligence.py",
            "test_seller_wp7a.py",
            "test_seller_wp7a2.py",
            "test_seller_wp7a3.py",
            "test_seller_wp7a4.py",
            "test_seller_wp7a5.py",
            "test_seller_wp7a6.py",
            "test_seller_wp7a7.py",
            "test_campaign_activity_rescheduling.py",
            "test_campaign_recovery_dispatch.py",
            "test_ai_seo.py",
            "test_ai_video_bulk_e2e.py",
            "test_ai_video_bulk_restart.py",
            "test_social_video_acceptance.py",
            "test_social_video_durable.py",
            "test_trend_analysis_api.py",
            "test_pr_sos_02_amazon_controls.py",
            "test_pr_sos_03_flipkart_controls.py",
            "test_marketing_plan.py",
            "test_supplier_portfolio_integration.py",
            "test_ai_studio_e2e.py",
            "test_ai_images_bulk.py",
            "test_ai_images_integration.py",
            "test_ai_images_handoff.py",
            "test_ai_video_recovery.py",
            "test_ads_failure_acceptance.py",
            "test_ads_concurrency_acceptance.py",
            "test_ads_security_privacy_acceptance.py",
            "test_ads_version_safety_acceptance.py",
        ],
    )
    args = parser.parse_args()
    name = f"vayujit_qa{args.token}_test"
    require_target(name, args.token)
    admin_url = make_url(os.environ["QA_DATABASE_ADMIN_URL"])
    if admin_url.host != "127.0.0.1" or admin_url.database != "postgres":
        raise ValueError("QA_ADMIN_MUST_BE_LOOPBACK_POSTGRES")
    db_url = admin_url.set(database=name)
    from qa.postgres_instance import approved_guard

    guarded_instance = approved_guard(admin_url)
    # Do not load any .env or inherited business credentials into this process.
    for key in list(os.environ):
        if key.startswith("VAYUJIT_") or key in {
            "OPENAI_API_KEY",
            "WORDPRESS_APPLICATION_PASSWORD",
        }:
            del os.environ[key]
    os.environ.update(
        VAYUJIT_ENV="test",
        VAYUJIT_ENVIRONMENT="test",
        VAYUJIT_DATABASE_URL=db_url.render_as_string(hide_password=False),
        VAYUJIT_TEST_DATABASE_URL=db_url.render_as_string(hide_password=False),
    )
    from vayujit_api.core.config import Settings

    Settings.model_config["env_file"] = None
    for field in Settings.model_fields.values():
        alias = field.validation_alias
        aliases = [alias] if isinstance(alias, str) else getattr(alias, "choices", [])
        for name_alias in aliases:
            if isinstance(name_alias, str):
                os.environ.pop(name_alias, None)
    # Settings defaults deny real providers. Keep these explicit to prevent drift.
    os.environ.update(
        VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP="true",
        VAYUJIT_INTELLIGENCE_EXTERNAL_KILL_SWITCH="true",
        VAYUJIT_INTELLIGENCE_SEARCH_PROVIDER_KILL_SWITCH="true",
        VAYUJIT_INTELLIGENCE_EXTERNAL_PROVIDER_MODE=(
            "LOCAL_FIXTURE" if os.environ.get("QA_PHASE") in {"2", "3"} else "DISABLED"
        ),
        VAYUJIT_MEDIA_STORAGE_DIRECTORY=str(args.output / "private-media"),
        VAYUJIT_BACKUP_DIRECTORY=str(args.output / "unused-backups"),
        VAYUJIT_MAINTENANCE_MARKER=str(args.output / "maintenance-disabled"),
        VAYUJIT_LOG_LEVEL="ERROR",
        VAYUJIT_WEB_ORIGIN=os.environ["QA_ORIGIN"],
        VAYUJIT_ALLOWED_ORIGINS=os.environ["QA_ORIGIN"],
    )
    from vayujit_api.core.test_database import PROJECT_MARKER, assert_safe_test_database

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    created = False
    engine = None
    try:
        if guarded_instance is not None:
            guarded_instance.create(args.token)
            created = True
        with admin.connect() as connection:
            exists = connection.scalar(
                text("select 1 from pg_database where datname=:name"), {"name": name}
            )
            if exists and guarded_instance is None:
                raise ValueError("QA_DATABASE_ALREADY_EXISTS_REFUSING_REUSE")
            if guarded_instance is None:
                connection.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        engine = create_engine(db_url, poolclass=NullPool)
        with engine.begin() as connection:
            if guarded_instance is not None:
                assert_safe_test_database(
                    connection, database_url=str(db_url), environment="test"
                )
        if guarded_instance is None:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE TABLE test_database_marker (marker_id integer PRIMARY KEY, "
                        "project_identifier text NOT NULL, suite_token text NOT NULL)"
                    )
                )
                connection.execute(
                    text(
                        "INSERT INTO test_database_marker VALUES (1, :marker, :token)"
                    ),
                    {"marker": PROJECT_MARKER, "token": args.token},
                )
                assert_safe_test_database(
                    connection, database_url=str(db_url), environment="test"
                )
        # Block outbound socket connections in addition to canonical kill switches.
        from qa.network_guard import restrict_egress

        restrict_egress(
            admin_url.port or 5432,
            local_supplier_fixture=os.environ.get("QA_PHASE") in {"2", "3"},
        )
        from vayujit_api.core.config import get_settings
        from vayujit_api.core.database import Base
        from vayujit_api.core.database import engine as app_engine
        from vayujit_api.main import app

        cfg = get_settings()
        if os.environ.get("QA_BROWSER_PHASE") == "WP7A7":
            from qa.wp7a7_fixture import install as install_closure_clock

            install_closure_clock(app, args.token, engine)
        if cfg.live_mutations_enabled or not cfg.external_mutations_emergency_stop:
            raise ValueError("QA_PROVIDER_SAFETY_DENIED")
        if os.environ.get("QA_BROWSER_PHASE") in {"WP7A5", "WP7A6", "WP7A7"}:
            from cryptography.fernet import Fernet

            # Local metadata/analysis only; all external kill switches and socket guards remain.
            cfg.intelligence_enabled = True
            cfg.credential_encryption_key = Fernet.generate_key().decode("ascii")
        if args.migrate:
            from alembic import command

            from qa.validate_postgres_instance import QaMigrationConfig

            root = Path(__file__).resolve().parents[1]
            migration = QaMigrationConfig(str(root / "apps/api/alembic.ini"))
            migration.set_main_option("script_location", str(root / "apps/api/alembic"))
            command.upgrade(migration, "head")
        else:
            Base.metadata.create_all(engine)
        args.output.mkdir(parents=True, exist_ok=True)
        schema = app.openapi()
        (args.output / "openapi.json").write_text(
            json.dumps(schema, indent=2), encoding="utf-8"
        )
        if args.pytest:
            # Same fresh marked database, egress guard and finally cleanup as browsers.
            # Do not reuse shared development/integration/golden databases.
            import pytest

            if "test_qa_phase3a_remediation.py" in args.pytest:
                tested_sources = [
                    "apps/api/vayujit_api/commerce/financial_router.py",
                    "apps/api/vayujit_api/commerce/inventory_router.py",
                    "apps/api/vayujit_api/operations/action_center_router.py",
                    "apps/api/tests/test_qa_phase3a_remediation.py",
                ]
                (args.output / "tested-source-sha256.json").write_text(
                    json.dumps(
                        {
                            name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
                            for name in tested_sources
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            if "test_qa_phase3b_remediation.py" in args.pytest:
                phase3b_sources = [
                    "apps/api/vayujit_api/commerce/financial_router.py",
                    "apps/api/vayujit_api/operations/action_center_router.py",
                    "apps/api/tests/test_qa_phase3b_remediation.py",
                    "apps/web/src/app/operations/action-center.component.ts",
                    "apps/web/src/app/marketplaces/financial-workspace.component.ts",
                    "apps/web/src/app/marketplaces/marketplace.service.ts",
                    "apps/web/src/app/shared/seller-navigation.component.ts",
                    "qa/tests/phase3b.spec.mjs",
                ]
                (args.output / "tested-phase3b-source-sha256.json").write_text(
                    json.dumps(
                        {
                            name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
                            for name in phase3b_sources
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            result = pytest.main(
                [
                    *[str(Path("apps/api/tests") / name) for name in args.pytest],
                    "-o",
                    "addopts=",
                    "--junitxml=" + str(args.output / "backend-results.xml"),
                ]
            )
            # Alembic uses the app engine too. Release this owned pool before
            # signed cleanup checks for active sessions; never terminate sessions.
            app_engine.dispose()
            raise SystemExit(result)

        if os.environ.get("QA_PHASE") == "3":
            from qa.runtime_supervisor import supervise

            supervise(args.port, args.token)
            app_engine.dispose()
            return

        @app.get("/__qa/witness", include_in_schema=False)
        def witness() -> dict[str, object]:
            assert engine is not None
            with engine.connect() as connection:
                assert_safe_test_database(
                    connection, database_url=str(db_url), environment="test"
                )
            return {
                "token": args.token,
                "disposable": True,
                "schema": "ORM_METADATA_NOT_MIGRATION_CERTIFICATION",
            }

        import uvicorn

        if os.environ.get("QA_BROWSER_PHASE") in {
            "WP7A",
            "WP7A2",
            "WP7A3",
            "WP7A4",
            "WP7A5",
            "WP7A6",
            "WP7A7",
        }:
            from qa.wp7a_fixture import install

            install(app, args.token, engine, args.output)
        if os.environ.get("QA_BROWSER_PHASE") in {
            "WP7A2",
            "WP7A3",
            "WP7A4",
            "WP7A5",
            "WP7A6",
            "WP7A7",
        }:
            from qa.wp7a2_fixture import install as install_followup

            install_followup(app, args.token, engine, args.output)

        if os.environ.get("QA_BROWSER_PHASE") in {
            "WP7A3",
            "WP7A4",
            "WP7A5",
            "WP7A6",
            "WP7A7",
        }:
            from qa.wp7a3_fixture import install as install_third

            install_third(app, args.token, engine, args.output)

        if os.environ.get("QA_BROWSER_PHASE") in {"WP7A4", "WP7A5", "WP7A6", "WP7A7"}:
            from qa.wp7a4_fixture import install as install_fourth

            install_fourth(app, args.token, engine, args.output)

        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=args.port,
                log_level="error",
                access_log=False,
            )
        )

        def watch_parent() -> None:
            # Parent closes only this child's stdin, allowing uvicorn/finally cleanup on Windows.
            sys.stdin.read()
            server.should_exit = True

        threading.Thread(target=watch_parent, daemon=True).start()
        server.run()
        app_engine.dispose()
    finally:
        # Release this process's application pool even if fixture installation fails.
        # Never terminate sessions belonging to another process or weaken drop guards.
        if "app_engine" in locals():
            app_engine.dispose()
        if engine is not None:
            with engine.connect() as connection:
                assert_safe_test_database(
                    connection, database_url=str(db_url), environment="test"
                )
                actual = connection.scalar(
                    text(
                        "select suite_token from test_database_marker where marker_id=1"
                    )
                )
                if actual != args.token:
                    raise ValueError("QA_CLEANUP_MARKER_MISMATCH")
            engine.dispose()
        if created and guarded_instance is not None:
            drop_timeout_ms = int(
                os.environ.get("QA_DATABASE_DROP_TIMEOUT_MS", "15000")
            )
            guarded_instance.drop(args.token, timeout_ms=drop_timeout_ms)
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "cleanup.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "database": name,
                        "marker_verified": True,
                        "database_absent": True,
                        "drop_statement_timeout_ms": drop_timeout_ms,
                        "signed_lifecycle": True,
                    }
                ),
                encoding="utf-8",
            )
        if created and guarded_instance is None:
            with admin.connect() as connection:
                # Exact fresh QA database only; never terminate another database's sessions.
                connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
                remains = connection.scalar(
                    text("select 1 from pg_database where datname=:name"),
                    {"name": name},
                )
                if remains:
                    raise ValueError("QA_CLEANUP_DATABASE_REMAINS")
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "cleanup.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "database": name,
                        "marker_verified": True,
                        "database_absent": True,
                    }
                ),
                encoding="utf-8",
            )
        admin.dispose()


if __name__ == "__main__":
    # SIGINT is handled by uvicorn; finally validates the token before cleanup.
    try:
        run()
    except Exception as error:  # noqa: BLE001 - sanitized CLI boundary
        # No exception text, SQL, environment, credentials or raw subprocess output.
        diagnostic = {
            "code": "QA_FIXTURE_FAILED",
            "exception_type": type(error).__name__,
            "frames": [
                {"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                for f in traceback.extract_tb(error.__traceback__)
            ],
        }
        if "--output" in sys.argv:
            destination = Path(sys.argv[sys.argv.index("--output") + 1])
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "fixture-failure.json").write_text(
                json.dumps(diagnostic), encoding="utf-8"
            )
        raise SystemExit(1) from None
