# WP6A — Video and Ads schema remediation

2026-10-30. **WP6A PASS — bounded local schema and browser validation.**
Application certification remains **INCOMPLETE**. Stop before WP7. This is not
certification of advertising execution, video rendering, production upgrades, or
all historical model/schema differences.

## Confirmed causes and corrections

| Finding | Actual contract/root cause | Smallest correction |
| --- | --- | --- |
| SE-WP6-VIDEO-001 | `apps/api/alembic/versions/20260904_0048_ai_video_slice2.py:249` builds `f"{name[:-3]}version"`, producing `storyboardversion` and `styleversion`. `video/models.py:248` and `:252` select underscored names. A fully migrated old head still fails; this is historical migration/model drift, not an unapplied migration. | New revision `20261205_0148` renames the two existing nullable INTEGER columns in place. No value or identity rewrite. |
| SE-WP6-ADS-001 | `ads/models.py:119`–`:122` requires campaign recovery fields. Historical `20260910_0058_ads_hard_closure.py:75`–`:78` added corresponding fields only to `ad_jobs`. Actual `ad_campaigns` lacked all four, breaking overview and dependent ORM reads. | Same revision adds nullable `failure_category VARCHAR(80)`, `retry_after_seconds INTEGER`, `next_retry_at TIMESTAMPTZ`, `correlation_id VARCHAR(64)` and its nonunique index. No defaults or invented backfill: historical unknowns remain NULL. |
| SE-WP6A-SCENE-001 | Real canonical storyboard POST with a scene failed NOT NULL on `video_scenes.generation_id`. Historical slice2 added storyboard ownership without relaxing the original generation requirement, whereas `video/models.py:335` and the existing storyboard service support generation-free drafts. | New `20261206_0149` makes the existing UUID generation link nullable, preserving its FK, index, records and established authority. No fake generation is created. |
| SE-WP6A-RETRY-001 | Video `load()` retained an earlier unavailable error after successful reload; failed reads also retained old result rows. | `apps/web/src/app/ai/ai-video.component.ts` clears the previous error when loading and clears old video rows on read failure. New Angular regression plus actual 503 → Retry browser test. |

No backend model, query, financial formula, route contract, approval authority or
historical migration was changed. Revision chain is
`20261204_0147 → 20261205_0148 → 20261206_0149` (single head).

## Migration safety

Both revisions verify the actual PostgreSQL schema online and lock affected
tables for the checks and transactional DDL. Unsupported or ambiguous schemas
fail before mutation. Offline SQL generation deliberately refuses to bypass
these checks. No table recreation, record deletion, synthetic evidence promotion,
UNKNOWN-to-zero conversion or permanent database upgrade was performed.

Rollback is conditional, not destructive: revision148 refuses to drop any
non-NULL new recovery value; revision149 refuses to restore NOT NULL while any
storyboard-only scene exists. Both refusals were executed and verified atomic.
Do not delete records or fabricate generation links to force downgrade. For a
future real installation, review retained data and recovery options before any
upgrade/downgrade; these tests authorize neither production changes nor backup work.

## Inventory and residual debt

Read-only, signed disposable probes inventoried **42 tables /712 columns** in
Video, Video bulk and Ads, including actual types/nullability/defaults, indexes,
FKs and checks. Before: old head147 and the six absent canonical columns. After:
head149 and **no missing/extra ORM column names**. Evidence:
`tmp/qa-seller-browser/{b7004c64985747de,eb682f109ceff301}/wp6a-schema-inventory.json`.

This does not mean complete schema parity. Three historical DB-nullable/ORM-not-null
differences remain: `video_generations.audio_mode`,
`video_bulk_operations.request_snapshot_json`, and
`video_bulk_children.source_media_ids_json`. Three numeric type renderings are
`DOUBLE PRECISION` versus ORM `FLOAT`; no coercion was attempted. The inventory
also records **105 missing ORM-declared index names** across these modules; this
is not proof of 105 missing access paths (equivalent differently named indexes
were not reconciled). Performance and broader historical compatibility remain
unassessed. These did not block the demonstrated local reads/draft operations;
they must not be silently represented as globally repaired.

The earlier isolated Ads comparison502 was **not reproduced** in the final
Chrome/Edge replay. Its original cause is unclassified; it is not closed merely
because the missing columns were fixed.

## Changes and architecture impact

Production: two new files under `apps/api/alembic/versions/` named above; localized
Video component reload handling. Tests: `test_seller_wp6a.py` (13),
`test_seller_wp6a_migration.py` (8), existing Video component spec (+1).

QA additions: `scripts/test-seller-wp6a.ps1`; `qa/wp6a-before.mjs`,
`wp6a-browser-retest.mjs`, `wp6a_schema_probe.py`, `wp6a_final_audit.py`,
`wp6a_redact_failure.py`, `wp6a_rotate_qa_credential.py`,
`qa/unit/wp6a-safety.test.mjs`. Shared integration changes:
`qa/fixture_server.py`, `wp4_final_audit.py`, `seller-browser-session.mjs`,
`seller-browser-explore.mjs`, `safety.mjs`, `server.mjs`.

WP6A-only proxy allowances admit credential-free synthetic local draft preparation,
not provider execution, account validation/enabling, campaign confirmation, video
queue/approval or workers. Other phases retain their previous policy. Two safety
self-tests cover exact routes/origins and invalid account payloads. Single-owner
constraint, auth, audit, provenance and backend prerequisite/version checks remain.

## QA credential incident and approved rotation

An initial migration test used plain Alembic Config; its ConfigParser percent
interpolation error exposed the QA-only credential in a traceback. It was a test
configuration defect, not the application schema defect. The test now reuses the
existing `QaMigrationConfig` escaping contract. Failed counts are preserved;
21 credential occurrences in the generated JUnit artifact were redacted without
retaining a raw copy. Tool transcript exposure cannot be retracted.

After explicit HUMAN approval and all active QA runs stopped, **only** the
dedicated QA role/local protected secret was rotated. NTFS owner/SYSTEM ACLs,
new login and rejection of the old credential were verified. Rotation PASS:
`tmp/qa-wp6a-credential-rotation.json`. No production `.env`, unrelated role,
permanent/golden database or marketplace secret was changed. Do not rerun the
one-time rotation helper without separate authorization.

## Validation decision

Final results: **8 migration +13 service +28 adjacent backend PASS;371 Angular
PASS;63 Node and54 Python QA PASS;9 real browser assertion groups PASS**.
See [migration evidence](wp6a-migration-validation.md),
[browser evidence and limitations](wp6a-browser-retest.md), and
[machine-readable resolution](wp6a-resolution.json).

All nine WP6A signed disposable databases are independently absent; original10
Docker containers and original networks/volumes preserved. Six retained traces
pass ZIP CRC. Current approved credential scan finds0 matches; historical exposure
is disclosed above, not erased by that result. Backup certification stays parked.
No provider calls, commercial writes, branches, commits or pushes. No WP7.
