"""Build deterministic integration-test inventory and shards."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def _node_ids(output: str) -> list[str]:
    values: set[str] = set()
    for raw in output.splitlines():
        value = raw.strip().replace("\\", "/")
        if "::" not in value:
            continue
        if value.startswith("apps/api/"):
            value = value.removeprefix("apps/api/")
        if value.startswith("tests/"):
            values.add(value)
    return sorted(values)


def build_manifest(
    pytest_path: Path, api_root: Path, shard_size: int
) -> dict[str, object]:
    command = ["apps/api", "-m", "integration", "--collect-only", "-q"]
    completed = subprocess.run(
        [str(pytest_path.resolve()), *command],
        cwd=api_root.resolve().parent.parent,
        check=True,
        text=True,
        capture_output=True,
    )
    node_ids = _node_ids(completed.stdout)
    if not node_ids:
        raise RuntimeError("No integration node IDs were collected.")
    shards = [
        {
            "id": f"integration-{index + 1:03d}",
            "node_ids": node_ids[start : start + shard_size],
        }
        for index, start in enumerate(range(0, len(node_ids), shard_size))
    ]
    for shard in shards:
        shard["count"] = len(shard["node_ids"])
    encoded = "\n".join(node_ids).encode()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "collection_command": "pytest apps/api -m integration --collect-only -q",
        "selected_count": len(node_ids),
        "node_ids": node_ids,
        "inventory_sha256": hashlib.sha256(encoded).hexdigest(),
        "shard_size": shard_size,
        "shard_count": len(shards),
        "shards": shards,
    }


def verify_manifest(manifest: dict[str, object]) -> dict[str, int]:
    expected = [str(value) for value in manifest["node_ids"]]
    members = [str(node) for shard in manifest["shards"] for node in shard["node_ids"]]
    expected_set = set(expected)
    member_set = set(members)
    counts = Counter(members)
    return {
        "missing": len(expected_set - member_set),
        "duplicates": sum(value - 1 for value in counts.values() if value > 1),
        "extras": len(member_set - expected_set),
        "membership_total": len(members),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("var/certification/integration-manifest.json"),
    )
    parser.add_argument("--shard-size", type=int, default=100)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument(
        "--pytest", type=Path, default=Path("apps/api/.venv/Scripts/pytest.exe")
    )
    args = parser.parse_args()
    if args.verify:
        manifest = json.loads(args.output.read_text(encoding="utf-8"))
        print(json.dumps(verify_manifest(manifest), sort_keys=True))
        return 0
    if args.shard_size < 1:
        parser.error("--shard-size must be positive")
    manifest = build_manifest(args.pytest, Path("apps/api"), args.shard_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: manifest[key]
                for key in ("selected_count", "shard_count", "inventory_sha256")
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
