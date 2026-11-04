"""Mechanically redact credential values from one WP6A generated failure artifact."""

import json
import sys
from urllib.parse import quote

from qa.postgres_instance import ROOT, QaInstance, database_name


def main(token: str) -> None:
    database_name(token)
    q = QaInstance()
    q.load(token)
    folder = ROOT / "tmp/qa-wp6a-backend" / token
    target = folder / "backend-results.xml"
    if folder.is_symlink() or target.is_symlink():
        raise RuntimeError("WP6A_REDACTION_PATH_DENIED")
    data = target.read_text(encoding="utf-8")
    values = {q.url.password, quote(q.url.password, safe="")}
    matches = sum(data.count(value) for value in values)
    for value in values:
        data = data.replace(value, "[REDACTED_QA_CREDENTIAL]")
    target.write_text(data, encoding="utf-8")
    assert all(value not in data for value in values)
    result = {
        "token": token,
        "credential_occurrences_redacted": matches,
        "failure_counts_preserved": True,
        "raw_copy_retained": False,
        "tool_transcript_cannot_be_retracted": True,
    }
    (folder / "redaction.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main(sys.argv[1])
