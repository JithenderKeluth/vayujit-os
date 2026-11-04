"""Read-only WP1 cleanup and evidence audit; never creates or drops databases."""

import json
import zipfile

from sqlalchemy import text

from qa.postgres_instance import PRIVATE, ROOT, QaInstance, database_name
from qa.validate_postgres_instance import secret_scan, unchanged


def main():
    instance = QaInstance()
    instance.verify_server()
    tokens = {
        "eca20e8eced7f200",
        "d36ec3f74d2a5144",
        "d13067df8b66b91a",
        "b513df9603474383",
        "cfcedd7e4e95464f",
        "65df78be6944404a",
        "56454b3b41fe4ffe",
        "172a4676e9954763",
        "8c8e0f00a236849d",
        "c46926f3a9d35b94",
        "baa7fa4093efbf17",
    }
    rows = []
    engine = instance.engine()
    try:
        with engine.connect() as connection:
            for token in sorted(tokens):
                record = instance.load(token)
                count = connection.scalar(
                    text("SELECT count(*) FROM pg_database WHERE datname=:name"),
                    {"name": database_name(token)},
                )
                assert record["state"] == "DROPPED" and count == 0
                rows.append(
                    {"token": token, "signed_state": record["state"], "absent": True}
                )
    finally:
        engine.dispose()
    traces = []
    for token in (
        "eca20e8eced7f200",
        "d13067df8b66b91a",
        "8c8e0f00a236849d",
        "c46926f3a9d35b94",
        "baa7fa4093efbf17",
    ):
        for archive in (ROOT / "tmp/qa-seller-browser" / token).rglob("trace.zip"):
            try:
                with zipfile.ZipFile(archive) as opened:
                    intact = opened.testzip() is None
            except zipfile.BadZipFile:
                intact = False
            if token == "baa7fa4093efbf17":
                assert intact, "FINAL_REPLAY_TRACE_MUST_BE_INTACT"
            traces.append(
                {
                    "path": archive.relative_to(ROOT).as_posix(),
                    "crc": "PASS" if intact else "INCOMPLETE_EARLIER_CAPTURE",
                }
            )
    secrets = [
        (PRIVATE / n).read_text().strip()
        for n in ("qa-password", "bootstrap-password", "guard-key")
    ]
    for token in tokens:
        for base in (
            ROOT / "tmp/qa-seller-browser" / token,
            ROOT / "tmp/qa-wp1-backend" / token,
        ):
            for file in base.rglob("*.json"):
                content = file.read_text(encoding="utf-8-sig")
                assert not any(secret in content for secret in secrets)
    result = {
        "status": "PASS",
        "read_only": True,
        "databases": rows,
        "docker_preservation": unchanged(instance),
        "secrets": secret_scan(instance),
        "traces": traces,
    }
    destination = ROOT / "tmp/qa-wp1-final-audit.json"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
