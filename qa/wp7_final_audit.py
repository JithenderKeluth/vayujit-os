"""Read-only WP7 lifecycle, trace integrity, action census and secret audit."""

import json
import zipfile
from collections import Counter
from urllib.parse import quote, quote_plus

from qa.postgres_instance import PRIVATE, ROOT, QaInstance
from qa.wp4_final_audit import main as lifecycle_audit


def main():
    status = lifecycle_audit("wp7")
    destination = ROOT / "tmp/qa-wp7-final-audit.json"
    result = json.loads(destination.read_text(encoding="utf-8"))
    instance = QaInstance()
    for database in result["databases"]:
        record = instance.load(database["token"])
        database["cleanup_resolution"] = record.get("cleanup_resolution", "NORMAL_GUARDED_DROP")
        database["original_failure_preserved"] = record.get("original_failure_preserved")
        database["no_database_deleted_by_reconciliation"] = record.get(
            "no_database_deleted_by_reconciliation"
        )
    secrets = [
        (PRIVATE / name).read_text().strip()
        for name in ("qa-password", "bootstrap-password", "guard-key")
    ]
    needles = {
        variant.encode()
        for value in secrets
        for variant in (value, quote(value, safe=""), quote_plus(value))
    }
    roots = [ROOT / "tmp/qa-wp7", ROOT / "tmp/qa-wp7-backend"]
    roots += [ROOT / "tmp/qa-seller-browser" / d["token"] for d in result["databases"]]
    files = 0
    trace_actions = []
    for folder in roots:
        if not folder.exists():
            continue
        for file in folder.rglob("*"):
            if not file.is_file():
                continue
            if file.suffix in {".xml", ".json", ".md"}:
                content = file.read_bytes()
                if any(needle in content for needle in needles):
                    raise ValueError("WP7_CREDENTIAL_MATCH_REVIEW_REQUIRED")
                files += 1
            if file.name == "trace.zip":
                counts = Counter()
                with zipfile.ZipFile(file) as trace:
                    assert trace.testzip() is None
                    for item in trace.namelist():
                        if not item.endswith((".trace", ".network")):
                            continue
                        content = trace.read(item)
                        if any(needle in content for needle in needles):
                            raise ValueError("WP7_TRACE_CREDENTIAL_MATCH_REVIEW_REQUIRED")
                        if item.endswith(".trace"):
                            for line in content.splitlines():
                                event = json.loads(line)
                                if event.get("type") == "before":
                                    # Never retain arguments, cookies, DOM or entered values.
                                    name = event.get("method", "unknown")
                                    counts[name] += 1
                trace_actions.append(
                    {
                        "path": file.relative_to(ROOT).as_posix(),
                        "crc": "PASS",
                        "action_method_counts": dict(counts),
                    }
                )
    result["extended_evidence_secret_scan"] = {
        "files_checked": files,
        "credential_matches": 0,
        "raw_output_persisted": False,
    }
    result["trace_action_census"] = trace_actions
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {"status": result["status"], "trace_census": len(trace_actions), "files_checked": files}
        )
    )
    return status


if __name__ == "__main__":
    raise SystemExit(main())
