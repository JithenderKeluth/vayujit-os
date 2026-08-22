from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from test_ai_images_integration import upload_source

from vayujit_api.identity.models import User
from vayujit_api.media.models import MediaAsset
from vayujit_api.media.service import storage_path, storage_root, upload_generated_video
from vayujit_api.operations.media_backup import create_media_backup, restore_media_backup
from vayujit_api.products.models import Product

pytest_plugins = ("test_ai_images_integration",)
pytestmark = pytest.mark.integration


def test_product_media_rows_and_files_restore_together(
    context: tuple[Any, sessionmaker[Session], dict[str, str]],
    tmp_path: Path,
) -> None:
    client, factory, ids = context
    image_id = upload_source(client)
    with factory() as db:
        owner = db.scalar(select(User).order_by(User.created_at))
        product = db.get(Product, ids["product_id"])
        assert owner is not None and product is not None
        video = upload_generated_video(
            db,
            owner,
            "approved.mp4",
            b"\x00\x00\x00\x18ftypisom-approved-video",
            width=16,
            height=16,
        )
        db.commit()
        image = db.get(MediaAsset, image_id)
        assert image is not None
        lineage = {
            "owner_id": str(owner.id),
            "product_id": str(product.id),
            "media_ids": [str(image.id), str(video.id)],
        }
        source_paths = [storage_path(image.storage_key), storage_path(video.storage_key)]
        archive, manifest = create_media_backup(storage_root(), tmp_path, lineage=lineage)
        restored_root = tmp_path / "restored-media"
        result = restore_media_backup(archive, manifest, restored_root)
        assert result["lineage"] == lineage
        assert all(path.exists() for path in source_paths)
        assert all(
            (restored_root / path.relative_to(storage_root())).exists() for path in source_paths
        )
        assert {image.checksum_sha256, video.checksum_sha256} == {
            item.checksum_sha256 for item in (image, video)
        }
