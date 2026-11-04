# Local application database migration preflight

3 November 2026, Asia/Calcutta. The original preparation findings below are
retained. A subsequent authorized backup/restore passed, but migration on the
restored copy failed. Source migration remains blocked. See
[actual rehearsal evidence](local-database-backup-rehearsal.md).
Subsequent final outcome: [approved source repair and upgrade completed](local-database-source-upgrade.md).
The original findings below describe the pre-upgrade schema, not its current state.

## Confirmed target and read-only findings

The owner authorized exact-target verification and preparation of a
backup-backed migration. No database modification has been performed.

- Application: this repository's Uvicorn application on `127.0.0.1:8000`.
- PostgreSQL endpoint: `127.0.0.1:5432`, database `vayujit`, role `vayujit`.
- Existing server container: `infrastructure-postgres-1`, observed ID prefix
  `9082e894b5af`, PostgreSQL 17.10. No container restart or recreation occurred.
- Root/API-directory configuration candidates agreed. The live API revision and
  the read-only database query both returned `20261010_0151`.
- Repository head: `20261207_0150`, sixteen descendant migration steps pending.
  Revision IDs must be interpreted through Alembic ancestry, not numeric suffixes.
- One owner row; `ck_users_single_owner` is present and must remain unchanged.
- Database inspection enforced `default_transaction_read_only=on` and verified
  `transaction_read_only=on`, with a five-second statement timeout.

Missing tables are confirmed, not inferred from HTTP errors:

| Required table | Present |
|---|---|
| catalog_product_lineages | No |
| catalog_product_variants | No |
| inventory_items | No |
| inventory_movements | No |
| channel_sku_mappings | No |
| marketplace_orders | Yes |
| operational_signals | No |

`video_generations` has legacy `storyboardversion` and `styleversion`; its
canonical underscore-named columns are absent. The four Ads recovery columns
introduced by the pending compatibility migration are absent as well. These
findings explain specific schema incompatibilities behind the affected modules;
they do not assert that every HTTP 500 shares exactly the same exception.

The health-check default still expects `20261203_0146`, which is also behind the
repository head. It must be aligned to the tested release after successful
migration, not changed now to disguise the old schema as ready.

Sanitized evidence: `tmp/local-database-migration-preflight.json`. No credentials,
connection URL, owner details, or business records are included. An initial health
request timed out; subsequent live/readiness checks and the completed preflight
succeeded. The diagnostic reports an allowlisted stage and exception class only.

## Backup and restore prerequisites

Existing tools were verified locally: age 1.3.2 and the current PostgreSQL
container's `pg_dump`/`pg_restore` 17.10. No host PostgreSQL client was found by
the existing optional resolver. No download or installation was attempted.

Do not run the PC-first backup script against this installation: its guarded
profile contract is different. Do not initialize a business profile to satisfy
that guard. PC-first certification stays parked.

Before any source migration:

1. Obtain the owner's backup destination. Reject repository, database-storage,
   media-storage and ambiguous destinations. Verify writability and available
   space. Record physical/off-device independence as UNVERIFIED unless proved.
2. Use an owner-provided age public recipient, or obtain approval to generate a
   recovery key with the existing owner/SYSTEM-only Windows ACL helper. Store the
   key separately from backup artifacts; never print or commit it. Owner must
   arrange safe recovery-key custody.
3. Identify and pause only this application and its applicable workers, preserve
   prior maintenance state, and prevent business writes while taking the final
   consistent database/media backup. No unrelated process or Docker lifecycle
   action is authorized by this plan.
4. Produce an encrypted, nonempty PostgreSQL custom-format backup using a
   binary-safe stream or the existing verified binary-copy mechanism. Never use
   Windows PowerShell 5 text redirection for a binary dump. Capture native exit
   codes and sanitized failures. Preserve media separately with hashes and ensure
   the runtime media root is unambiguous.
5. Verify decryption, artifact hashes, and archive contents. Independently restore
   the database into a newly marked, temporary PostgreSQL container with no
   published ports or external network, if the owner approves this real-data
   restore environment. Restore media into separate protected temporary storage.
   The approved `vayujit-qa-postgres` instance is synthetic-only and must NOT receive
   this business backup.
