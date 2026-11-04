"""Read-only local migration preflight. Never backs up, migrates, seeds or deletes data."""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
stage = "initialization"


def allowed_target(host: str | None, port: int | None, name: str | None) -> bool:
    # This diagnostic's authority is the confirmed local application, not a URL
    # found in an environment file or the separately approved synthetic QA server.
    return host == "127.0.0.1" and port == 5432 and name == "vayujit"


def run() -> dict[str, object]:
    global stage
    stage = "configuration"
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.pool import NullPool
    from vayujit_api.core.config import Settings

    os.chdir(ROOT)
    # Compare both supported invocation directories, without printing credentials.
    candidates = [
        Settings(_env_file=(ROOT / ".env", ROOT.parent.parent / ".env")).database_url,
        Settings(_env_file=(ROOT / "apps/api/.env", ROOT / ".env")).database_url,
    ]
    if len(set(candidates)) != 1:
        return {
            "status": "BLOCKED",
            "code": "AMBIGUOUS_CONFIG_TARGET",
            "database_changed": False,
        }
    url = make_url(candidates[0])
    target = {"host": url.host, "port": url.port, "database": url.database}
    if url.get_backend_name() != "postgresql" or not allowed_target(
        url.host, url.port, url.database
    ):
        return {
            "status": "BLOCKED",
            "code": "EXACT_TARGET_CONFIRMATION_REQUIRED",
            "target": target,
            "database_changed": False,
        }
    witness_script = (
        "$ErrorActionPreference='Stop'; $l=@(Get-NetTCPConnection -LocalPort 8000 -State Listen);"
        "if($l.Count -ne 1){exit 2};"
        "$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$l[0].OwningProcess);"
        "@{pid=$p.ProcessId;module_matches=($p.CommandLine -match 'uvicorn\\s+vayujit_api\\.main:app');"
        "repo_matches=($p.CommandLine -like ('*'+(Get-Location).Path+'*'));"
        "loopback=($l[0].LocalAddress -eq '127.0.0.1')}|ConvertTo-Json -Compress"
    )
    stage = "runtime_witness"
    witness = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", witness_script],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if witness.returncode:
        return {
            "status": "BLOCKED",
            "code": "RUNTIME_IDENTITY_UNAVAILABLE",
            "database_changed": False,
        }
    runtime = json.loads(witness.stdout)
    if not all(
        runtime.get(k) is True for k in ("module_matches", "repo_matches", "loopback")
    ):
        return {
            "status": "BLOCKED",
            "code": "RUNTIME_IDENTITY_MISMATCH",
            "database_changed": False,
        }
    stage = "api_health"
    with urllib.request.urlopen(
        "http://127.0.0.1:8000/health/ready", timeout=20
    ) as response:
        health = json.load(response)
    config = Config(str(ROOT / "apps/api/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "apps/api/alembic"))
    graph = ScriptDirectory.from_config(config)
    stage = "database_identity"
    engine = create_engine(
        url,
        poolclass=NullPool,
        connect_args={
            "options": "-c default_transaction_read_only=on -c statement_timeout=5000",
            "application_name": "vayujit_explicit_local_migration_preflight",
        },
    )
    try:
        with engine.connect() as db:
            assert db.scalar(text("SHOW transaction_read_only")) == "on"
            identity = db.execute(
                text(
                    "SELECT current_database(), current_user, current_setting('server_version')"
                )
            ).one()
            revisions = list(
                db.scalars(text("SELECT version_num FROM alembic_version"))
            )
            if identity[0] != url.database or revisions != [
                health.get("current_migration")
            ]:
                return {
                    "status": "BLOCKED",
                    "code": "RUNTIME_DATABASE_REVISION_MISMATCH",
                    "database_changed": False,
                }
            stage = "schema_metadata"
            schema = inspect(db)
            names = set(schema.get_table_names())
            required = [
                "catalog_product_lineages",
                "catalog_product_variants",
                "inventory_items",
                "inventory_movements",
                "channel_sku_mappings",
                "marketplace_orders",
                "operational_signals",
            ]
            video_columns = {
                c["name"]: c for c in schema.get_columns("video_generations")
            }
            ads_columns = {c["name"] for c in schema.get_columns("ad_campaigns")}
            pending = list(graph.iterate_revisions(graph.get_heads(), revisions))
            existing_relations = set(
                db.scalars(
                    text(
                        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                        "WHERE n.nspname='public'"
                    )
                )
            )
            collisions = []
            for migration in reversed(pending):
                tree = ast.parse(Path(migration.path).read_text(encoding="utf-8"))
                upgrades = [
                    n
                    for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == "upgrade"
                ]
                for upgrade in upgrades:
                    for call in ast.walk(upgrade):
                        if (
                            isinstance(call, ast.Call)
                            and isinstance(call.func, ast.Attribute)
                            and call.func.attr in {"create_table", "create_index"}
                            and call.args
                            and isinstance(call.args[0], ast.Constant)
                            and isinstance(call.args[0].value, str)
                            and call.args[0].value in existing_relations
                        ):
                            collisions.append(
                                {
                                    "revision": migration.revision,
                                    "operation": call.func.attr,
                                    "object": call.args[0].value,
                                }
                            )
            result = {
                "status": "READ_ONLY_PREFLIGHT_COMPLETE",
                "database_changed": False,
                "target": target,
                "runtime": runtime,
                "role": identity[1],
                "server_version": identity[2],
                "database_revision": revisions,
                "api_current_revision_matches": True,
                "repository_heads": graph.get_heads(),
                "health_expected_revision": health.get("expected_migration"),
                "pending": [
                    {"revision": r.revision, "description": r.doc}
                    for r in reversed(pending)
                ],
                "pending_create_collisions": collisions,
                "known_table_presence": {n: n in names for n in required},
                "video_version_columns": {
                    n: n in video_columns
                    for n in (
                        "storyboardversion",
                        "storyboard_version",
                        "styleversion",
                        "style_version",
                    )
                },
                "ads_recovery_columns": {
                    n: n in ads_columns
                    for n in (
                        "failure_category",
                        "retry_after_seconds",
                        "next_retry_at",
                        "correlation_id",
                    )
                },
                "owner_rows": db.scalar(text("SELECT count(*) FROM users")),
                "single_owner_constraint_present": any(
                    c["name"] == "ck_users_single_owner"
                    for c in schema.get_check_constraints("users")
                ),
                "secrets_or_business_records_in_report": False,
            }
            db.rollback()
            return result
    finally:
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.parse_args()
    try:
        result = run()
    except Exception as error:  # noqa: BLE001 - redact at CLI boundary
        # SQL exceptions can contain connection strings or customer data. Never
        # persist traceback/message/raw process output at this diagnostic boundary.
        result = {
            "status": "BLOCKED",
            "code": "PREFLIGHT_FAILED",
            "stage": stage,
            "exception_type": type(error).__name__,
            "database_changed": False,
        }
    destination = ROOT / "tmp/local-database-migration-preflight.json"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    raise SystemExit(0 if result["status"] == "READ_ONLY_PREFLIGHT_COMPLETE" else 1)
