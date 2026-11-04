"""Read-only lifecycle, baseline, trace-integrity and secret audit for WP7A2."""

import hashlib
import json
import zipfile
from urllib.parse import quote, quote_plus

from qa.postgres_instance import PRIVATE, ROOT
from qa.validate_postgres_instance import EVIDENCE, unchanged
from qa.wp4_final_audit import main as lifecycle_audit


def observed_preservation(instance):
    try:
        return {"status": "PASS", **unchanged(instance)}
    except AssertionError:
        # Preserve the strict historical result, but still report database
        # absence and the exact safe drift rather than aborting every audit.
        baseline = json.loads((EVIDENCE / "preflight.json").read_text(encoding="utf-8-sig"))
        differences = []
        for expected in baseline["containers"]:
            c = json.loads(instance.docker("inspect", expected["id"]))[0]
            actual = {
                "id": c["Id"],
                "name": c["Name"],
                "image": c["Image"],
                "status": c["State"]["Status"],
                "started": c["State"]["StartedAt"],
                "finished": c["State"]["FinishedAt"],
                "mounts": [
                    {k: m.get(k) for k in ("Type", "Name", "Source", "Destination", "RW")}
                    for m in c["Mounts"]
                ],
                "networks": list(c["NetworkSettings"]["Networks"]),
            }
            changed = [k for k in expected if expected[k] != actual[k]]
            if changed:
                differences.append(
                    {
                        "container": expected["name"],
                        "changed_fields": changed,
                        "runtime_only": set(changed) <= {"status", "started", "finished"},
                    }
                )
        from qa.postgres_instance import HOST_NETWORK, NETWORK, VOLUME

        collections = {}
        for kind, additions in [("network", {NETWORK, HOST_NETWORK}), ("volume", {VOLUME})]:
            actual = set(instance.docker(kind, "ls", "--format", "{{.Name}}").splitlines())
            expected = set(baseline[kind + "s"]) | additions
            collections[kind] = {"missing": len(expected - actual), "added": len(actual - expected)}
        return {
            "status": "HISTORICAL_BASELINE_CHANGED",
            "strict_original_check": "FAIL",
            "original_containers_inspected": len(baseline["containers"]),
            "differences": differences,
            "collections": collections,
            "structural_identity_unchanged": all(d["runtime_only"] for d in differences)
            and all(v == {"missing": 0, "added": 0} for v in collections.values()),
            "cause": (
                "UNATTRIBUTED; no unrelated Docker resource is changed "
                "to restore an old runtime state"
            ),
        }


def main():
    code = lifecycle_audit("wp7a2", docker_audit=observed_preservation)
    destination = ROOT / "tmp/qa-wp7a2-final-audit.json"
    result = json.loads(destination.read_text())
    baseline = json.loads((ROOT / "tmp/qa-wp7a2/baseline.json").read_text())
    result["historical_baseline_unchanged"] = all(
        hashlib.sha256((ROOT / row["file"]).read_bytes()).hexdigest() == row["sha256"]
        for row in baseline["files"]
    )
    secrets = [
        (PRIVATE / name).read_text().strip()
        for name in ("qa-password", "bootstrap-password", "guard-key")
    ]
    needles = {v.encode() for s in secrets for v in (s, quote(s, safe=""), quote_plus(s))}
    roots = [ROOT / "tmp/qa-wp7a2", ROOT / "tmp/qa-wp7a2-backend"]
    roots += [ROOT / "tmp/qa-seller-browser" / d["token"] for d in result["databases"]]
    files, traces = 0, 0
    for root in roots:
        for file in root.rglob("*"):
            if not file.is_file():
                continue
            if file.suffix in {".json", ".md", ".xml"}:
                if any(n in file.read_bytes() for n in needles):
                    raise ValueError("WP7A2_SECRET_MATCH_REVIEW_REQUIRED")
                files += 1
            if file.name == "trace.zip":
                with zipfile.ZipFile(file) as trace:
                    assert trace.testzip() is None
                    for entry in trace.namelist():
                        if any(n in trace.read(entry) for n in needles):
                            raise ValueError("WP7A2_TRACE_SECRET_MATCH_REVIEW_REQUIRED")
                traces += 1
    result["extended_secret_scan"] = {"files": files, "traces": traces, "matches": 0}
    result["approved_recoveries"] = [
        json.loads(p.read_text()) for p in (ROOT / "tmp/qa-wp7a2").glob("recovery-*.json")
    ]
    result["database_absence_status"] = (
        "PASS"
        if all(d["state"] == "DROPPED" and d["absent"] for d in result["databases"])
        else "FAIL"
    )
    if result["docker_preservation"]["status"] != "PASS":
        result["status"] = "DATABASES_ABSENT_ENVIRONMENT_BASELINE_DRIFT"
        code = 1
    if not result["historical_baseline_unchanged"]:
        result["status"] = "BASELINE_CHANGED"
        code = 1
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "databases": len(result["databases"]),
                "secret_matches": 0,
                "traces": traces,
            }
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
