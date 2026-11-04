# WP1 — Supplier-to-economics remediation

Date: 2026-10-28. **WP1 COMPLETE — BOUNDED LOCAL BROWSER RETEST PASSED.**
Application certification remains **INCOMPLETE**. No next work package was started.

## Evidence and scope

Reviewed the exploration report, finding ledger, journey coverage, prioritized backlog,
target experience, historical PNGs and Playwright trace action metadata. Reproduced
the three priority defects in fresh authenticated Chrome against approved disposable
PostgreSQL before changing their contracts. The related Compare defect was also fixed.
Original observations and unsuccessful investigation runs remain evidence, not passes.

| Finding | Demonstrated root cause | Correction | Resolution |
| --- | --- | --- | --- |
| SE-BROWSER-001 | Supplier CTA hardcoded LIVE_READ_ONLY despite canonical LOCAL_FIXTURE configuration. Historical search mode was not the intended execution mode. | Backend projects current execution_mode separately; frontend uses only recognized configured modes, disables unknown/disabled/loading/error states, includes mode in replay identity and blocks busy duplicates. Existing acquisition authorization remains authoritative. | RESOLVED, local deterministic browser/API retest |
| SE-BROWSER-002 | URL canonical ProductOpportunity/CrossMarketplaceSupplier IDs were omitted. Legacy EconomicContext opportunity_id/supplier_id reference different model domains, so blindly assigning URL IDs would be incorrect. | Add nullable, correctly typed canonical FKs; retain legacy fields unchanged. Validate owner, non-archived opportunity, linked product and scoped supplier discovery correlation; reject mixed, unrelated and stale context. Save economic_context_id in URL, restore and verify exact scope on reload; no quote or cost substitution. | RESOLVED, persisted API + desktop/mobile |
| SE-BROWSER-003 | #comparison was embedded in the router path and encoded as %23comparison. | Separate route and fragment; preserve context queries. | RESOLVED, browser retest |
| SE-BROWSER-004 | UI loaded contexts/gaps but never invoked existing assessment authority; missing assessment looked like zero gaps. | Expose Assess existing evidence, busy/error/retry and Reassess states; UNKNOWN before assessment; retain prior version on failure; supplier name and explicit next economics handoff. | RESOLVED, actual UI assessment + reload |

## Closely related corrections

- A previously HUMAN-shortlisted supplier can resume its persisted verification after
  refresh without treating a newly evaluated shortlist version as another approval.
  The link says existing verification, not that the current shortlist is approved.
- Scoped pages label synthetic fixture evidence explicitly. The original accepted-source
  metadata already records fixture status; the projection now preserves that marker,
  including cached supplier detail. Missing origin is never described as verified real.
- Economics has explicit product/supplier headings, missing-input guidance and a jump
  link to inputs. Browser retesting caught a plain-hash/base-URL regression in this
  new link; it now uses RouterLink with preserved queries and has a regression test.
- No economics formula, commercial value, readiness threshold, supplier claim,
  approval authority or network safety rule was relaxed. UNKNOWN remains unavailable.

## Architecture and changed files

Backend, under `apps/api/vayujit_api/intelligence/`:
`supplier_router.py`, `cross_marketplace_service.py`, `due_diligence_service.py`,
`economic_models.py`, `economic_schemas.py`, `economic_service.py`,
`economic_integration_service.py`.

Migration `apps/api/alembic/versions/20261204_0147_economic_canonical_scope.py` adds
two nullable canonical FK columns/indexes with RESTRICT deletion and reversible DDL.
No fabricated backfill or ownership migration. Fresh signed test databases reached
this Alembic head; downgrade execution was not separately certified in WP1.

Angular, under `apps/web/src/app/intelligence/`:
`cross-marketplace-supplier.component.ts`, `supplier-journey-nav.component.ts`,
`sourcing-economics-workspace.component.ts`, `supplier-due-diligence.component.ts`,
`supplier-shortlisting.component.ts`, `supplier-shortlisting.service.ts`, new
`supplier-evidence-origin.ts`; tests in `seller-wp1.spec.ts`,
`supplier-shortlisting.component.spec.ts`, `sourcing-economics-workspace.component.spec.ts`.

