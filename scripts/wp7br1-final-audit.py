"""Read-only R1 absence and evidence audit. No lifecycle mutations or repairs."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote, quote_plus

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "apps/api")]


def main() -> None:
    from sqlalchemy import text

    from qa.postgres_instance import PRIVATE, QaInstance, database_name
    from qa.wp7a3_final_audit import observed_preservation

    instance = QaInstance()
    instance.verify_server()
    folders = [
        p for p in (ROOT / "tmp/qa-seller-browser").iterdir() if (p / "wp7br1-run.json").exists()
    ]
    # This startup never reached READY, hence has no parent run receipt.
    # Its retained session/cleanup records identify the exact R1-owned attempt.
    startup = ROOT / "tmp/qa-seller-browser/27c1eddaf9ab91c5"
    final = json.loads((startup / "session-final.json").read_text())
    assert final["token"] == startup.name and final["cleanup"]["signed_lifecycle"]
    folders.append(startup)
    backend = ROOT / "tmp/qa-wp7br1-backend"
    roots = folders + list(backend.iterdir())
    tokens = sorted({p.name for p in roots})
    rows = []
    engine = instance.engine()
    try:
        with engine.connect() as connection:
            for token in tokens:
                state = instance.load(token)
                absent = (
                    connection.scalar(
                        text("SELECT count(*) FROM pg_database WHERE datname=:name"),
                        {"name": database_name(token)},
                    )
                    == 0
                )
                rows.append({"token": token, "signed_state": state["state"], "absent": absent})
    finally:
        engine.dispose()
    baseline = json.loads((ROOT / "tmp/qa-wp7br1/preserved-wp7b.json").read_text())
    preserved = all(
        hashlib.sha256((ROOT / r["file"]).read_bytes()).hexdigest() == r["sha256"]
        for r in baseline["files"]
    )
    prior = json.loads((ROOT / "tmp/qa-wp7b/provenance.json").read_text())
    a7_preserved = all(
        hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
        for name, digest in prior["manifest"].items()
    )
    secrets = [
        (PRIVATE / n).read_text().strip()
        for n in ("qa-password", "bootstrap-password", "guard-key")
    ]
    needles = {v.encode() for s in secrets for v in (s, quote(s, safe=""), quote_plus(s))}
    traces, files, leaks = [], 0, 0
    for root in roots + [ROOT / "tmp/qa-wp7br1", ROOT / "docs/qa/seller-experience"]:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() in {".json", ".jsonl", ".md", ".xml"}:
                files += 1
                leaks += int(any(n in p.read_bytes() for n in needles))
            if p.name == "trace.zip":
                with zipfile.ZipFile(p) as z:
                    crc = z.testzip() is None
                    for name in z.namelist():
                        leaks += int(any(n in z.read(name) for n in needles))
                traces.append({"path": p.relative_to(ROOT).as_posix(), "crc_pass": crc})
    result = {
        "package": "WP7B-R1",
        "read_only": True,
        "instance_id": instance.manifest["instance_id"],
        "endpoint": "127.0.0.1:55432",
        "role": "vayujit_qa_admin",
        "databases": rows,
        "database_cleanup": (
            "PASS"
            if rows and all(r["absent"] and r["signed_state"] == "DROPPED" for r in rows)
            else "FAIL"
        ),
        "original_wp7b_files_unchanged": preserved,
        "original_wp7b_file_count": len(baseline["files"]),
        "original_wp7a7_provenance_files_unchanged": a7_preserved,
        "protected_secret_matches": leaks,
        "text_files_scanned": files,
        "traces": traces,
        "docker_preservation": observed_preservation(instance),
        "permanent_database_accessed": False,
        "raw_output_persisted": False,
    }
    (ROOT / "tmp/qa-wp7br1/final-audit.json").write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "database_cleanup",
                    "original_wp7b_files_unchanged",
                    "protected_secret_matches",
                )
            }
            | {"databases": len(rows), "traces": len(traces)}
        )
    )
    if (
        result["database_cleanup"] != "PASS"
        or not preserved
        or not a7_preserved
        or leaks
        or not all(t["crc_pass"] for t in traces)
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 -- sanitize the CLI boundary; never print connection details
        print(json.dumps({"status": "BLOCKED", "raw_error_persisted": False}))
        raise SystemExit(1) from None
