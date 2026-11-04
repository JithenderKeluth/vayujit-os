"""WP7A4 read-only final audit; never changes Docker resources or repairs lifecycle state."""

import hashlib
import json
import zipfile
from urllib.parse import quote, quote_plus

from qa.postgres_instance import PRIVATE, ROOT
from qa.wp4_final_audit import main as audit
from qa.wp7a3_final_audit import observed_preservation


def main(package="wp7a4"):
    if package not in {"wp7a4", "wp7a5", "wp7a6", "wp7a7"}:
        raise ValueError("QA_AUDIT_SCOPE_DENIED")
    code = audit(package, docker_audit=observed_preservation)
    target = ROOT / f"tmp/qa-{package}-final-audit.json"
    result = json.loads(target.read_text())
    baseline = json.loads((ROOT / f"tmp/qa-{package}/baseline.json").read_text())
    result["historical_baseline_unchanged"] = all(
        hashlib.sha256((ROOT / row["file"]).read_bytes()).hexdigest() == row["sha256"]
        for row in baseline["files"]
    )
    secrets = [
        (PRIVATE / n).read_text().strip()
        for n in ("qa-password", "bootstrap-password", "guard-key")
    ]
    needles = {
        v.encode()
        for secret in secrets
        for v in (secret, quote(secret, safe=""), quote_plus(secret))
    }
    roots = [ROOT / f"tmp/qa-{package}", ROOT / f"tmp/qa-{package}-backend"]
    roots += [ROOT / "tmp/qa-seller-browser" / d["token"] for d in result["databases"]]
    files = traces = 0
    for root in roots:
        for file in root.rglob("*"):
            if not file.is_file():
                continue
            if file.suffix in {".json", ".md", ".xml"}:
                if any(n in file.read_bytes() for n in needles):
                    raise ValueError("WP7A4_SECRET_REVIEW_REQUIRED")
                files += 1
            if file.name == "trace.zip":
                with zipfile.ZipFile(file) as trace:
                    assert trace.testzip() is None
                    for name in trace.namelist():
                        if any(n in trace.read(name) for n in needles):
                            raise ValueError("WP7A4_TRACE_SECRET_REVIEW_REQUIRED")
                traces += 1
    for file in (ROOT / "docs/qa/seller-experience").glob(f"*{package}*.*"):
        if file.suffix in {".json", ".md"}:
            assert not any(n in file.read_bytes() for n in needles)
            files += 1
    result["extended_secret_scan"] = {"files": files, "traces": traces, "matches": 0}
    result["database_absence_status"] = (
        "PASS"
        if result["databases"]
        and all(d["absent"] and d["state"] == "DROPPED" for d in result["databases"])
        else "FAIL"
    )
    if result["docker_preservation"]["status"] != "PASS":
        code = 1
        result["status"] = "DATABASES_ABSENT_ENVIRONMENT_BASELINE_DRIFT"
    if not result["historical_baseline_unchanged"]:
        code = 1
        result["status"] = "BASELINE_CHANGED"
    if package in {"wp7a6", "wp7a7"} and result["database_absence_status"] != "PASS":
        # Runtime drift never implies that a still-present QA database is absent.
        code = 1
        result["status"] = "CLEANUP_PENDING"
    target.write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                "status": result["status"],
                "databases": len(result["databases"]),
                "traces": traces,
                "secret_matches": 0,
            }
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
