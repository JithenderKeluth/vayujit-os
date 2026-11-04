"""Extract only numeric synthetic plan evidence, never headers, cookies or raw trace output."""

import json
import zipfile
from pathlib import Path

rows = []
for archive in Path("tmp/qa-seller-browser/346ac65c280b5d93").rglob("trace.zip"):
    seen = set()
    with zipfile.ZipFile(archive) as trace:
        for item in trace.infolist():
            if not item.filename.startswith("resources/") or item.file_size > 2_000_000:
                continue
            try:
                value = json.loads(trace.read(item))
            except (ValueError, UnicodeError):
                continue
            if isinstance(value, dict) and "id" in value and "budget_envelope" in value:
                if value["id"] in seen:
                    continue
                seen.add(value["id"])
                budget = value["budget_envelope"]
                if isinstance(budget, dict):
                    rows.append(
                        {
                            "context": archive.parent.name,
                            "total": budget.get("total"),
                            "currency": budget.get("currency"),
                            "allocations": budget.get("allocations"),
                            "status": value.get("status"),
                            "automation": value.get("automation_mode"),
                        }
                    )
print(json.dumps({"source": "retained synthetic browser trace response bodies", "rows": rows}))
