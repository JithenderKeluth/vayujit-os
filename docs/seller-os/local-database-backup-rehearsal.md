# Local database encrypted backup and migration rehearsal

3 November 2026, Asia/Calcutta. Run: `c2bd95c186adede5`.

## Decision

Historical first-run decision below is preserved. A later separately authorized
fresh backup and atomic reconciliation/upgrade succeeded on source; current
outcome: [source upgrade applied and verified](local-database-source-upgrade.md).

Encrypted backup and isolated restore: **VERIFIED**.
Copy-only migration rehearsal: **BLOCKED — DuplicateTable**.
Original database migration: **NOT RUN**. Application HTTP 500s are not yet fixed.
This is not PC-first deployment certification or off-device backup certification.

The owner supplied `C:\vayujit-os db encr bkp` and separately authorized the
protected recovery key and real-data restore in a temporary container with no
network or published ports. The synthetic-only QA server was not used for this
data. No source DDL or migration was executed.

## Target and artifacts

Confirmed source: database/role `vayujit`, loopback `127.0.0.1:5432`, PostgreSQL
17.10, container `infrastructure-postgres-1` (ID prefix `9082e894b5af`).
Source journal remained `20261010_0151` in the subsequent read-only check.
There is one owner and `ck_users_single_owner` remains required.

Backup directory: `C:\vayujit-os db encr bkp\migration-c2bd95c186adede5`.

| Encrypted artifact | Bytes |
|---|---:|
| database.dump.age | 2,727,180 |
| media.zip.age | 118,952,395 |
| media.json.age | 2,375,808 |
| recovery-configuration.json.age | 385 |

The age recovery identity is separate, under
`%LOCALAPPDATA%\VAYUJIT OS\migration-recovery-keys\c2bd95c186adede5\recovery.agekey`.
Owner/SYSTEM-only ACL checks passed. Never paste this file into chat, logs or
reports. Owner must arrange offline key custody separately from ciphertext.
The C: destination is on this PC: physical independence **UNVERIFIED**; it does
not establish protection against losing the PC or its disk.

## Actual runtime results

| Check | Actual result |
|---|---|
| Exact source identity and loopback binding | PASS |
| Read-only repeatable-read exported PostgreSQL snapshot | PASS |
| Binary-safe dump encryption and nonempty ciphertext/header | PASS |
| Recovery configuration encrypted and decryption hash verified | PASS |
| Database decryption hash verification | PASS |
| Wrong-key rejection | PASS |
| Corrupted-ciphertext rejection | PASS |
| Independent PostgreSQL restore, no network/no published ports | PASS |
| Every original table's rows and financial numeric values compared with snapshot | PASS |
| Restored revision and single-owner constraint | PASS |
| Independent media restore and checksums | PASS — 8,959 media-tree files |
| All sixteen pending upgrades on restored copy | FAIL — first duplicate table |
| Fresh source row comparison after rehearsal | NOT EXECUTED after migration failure |
| Original database upgrade | NOT RUN |
| Temporary resources and plaintext cleanup | PASS |

The media count is a filesystem-tree count, not a count of catalog product
images. Source data was accessed read-only. A post-rehearsal full fresh-source
row comparison did not execute, so no such equality claim is made. This was not
a final maintenance-window backup. Overall run status remains **FAIL**, duration
371.891 seconds; per-stage durations were not recorded.

## Precise migration blocker

The database journal is behind some already-existing schema objects while other
required tables are absent. The historical cause of this mixed state is unknown.
The isolated migration's native failure classification was `native_DuplicateTable`
(exit 1) in `copy_only_migration_rehearsal`.

Read-only collision inspection confirmed:

| Pending migration | Already-existing object |
|---|---|
| 20261011_0152 | intelligence_supplier_comparison_snapshots |
| 20261012_0153 | intelligence_supplier_procurement_readiness_assessments |
| 20261012_0153 | intelligence_supplier_procurement_readiness_acknowledgements |
| 20261012_0153 | ix_pr8c_ack_assessment |

The first canonical CREATE is in
`apps/api/alembic/versions/20261011_0152_supplier_comparison_snapshot.py`.
Do not blindly DROP/recreate, stamp the journal or add IF NOT EXISTS to bypass
the conflict. Existing object existence does not establish schema equivalence.

Next: compare complete existing column/type/default/nullability, constraint and
index contracts with canonical migrations; design a strictly checked,
non-destructive reconciliation if equivalent. Rehearse from the retained
ciphertext in a new isolated restore, prove preservation through the full
upgrade chain, then obtain/confirm authority for a source maintenance window.
No speculative repair has been applied to source or historical migrations.

## Cleanup and evidence

Only marked run resources were removed: the migration runner, restore container
and restore volume for `c2bd95c186adede5`; protected plaintext staging was removed.
Independent label-filtered Docker checks returned no remaining resources for
this token. The real recovery key and all encrypted artifacts were retained.
Source and QA containers remained present/healthy; no restart/remove command
was issued against either. A final start-time comparison did not run after the
early migration failure and is not claimed.

