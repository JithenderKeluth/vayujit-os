# WP7 — Integrated application certification report

**Application certification: FAIL.** Significant required coverage and manual accessibility remain incomplete. This is not a production-launch decision and not a claim that passing modules establish whole-application correctness. WP8 has not started.

## Actual WP7 results

| Check | Actual result |
| --- | --- |
| Fresh routes | 156 declarations; 124 templates rendered; route visits are not feature passes |
| Backend/migration matrix | 233 passed, 1 failed, 0 errors, 0 skipped; runner exit 1; tmp/qa-wp7-backend/5054adde90dd4055/backend-results.xml |
| Angular | 377 passed /82files;4new responsive semantic tests |
| Accepted browser groups | 118 journey groups passed, plus 36 responsive checks. Original failed runs retained separately. |
| Node QA | 72 passed;6new fail-closed quality/shutdown/JUnit-census tests |
| Python QA | 70 passed;13 exact-orphan safety tests; no real database in unit tests |
| Focused finance/WP6B replay | 35 passed /0 failed; overlaps the aggregate cases, not 35 additional unique cases |
| Effective backend cases after focused retest | 234 distinct cases: 234 last-observed PASS, 0 FAIL, 0 skipped. Initial aggregate failure remains recorded. |
| Production build | PASS;422.71kB under unchanged500kB budget |
| TypeScript/app/spec | See exact current static checks in gate |
| Full lint/types | Existing ESLint2warnings; backend Ruff1import-order error; strict mypy219diagnostics in pre-WP7 backend code; full Black/compileall and money strict typing separately recorded |
| Accessibility | 551 scans; 0 violations; incomplete/manual scope retained |
| Disposable cleanup | PASS |


See [journey matrix](wp7-journey-coverage-matrix.md), [fresh inventory](wp7-route-and-capability-inventory.md), [browser evidence and commands](wp7-browser-evidence.md), [defect/reconciliation register](wp7-defect-register.md), [accessibility dispositions](wp7-accessibility-evidence.md) and [machine-readable gate](wp7-certification-gate.json). Exact revision, dirty source/build hashes, dependency lock, actual browser versions, migration head and evidence hashes are retained. No earlier WP counts are included as new WP7 passes.

## Corrections and architecture

Four bounded responsive roots across six pages: Ads recommendation/rule tables, campaign form intrinsic sizing, AI generation/history grids and publishing jobs table. Named focusable horizontal regions preserve complete table content and explicit header scopes; controls shrink without removing validation or actions. Four Angular regressions and independent Chrome/Edge390/768/1440 checks cover these corrections where accepted. No financial, provider, database schema, ownership or HUMAN authority changed.

QA-only corrections: bounded host shutdown now outlasts the already bounded guarded DROP; stale WP3 text assertion updated to the later truthful Catalog wording; direct-child Application menu locator avoids Advanced-summary ambiguity. Existing guarded deletion protections and failures remain visible. Aggregate-workload cleanup observed CheckpointDone wait; OperationalError/timeout is retained, not falsely called success. Exact-token signed recovery and final independent database absence are required.

## Known-risk dispositions

- **Ads502 / historical marketplace account-list502:** current successful reads and bounded outage/recovery tests do not identify the historical causes. Remain P2 unreproduced/unclassified; no fabricated resolution. Production nginx unchanged.
- **Schema/index debt:** fresh read-only head149 review:42Video/Ads tables, no missing ORM columns,105missing index names (26prefix access paths;79unproven performance risks),3nullable differences, equivalent Float/DOUBLEPRECISION renderings. No blind index migration/backfill/NOT NULL change. Representative load/EXPLAIN and historical-data validation remain pending. This subset is not an all421-model schema certificate.
- **Finance:** Decimal tests/modeling remain bounded by [precision policy](wp6b-financial-precision-policy.md). Source100.125×2 retains200.25 while stored unit100.13 must not reconstruct totals. Current v2 projections are mutable, not immutable accounting history. Real GST/fee schedules, reconciliation, historical accounting and sole-ledger use NOT CERTIFIED. Unknowns remain unknown.
- **Static debt:** no WP7 backend production changes; the current backend strict errors are missing annotations/untyped calls/Any returns/redundant casts/unused ignores, not proof of financial correctness or a new runtime defect. They weaken assurance on critical sourcing/operations paths and require scoped cleanup, not suppression. Ruff's main.py import-order failure is maintainability debt, not demonstrated startup failure. Existing runtime warnings remain disclosed.
- **Accessibility:** incomplete conditional/offscreen/manual/assistive states remain, no WCAG claim. New layout wrappers preserve keyboard reachability rather than hiding columns.
- **Backup:** PARKED. No encrypted independent restore, permanent data protection or activation result inferred from application tests.

