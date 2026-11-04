# Local application database — approved source repair and upgrade

3 November 2026, Asia/Calcutta.

**SOURCE SCHEMA REPAIR AND UPGRADE — APPLIED AND VERIFIED.**
This is a local database recovery result, not whole-application, live-provider,
production-launch or PC-first backup certification.

## Actual result

- Exact original database/role: `vayujit`, `127.0.0.1:5432`.
- PostgreSQL container: `infrastructure-postgres-1`, same recorded identity.
- Source run: `a458dcc51f7c96d9`.
- Source transaction committed once, after every fresh backup/copy gate passed.
- Revision: `20261010_0151` → `20261207_0150`, **16 canonical upgrades**.
- Required pre-existing-table reconciliation: **31 canonical defaults, 24
  canonical indexes**. Three table contracts verified before reuse; no table
  replacement, blind stamp, timestamp conversion or row rewrite.
- All **392 original tables' rows and financial numeric values** matched the
  fresh pre-upgrade snapshot immediately before commit. A separate fresh process
  verified those preservation invariants after commit, before API recovery.
- One owner and validated `ck_users_single_owner` preserved.
- API recovered; canonical maintenance state restored OFF.
- Actual `/health/ready`: **healthy**, current and expected revisions both
  `20261207_0150`. Read-only preflight reports no pending revisions/collisions.
- Source operation including backup and recovery: **375.093 seconds**.

Normal authenticated reads after application recovery may legitimately update
session/activity metadata. The preservation result is a point-in-time migration
proof, not a claim that all business records are frozen forever.

## Authorization and safety gates

The owner separately approved (1) backup/isolated restore, (2) source upgrade
conditional on successful prerequisites, (3) isolated-copy reconciliation, and
(4) the exact tested reconciliation plus source upgrade after fresh checks.
Only the existing `vayujit` database was eligible. No new business database was
created, no synthetic data was promoted, and no QA/golden/unrelated database was
used for real data.

Before source DDL:

1. Reconfirmed exact endpoint, role, live API process and legacy revision, plus
   all three empty-table contracts.
2. Verified the canonical maintenance marker blocked an unauthenticated empty
   login POST with `503 / maintenance_mode`; no credentials were submitted.
3. Paused only the captured API supervisor/process tree, checked process creation
   times to prevent PID-reuse errors, and verified loopback port 8000 absent.
   Publishing workers were disabled; unexpected workers would block execution.
4. Required zero other sessions in the exact source database; unrelated sessions
   were not terminated.
5. Completed a fresh encrypted backup, independent restore, copy upgrade,
   deliberately injected late-failure rollback proof, preservation comparisons,
   wrong-key rejection, corrupt-ciphertext rejection and media restore.
6. Compared the exact repair operations with the approved passing rehearsal.
7. Applied reconciliation and all Alembic steps on **one caller-owned PostgreSQL
   transaction**. Unexpected contracts/operations, lock timeout, concurrent
   migration or preservation mismatch fail closed before commit.
8. Verified preservation/head in a fresh read-only source process, then restarted
   only the application and cleared only this operation's maintenance state.

The late-failure rollback experiment ran on isolated copies, not the original.
It proved rollback of the complete repair, sixteen upgrades, journal transitions
and records. No source downgrade, restore, schema reset, DROP/recreate, manual
stamp or disabled constraint was used.

## Fresh retained backup

Directory:
`C:\vayujit-os db encr bkp\migration-158e44eb2e660a63`.

Encrypted artifacts: `database.dump.age`, `media.zip.age`, `media.json.age`,
`recovery-configuration.json.age`. Protected verification report:
`verification.json` in that directory.

Separate recovery identity:
`%LOCALAPPDATA%\VAYUJIT OS\migration-recovery-keys\158e44eb2e660a63\recovery.agekey`.
Private key material was never printed or placed beside ciphertext. Final ACL
checks confirmed owner/SYSTEM-only access, key retention, wrong-key removal and
absence of the backup's plaintext staging directory.

Fresh backup/rehearsal run `158e44eb2e660a63`: **PASS**, 332.844 seconds.
Independent restore verified original table rows/numeric values and **8,959
media-tree files**. This is not a count of catalog product images. New copy
upgrade and atomic rollback proof passed before source execution.

Exact marked restore/runner containers and volume were removed, with an
independent label-filtered absence check. Source and QA PostgreSQL container
identities/start times were unchanged by the backup/rehearsal. No unrelated
Docker cleanup occurred. Protected source verification/process-state JSON was
retained for audit; it contains metadata/fingerprints, not plaintext backup data.

**This is still a local C: backup. Physical/off-device independence is
UNVERIFIED.** Owner should copy encrypted artifacts off this PC and keep a secure
offline copy of the matching recovery key separately. Do not delete the older
backup/key while deciding retention. No off-device copy was performed here.

## Windows recovery issues encountered and corrected

Two attempts stopped before any database change:

| Run | Result | Disposition |
|---|---|---|
| abaa011894b7e07d | FAIL at API pause; no source commit | Original report retained. Two captured processes were later absent and one worker remained. Exact first native error was not retained, so its precise cause is unknown. Race-safe stop now accepts only positively rechecked process absence and never suppresses a genuine surviving-process failure. |
| 486b99eca04bb195 | FAIL during process inspection; no source commit | Safe helper classified `unexpected_api_descendant`; read-only inspection identified the API's own direct-child system `conhost.exe`. It is now recognized but never directly terminated. Unrelated/non-system console hosts are still rejected. |