6. Compare source/restore schema revisions, owner constraint, canonical record
   counts and financial precision/media hashes without logging record contents.
   Retain encrypted backups; clean only positively identified temporary resources.

At the original preflight these gates were NOT RUN. The subsequent authorized
run `c2bd95c186adede5` verified encrypted database/configuration backup and
independent database/media restore. It used a read-only exported PostgreSQL
snapshot, not an application maintenance window. This does not establish a final
quiesced pre-migration backup or off-device protection.

## Controlled migration rehearsal and application

1. Rehearse all sixteen checked-in upgrades on the isolated restored copy first.
   The Video/Ads repair intentionally rejects unsupported/ambiguous schema; do
   not stamp a revision, create tables manually, or bypass its checks.
2. Compare preservation invariants and test affected APIs on that isolated copy
   with real-provider egress and all external writes disabled. Existing synthetic
   QA success does not substitute for this legacy-data compatibility rehearsal.
3. Reconfirm the exact source identity and revision and the verified backup while
   writes remain quiesced. Apply the same tested migration path only under the
   owner's authority. Pin the database URL privately in the migration process;
   do not pass it on the command line or rely on a different working directory's
   `.env` precedence. The generic `npm.cmd run db:migrate` is not a substitute for
   these safeguards.
4. Align expected migration metadata, restart only the affected application
   processes, and verify health/readiness, authentication, catalog, inventory,
   orders, financial views, operational briefing, Video and recovery. Preserve
   all data, source approvals, HUMAN decisions and single-owner architecture.
5. On failure, stop writes and preserve safe diagnostics. Do not reset the source
   database or perform an automatic downgrade. A validated restore of the retained
   pre-migration backup is the rollback path, subject to explicit target checks.

## Owner inputs and current gate (updated after rehearsal)

- Owner supplied `C:\vayujit-os db encr bkp` and approved a separate protected
  recovery key and isolated real-data restore. Those operations ran.
- Owner still needs to arrange offline recovery-key custody and an independently
  protected backup copy; physical destination independence is UNVERIFIED.
- Source is still at `20261010_0151`. Existing objects from pending revisions
  `20261011_0152` and `20261012_0153` conflict with their canonical CREATE
  operations. The first copy-only failure is `DuplicateTable` for
  `intelligence_supplier_comparison_snapshots`.
- Strict schema-contract comparison and a non-destructive reconciliation plan
  must pass on a restored copy before any source upgrade. No blind stamping,
  dropping existing tables, or skipping validation is acceptable.
- Subsequent owner approval covers the exact source upgrade only after every
  prerequisite passes. A read-only contract audit then established that the
  existing collision tables are not equivalent (defaults and indexes differ;
  shortlist linkage is absent). A timestamp discrepancy was a reflection-format
  false positive and has been corrected. The originally failed copy-upgrade was
  subsequently resolved in an approved isolated-copy-only rehearsal. That run
  passed all sixteen upgrades and fresh-process preservation; source repair and
  upgrade remain NOT RUN. See the rehearsal reports for this chronology and the
  additional source authorization boundary.

Until backup verification and the legacy-data rehearsal pass, the source migration
is blocked. No marketplace/provider request, publishing, supplier contact,
procurement, payment, branch, commit or push is part of this operation.

## Reproducible checks

Executed results: read-only runtime/schema preflight completed; the final focused
suite contains 26 passing pure guard/native-process tests, zero failed. The
original twelve target-guard tests are included, not an additional total.
Focused Ruff, Black, Python compilation, PowerShell parser checks and
`git diff --check` were rerun for the diagnostic scripts. Actual runtime evidence
is recorded separately: backup/restore VERIFIED; copy migration FAILED; source
migration NOT RUN. No application/UI code was changed or browser repair claimed.

```powershell
# Read-only target/schema preflight; never invokes a migration.
.\apps\api\.venv\Scripts\python.exe scripts\preflight-local-database.py --read-only

# Pure target-guard tests; no database connection.
.\apps\api\.venv\Scripts\python.exe -m pytest qa\unit\test_local_database_preflight.py -q
```
