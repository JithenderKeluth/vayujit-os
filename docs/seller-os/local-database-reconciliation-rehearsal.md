# Checked legacy-schema reconciliation — isolated-copy rehearsal

3 November 2026, Asia/Calcutta.

**COPY-ONLY RECONCILIATION AND SIXTEEN UPGRADES: PASSED.**
**At this isolated-copy milestone, original repair/migration was NOT RUN.**
The owner subsequently approved the exact repair, and a new fresh backup plus
atomic-copy/rollback/preservation rehearsal passed before a successful source
upgrade. See [the final source execution report](local-database-source-upgrade.md).
The evidence below remains the historical copy-only result.

## Authority and boundaries

The owner approved a non-destructive reconciliation and test on a new isolated
restore of retained backup `c2bd95c186adede5`. This does not authorize additional
source repair beyond the previously conditionally approved sixteen migrations.
The exact successful repair plan has been submitted for separate source approval.
No source/QA database connection is made by the new rehearsal orchestrator.
The only source access after this run was the existing read-only metadata audit.

The original database is still `vayujit` at `127.0.0.1:5432`, at revision
`20261010_0151`. Application failures have not been retested or declared fixed.
The PC-first certification remains parked; no permanent profile was initialized.

## Confirmed root cause and correction

Three pre-existing PR-8B/8C tables collide with CREATE operations in journal-
pending revisions `20261011_0152` and `20261012_0153`. Their required columns,
primary-key, uniqueness and foreign-key/delete semantics are compatible, but
canonical server defaults and canonical indexes are missing. The shortlist
comparison linkage is also missing. Their historical creation path is unknown.

The initial timestamp warning was **an audit-tool false positive**, not schema
drift. Generic `str(type)` lost PostgreSQL timezone information. The helper now
compiles reflected types using the PostgreSQL dialect. A regression test and a
fresh read-only source audit confirm all three `created_at` columns already use
`TIMESTAMP WITH TIME ZONE`. **No timestamp conversion ran.**

Exact reconciliation executed on the restored copy:

| Operation | Count | Behavior |
|---|---:|---|
| Set missing canonical server defaults | 31 | Literal/defaults from canonical migrations; no row updates |
| Add missing canonical indexes | 24 | Preserve existing indexes and constraints |
| Adopt existing tables after required-contract verification | 3 | No DROP/recreate |
| Timestamp changes | 0 | Existing types already canonical |
| Canonical Alembic upgrade steps | 16 | Normal revision transitions, not blind stamping |

Historical migration files were not edited. The copy runner uses the original
Alembic revision graph, with checked operations only for the two known collision
revisions. Existing-table/index CREATE operations may be reused only after
canonical columns/defaults, PK/UQ/FK semantics and required indexes are verified.
All remaining operations delegate to Alembic, including the shortlist column,
index and foreign key; these are not skipped.

The reconciliation checks every table before changing any schema, inside one
transaction with exclusive locks and a five-second lock timeout. It requires all
three legacy tables to remain empty and rejects unexpected columns, nullability,
types, conflicting defaults, constraints, index shapes/options, generated
columns, row security, custom triggers and invalid/unvalidated indexes or
constraints. The copy database name, role, random run marker and legacy revision
must match. There is no source-target option.

## Actual execution evidence

Successful run: `88059bbb352b71df`.
Safe report: `tmp/local-reconciliation-88059bbb352b71df.json`.
Duration including cleanup: **21.047 seconds**.

| Runtime gate | Result |
|---|---|
| Retained protected backup marker, evidence hash and all four ciphertext hashes | PASS |
| Existing recovery-key owner/SYSTEM-only ACL | PASS |
| Fresh marked PostgreSQL container/volume, no network or published ports | PASS |
| Decrypt retained database ciphertext and restore with exit-on-error, single transaction | PASS |
| Confirm restored legacy revision and add copy-only marker | PASS |
| Strict empty-table reconciliation | PASS — 31 defaults, 24 indexes, no timestamp changes |
| Sixteen upgrades reach exact repository head | PASS — `20261207_0150` |
| Preserve original 392 tables' rows and financial numeric values | PASS — deterministic per-table row-count/digest comparisons |
| Separate fresh process reconnects and verifies old rows/precision | PASS |
| Fresh-process canonical PR-8B/8C schema, shortlist linkage, required catalog/inventory/operations tables | PASS |
| One owner and validated `ck_users_single_owner` | PASS |
| Source/QA container identity and start times unchanged | PASS |
| Three exact marked containers and one marked volume removed | PASS |
| Protected plaintext staging removed | PASS |
| Original database modification | NOT RUN |

