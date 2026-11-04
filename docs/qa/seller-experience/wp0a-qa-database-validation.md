# WP0A — QA database validation evidence

Date: 2026-10-28. Classification: **WP0A isolated QA infrastructure validated**.
This does not close WP0, certify application journeys, or authorize WP0B execution.

## Actual identity

- Container: `vayujit-qa-postgres`.
- Full ID: `a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23`.
- Instance UUID: `389b97d2-a4cd-4d9b-972e-6bb2bf5785eb`.
- Server: PostgreSQL `17.10`, matching application deployment major 17.
- Endpoint: **only `127.0.0.1:55432`**; checked in effective Docker port mapping.
- Role: `vayujit_qa_admin`, non-superuser CREATEDB, no role memberships.
- Scope: exact `vayujit_qa<16-lowercase-hex>_test`, signed token/lifecycle and
  database owner/OID/marker required. A matching prefix alone never permits deletion.

Setup and commands: [WP0A setup](wp0a-qa-database-setup.md).

## Runtime checks

Machine-readable local evidence: `tmp/qa-postgres-evidence/validation.json`.
Preflight preservation record: `tmp/qa-postgres-evidence/preflight.json`.
Signed lifecycle records remain protected under the ignored private directory;
no passwords, private signing keys or raw subprocess logs are in these documents.

| Runtime check | Result |
| --- | --- |
| Exact engine/container/image, network, mounts, effective loopback endpoint and server marker | PASS |
| Minimum role attributes; maintenance CREATE and instance-identity UPDATE/DELETE denied | PASS |
| Fresh token-owned database creation | PASS |
| Harness refuses deletion of `postgres` | PASS |
| Harness refuses deletion of `vayujit_golden_test` | PASS; target not connected to or modified |
| Harness refuses deletion of unrelated name | PASS |
| Existing database reuse rejected | PASS |
| Missing lifecycle rejected before deletion | PASS |
| Wrong recorded owner rejected | PASS |
| Wrong lifecycle state rejected | PASS |
| Wrong recorded database OID rejected | PASS |
| Tampered/unsigned lifecycle rejected | PASS |
| Incorrect database marker rejected | PASS |
| Active session blocks cleanup | PASS; no forced termination |
| Fresh-process real Alembic upgrade and canonical owner fixture | PASS |
| Guarded cleanup | PASS |
| Database absence after cleanup | PASS |
| Existing fixture server HTTP readiness witness and signed cleanup | PASS |
| Unrelated Docker resources unchanged | PASS |
| Actual credential/signing-key values absent from captured logs and generated report/document files | PASS |

The migration check ran all existing migrations to head `20261203_0146`, without
changing production migrations or using metadata creation as a substitute. Normal
`POST /api/v1/auth/setup-owner` returned 201, authenticated `GET /api/v1/auth/me`
returned 200, and a second owner setup returned 409. Persisted owner count was one
and `ck_users_single_owner` existed. These are synthetic disposable fixtures only.

Separately, the existing `qa.fixture_server` was started in an owned subprocess,
its single `/__qa/witness` HTTP response matched the issued token, stdin-driven
shutdown completed with exit 0, and its cleanup report and signed DROPPED state
were verified. This bounded check is **not** the seller-experience browser suite.

Only maintenance/template databases remained after the migration fixture cleanup.
The additional HTTP fixture also reached signed DROPPED state. Original container
IDs, image IDs, states, start/finish timestamps, mounts and network attachments
matched the preflight snapshot for all **10 original containers**. Original network
and volume name sets were preserved; only the dedicated QA additions exist.
No connection to the unrelated port-5432 PostgreSQL server was made for validation.

## Issues encountered and disposition

