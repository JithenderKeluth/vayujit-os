# WP2 — Goals, opportunities, research and product selection

Date: 2026-10-29. **IMPLEMENTED / BOUNDED LOCAL BROWSER RETEST PASSED.**
Application certification remains **INCOMPLETE**. Stop after WP2; no next package started.

## Authoritative evidence and finding mapping

Reviewed the original exploration report, finding ledger, journey coverage, completion
backlog, target experience, WP1 implementation/retest/resolution, captured screenshots
and trace action metadata. The original observations are preserved, not replaced by
the new outcomes. No additional ranked finding IDs were invented.

| Existing ID | Reproduced cause | Implemented correction / actual outcome |
| --- | --- | --- |
| SE-BROWSER-005 | Evidence-card read helper deliberately swallowed404 without a visible result. | Per-area loading, absent saved assessment, loaded and error feedback in an accessible live region; exact product context retained. All six absent projections exercised in Chrome. |
| SE-BROWSER-008 | Hardcoded Research complete eyebrow irrespective of run existence. | Canonical projection supplies run count/latest status; list distinguishes not started, queued, gaps and completed. Empty fresh installation now says Research not started. Manual identities are not described as a successful live search. |
| SE-BROWSER-011 / SE-HANDOFF-001 | Working Catalog conversion authority had no frontend invocation. | Selected-opportunity next-actions component exposes owned brand selection, explicit local-draft confirmation, safe conversion/replay and exact Catalog link. No prices, costs, stock, supplier facts or publication invented. |
| SE-BROWSER-014 | My Research routed directly to the broad technical /intelligence workspace. | Focused saved-goal/research landing at /intelligence/research; exact goal links to its plan/run and scoped opportunities. Advanced tools remain linked, not removed. |
| SE-AUTHORITY-001 | Projection, journey, Agent and Catalog searched for any historical shortlist, even after rejection; action-derived replay key prevented genuine reselection. Browser/API reproduction confirmed selected_after_rejection=true. | Shared current-decision/current-selection query over the existing immutable decision ledger, current assessment and non-archived opportunity. Rejection revokes current selection; explicit reselection appends a new decision. Identical authorized replay reuses identity; conflicting explicit key409; stale new decision409; advisory lock serializes concurrent decisions. |
| SE-AUTHORITY-002 | Conversion checked goal ownership but not the goal/opportunity relationship. | Conversion now requires explicit opportunity linkage or the existing Business Agent run/candidate lineage for the supplied goal. Unrelated-goal409 tested. This is not a certification of live category discovery or every goal-context authority. |

Only browser IDs005/008/011/014 are resolved in the canonical browser ledger. WP1's
001–004 remain resolved; the other twelve browser findings remain open. Broader audit
IDs are follow-up correlations, not silently recategorized historical findings.

## Coherent seller flow

- Goal guidance explains supported product research, known constraints, plan/run review,
  step-based progress and the difference between evidence review and business success.
- There is no supported in-place goal editing API. Prepare a revised goal opens a new
  draft, preserves the original goal/evidence and explicitly says so. It does not fake
  an update. Goal selection and creation synchronize goal_id with the URL/history.
- Opportunities keep the requested goal on direct detail/list navigation and reload.
  Stale asynchronous detail responses are ignored; switching an opportunity clears old
  detail/evidence. No active-goal substitution is used for an explicit goal query.
- Manually entered/imported origin is distinct from verified evidence; mixed live/fixture
  results say MIXED. Scores, confidence, risk and readiness remain separate. Missing
  evidence is never turned into a score of zero or a positive demand claim.
- Comparison can show saved assessed identities and their unknowns even when the
  canonical score authority returns NOT_COMPARABLE. No threshold, ranking rule or
  score is changed to make alternatives appear comparable.
- HUMAN decision history is read from the existing ledger through an owner-scoped
  GET endpoint. Selecting/rejecting has explicit confirmation; cancel performs no write.
  History retains rationale/time/assessment; stale decisions are labelled.
- Catalog conversion reuses the existing authority and product identity. A new product
  creation can now participate in the conversion transaction (`commit=False`, default
  behavior unchanged elsewhere), so product+lineage commit atomically. Conversion is
  serialized by owner/opportunity; concurrent calls produce one product and one lineage.
- A503 conversion retest discovered that the new form collapsed on failure. Its recorded
  selection/form values now remain visible, while further writes require a successful
  context reload. No error is reclassified as saved/approved. Styling uses the existing
  teal/white visual language and visible keyboard focus.

## Files changed for WP2

Backend:

- `apps/api/vayujit_api/intelligence/product_opportunity_scoring_service.py`
- `apps/api/vayujit_api/intelligence/product_opportunity_scoring_router.py`
- `apps/api/vayujit_api/intelligence/commerce_journey.py`
- `apps/api/vayujit_api/intelligence/business_agent_service.py`
- `apps/api/vayujit_api/catalog/service.py`
- `apps/api/vayujit_api/products/service.py`
- `apps/api/tests/test_seller_wp2.py`

