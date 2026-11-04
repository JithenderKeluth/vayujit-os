"""Private CLI used by the Windows PC profile's encrypted backup wrapper."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from vayujit_api.core.config import get_settings
from vayujit_api.operations.media_backup import create_media_backup, restore_media_backup


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--output-directory", required=True)
    create.add_argument("--backup-id", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--archive", required=True)
    verify.add_argument("--manifest", required=True)
    args = parser.parse_args()

    if args.command == "create":
        destination = Path(args.output_directory)
        destination.mkdir(parents=True, exist_ok=True)
        archive, manifest = create_media_backup(
            get_settings().media_storage_directory,
            destination,
            lineage={
                "backup_id": args.backup_id,
                "environment": "pc_local",
                "database_name": "vayujit_business",
            },
        )
        output_archive = destination / "media.zip"
        output_manifest = destination / "media.json"
        archive.replace(output_archive)
        manifest.replace(output_manifest)
        print(json.dumps({"files": len(json.loads(output_manifest.read_text("utf-8"))["files"])}))
        return 0

    with tempfile.TemporaryDirectory(prefix="vayujit-media-verify-") as temporary:
        report = restore_media_backup(
            args.archive,
            args.manifest,
            Path(temporary) / "restored-media",
        )
        shutil.rmtree(Path(temporary) / "restored-media", ignore_errors=True)
        print(json.dumps({"verified_files": report["files"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
