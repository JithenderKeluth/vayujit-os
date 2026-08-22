from __future__ import annotations

import argparse
import json
import sys

from vayujit_api.operations.media_backup import (
    MediaBackupError,
    create_media_backup,
    restore_media_backup,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="VAYUJIT local media backup tooling")
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("source")
    backup.add_argument("destination")
    restore = sub.add_parser("restore")
    restore.add_argument("archive")
    restore.add_argument("manifest")
    restore.add_argument("destination")
    args = parser.parse_args()
    try:
        if args.command == "backup":
            archive, manifest = create_media_backup(args.source, args.destination)
            print(
                json.dumps(
                    {
                        "status": "PASS",
                        "archive": str(archive),
                        "manifest": str(manifest),
                    }
                )
            )
        else:
            result = restore_media_backup(args.archive, args.manifest, args.destination)
            print(json.dumps({"status": "PASS", **result}))
        return 0
    except MediaBackupError as error:
        print(json.dumps({"status": "FAIL", "message": str(error)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