Frontend:

- New `apps/web/src/app/intelligence/opportunity-next-actions.component.ts`
- New `apps/web/src/app/intelligence/seller-research.component.ts`
- New `apps/web/src/app/intelligence/seller-wp2.spec.ts`
- `product-opportunity.service.ts`, `product-opportunity-workspace.component.ts` and
  its existing spec, `business-agent-workspace.component.ts`, under the same directory
- `apps/web/src/app/app.routes.ts`
- `apps/web/src/app/shared/seller-navigation.component.ts` and its spec

QA and documentation:

- `scripts/test-seller-wp2.ps1`, `qa/fixture_server.py`
- `qa/wp2-before.mjs`, `qa/wp2-fixtures.mjs`, `qa/wp2-browser-retest.mjs`
- `qa/safety.mjs`, `qa/server.mjs`, `qa/unit/wp2-safety.test.mjs`
- `qa/wp2_final_audit.py`, `qa/postgres_instance.py`, `qa/unit/test_postgres_instance.py`
- Three WP2 reports, browser finding ledger, journey coverage and backlog addenda

No database migration is required for WP2: existing decision, product and lineage
tables are reused. Fresh disposable databases migrated to the existing head20261204_0147.
Prior dirty-worktree/PC-first/WP1 changes were preserved, not attributed to WP2.

## Actual validation

| Check | Final execution, not sum of reruns |
| --- | --- |
| Persisted WP2 + WP1 contracts | **16 passed** (8 new WP2, 8 WP1), 0 failed/errors/skipped; run1e9e4b3896f74ca1 |
| Existing scoring, Catalog, Business Agent regressions | **21 passed**, 0 failed/errors/skipped; run713a093e99ba455b |
| Full Angular suite | **289 passed**, 73 files; 9 net additional WP2 tests versus WP1's280 |
| QA Node self-tests | **51 passed**, 0 failed/skipped; includes two WP2 safety tests |
| QA Python self-tests | **54 passed**, 0 failed/skipped; includes bounded recovery-timeout guard |
| Final authenticated Chrome desktop/mobile replay | **23 passed, 0 failed**, run7cc1ce7878744301 |
| Axe | Four actual scans: **0 violations, 0 incomplete** in those states; no WCAG claim |
| Production build | PASS; initial518.03kB versus500kB budget warning; WP1 was517.89kB |
| Focused ESLint/Ruff/Black/compileall, strict mypy4 contracts | PASS; not repository-wide historical debt closure |
| PowerShell parser, Node syntax, git diff --check | PASS; line-ending warnings separately retained |

Existing deprecation, duplicate OpenAPI operation-ID and bundle warnings were not
removed by weakening checks. New strict typing errors and fixture typing/import
errors found during implementation were corrected and rerun.

## QA boundary and cleanup recovery

Only the approved signed `vayujit-qa-postgres` instance at127.0.0.1:55432 and its
non-superuser QA role were used. The QA proxy now permits canonical score comparison
POSTs and **queued** synthetic run creation only with max_provider_calls=0 and a
wp2- key. Run start/real acquisition remain denied. No run was executed to manufacture
live candidates: two manual synthetic identities were prepared through supported APIs
under the existing run/candidate lineage. The report never calls that live discovery.

Two owned databases were left as invalid PostgreSQL tombstones after the existing
15-second guarded DROP timed out. Original CLEANUP_BLOCKED evidence remains. Explicit
resume now accepts a validated15–90-second timeout only for its own recovery connection;
it still verifies signed DROPPING state, exact instance/role/owner/OID and zero sessions.
Normal cleanup retains its default; no FORCE, role/server configuration change,
catalog edit, session termination or unrelated resource deletion. Both exact tombstones
were recovered with90seconds. The engine-level reason for the slow DROP was not fully
profiled; statement-timeout cancellation itself was directly observed.

`tmp/qa-wp2-final-audit.json` is the independent read-only cleanup/resource/trace proof.
All13 WP2 databases are absent and signed DROPPED. Original10 Docker containers and
original networks/volumes are unchanged. Synthetic fixtures are intentionally removed;
screenshots, traces and failure reports remain. No permanent/golden database or real
seller records were initialized or modified. Backup certification remains parked.

## Remaining limitations / stop

Read [actual journeys and evidence](wp2-browser-retest.md) and the
[resolution record](wp2-resolution.json). Live product discovery, source approval,
provider failures, genuine market demand, real supplier acquisition and all-viewport/
screen-reader certification remain unverified. Goal revisions are new drafts, not
in-place editing. Mobile navigation/breadcrumb/banner friction and the other twelve
browser findings remain open. No marketplace writes, supplier contact, procurement,
payments, new branches, commits or pushes. No application certification is claimed.
