# WP6A — Fresh-install and populated-upgrade evidence

2026-10-30. Actual Windows/PostgreSQL execution, not static-only assertions.

## Authorized boundary

Reused approved `vayujit-qa-postgres`, PostgreSQL17.10,
`127.0.0.1:55432`, non-superuser `vayujit_qa_admin`, instance
`389b97d2-a4cd-4d9b-972e-6bb2bf5785eb`. Exact instance/container, signed lifecycle,
database owner/OID, marker and `vayujit_qa<16hex>_test` contract verified by existing
harness. No inferred authorization from a URL alone, no permanent/golden targets.

## Final executed results

| Suite / evidence token | Cases | Result |
| --- | ---: | --- |
| Migration `e0792d218c174a3e` | 8 | PASS,0 failed/error/skipped |
| Video/Ads service `bd2d7343bbfd48f9` | 13 | PASS,0 failed/error/skipped |
| WP6/WP5/inventory adjacent `1203b9aa570247fe` | 28 (9+11+8) | PASS,0 failed/error/skipped |

Artifacts: `tmp/qa-wp6a-backend/<token>/backend-results.xml` and `cleanup.json`.
Each suite used a fresh signed disposable database and actual full Alembic
migrations; ORM metadata creation is not a substitute for migration evidence.

### Eight migration cases

1. Fresh full chain reaches head149; canonical version names, Ads NULL/no-default
   fields/index and nullable scene link exist; duplicate `upgrade head` is a no-op.
2. Representative persisted owner/brand/product, project, storyboard, style,
   generation, scene, account and campaign survive downgrade to exact old head147
   and upgrade to149. Counts, IDs, owner/context/FKs, versions, states, timestamps,
   idempotency keys and values compared. Version values7/3 preserved by rename;
   new recovery values remain NULL. Populated canonical reads return200 after repair.
3. Non-NULL recovery metadata makes downgrade fail; current head/data retained.
4. A storyboard-only scene makes downgrade fail; current head/data retained.
5–8. Both aliases present, wrong version type, absent legacy alias and partially
   present Ads fields each fail atomically; original column maps and old head
   retained. Only the same owned fixture is restored by test cleanup.

These are representative existing-data paths, not every possible historic schema.
The test constructs the old schema through real downgrade, never table recreation.

### Thirteen service cases

Nine parametrized list/overview/script/storyboard/style/optimization/anomaly/
comparison reads return200 twice. Four cases verify disabled/unverified local
account create/edit/reload and unknown-ID404; campaign preview refusal409/422 with
no campaign created; scene edit persists and increments row_version while stale
edit returns409; empty storyboard approval blocked and logout restores401 for
Video/Ads reads. No real provider credentials, job execution or fake approvals.

## Original failures retained

`15efc2aa00894470`:7 failures from test ConfigParser escaping; secret-bearing JUnit
values redacted and QA credential rotated with HUMAN approval (see remediation).
`f89126dd5d78445b`:11 passed/2 failed exposed the real scene NOT NULL blocker and
a test helper incorrectly parsing empty logout204 as JSON. Corrected schema and
empty-body helper were retested by the final13-case run.
`2905050ebbd74ad5`:7-case intermediate revision148 run passed but is superseded
by the8-case final149 suite. Reruns are not summed into unique coverage.

## Static/build and cleanup

Strict mypy on both migrations: PASS, no suppression. Ruff/Black use the repository
API configuration (`--config apps/api/pyproject.toml`), including explicit migration
paths;8 new Python files pass. A first check without that config picked up unrelated
ambient import/line-length rules; this is not the project's configured gate.
Compileall, JavaScript syntax, PowerShell5.1 parser, focused Video ESLint,
app/spec TypeScript and production build PASS. Angular371/81files; Node63;
Python54. Initial bundle422.71kB below unchanged500kB warning budget.
Older repository-wide typing/lint debt and FastAPI startup/operation-ID warnings
are not closed by these focused checks.

`tmp/qa-wp6a-final-audit.json`: **9/9 signed DROPPED and independently absent**,
no guarded recovery needed; original10 containers/networks/volumes preserved;
6 traces CRC PASS; current approved credential matches0, raw container logs not
persisted. No unrelated Docker cleanup or backup operations.

## Reproduce on Windows

```powershell
.\scripts\qa-postgres.ps1 -Action Status
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp6a.ps1 -Action Migration
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp6a.ps1 -Action Backend
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp6a.ps1 -Action Adjacent
npm.cmd run qa:unit
.\apps\api\.venv\Scripts\python.exe -m unittest discover -s qa/unit -p 'test_*.py'
npm.cmd test --workspace @vayujit/web -- --watch=false
npm.cmd run build --workspace @vayujit/web -- --configuration production
.\apps\api\.venv\Scripts\python.exe -m qa.wp6a_final_audit
git -c safe.directory=C:/Users/jithe/Documents/vayujit-os diff --check
```

Only use the existing attested QA environment; do not replace missing approval
with another connection string. Process-local ExecutionPolicy does not change
Windows system policy. This document does not authorize migration of real data.