The original encrypted media/configuration artifacts were rehashed, not restored
again in this narrower run. Independent media/configuration restoration and
wrong-key/corruption checks remain the actual earlier backup evidence, not new
tests claimed here. No current-source full row comparison or final maintenance-
window backup was performed in this copy-only task.

### Failed attempt preserved

Run `09b6b1534832ed3b` failed at `retained_ciphertext_restore`, exit 1, before
reconciliation, after 4.422 seconds. Exact marked container, volume and staging
cleanup passed. Its report remains FAIL. The original native stderr was discarded
by the existing binary helper, so its precise native cause is **not established**.

The new runner's readiness now requires the final TCP-listening PostgreSQL server
instead of relying on a Unix-socket readiness check that can observe Docker's
temporary initialization server. Startup race is a plausible explanation, not a
proven diagnosis of that first failure. Optional binary-helper diagnostics now
distinguish producer/consumer failures, absent database, refused/closed connection
and unsupported dump version using fixed classifications only. The bounded
stderr buffer stays in memory; raw output/arguments are never retained in reports.
After these changes the complete fresh retry passed. Default behavior for the
earlier helper's other callers is preserved.

## Focused tests and static checks

Final focused suite: **65 passed, 0 failed**:

- Existing exact-target, binary pipeline and migration-contract guards.
- New empty/nonempty-table and unknown-drift rejection cases.
- Canonical literal/default matching and refusal of unreconciled adoption.
- Source-name and missing-copy-marker rejection.
- Timezone-aware reflection regression.
- Native warning/nonzero exit/timeout behavior and sanitized failure diagnostics.

Ruff, Black, Python compilation, PowerShell parser and `git diff --check` passed
for the affected files. One initial test used raw migration default text where
reflected SQL default syntax was required; its fixture was corrected, not the
canonical verification assertion. Formatting/lint failures were fixed and rerun.
No repository-wide mypy, Angular/browser or application certification is claimed
by this database-copy rehearsal.

```powershell
# Database-free focused regressions.
.\apps\api\.venv\Scripts\python.exe -m pytest qa\unit\test_local_database_preflight.py qa\unit\test_local_migration_rehearsal.py qa\unit\test_local_migration_contract.py qa\unit\test_local_reconciliation.py -q

# Explicit isolated-copy-only rehearsal; reuses protected retained ciphertext/key.
.\apps\api\.venv\Scripts\python.exe scripts\rehearse_local_reconciliation.py --confirm-isolated-copy-only
```

The rehearsal command creates fresh random marked resources and removes only
those resources. It does not migrate source, acquire another live backup, pull
images, call providers or use the synthetic-only QA database for real data.

## Changed files

- `scripts/audit_local_migration_contract.py`: preserve timezone type information.
- `scripts/local_reconciliation_copy.py`: strict copy-only reconciliation,
  checked canonical upgrades and fresh-process preservation verification.
- `scripts/rehearse_local_reconciliation.py`: retained-ciphertext restore,
  disconnected runners, safe report capture and exact ID/marker cleanup.
- `scripts/local-reconciliation-private.ps1`: protected fresh plaintext staging,
  reusing existing ACL helpers; no new recovery key.
- `scripts/local_migration_rehearsal.py`: opt-in bounded, allowlisted binary
  failure classification; no change to backup/restore success requirements.
- `qa/unit/test_local_reconciliation.py` and
  `qa/unit/test_local_migration_rehearsal.py`: guard/redaction regressions.
- This report and the existing preflight/backup rehearsal reports.

## Remaining source gate

The proposed source plan includes the exact **31 defaults + 24 indexes** before
the checked sixteen-step upgrade. This is additional repair, so execution is
waiting for separate owner authorization. Even if approved, source must be
quiesced, its exact identity/schema/empty-table assumptions reconfirmed and a
fresh encrypted backup/preservation check completed. Changed prerequisites must
stop execution or require another copy rehearsal; the retained older backup is
not proof that current source has not changed.

After an authorized successful source upgrade, expected-release readiness
configuration must be aligned and affected APIs/browser journeys retested. Those
steps, any rollback execution, and real-provider certification are NOT RUN here.
Local C: backup independence remains UNVERIFIED and offline recovery-key custody
remains an owner responsibility. No marketplace calls, supplier actions, payments,
commits, pushes, branches, permanent initialization or unrelated cleanup occurred.