QA: `apps/api/tests/test_seller_wp1.py`, `scripts/test-seller-wp1.ps1`,
`qa/fixture_server.py`, `qa/seller-browser-session.mjs`, `qa/wp1-browser-retest.mjs`,
`qa/wp1_final_audit.py`, `qa/unit/test_wp1_reset.py`, `qa/postgres_instance.py`,
`qa/unit/test_postgres_instance.py`, `apps/api/vayujit_api/core/test_database.py`.
The existing dirty worktree and parked PC-first changes were preserved, not attributed
to this package.

## QA infrastructure defects encountered

The non-superuser fixture reset tried to terminate a server-owned process. It now
targets only current-role client sessions in the already validated exact disposable
database. No new database privileges were granted. Fixture child engine disposal now
precedes signed cleanup.

One unused preflight database was left in signed DROPPING state after an interrupted
DROP, with PostgreSQL datconnlimit=-2, same recorded owner/OID and zero sessions.
The original DROP OperationalError trigger remains unestablished. A separate explicit
resume_drop revalidates the signed lifecycle and exact instance/owner/OID; the invalid
tombstone branch requires zero sessions and a prior signed DROPPING transition after
marker verification. Normal drop still rejects DROPPING. No FORCE, catalog edit,
superuser escalation or unrelated deletion. Four focused lifecycle tests cover this.
PostgreSQL documents -2 as an invalid database in its
[pg_database catalog](https://www.postgresql.org/docs/17/catalog-pg-database.html).
The original CLEANUP_BLOCKED evidence is retained; the later read-only audit confirms
all eleven WP1 databases absent and signed DROPPED.

## Final validation

| Executed check | Actual result |
| --- | --- |
| Migration-backed persisted backend, latest run 172a4676e9954763 | 13 passed, 0 failed/errors/skipped: 8 WP1 + 5 adjacent economics/DD |
| Angular complete suite, final rerun | 280 passed, 72 files; baseline 267, 13 net additional tests |
| QA Node self-tests | 49 passed, 0 failed/skipped |
| Python QA self-tests | 53 passed, 0 failed/skipped |
| Main interactive browser checks d13067df8b66b91a | 31 final passing checks; one earlier fixed-time observation failed and settled retest passed; raw 32 entries preserved |
| Independent final browser replay baa7fa4093efbf17 | 13 passed, 0 failed; fresh UI owner, HUMAN selection/shortlist, assessment, saved economics, mobile reload/keyboard |
| Final axe | 4 scans, 0 violations; 17 incomplete mobile assessment table nodes require manual contrast review |
| Production build | PASS; existing initial bundle 517.89 kB exceeds 500 kB warning by 17.89 kB |
| Focused Ruff, Black, compileall, strict mypy | PASS; strict mypy covers 4 changed contracts, not whole repository |
| Focused ESLint, PowerShell parser, Node syntax, git diff --check | PASS; line-ending warnings are not whitespace errors |
| Read-only signed cleanup/resource audit | 11/11 databases absent/DROPPED; original 10 Docker containers/networks/volumes preserved; credential matches 0 |

Counts are final executions, not the sum of reruns. Detailed evidence, limitations
and exact commands are in [browser retest](wp1-browser-retest.md) and
[machine-readable resolution](wp1-resolution.json).

## Remaining work / stop boundary

SE-BROWSER-005–020 and the additional suspected contrast finding are not closed.
In particular shortlist overview counters (007), live category hypothesis/research,
catalog conversion handoff and long economics-page hierarchy remain separate work.
Live supplier acquisition was neither enabled nor certified. No real business data,
golden database, marketplace actions, supplier contact, RFQ, payments, commits or
branches. Single-owner constraint remains. Backup certification remains parked.