## Remaining work before any WP8 decision

Complete explicitly missing supported local artifact/action journeys and state matrices, particularly discovery failure/retry/source review, full channel-specific draft/authorization states, inventory browser adjustment/recovery, creative artifact/campaign/review flows and source-led deep-link identity hypotheses. Complete required manual accessibility dispositions. Preserve open lower-severity usability and reliability observations; obtain separate authorization for any new financial architecture, high-risk schema or unsupported capability. Rerun dependent journeys after any changes.

## Separate real-business launch blockers

Independent encrypted restore/destination verification; owner-controlled real-data activation and operational recovery; genuine seller registration/API entitlement/credentials/official contracts; separately authorized live read-only provider certification and explicit HUMAN gates before external writes; accounting/reconciliation scope and external retained ledger; security/secrets/backup operations and owner acceptance. None is authorized or certified by WP7.

No permanent/golden database changes, live supplier/marketplace calls, payments, procurement, unrelated Docker deletion, branches, commits or pushes. Single-seller invariant and canonical HUMAN/provenance/idempotency controls preserved. Stop after WP7 for review.

## Exact orphan reconciliation

The owner explicitly approved recovery only for QA token4963364d9460948d. Existing signed instance/role/token authority, original timeout evidence, regular-file fingerprints, exact legacy lock content, no matching owner process, a READ ONLY pg_database absence check and no active matching database operation were verified. The signed record now attests HUMAN_AUTHORIZED_INDEPENDENT_ABSENCE_RECONCILIATION. No database was deleted by reconciliation; the original failed session remains unchanged. This is independent absence evidence, not a retroactive normal-cleanup PASS. All other failed run records and normal/recovery DROP histories remain disclosed in the gate. The focused13 recovery unit tests use mocks/temp files only. The recovery helper refuses every other token, a live database, active operation, changed lock, bad signature, wrong state or missing approval. It does not extend normal deletion authority.

## Changed files

- `apps/web/src/app/ads/ads-optimization.component.ts`
- `apps/web/src/app/ads/wp7-responsive.spec.ts`
- `apps/web/src/app/campaigns/campaigns.css`
- `apps/web/src/app/ai/ai.css`
- `apps/web/src/app/ai/ai-history.component.ts`
- `apps/web/src/app/publishing/jobs.component.ts`
- `apps/api/tests/test_pr_sos_05_financials.py`
- `qa/safety.mjs`
- `qa/seller-browser-session.mjs`
- `qa/wp3-browser-retest.mjs`
- `qa/wp4-browser-retest.mjs`
- `qa/wp4_final_audit.py`
- `qa/wp7-inventory.mjs`
- `qa/wp7-run.mjs`
- `qa/wp7-browser.mjs`
- `qa/wp7-layout.mjs`
- `qa/wp7-quality.mjs`
- `qa/unit/wp7-quality.test.mjs`
- `qa/wp7-static.mjs`
- `qa/wp7-environment.mjs`
- `qa/wp7-final-checks.mjs`
- `qa/wp7-report.mjs`
- `qa/wp7_final_audit.py`
- `qa/wp7_probe.py`
- `qa/wp7_recover.py`
- `qa/wp7-continue.mjs`
- `qa/wp7_orphan_reconcile.py`
- `qa/unit/test_wp7_orphan_reconcile.py`
- `scripts/test-seller-wp7.ps1`

The eight wp7-* certification deliverables in this directory were also created/updated. Unrelated worktree changes were preserved.
