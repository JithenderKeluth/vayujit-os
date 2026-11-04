# WP0 — browser QA restoration: authorization stop

**WP0: BLOCKED / NOT COMPLETE. Application certification: INCOMPLETE.**

No database connection, fixture creation, application startup, authenticated
browser test, persisted API test, accessibility scan or cleanup command was run
in this work package. WP1 has not begun. The PC-first backup workstream remains
parked. This is the requested stop report, not a restoration PASS.

## Exact blocker

The current execution environment has no `QA_DATABASE_ADMIN_URL`. More
importantly, the request does not identify an owner-approved PostgreSQL instance,
port, QA role or permitted disposable database namespace on that instance.
Authorization to restore QA in principle is not authorization to choose a server.
Neither a discovered connection string nor an arbitrary approval environment
variable would supply that missing owner decision.

The prior [audit execution](audit-execution.json) recorded the same absent QA
configuration and an actual `QA_ADMIN_REQUIRED` preflight exit. That result is
historical evidence, not a command rerun in WP0. The current presence-only check
again found the variable unset; no credential value was printed or searched for.
No authentication attempt was made, so database availability, password validity
and role privileges are UNKNOWN—not proven broken.

The existing runner deliberately does not load business `.env` credentials.
Environment variables supplied in one shell are inherited only by its subsequently
launched children; setting a different PowerShell window does not update an
already-running execution process. We cannot establish from the available
evidence whether a previously approved shell exited or why its configuration
was not supplied to this execution environment.

## Existing infrastructure: reuse, not replacement

Source inspection only:

| Mechanism | Existing boundary | Current execution status |
| --- | --- | --- |
| `qa/probe-owned-runtime.mjs:8` | Requires QA admin URL before creating its run folder or fixture; owns/restarts only its own API process. | NOT RUN; authorization missing. |
| `qa/fixture_server.py:18–55` | Requires 16 lowercase hex token, exact fresh `vayujit_qa<token>_test` name, admin host `127.0.0.1`, maintenance DB `postgres`. | SOURCE REVIEWED, not database-verified in WP0. |
| Fixture setup `:94–119` | Refuses existing target; creates a new database and canonical project marker plus suite token; verifies connected DB/name/environment/marker. | SOURCE REVIEWED. |
| Settings and egress guards | Removes inherited business/provider settings; no `.env`; explicit emergency stop and research/provider kill switches; local synthetic fixture only. | SOURCE REVIEWED, not live network certification. |
| Fixture teardown `:222–250` | Rechecks marker/token, disposes owned engines, drops exactly the newly created DB with FORCE, verifies its absence and writes cleanup JSON. | NOT RUN. No cleanup PASS claimed. |
| `qa/cleanup_disposable.py` | Abandoned-run recovery validates exact token/project marker; refuses active sessions; drops only that exact test DB. | NOT RUN. Not a broad cleanup tool. |
| `core/test_database.py` | Environment/name/current-database/project-marker checks; test-only reset/session operations. | SOURCE REVIEWED; broader core name regex is not permission to choose another DB. |
| `qa/verify-phase4c-cleanup.py` | Read-only exact-name absence check, but reads historical 4C targets and overwrites its historical report. | Do not run unchanged as a new WP0 proof; keep new evidence WP0-scoped. |

These controls are technically reusable candidates. They do **not** themselves
record HUMAN approval of the PostgreSQL instance. The core test helper accepts
more names than this runner; WP0 must use the stricter per-run target contract.
Metadata-based fixture setup is not Alembic migration certification.

## Required authorization and isolation boundary

Preferred boundary: an owner-identified **QA-only PostgreSQL instance/cluster**
bound to loopback, with a dedicated non-superuser QA role. Do not select the
existing business/development instance simply because it is reachable.

| Target | Permitted scope after explicit approval | Forbidden |
| --- | --- | --- |
| Approved QA instance, database `postgres` | Connection for narrowly scoped fixture administration and read-only identity/absence metadata. | Application table/schema initialization in `postgres`. |
| Fresh `vayujit_qa<16-lowercase-hex>_test` | Create, mark, synthetic canonical setup, API/browser testing, exact-token teardown and absence verification. | Reusing an existing DB, promoting fixtures to business data, deleting by prefix/glob. |
| Golden database, future permanent business DB, unrelated databases | None. | Connections for app tests, schema changes, resets, session termination, deletion or inferred approval. |
| Docker/PC-first backup resources | None in this work package without a separately reviewed QA-only provision plan. | Starting/stopping/pruning unrelated resources or resuming backup certification. |

PostgreSQL `CREATEDB` is a server-level role capability, not a database-name-pattern
permission. The fixture enforces the name/marker rules in code; a dedicated QA
instance supplies a stronger boundary than pretending a role can create only
matching names. On a mixed-use instance, role membership, ownership and PUBLIC
permissions need explicit review before approval. No grants or revocations against
unrelated databases are proposed or executed here.

Please supply a non-secret approval identifying:

