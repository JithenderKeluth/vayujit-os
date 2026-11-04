"""Classify actionability failures without persisting raw messages, arguments or trace output."""

import json
import re
import zipfile
from pathlib import Path

rules = {
    "outside_viewport": "outside of the viewport",
    "pointer_interception": "intercepts pointer events",
    "not_stable": "not stable",
    "disabled": "not enabled",
    "not_visible": "not visible",
    "detached": "detached",
}
for archive in Path("tmp/qa-seller-browser/30acda7f64c5d746").rglob("trace.zip"):
    before = {}
    logs = {}
    with zipfile.ZipFile(archive) as trace:
        for item in trace.namelist():
            if not item.endswith(".trace"):
                continue
            for line in trace.read(item).splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("type") == "before":
                    before[row.get("callId")] = row
                if row.get("type") == "log":
                    logs.setdefault(row.get("callId"), []).append(str(row.get("message", "")))
                if row.get("type") == "after" and row.get("error"):
                    message = row["error"].get("message", "")
                    message += " ".join(logs.get(row.get("callId"), []))
                    earlier = before.get(row.get("callId"), {})
                    interceptors = []
                    for log in logs.get(row.get("callId"), []):
                        if "intercepts pointer events" not in log:
                            continue
                        for tag, attrs in re.findall(r"<([a-z]+)\b([^>]*)>", log):
                            classes = re.search(r'class="([a-zA-Z0-9_ -]{0,160})"', attrs)
                            item = {
                                "tag": tag,
                                "classes": classes.group(1).split() if classes else [],
                            }
                            if item not in interceptors:
                                interceptors.append(item)
                    print(
                        json.dumps(
                            {
                                "context": archive.parent.name,
                                "method": earlier.get("method"),
                                "source": [
                                    {"file": Path(s.get("file", "")).name, "line": s.get("line")}
                                    for s in earlier.get("stack", [])[:1]
                                ],
                                "classifications": [
                                    name for name, needle in rules.items() if needle in message
                                ],
                                "interceptors": interceptors[:5],
                            }
                        )
                    )
