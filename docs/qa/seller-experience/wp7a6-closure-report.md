# WP7A-6 closure report

**WP7A — INCOMPLETE.** Execution and two bounded corrections were completed, but the requested seven-entry acceptance closure was **not achieved**. No new follow-up package was started.

## Original coverage reconciliation

Original denominator **48**; inherited closed **41**; newly closed **0**; remaining **7 PARTIAL**; untested original entries **0**. The seven entries were attempted in all four required browser contexts, but many required sub-scenarios remain unexecuted. Do not confuse 28 successful partial executions with 28 complete acceptance passes.

| Stable ID | Route | Disposition | Evidence boundary |
|---|---|---|---|
| R-3feda36d | /social/posts/:id | PARTIAL | Image-only creation, exact media/content/product, preview/edit stale fingerprint and reload verified; HUMAN review and concurrent-action matrix remain incomplete. No publication. |
| R-55e822d5 | /marketplaces/overview | PARTIAL | Sandbox configuration persisted; real connection is NOT certified. Expired/revoked and exact account projections remain unverified. |
| R-551d2f8c | /marketplaces/listings/:id/flipkart | PARTIAL | flipkart: persisted draft and missing-readiness/default-deny checked; readiness correction and complete authorization matrix not yet verified. |
| R-db243c36 | /marketplaces/listings/:id/meesho | PARTIAL | meesho: persisted draft and missing-readiness/default-deny checked; readiness correction and complete authorization matrix not yet verified. |
| R-d6a495d5 | /marketplaces/listings/:id/amazon | PARTIAL | amazon: persisted draft and missing-readiness/default-deny checked; readiness correction and complete authorization matrix not yet verified. |
| L-16 | /campaigns/new | PARTIAL | Exact draft/activity persisted and reloaded; dependency/artifact-version stale fingerprint matrix remains unverified. |
| L-17 | /ads/campaigns/:id | PARTIAL | Local fake account/wizard exercised without submission; complete creative/authorization matrix remains unverified. Historical 502 not classified as resolved. |

## Actual tests

- Latest Node QA: 120 passed; includes 8 new A6 safety/gate tests.
- Python QA: 156 passed.
- Angular: 428 passed, including 2 added Social regressions.
- Backend full adjacent run bed1d274ee1d45bb: **70 passed, 1 failed**, 0 errors/skips. That failure was the initial non-JSON-safe rejection correction, not suppressed.
- Post-fix focused 5740623d2b3c4fc8: **3 passed**, 0 failures/errors/skips. Latest-per-stable-test aggregation: **72 unique tests, 1 latest failures**; NOT one all-green full run. [All run counts](../../../tmp/qa-wp7a6/backend-summary.json). Earlier invalid-payload failures remain preserved.
- Final browser befaa935c05fac4a: **0 fully PASS / 28 PARTIAL / 0 FAIL / 0 BLOCKED** (7 IDs × 4 contexts). Persisted row snapshots for six entry types; Ads wizard lacks campaign/creative persisted proof.
- Axe: **28 scans, 0 violations, 14 incomplete rule occurrences**; incomplete/manual checks are not compliance PASS.
- Production build, scoped ESLint, app/spec TypeScript, focused strict mypy (Amazon router), Ruff, Black, compileall, parser and git diff --check: latest fixed command set PASS. [Exact commands/results](../../../tmp/qa-wp7a6/quality.json). Historical repository-wide debt is not recertified; no ignores or thresholds weakened.

## Isolation, preservation and outstanding blocker

Dedicated attested QA instance only: 127.0.0.1:55432, vayujit_qa_admin, allowed vayujit_qa<16hex>_test, signed token/marker/OID lifecycle. HUMAN-approved recovery completed on 4 November 2026 (Asia/Calcutta). The exact QA database `vayujit_qa0e63cd34fede26e1_test` (OID 13516456) was removed using the existing non-FORCE `resume_drop` after fresh instance/container, signed lifecycle, owner/OID, zero-session and no-active-QA-process checks. [Recovery evidence](../../../tmp/qa-wp7a6/recovery-0e63cd34fede26e1.json); previous failure reports are preserved in `tmp\qa-wp7a6\before-approved-recovery-20261104T015051Z`. A fresh process independently confirms all 9 run databases absent and signed DROPPED. The historical session-final CLEANUP_BLOCKED record was retained unchanged. No other database, Docker resource, or normal app process was modified by recovery. Final run itself CLEANED. Independent process [audit](../../../tmp/qa-wp7a6-final-audit.json) records exact states, trace CRCs, zero protected-secret matches and unchanged historical baseline. It deliberately returns nonzero.

Historical application-PostgreSQL StartedAt/FinishedAt drift remains UNATTRIBUTED; structural container/network/volume identity unchanged. No container restart/recreation to conceal it. Earlier database-recovery evidence SHA256s unchanged. No permanent/golden database writes, .env edits, new migrations, live calls, supplier actions, commercial writes, branches, commits or pushes. PC-first certification parked.

Normal API/frontend were paused with explicit permission, then restored using captured process identity. Recovery state: true; API health HTTP 200; frontend HTTP 200. [Safe restoration evidence](../../../tmp/qa-wp7a6/app-health.json). External mutation stop retained; source health probes were read-only.

## Decisions and limits

1. Exact QA tombstone recovery approved and independently verified; no cleanup approval remains pending. Seven functional entries are still PARTIAL. This cleanup-only operation did not rerun or close those journeys.
2. The remaining local HUMAN-review, expiry/revocation, failure/recovery, dependency/version and Ads creative cases still need execution in this same acceptance contract. They are not externally blocked merely because live integrations are unavailable. Do not narrow the denominator or announce PASS.
3. Audit/approve the smallest existing-authority catalog-to-Amazon draft preparation repair before broadening into new workflow functionality; never clear readiness by synthetic claims of real authorization.

Real connections, publication/spend, complete WCAG, immutable accounting, independent backup and launch readiness remain uncertified. Stop here for review; no automatic WP7A-7/WP7B/C/WP8.

## Cleanup-only follow-up — 4 November 2026

Executed under the owner's exact-database recovery approval. Existing lifecycle/recovery guard unit tests: **38 passed** (`apps/api/.venv/Scripts/python.exe -m pytest qa/unit/test_postgres_instance.py qa/unit/test_wp7a2_recovery.py -q`). Certification gate self-tests: **8 passed** (`node --test qa/unit/wp7a6-contract.test.mjs`). Both changed JavaScript helpers passed `node --check`. No application Python, Angular, schema, database guard or approval authority changed in this follow-up; no application process was paused or restarted. Historical large-suite counts above were not rerun for cleanup. The fresh-process audit's nonzero exit remains attributable to the retained historical Docker timestamp observation, not to pending QA database cleanup.