```text
I authorize WP0 disposable QA on this specific QA-only PostgreSQL instance:
Host: 127.0.0.1
Port: <owner-confirmed port>
Instance/cluster identity: <owner-confirmed QA instance>
Maintenance database: postgres
Dedicated QA role: <owner-approved role>
Scope: create only fresh vayujit_qa<16 lowercase hex>_test databases,
write canonical synthetic fixtures and markers, run protected local tests,
then remove only those newly created and token/marker-verified databases.
Allow read-only server/role identity and exact-target absence verification.
All other databases, production data, providers and backup resources are excluded.
```

Do not include a password or full connection string in the approval/report/chat.
No server, port, role or credentials have been chosen on the owner's behalf.

## Exact safe owner setup steps — not executed

1. Identify an existing QA-only PostgreSQL instance, or obtain explicit approval
   for a separate QA-only instance before provisioning it. Confirm its loopback
   port and instance identity. Do not initialize VAYUJIT's permanent business DB.
2. On that **chosen QA-only server**, its HUMAN administrator may create a
   dedicated role if one does not already exist. Do not run this on a guessed or
   mixed-use server. Example role name below is a proposal, not an approved target:

   ```sql
   CREATE ROLE vayujit_qa LOGIN CREATEDB NOSUPERUSER NOCREATEROLE NOREPLICATION NOBYPASSRLS;
   ```

   Set its password with psql's interactive `\password vayujit_qa` prompt or the
   owner's approved secret manager—not a password literal in SQL/history. Use an
   existing reviewed role instead if appropriate; do not rerun CREATE blindly.
3. Record the target/scope approval above. Make the credential available privately
   to the **same process environment that launches the QA commands**. Do not edit
   production `.env`. Example PowerShell setup after approval:

   ```powershell
   $qaPort = [int](Read-Host 'Approved QA-only PostgreSQL port')
   if ($qaPort -lt 1 -or $qaPort -gt 65535) { throw 'Invalid approved port' }
   $qaCredential = Get-Credential -Message 'Approved dedicated QA PostgreSQL role'
   $qaUserEncoded = [Uri]::EscapeDataString($qaCredential.UserName)
   $qaPasswordEncoded = [Uri]::EscapeDataString($qaCredential.GetNetworkCredential().Password)
   $env:QA_DATABASE_ADMIN_URL = 'postgresql+psycopg://{0}:{1}@127.0.0.1:{2}/postgres' -f $qaUserEncoded,$qaPasswordEncoded,$qaPort
   $env:QA_PYTHON = (Resolve-Path .\apps\api\.venv\Scripts\python.exe).Path
   ```

   Assignment is not proof of authorization. Do not print the variable, enable
   shell tracing around it, store it in reports or substitute a golden/business URL.
   An already-running agent may need an approved environment/secret handoff or
   fresh launch; a separate owner shell does not retroactively configure it.
4. After target approval and reviewed role/instance identity, run the existing
   narrow owned-runtime rehearsal from repository root:

   ```powershell
   try {
     node qa/probe-owned-runtime.mjs
     if ($LASTEXITCODE -ne 0) { throw 'Disposable QA runtime did not pass; inspect safe evidence' }
   } finally {
     Remove-Item Env:QA_DATABASE_ADMIN_URL -ErrorAction SilentlyContinue
     Remove-Item Env:QA_PYTHON -ErrorAction SilentlyContinue
     $qaCredential = $null
     $qaPasswordEncoded = $null
     $qaUserEncoded = $null
   }
   ```

   Clearing references reduces accidental reuse; it is not a guarantee that
   strings or environment secrets were securely erased from process memory.
   This probe creates its own fresh token-marked installation after approval,
   checks readiness/restart, and should emit the owned run token and cleanup
   evidence. It is **not** the complete WP0 browser/journey matrix.
5. On resume, independently verify the exact new test DB is absent with an
   owner-approved read-only metadata query and retain fresh WP0 cleanup evidence.
   Never call broad DROP, prefix cleanup or Docker prune. If guarded cleanup
   fails, stop and inspect only the exact owned target/token before any recovery.
6. Then run the requested authenticated desktop/mobile/API scenarios using the
   existing harness with WP0-scoped reports and preserved history. Legacy
   `qa/run.mjs` and report generators update older reports; archive/review those
   output paths first. The existing archive helper does not cover all 4C artifacts.
   Do not overwrite the twelve historical open finding dispositions.

## Current results and completion gate

- Current check: `QA_DATABASE_ADMIN_URL` presence only — **absent**. No URL or
  credential was logged. No DB authorization was inferred from other variables.
- Source review: existing fixture/bootstrap/cleanup contracts and earlier QA
  procedures. This is not an isolation, teardown or browser runtime PASS.
- Tests executed in WP0: **0**. No browser, persisted API or axe tests ran.
- Newly confirmed application defects: **none**. Previously suspected issues
  disproven: **none**. Historical counts are not WP0 results.
- Cleanup: **NOT APPLICABLE — no WP0 resources created**. Absence of pre-existing
  or unrelated databases was not queried or claimed.

All nine requested journey groups remain BLOCKED; see
[live-journey disposition](wp0-live-journey-findings.md) and the exact
[execution record](wp0-execution-evidence.json).

WP0 may be closed only after explicit target approval, fresh authenticated
browser **and** persisted API execution, demonstrated isolation, verified exact
cleanup and evidence for the named flows. Until then **STOP before WP1**.
