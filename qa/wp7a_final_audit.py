"""Read-only WP7A evidence audit; identical signed lifecycle authority to WP7."""

import hashlib
import json
import zipfile
from urllib.parse import quote, quote_plus

from qa.postgres_instance import PRIVATE, ROOT
from qa.wp4_final_audit import main as lifecycle_audit


def main():
    code = lifecycle_audit("wp7a")
    destination = ROOT / "tmp/qa-wp7a-final-audit.json"
    result = json.loads(destination.read_text())
    baseline = json.loads((ROOT / "tmp/qa-wp7a/baseline.json").read_text())
    result["original_baseline_unchanged"] = all(
        hashlib.sha256((ROOT / row["file"]).read_bytes()).hexdigest() == row["sha256"]
        for row in baseline["files"]
    )
    secrets = [
        (PRIVATE / n).read_text().strip()
        for n in ("qa-password", "bootstrap-password", "guard-key")
    ]
    needles = {v.encode() for s in secrets for v in (s, quote(s, safe=""), quote_plus(s))}
    roots = [ROOT / "tmp/qa-wp7a", ROOT / "tmp/qa-wp7a-backend"]
    roots += [ROOT / "tmp/qa-seller-browser" / d["token"] for d in result["databases"]]
    checked, archives = 0, 0
    for root in roots:
        for file in root.rglob("*"):
            if not file.is_file():
                continue
            if file.suffix in {".xml", ".json", ".md"}:
                if any(n in file.read_bytes() for n in needles):
                    raise ValueError("WP7A_SECRET_MATCH_REVIEW_REQUIRED")
                checked += 1
            if file.name == "trace.zip":
                with zipfile.ZipFile(file) as trace:
                    assert trace.testzip() is None
                    for entry in trace.namelist():
                        if any(n in trace.read(entry) for n in needles):
                            raise ValueError("WP7A_TRACE_SECRET_MATCH_REVIEW_REQUIRED")
                archives += 1
    result["extended_secret_scan"] = {"files": checked, "traces": archives, "matches": 0}
    if not result["original_baseline_unchanged"]:
        result["status"] = "BASELINE_CHANGED"
        code = 1
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "databases": len(result["databases"]),
                "secret_matches": 0,
                "traces": archives,
            }
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
