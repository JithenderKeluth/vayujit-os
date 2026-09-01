from __future__ import annotations

import subprocess
import sys


def test_refresh_migration_is_current_head():
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd="apps/api",
        capture_output=True,
        text=True,
        check=True,
    )
    assert "20261016_0095" in result.stdout
