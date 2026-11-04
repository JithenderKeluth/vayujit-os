"""Read-only metadata proof for exact Phase 4C disposable targets; never drops."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main() -> None:
    backend = sys.argv[1]
    if not re.fullmatch(r"tmp/qa-agent/[a-f0-9]{16}", backend):
        raise ValueError("QA_AUDIT_BACKEND_TARGET_DENIED")
    reports = [
        "docs/qa/phase-4c-execution.json",
        "docs/qa/history/phase-4c-initial-fixture-contract-blocked.json",
    ]
    targets = {
        row["database"]
        for report in reports
        for row in json.loads(Path(report).read_text(encoding="utf-8"))["cleanup"]
    }
    targets.add(json.loads(Path(backend, "cleanup.json").read_text())["database"])
    if any(not re.fullmatch(r"vayujit_qa[a-f0-9]{16}_test", name) for name in targets):
        raise ValueError("QA_AUDIT_DATABASE_TARGET_DENIED")
    url = make_url(os.environ["QA_DATABASE_ADMIN_URL"])
    if url.host != "127.0.0.1" or url.database != "postgres":
        raise ValueError("QA_AUDIT_ADMIN_TARGET_DENIED")
    engine = create_engine(url)
    with engine.connect() as connection:
        present = connection.scalars(
            text("SELECT datname FROM pg_database WHERE datname = ANY(:targets)"),
            {"targets": sorted(targets)},
        ).all()
    engine.dispose()
    result = {
        "method": (
            "read-only pg_database query of exact task-owned names; "
            "no DROP or session termination"
        ),
        "targets": sorted(targets),
        "remaining": list(present),
        "status": "PASS" if not present else "FAIL",
    }
    Path("docs/qa/phase-4c-cleanup-verification.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result))
    if present:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
