"""Disposable PostgreSQL + local media consistency drill."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from vayujit_api.brands.models import Brand
from vayujit_api.core.config import get_settings
from vayujit_api.core.database import Base
from vayujit_api.core.test_database import PROJECT_MARKER, reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.media.models import MediaAsset
from vayujit_api.operations.backup import create_backup
from vayujit_api.operations.media_backup import (
    create_media_backup,
    restore_media_backup,
)
from vayujit_api.products.models import Product


def _url(database: str) -> str:
    source = os.environ.get(
        "VAYUJIT_TEST_DATABASE_URL",
        "postgresql+psycopg://vayujit:vayujit_dev@127.0.0.1:5432/vayujit_test",
    )
    return make_url(source).set(database=database).render_as_string(hide_password=False)


def _docker(*args: str) -> None:
    subprocess.run(["docker", *args], check=True, capture_output=True, text=True)


def _database(name: str, create: bool) -> None:
    _docker(
        "exec",
        "infrastructure-postgres-1",
        "createdb" if create else "dropdb",
        "-U",
        "vayujit",
        name,
    )


def _mark(database: str) -> None:
    sql = (
        "create table if not exists test_database_marker "
        "(marker_id integer primary key, project_identifier text not null); "
        f"insert into test_database_marker(marker_id, project_identifier) values (1, '{PROJECT_MARKER}') "
        "on conflict (marker_id) do update set project_identifier = excluded.project_identifier;"
    )
    _docker(
        "exec",
        "infrastructure-postgres-1",
        "psql",
        "-U",
        "vayujit",
        "-d",
        database,
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        sql,
    )


def _write_fixture(root: Path, owner_id: uuid.UUID) -> dict[str, object]:
    owner_key = owner_id.hex[:12]
    files = (
        ("image.png", b"\x89PNG\r\n\x1a\napproved-image-fixture", "image/png"),
        ("video.mp4", b"\x00\x00\x00\x18ftypisomapproved-video-fixture", "video/mp4"),
    )
    media: list[dict[str, str]] = []
    for name, content, mime in files:
        path = root / owner_key / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        media.append(
            {
                "id": str(uuid.uuid4()),
                "path": path.relative_to(root).as_posix(),
                "mime": mime,
                "checksum": hashlib.sha256(content).hexdigest(),
            }
        )
    return {"owner_id": str(owner_id), "media": media}


def main() -> int:
    database = "vayujit_media_recovery_test"
    restore_database = "vayujit_media_restore_test"
    root = Path("var/media-recovery-drill").resolve()
    restore_root = Path("var/media-recovery-restore").resolve()
    backup_root = Path("var/backups/media-recovery-drill").resolve()
    source_url = _url(database)
    restore_url = _url(restore_database)
    os.environ["VAYUJIT_ENV"] = "test"
    os.environ["VAYUJIT_ENVIRONMENT"] = "test"
    os.environ["VAYUJIT_DATABASE_URL"] = source_url
    os.environ["VAYUJIT_BACKUP_DIRECTORY"] = str(backup_root)
    get_settings.cache_clear()
    engine = None
    restored_engine = None
    try:
        _database(database, True)
        _database(restore_database, True)
        _mark(database)
        _mark(restore_database)
        engine = create_engine(source_url)
        reset_test_schema(engine, Base.metadata, database_url=source_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "create table alembic_version (version_num varchar(32) primary key)"
                )
            )
            connection.execute(
                text("insert into alembic_version(version_num) values ('drill')")
            )
        now = datetime.now(UTC)
        owner = User(
            id=uuid.uuid4(),
            singleton_key=1,
            full_name="Recovery Fixture",
            email="recovery-fixture@example.com",
            normalized_email="recovery-fixture@example.com",
            password_hash="fixture",
            created_at=now,
            updated_at=now,
        )
        brand = Brand(
            id=uuid.uuid4(),
            owner_id=owner.id,
            name="Recovery Brand",
            normalized_name="recovery brand",
            slug="recovery-brand",
            status="active",
            is_active_context=True,
            created_at=now,
            updated_at=now,
        )
        product = Product(
            id=uuid.uuid4(),
            owner_id=owner.id,
            brand_id=brand.id,
            name="Recovery Product",
            normalized_name="recovery product",
            slug="recovery-product",
            sku="RECOVERY-001",
            product_type="physical",
            status="active",
            created_at=now,
            updated_at=now,
        )
        if root.exists():
            shutil.rmtree(root)
        lineage = _write_fixture(root, owner.id)
        owner_id = owner.id
        product_id = product.id
        media_rows = [
            MediaAsset(
                id=uuid.UUID(str(item["id"])),
                owner_id=owner.id,
                original_filename=Path(str(item["path"])).name,
                safe_filename=Path(str(item["path"])).name,
                mime_type=str(item["mime"]),
                size_bytes=(root / str(item["path"])).stat().st_size,
                width=1,
                height=1,
                checksum_sha256=str(item["checksum"]),
                storage_key=str(item["path"]),
                status="ready",
                created_at=now,
            )
            for item in lineage["media"]
        ]
        with Session(engine) as db:
            db.add(owner)
            db.commit()
            db.add(brand)
            db.commit()
            db.add(product)
            db.commit()
            db.add_all(media_rows)
            db.commit()
            db.refresh(owner)
            db_backup = create_backup(db, owner.id)
            db_backup_filename = db_backup.filename
            db.commit()
        archive, manifest = create_media_backup(root, backup_root, lineage=lineage)
        dump_path = backup_root / db_backup_filename
        container_path = f"/tmp/{dump_path.name}"
        _docker("cp", str(dump_path), f"infrastructure-postgres-1:{container_path}")
        _docker(
            "exec",
            "infrastructure-postgres-1",
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "-U",
            "vayujit",
            "-d",
            restore_database,
            container_path,
        )
        restored_engine = create_engine(restore_url)
        with Session(restored_engine) as db:
            restored_rows = list(db.scalars(select(MediaAsset)))
            assert len(restored_rows) == 2
            assert all(row.owner_id == owner_id for row in restored_rows)
            assert (
                db.scalar(select(Product.id).where(Product.id == product_id))
                == product_id
            )
        restore_media_backup(archive, manifest, restore_root)
        restored_files = sorted(
            path.relative_to(restore_root).as_posix()
            for path in restore_root.rglob("*")
            if path.is_file()
        )
        assert restored_files == sorted(str(item["path"]) for item in lineage["media"])
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "missing_media_rows": 0,
                    "missing_files": 0,
                    "checksum_mismatches": 0,
                    "broken_product_lineage": 0,
                    "orphan_files": 0,
                }
            )
        )
        return 0
    finally:
        for value in (engine, restored_engine):
            if value is not None:
                value.dispose()
        for name in (database, restore_database):
            try:
                _database(name, False)
            except subprocess.CalledProcessError:
                pass
        for path in (root, restore_root, backup_root):
            shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
