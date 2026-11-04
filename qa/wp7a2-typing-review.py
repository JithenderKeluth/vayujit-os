"""Compare strict Ads router diagnostics with its unchanged HEAD baseline."""

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from mypy.build import BuildSource, build
from mypy.errors import CompileError
from mypy.main import process_options

ROOT = Path(__file__).resolve().parents[1]
TARGET = "apps/api/vayujit_api/ads/router.py"


def diagnostics(source):
    sources, options = process_options(
        ["--strict", "--follow-imports=skip", "--config-file", "apps/api/pyproject.toml", TARGET]
    )
    options.incremental = False
    try:
        result = build(sources=[BuildSource(TARGET, sources[0].module, source)], options=options)
        return result.errors
    except CompileError as error:
        return error.messages


def main():
    old = subprocess.run(
        ["git", "-c", "safe.directory=" + ROOT.as_posix(), "show", "HEAD:" + TARGET],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    before, after = diagnostics(old), diagnostics((ROOT / TARGET).read_text())

    def normalize(messages):
        return Counter(re.sub(r"^.*?:\d+(?::\d+)?: ", "", m) for m in messages if ": error:" in m)

    added = normalize(after) - normalize(before)
    value = {
        "baseline": "HEAD Ads router source; no source files checked out or replaced",
        "strict": True,
        "follow_imports": "skip",
        "baseline_errors": sum(normalize(before).values()),
        "current_errors": sum(normalize(after).values()),
        "added_diagnostic_count": sum(added.values()),
        "added_diagnostics": list(added),
        "status": "NO_NEW_DIAGNOSTICS" if not added else "FAIL",
        "whole_repository_typing_certified": False,
    }
    (ROOT / "tmp/qa-wp7a2/typing-baseline-review.json").write_text(
        json.dumps(value, indent=2), encoding="utf-8"
    )
    print(json.dumps(value))


if __name__ == "__main__":
    main()
