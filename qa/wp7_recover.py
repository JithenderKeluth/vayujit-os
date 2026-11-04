"""Explicit exact-token retry of interrupted WP7-owned DROP; no authority bypass."""

import json
import sys

from qa.postgres_instance import ROOT, GuardDenied, QaInstance


def main(tokens):
    instance = QaInstance()
    instance.verify_server()
    failed = False
    for token in tokens:
        # Evidence marker is supplemental; signed lifecycle/instance/owner/OID/SQL
        # marker and active-session guards remain the deletion authority.
        evidence = ROOT / "tmp/qa-seller-browser" / token / "wp7-run.json"
        if not evidence.exists():
            raise ValueError("WP7_OWNED_EVIDENCE_REQUIRED")
        record = instance.load(token)
        row = {
            "token": token,
            "initial_state": record["state"],
            "status": "BLOCKED",
            "raw_output_persisted": False,
        }
        try:
            if record["state"] == "DROPPING":
                instance.resume_drop(token, timeout_ms=90000)
            elif record["state"] != "DROPPED":
                raise ValueError("WP7_ACTIVE_RUN_RECOVERY_DENIED")
            row["state"] = instance.load(token)["state"]
            row["status"] = "PASS" if row["state"] == "DROPPED" else "BLOCKED"
        except Exception as error:  # noqa: BLE001 - redact SQL/credentials
            row["exception_type"] = type(error).__name__
            if isinstance(error, GuardDenied) and str(error) in {
                "QA_LIFECYCLE_BUSY",
                "QA_DELETE_ACTIVE_SESSIONS",
                "QA_DELETE_STATE_DENIED",
                "QA_DELETE_OWNER_OID_DENIED",
                "QA_DELETE_MARKER_DENIED",
            }:
                row["safe_code"] = str(error)
            row["sqlstate"] = getattr(getattr(error, "orig", None), "sqlstate", None)
            failed = True
        (ROOT / f"tmp/qa-wp7/recovery-{token}.json").write_text(
            json.dumps(row, indent=2), encoding="utf-8"
        )
        print(json.dumps(row))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