1. **Docker effective publication:** internal-only networking produced no actual
   host listener on this engine despite the requested binding. Corrected only on
   the newly created QA resources by adding a dedicated non-masquerading host
   bridge alongside the internal bridge. No existing resources were removed.
   Verification now checks both declared and effective port mappings. Docker
   documents the distinction between network isolation and
   [published ports](https://docs.docker.com/engine/network/port-publishing/).
2. **Alembic URL interpolation:** the first two bounded migration attempts failed
   at `apps/api/alembic/env.py:10` → ConfigParser `before_set`, before migrations,
   because secure generated credentials required URL percent-encoding.
   The QA-only `QaMigrationConfig` escapes literal percent signs for ConfigParser
   and preserves the decoded connection URL. A unit regression asserts exact URL
   roundtrip. Passwords were not weakened or regenerated, and production code was
   not changed. The general production Alembic encoded-URL handling remains a
   separately scoped existing issue for future review.
3. **Stopped-instance control:** identity-only checks support a positively
   identified stopped container without requiring an active port mapping; database
   operations still require the running server and all normal checks. Actual
   Stop → Start → Status commands passed, preserving the same ID and storage.

Earlier failed attempts were not counted as passes; each created migration
fixture was safely removed. The final rerun and the test commands below are the
certification basis.

## Tests and quality checks

- Bounded Docker/PostgreSQL/API runtime matrix: **20 passed, 0 failed**.
- Python QA unit suite: **48 passed, 0 failed** (20 new WP0A tests, 28 existing).
- QA Node harness tests: **49 passed, 0 failed, 0 skipped**. The printed synthetic
  `desktop: FAILED QA-TEST failure` is an expected reporter negative-test input,
  not a browser test or runtime failure.
- PowerShell 5.1 parser: PASS for `scripts/qa-postgres.ps1`.
- NTFS ACL checks and Status, Stop, Start commands: executed successfully.
- Black: PASS for all five changed Python files.
- Ruff: PASS for new WP0A modules/tests and `qa/cleanup_disposable.py`.
  The unchanged top-level exception-redaction boundary in `qa/fixture_server.py`
  retains its existing BLE001 warning; no exception text was exposed to satisfy lint.
- Python compilation: PASS for all five changed Python files.
- `git diff --check`: PASS; Git emitted existing LF/CRLF normalization notices,
  not whitespace errors.

Final runtime fixture: `vayujit_qaca1f39e55a784aae_test`; HTTP fixture:
`vayujit_qaf93d118677e94a8b_test`. Both reached guarded cleanup. The final report
records **20 PASS / 0 FAIL**, with real migration head `20261203_0146`.
Windows `Get-NetTCPConnection -State Listen -LocalPort 55432` independently
returned `127.0.0.1`, port `55432`, state `Listen`.
Final independent read-only verification found exactly `postgres`, `template0`,
and `template1`; all **8** recorded disposable fixture lifecycles were DROPPED.
Secret scanning and original-resource preservation were rechecked after the
documentation updates and passed.

Commands:

```powershell
& .\apps\api\.venv\Scripts\python.exe -m qa.validate_postgres_instance
& .\apps\api\.venv\Scripts\python.exe -m unittest discover -s qa/unit -p 'test_*.py'
& 'C:\Program Files\nodejs\node.exe' --test 'qa/unit/*.test.mjs'
& .\apps\api\.venv\Scripts\python.exe -m black --check qa/postgres_instance.py qa/validate_postgres_instance.py qa/unit/test_postgres_instance.py qa/fixture_server.py qa/cleanup_disposable.py
& .\apps\api\.venv\Scripts\python.exe -m ruff check qa/postgres_instance.py qa/validate_postgres_instance.py qa/unit/test_postgres_instance.py qa/cleanup_disposable.py
& .\apps\api\.venv\Scripts\python.exe -m py_compile qa/postgres_instance.py qa/validate_postgres_instance.py qa/unit/test_postgres_instance.py qa/fixture_server.py qa/cleanup_disposable.py
git diff --check
```

## Scope and remaining boundaries

Changed infrastructure/harness files: `infrastructure/docker-compose.qa.yml`,
`infrastructure/qa-postgres-init.sh`, `scripts/qa-postgres.ps1`,
`qa/postgres_instance.py`, `qa/validate_postgres_instance.py`,
`qa/unit/test_postgres_instance.py`, `qa/fixture_server.py`,
`qa/cleanup_disposable.py`, and these two documents.

No permanent database initialized; no golden/unrelated database touched; no
marketplace calls, Docker removal, PC-first backup execution, commits, pushes or
branches. Existing dirty backup work was preserved. No seller-facing changes.
Angular, browser journeys, axe and complete historical application regressions
were intentionally not run: they belong to WP0B or later scoped work.

No outstanding WP0A infrastructure approval is required. WP0B remains **NOT RUN**;
stop at this verified identity and scope handoff. Application certification
remains **INCOMPLETE**.