- Original immutable report: `tmp/local-migration-rehearsal-c2bd95c186adede5.json`.
- Read-only collision evidence: `tmp/local-database-migration-preflight.json`.
- Derived verification summary:
  `tmp/local-migration-backup-verification-c2bd95c186adede5.json` and
  `backup-verification-summary.json` in the backup directory. It includes
  ciphertext hashes and the original report hash; it does not change FAIL to PASS.

## Changed files and focused verification

- `scripts/preflight-local-database.py`: exact-target read-only checks and pending
  CREATE-object collision inventory.
- `scripts/local-migration-private.ps1`: existing Windows private-ACL/key helpers,
  marked run directories and post-cleanup identity/backup ACL verification.
- `scripts/local_migration_rehearsal.py`: exported-snapshot encrypted backup,
  isolated restore, copy-only upgrades, preservation checks and guarded cleanup.
- `scripts/summarize_local_migration.py`: exact-run evidence derivation; no source
  database connection and no private-key contents read.
- Two focused test modules under `qa/unit/`: **26 passed, 0 failed**. Pure native
  subprocess/filesystem/guard tests, not Docker certification tests.
- This report and `local-database-migration-preflight.md`.

Run focused tests (no database connection):

```powershell
.\apps\api\.venv\Scripts\python.exe -m pytest qa\unit\test_local_database_preflight.py qa\unit\test_local_migration_rehearsal.py -q
.\apps\api\.venv\Scripts\python.exe scripts\preflight-local-database.py --read-only
```

The second command is a read-only live diagnostic, not a repair command.
Ruff/Black, compilation, PowerShell parser and diff checks apply to these changed
scripts only, not repository-wide debt. Reporting-only refinements after the
runtime failure were statically/pure-test checked; the complete restore was not
rerun after those refinements. No Angular code changed. No marketplace/provider
call, supplier action, permanent initialization, branch, commit or push occurred.

Remaining blockers: strict legacy-schema reconciliation and successful copy
upgrade/preservation; source maintenance authorization and final backup/recheck;
post-upgrade API/browser verification. Offline recovery-key custody and verified
independent backup storage remain owner responsibilities.

## Conditional source approval and subsequent read-only contract audit

The owner subsequently approved applying the tested sixteen migrations to only
`vayujit` at `127.0.0.1:5432`, **only after every backup, restore, preservation and
copy-upgrade prerequisite passes**. This does not turn the failed copy upgrade
into a pass. No source migration or repair has been run.

The additional audit records canonical upgrade operations against an in-memory
recorder, not a live Alembic context, and compares them with a read-only schema
inspection. The first attempt was BLOCKED by an API-readiness timeout. One retry
completed successfully. Evidence: `tmp/local-migration-contract-audit.json`.

The three conflicting tables each contain zero rows at inspection time, but their
contracts are **not equivalent** to the canonical migrations:

- The initial audit reported a `created_at` timezone mismatch. **This finding
  was disproven:** SQLAlchemy's generic string representation omitted timezone
  information. PostgreSQL-dialect-aware reflection and a fresh read-only source
  check confirm `TIMESTAMP WITH TIME ZONE` on all three. No timestamp change was
  required or performed. The audit helper and regression coverage were corrected.
- Canonical server defaults are missing, including JSON/state defaults and the
  HUMAN provenance defaults where specified.
- Index names/sets differ. The existing acknowledgement composite index does not
  establish equivalence for the remaining schema.
- The shortlist's required `comparison_snapshot_id` column, index and foreign key
  are absent. They must not be skipped by blindly advancing the Alembic journal.
- Primary-key, unique-column and foreign-key reference/delete semantics compared
  by this audit agree. This is not a claim that every constraint name, index
  option or complete legacy schema is identical.

The audit does not infer the historical cause of this drift. Empty tables alone
do not authorize destructive replacement or unconditional adoption. A separately
scoped repair must reject unexpected layouts, preserve historical rows and
constraints, and pass on another isolated restore before any source decision.
Approval has been requested for isolated-copy reconciliation/testing; additional
source reconciliation beyond the original sixteen upgrades remains a separate
authorization boundary.

Additional files: `scripts/audit_local_migration_contract.py` and
`qa/unit/test_local_migration_contract.py`. Eight new database-free tests cover
in-memory migration recording, mandatory contracts and conservative difference
reporting. Combined focused total: **34 passed, 0 failed** (the earlier 26 plus
these eight). No second full backup/restore or copy-upgrade run was performed.

That 34-test/no-second-run statement describes the earlier audit stage only.
The subsequently approved isolated-copy reconciliation is now complete:
**65 focused tests passed; all sixteen upgrades and fresh-process preservation
verification passed on a retained-backup restore. Source migration remains NOT
RUN.** See [the reconciliation rehearsal](local-database-reconciliation-rehearsal.md)
for exact changes, failed-attempt disclosure, cleanup and the additional source
authorization boundary.

```powershell
# Read-only audit; no migration/repair function exists in this script.
.\apps\api\.venv\Scripts\python.exe scripts\audit_local_migration_contract.py

# All focused, database-free tests from this workstream.
.\apps\api\.venv\Scripts\python.exe -m pytest qa\unit\test_local_database_preflight.py qa\unit\test_local_migration_rehearsal.py qa\unit\test_local_migration_contract.py -q
```