Recovery also exposed assignment to a missing `new_root` property on a
deserialized PowerShell object (line 81 in the then-current helper). The API had
launched, but state persistence failed. Resume-state initialization now creates
that property before starting a process. The prior API was independently health-
checked and maintenance was cleared before the successful attempt.

Helper failures now propagate allowlisted codes/line numbers to the parent;
raw command output, secrets and customer records are not included. The historical
failed reports describe state at failure, not the final recovered state.

## Application/readiness changes and validation

After successful source verification, the non-secret default
`expected_migration_revision` was aligned to `20261207_0150`; a test ties it to
the checked-in Alembic head while preserving explicit deployment overrides.
Neither root nor API `.env` contained an explicit expected-revision override.
**No `.env` was edited and no credentials were changed.** Current API recovery
also explicitly kept external mutations blocked.

The frontend was not listening on port 4200 when checked. The existing
`npm.cmd run dev:web` command was started with installed dependencies and CLI
analytics disabled; Angular development bundle generation passed and watch mode
is running on `127.0.0.1:4200`. This is not a production-build result.

The browser connector was unavailable. The computer-use skill was used with
the existing authenticated Chrome session through native Windows controls.
Old console messages were distinguished from fresh observations by reloading
the page; no passwords, cookies or tokens were extracted or entered.

| Authenticated view | Actual observation |
|---|---|
| Business Agent | Saved goal/run loaded; no fresh visible HTTP 500; existing evidence-gap result retained |
| Action Center | Operational briefing and normal empty/filter state loaded; previous unavailable banner absent |
| Inventory | Unified inventory and honest no-canonical-inventory state loaded, not a server error |
| Orders | Unified orders view loaded without previous visible HTTP 500 |
| Financials | Sales/profitability, alerts, trends, fees and settlement sections loaded without previous visible HTTP 500 |
| Catalog | Product master and existing product content loaded without previous visible HTTP 500 |
| Video | Studio, project/history/script/storyboard/recovery sections loaded; no generation requested and no visible HTTP 500 |
| Dashboard | Daily seller status, workspace counters and journey guidance loaded; left open for the owner |

These are actual native-browser observations, not a Playwright network trace or
complete API-status census. No create/update/approval/research/provider action
was clicked. This work does not claim mobile, axe or whole-application coverage.
Product discovery may still report no eligible evidence; schema repair does not
fabricate an opportunity, approve sources, or make research commercially valid.

## Test and quality results

| Suite/check | Actual result |
|---|---|
| Focused Python target/preservation/reconciliation/native/source guards | **76 passed** |
| Configuration/readiness tests, no database fixture/conftest | **8 passed** |
| Windows mocked process/security/recovery tests | **9 passed**; no real processes stopped by that test script |
| Focused strict mypy: configuration and readiness tests | PASS, two files |
| Ruff / Black / compilation / PowerShell parser / diff check | PASS on affected files |
| Fresh encrypted backup, restore, negative-key/corruption and copy preservation | PASS, actual Docker/Windows execution |
| Source atomic commit and independent process preservation | PASS, actual source execution |
| Angular dev bundle/startup | PASS; existing local dependencies only |

The initial focused mypy failure was an existing `Any` return in the test helper.
It was corrected using typed Pydantic validation and both tests and strict mypy
passed afterward. One nonblocking Alembic `path_separator` deprecation warning
remains. No broad historical lint/typing cleanup or full Angular suite was run.

## Evidence and changed files

- `tmp/local-source-migration-a458dcc51f7c96d9.json`: committed source result,
  operations, fresh-process verification and recovery.
- `tmp/local-migration-rehearsal-158e44eb2e660a63.json`: fresh backup/copy evidence.
- `tmp/local-reconciliation-3830d7929ed9bb2f.json`: prior isolated atomic/rollback
  rehearsal, used to pin the exact approved repair plan.
- `tmp/local-database-migration-preflight.json`: subsequent read-only head/table/
  Video/Ads/owner verification, no pending upgrades.
- Earlier failed-attempt reports remain under their original run IDs.

Implementation additions/changes: source orchestrator
`scripts/apply_verified_local_migration.py`; exact API maintenance helper
`scripts/local-api-maintenance.ps1`; process guards/test
`scripts/local-api-process-security.psm1` and
`scripts/test-local-api-process-security.ps1`; shared backup/reconciliation helpers
`scripts/local_migration_rehearsal.py` and `scripts/local_reconciliation_copy.py`;
`qa/unit/test_verified_source_migration.py`; configuration and readiness tests;
this report and the earlier linked preflight/rehearsal reports. Historical Alembic
migration files were not changed for this repair.

## Normal use and limits

Open **http://127.0.0.1:4200/** and refresh any old page. Services are currently
running; do not launch duplicate copies. For a future stopped local installation,
use two repository-root PowerShell terminals:

```powershell
npm.cmd run dev:api
# In the other terminal:
npm.cmd run dev:web
```

Do not rerun the source repair as a startup step; its legacy-revision guard will
reject an already-upgraded database. No publishing worker is needed for these
read-only checks. Real provider research, publishing, supplier actions, payments,
production launch and independent off-device backup remain separate boundaries.
No golden database modification, marketplace call, RFQ, procurement, branch,
commit or push occurred.
