# PR-SOS-07 — Single-Seller Production Infrastructure, Security & Operational Readiness

## Scope and safety boundary

This milestone hardens the existing one-seller/one-installation/one-database
architecture. `ck_users_single_owner` remains authoritative; shared-database
multi-tenancy is explicitly out of scope. No production deployment, paid
service activation, live marketplace mutation, supplier contact, RFQ, payment,
or external write was performed.

## Canonical-authority audit

The implementation reuses the existing authorities rather than adding a second
operations system:

- `Settings` validates environment, secrets, HTTPS, origins, storage, database,
  and mutation switches at startup.
- `OperationalMiddleware` supplies correlation IDs, structured request logs,
  request limits, maintenance-mode write blocking, and safe error metrics.
- `/health/live`, `/health/ready`, `/api/v1/system/health`, and the authenticated
  Operations Control Center remain the health/readiness projections.
- `operations.backup` owns PostgreSQL backup creation, path confinement,
  checksum verification, and restore-readiness checks.
- Existing catalog/media, marketplace, inventory/orders, Business Agent, and
  HUMAN approval authorities remain unchanged.

## PR-SOS-07 corrections

1. Production settings now reject loopback database hosts and default shared
   database roles, require durable object storage (filesystem media remains
   local/test-only), require a backup destination, and require HTTPS public URLs
   when supplied.
2. Health and release-readiness now compare the live migration revision with
   the configurable `VAYUJIT_EXPECTED_MIGRATION_REVISION` (defaulting to the
   current supported head `20261202_0145`) instead of stale historical values.
3. The safe configuration report exposes only booleans/status metadata: no DSN,
   password, token, key, private path, or provider payload is returned.
4. `infrastructure/production.env.example` documents the first-boot contract;
   it contains placeholders only and is not a credential source.

## Deployment and recovery contract

Use a private PostgreSQL service, durable object storage for media, a secret
manager for session/encryption/provider credentials, and separate databases and
credentials for staging and production. Run `scripts/validate-production-config.ps1`
and `scripts/release-prerequisites.ps1` before `scripts/migrate-api.ps1`.
Take and verify a fresh backup before migration. Roll back application binaries
first; never automatically downgrade a partially applied database migration.
Run restore drills into a disposable marked database using
`scripts/restore-disposable.ps1` and the media recovery scripts. Keep the
maintenance marker/emergency-stop active during recovery and re-run health,
owner-isolation, and HUMAN-approval checks before reopening writes.

## Validation matrix

The focused PR-SOS-07 suite is `apps/api/tests/test_pr_sos_07_readiness.py`.
The adjacent operational/security suites are:

- `test_production_readiness_security.py`
- `test_production_readiness_closure.py`
- `test_production_hardening.py`
- `test_operations_control_center.py`
- `test_operations_hardening.py`
- `test_media_backup_recovery.py`
- `test_media_recovery_integration.py`
- `test_pr_sos_01_catalog.py` through `test_pr_sos_06_action_center.py`

The report must record actual local test output, Angular build/test/lint output,
static checks, migration checks, browser/axe evidence, and any environment
limitations. Live provider credentials, production host provisioning, external
monitoring, signing, and real marketplace certification remain explicit
follow-up gates and are not claimed here.

## Execution record (2026-10-13)

All commands below were run against disposable/local state. The golden database
was not changed.

| Gate | Result |
| --- | --- |
| Focused PR-SOS-07 and production-readiness regressions | **86 passed**, 3 framework/Pydantic warnings, 53.01s |
| Adjacent PR-SOS-01 through PR-SOS-06 integration matrix | **33 passed**, 69 existing framework/Pydantic warnings, 11:00 |
| Angular tests | **62 files / 223 tests passed** |
| Angular lint | **0 errors / 2 existing lifecycle warnings** in the two campaign dialogs |
| Angular production build | Passed; existing initial bundle advisory **514.20 kB / 500 kB** |
| Production dependency audit (`npm audit --omit=dev --audit-level=high`) | **0 vulnerabilities** after updating Angular 22 packages to 22.2.2 |
| Dependency license inventory | Completed with `WARN` for unknown internal/package metadata; **0 GPL/AGPL flags** |
| Focused Ruff | Passed |
| Focused Black | 4 implementation/test files unchanged |
| Focused strict mypy | Passed; 3 source files |
| Python compileall | Passed |
| `git diff --check` | Passed (line-ending notices only) |
| Fresh disposable Alembic migration | Passed on `vayujit_prsos07mig_test`; revision **20261202_0145 (head)** |

The pre-existing repository-wide `scripts/check-api.ps1` remains non-green because
it scans historical dirty migration files and unrelated modules (Ruff/Black and
mypy findings outside this change). The focused PR-SOS-07 files are clean. The
integration fixture database is SQLAlchemy-created rather than migration-owned;
running Alembic against it correctly refused the existing `users` table. A fresh
marked database completed the full migration chain successfully.

## Browser, accessibility, and operational boundary

PR-SOS-07 introduced no new Angular route or interaction surface. The existing
authenticated Chrome/CDP certification was reused: **30/30 browser scenarios
passed**, responsive checks covered **320/360/390/768/1024/1440px**, and the
authenticated axe-core 4.11.0 ledger recorded **12 scans, 0 violations, 0
incomplete, 5,382 passing checks**. Those records are retained in
`docs/seller-os/pr-sos-06-validation.md` and `tmp/ux-browser/`; no production
host or real provider was contacted by this milestone.

The remaining production-readiness blockers are external by design: provisioned
HTTPS hosting/reverse proxy, secret-manager/key rotation, durable object storage,
external monitoring/alert delivery, scheduled encrypted backups and a witnessed
restore drill, and real provider/marketplace certification. The application keeps
external mutations deny-by-default and the emergency stop active until those
controls are explicitly configured and reviewed.

## Final classification

**PR-SOS-07 — IMPLEMENTED / LOCAL OPERATIONAL CERTIFICATION COMPLETE; PRODUCTION
DEPLOYMENT READINESS PENDING EXTERNAL INFRASTRUCTURE AND HUMAN APPROVAL.**

The single-seller architecture, owner constraint, safe configuration reporting,
readiness checks, migration preflight, backup/recovery boundaries, security
regressions, adjacent product workflows, and local frontend certification are
validated. This is not a claim of a deployed production host, live supplier or
marketplace connectivity, or external mutation authorization.
