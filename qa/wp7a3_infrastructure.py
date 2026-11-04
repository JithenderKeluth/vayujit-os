"""Read-only Docker lifecycle review. Never connects to the business database."""

import json
import subprocess
from datetime import UTC, datetime

from qa.postgres_instance import ROOT, QaInstance
from qa.validate_postgres_instance import EVIDENCE


def main():
    q = QaInstance()
    q.verify_server()
    baseline = json.loads((EVIDENCE / "preflight.json").read_text(encoding="utf-8-sig"))
    old = next(c for c in baseline["containers"] if c["name"] == "/infrastructure-postgres-1")
    current = json.loads(q.docker("inspect", old["id"]))[0]
    fields = {
        "id": current["Id"],
        "name": current["Name"],
        "image": current["Image"],
        "status": current["State"]["Status"],
        "started": current["State"]["StartedAt"],
        "finished": current["State"]["FinishedAt"],
        "mounts": [
            {k: m.get(k) for k in ("Type", "Name", "Source", "Destination", "RW")}
            for m in current["Mounts"]
        ],
        "networks": list(current["NetworkSettings"]["Networks"]),
    }
    # Capture bounded raw output in memory only. Retain action/timestamp, never
    # Actor attributes, SQL, connection arguments or unrestricted log lines.
    until = datetime.now(UTC).isoformat()
    events = subprocess.run(
        [
            q.manifest["docker_executable"],
            "events",
            "--since",
            old["started"],
            "--until",
            until,
            "--filter",
            "container=" + old["id"],
            "--format",
            "{{json .}}",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    allowed = {"start", "stop", "die", "restart", "kill", "create", "destroy", "oom"}
    observed = []
    for line in events.stdout.splitlines():
        try:
            v = json.loads(line)
            if v.get("Action") in allowed:
                observed.append(
                    {
                        "action": v["Action"],
                        "time": v.get("time"),
                        "time_nano": v.get("timeNano"),
                    }
                )
        except ValueError:
            pass
    logs = subprocess.run(
        [q.manifest["docker_executable"], "logs", "--tail", "1000", old["id"]],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    categories = {
        "ready": "database system is ready to accept connections",
        "shutdown_request": "received fast shutdown request",
        "clean_shutdown": "database system is shut down",
        "crash_recovery": "database system was interrupted",
        "redo_complete": "redo done at",
        "recovery_consistent": "database system is ready to accept read-only connections",
        "checkpoint_error": "invalid checkpoint record",
    }
    counts = {
        k: sum(phrase in line for line in (logs.stdout + logs.stderr).splitlines())
        for k, phrase in categories.items()
    }
    result = {
        "read_only": True,
        "business_database_connected": False,
        "container_id": old["id"],
        "original": old,
        "current": fields,
        "changed_fields": [k for k in old if old[k] != fields[k]],
        "same_container_no_recreation": old["id"] == fields["id"],
        "restart_count": current["RestartCount"],
        "oom_killed": current["State"]["OOMKilled"],
        "exit_code": current["State"]["ExitCode"],
        "docker_event_command_exit": events.returncode,
        "retained_lifecycle_events": observed,
        "log_command_exit": logs.returncode,
        "recognized_log_event_counts": counts,
        "raw_logs_or_process_arguments_persisted": False,
        "attribution": (
            "UNATTRIBUTED unless retained event/log evidence independently identifies "
            "the initiator; timestamps alone do not."
        ),
        "data_integrity": (
            "No row-level integrity claim: no historical row hashes or authenticated "
            "business-data comparison. Startup/recovery logs do not prove absence of data loss."
        ),
        "harness_scope": (
            "WP7A3 issues read-only inspect/events/logs to this container; it does not "
            "start, stop, exec into, recreate or reconfigure it."
        ),
    }
    (ROOT / "tmp/qa-wp7a3/infrastructure-review.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "same_container": result["same_container_no_recreation"],
                "changed_fields": result["changed_fields"],
                "events_retained": len(observed),
                "recognized_log_event_counts": counts,
                "attribution": "UNATTRIBUTED",
            }
        )
    )


if __name__ == "__main__":
    main()
