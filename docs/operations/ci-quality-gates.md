# CI quality gates

The repository uses one GitHub Actions workflow at .github/workflows/ci.yml.
It is intentionally split into bounded jobs: dependency/lockfile integrity, API
unit quality, Angular, Electron, disposable migration safety, and a bounded local
certification gate. The workflow does not run every long integration suite in one
job; those suites remain available through the existing PowerShell commands.

CI uses npm ci, never npm install, and runs the production-only dependency audit.
API quality runs pytest, Ruff, Black, and mypy. The migration job performs
upgrade -> downgrade -> upgrade against a disposable PostgreSQL service and
asserts one Alembic head.

The workflow has no provider secrets and explicitly sets all live-provider and
Ads-spend switches to false. It does not call live connectors, write generated
secrets, or target production resources. Pull requests and pushes fail on any
non-zero command result.
