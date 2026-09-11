"""Run one deterministic integration shard and persist a resumable result record."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("var/certification/integration-manifest.json"))
    parser.add_argument("--shard", required=True)
    parser.add_argument("--output", type=Path, default=Path("var/certification/shard-results.jsonl"))
    parser.add_argument("--pytest", type=Path, default=Path("apps/api/.venv/Scripts/pytest.exe"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    shard = next((item for item in manifest["shards"] if item["id"] == args.shard), None)
    if shard is None:
        raise SystemExit(f"Unknown shard: {args.shard}")
    node_ids = [str(value) for value in shard["node_ids"]]
    started = time.perf_counter()
    completed = subprocess.run([str(args.pytest), *node_ids], cwd=Path("apps/api"), text=True, check=False)
    record = {
        "shard_id": args.shard,
        "node_ids": node_ids,
        "passed": completed.returncode == 0,
        "failed": completed.returncode != 0,
        "skipped": None,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "timestamp": datetime.now(UTC).isoformat(),
        "inventory_sha256": manifest["inventory_sha256"],
        "node_ids_sha256": hashlib.sha256("\n".join(node_ids).encode()).hexdigest(),
        "return_code": completed.returncode,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())