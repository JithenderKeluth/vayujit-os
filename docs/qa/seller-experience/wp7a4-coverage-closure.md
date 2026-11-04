# WP7A-4 — Coverage closure

**WP7A INCOMPLETE. Application certification remains INCOMPLETE.**

Exactly48 original outstanding entries reconciled; L-11 remains its prior scoped closure and is not counted anew. 32 newly closed, 0 failed, 0 blocked, 16 partial, 0 untested, 0 unsupported exclusions. Partial evidence is never PASS. All48 were attempted; required sub-scenarios listed below remain incomplete where applicable.

## Regression evidence

- backend: PASS; Three independently cleaned disposable PostgreSQL runs: a909d1776a7048ef 98 passed; 4a7a4f9553134d95 14 passed; adc229c403da4d8b 11 passed. 123 executions, 111 distinct classname/test-name identities, 0 failures/errors/skips in retained backend-results.xml. Each runner exit_code=0. Commands: scripts/test-seller-wp7a4.ps1 -Action Backend / BackendMarketing / BackendPortfolio. These are adjacent selected regressions, not the entire historical backend suite.
- angular: PASS; 2026-11-02 final npm.cmd run test --workspace=@vayujit/web: 87 files, 413 tests passed, 0 failed. Earlier harness mocks and a parametrized-test TypeScript inference failure were repaired; original assertions retained.
- node_qa: PASS; 2026-11-02 node --test qa/unit/*.test.mjs: 106 passed, 0 failed, 0 skipped; includes 17 WP7A4 gate/safety/rollup/evidence/waiter self-tests.
- python_qa: PASS; 2026-11-02 apps/api/.venv/Scripts/python.exe -m pytest qa/unit -q: 80 passed in 6.25s.
- build: PASS; 2026-11-02 npm.cmd run build --workspace=@vayujit/web: exit 0; production output dist/apps/web; initial bundle 422.71 kB, estimated transfer 109.56 kB. Final source/build/lock hashes captured before the last browser replay in revision-final.json.
- lint: PASS; 2026-11-02 npm.cmd run lint --workspace=@vayujit/web: exit 0, 0 errors, 2 existing OnInit-interface warnings in campaigns/catch-up-dialog.component.ts and reschedule-dialog.component.ts. Historical lint debt is not silently fixed or called clean.
- typescript: PASS; 2026-11-02 node node_modules/typescript/bin/tsc -p apps/web/tsconfig.app.json --noEmit and -p apps/web/tsconfig.spec.json --noEmit: both exit 0.
- mypy: PASS; 2026-11-02 from apps/api: .venv/Scripts/python.exe -m mypy --strict vayujit_api/ai/schemas.py vayujit_api/ai/service.py vayujit_api/ads/marketing.py vayujit_api/intelligence/portfolio_integration.py: Success, no issues in 4 source files. An initial command used a duplicated working-directory path and did not launch; corrected command actually passed. This does not clear historical Ads-router typing debt.
- ruff_black: PASS; 2026-11-02 Ruff and Black --check, explicit apps/api/pyproject.toml configuration: all checks passed, 11 files unchanged. Scope: four changed production Python modules, test_seller_wp7a4.py, wp7a4_fixture.py, wp7a4_final_audit.py, lifecycle/recovery/budget/action-diagnostic tools.
- compile_parser: PASS; 2026-11-02 compileall -q on the same 11 Python files; node --check on all 9 qa/wp7a4*.mjs modules; Windows PowerShell parser on scripts/test-seller-wp7a4.ps1: exit 0. No migration added; fresh fixture runs applied the existing Alembic head. No downgrade certification claimed.
- diff: PASS; 2026-11-02 git -c safe.directory=C:/Users/jithe/Documents/vayujit-os diff --check: exit 0. Existing LF-to-CRLF notices are distinct from whitespace errors. Rechecked after final report generation.

## Database, source and environment integrity

Read-only final audit: PASS; 10 task-owned database identities. Historical report hashes unchanged: true. Protected secret matches: 0; trace CRC/secret checks: 23. Docker preservation status: HISTORICAL_BASELINE_CHANGED; preserve its exact historical runtime timestamp discrepancy, rather than claiming strict historical equality. Detailed proof: tmp/qa-wp7a4-final-audit.json. No permanent/golden database, real provider, public deployment, external publishing, supplier contact, procurement/payment or marketplace mutation was authorized or performed. Backup remains parked; no branch/commit/push.

## Complete original-ID ledger

| Original ID | Route | Outcome | Exact remaining disposition |
|---|---|---|---|
| R-184826c3 | `/intelligence/trends/:contextId` | PARTIAL | Owned context/reload verified; populated observation/source analysis remains unverified. |
| R-8a5edab2 | `/` | PASS | VERIFIED_LOCAL_SCOPE |
| R-7e93fba0 | `/login` | PASS | VERIFIED_LOCAL_SCOPE |
| R-17b7d214 | `/ads/accounts/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-66842e70 | `/ads/campaigns/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-794214d7 | `/campaigns/:id/video/:activityId` | PARTIAL | Exact approved Video binding and reload verified; the activityId route renders an overview rather than an activity-specific detail. |
| R-ec41ffe0 | `/campaigns/:id/video` | PASS | VERIFIED_LOCAL_SCOPE |
| R-8522d9c2 | `/campaigns/:id/activities/new` | PASS | VERIFIED_LOCAL_SCOPE |
| R-f4ba2c21 | `/campaigns/:id/dependencies` | PASS | VERIFIED_LOCAL_SCOPE |
| R-e4940841 | `/campaigns/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-3feda36d | `/social/posts/:id` | PARTIAL | Canonical social draft and persisted identity checked; image/video-specific and stale-review permutations remain. |
| R-55e822d5 | `/marketplaces/overview` | PARTIAL | Overview and reload checked; full configured-channel snapshot requires remaining account fixtures. |
| R-551d2f8c | `/marketplaces/listings/:id/flipkart` | PARTIAL | Exact catalog-linked draft/default-deny reviewed; complete channel readiness/review authorization transitions remain. |
| R-db243c36 | `/marketplaces/listings/:id/meesho` | PARTIAL | Exact catalog-linked draft/default-deny reviewed; complete channel readiness/review authorization transitions remain. |
| R-d6a495d5 | `/marketplaces/listings/:id/amazon` | PARTIAL | Exact catalog-linked draft/default-deny reviewed; complete channel readiness/review authorization transitions remain. |
| R-8f16bd41 | `/ai/images/assets/:outputId` | PASS | VERIFIED_LOCAL_SCOPE |
| R-5e241b88 | `/ai/studio/artifacts/:id/compare` | PASS | VERIFIED_LOCAL_SCOPE |
| R-75d260b7 | `/ai/artifacts/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-2e8db403 | `/settings/publishing/connectors` | PASS | VERIFIED_LOCAL_SCOPE |
| R-756ae8b2 | `/publishing/destinations/shopify` | PASS | VERIFIED_LOCAL_SCOPE |
| R-af04ee8c | `/publishing/destinations/wordpress` | PASS | VERIFIED_LOCAL_SCOPE |
| R-730f1388 | `/media/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-a8d8b217 | `/publishing/destinations/:id/edit` | PASS | VERIFIED_LOCAL_SCOPE |
| R-9b0fb4bc | `/publishing/destinations/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-68adcdc8 | `/publishing/executions/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-2b4d90d2 | `/publishing/schedules/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-30072869 | `/publishing/jobs/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-e309647e | `/operations/workers/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-9dc8a702 | `/workflows/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-541d7261 | `/approvals/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-eb4987ba | `/intelligence/supplier-portfolios/:portfolioId` | PASS | VERIFIED_LOCAL_SCOPE |
| R-8d64a30d | `/**` | PASS | VERIFIED_LOCAL_SCOPE |
| L-09 | `/ai/generate` | PASS | VERIFIED_LOCAL_SCOPE |
| L-10 | `/ai/studio` | PARTIAL | Completed snapshot retained; queued old-context work rejects as stale after a Product change. Provider retry/supersession permutations remain. |
| L-12 | `/ai/images` | PARTIAL | Image regeneration/reload/source approval retained; injected provider failure/recovery still requires exact child controls. |
| L-13 | `/ai/studio/bulk` | PARTIAL | Canonical cancellation/reload exercised; partial success/provider retry combinations remain. |
| L-14 | `/ai/images/bulk` | PASS | VERIFIED_LOCAL_SCOPE |
| L-15 | `/ai/studio/seo` | PARTIAL | Keyword/tag creation and tag reload executed; analysis history/reanalysis/context permutations remain. |
| L-16 | `/campaigns/new` | PARTIAL | Canonical product/approved-content activity binding persisted; full recovery/stale binding permutations remain. |
| L-17 | `/ads/campaigns/:id` | PARTIAL | Persisted fake Ads campaign, explicit HUMAN confirmation and reload checked; creative/stale/expired-authorization permutations remain. |
| L-18 | `/ai/brand-voices` | PASS | VERIFIED_LOCAL_SCOPE |
| L-19 | `/ai/presets` | PASS | VERIFIED_LOCAL_SCOPE |
| L-20 | `/ai/usage` | PASS | VERIFIED_LOCAL_SCOPE |
| L-21 | `/ai/video/bulk` | PARTIAL | Actual local deterministic bulk Video preview, fingerprint, queued child and worker completion executed; cancel/retry/partial and browser reload identity remain. |
| L-22 | `/social/compose` | PARTIAL | Supported composer and persisted text draft exercised; Video composer needs a canonical approved Video output. |
| L-23 | `/ads/marketing` | PARTIAL | Manual persisted plan preview/confirmation/reload exercised; recommendation/version/change permutations remain. |
| L-24 | `/settings/ai/providers` | PASS | VERIFIED_LOCAL_SCOPE |
| L-25 | `/ai/artifacts/:id` | PASS | VERIFIED_LOCAL_SCOPE |

## Reproduction and safe resumption

`powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a4.ps1 -Action Browser`

For exact selected-ID replay set QA_WP7A4_IDS to the comma-separated original IDs before this command; four contexts remain required. Backend: same runner -Action Backend; focused post-budget marketing validation: -Action BackendMarketing. QA: node --test qa/unit/*.test.mjs and apps/api/.venv/Scripts/python.exe -m pytest qa/unit -q. Independent audit: apps/api/.venv/Scripts/python.exe -m qa.wp7a4_final_audit. All new DB runs must use the existing attested protected QA profile and a new signed token; never reuse an absent DB, bypass a guard, or generalize exact recovery approval.

The live checkpoint retains completed IDs, remaining closure IDs and fixture identities. Interrupted attempts and scope gaps are not erased. This work stops at WP7A-4; no WP7B/C/WP8 or application PASS.

## Changed implementation files

- `apps/api/vayujit_api/ai/schemas.py`
- `apps/api/vayujit_api/ai/service.py`
- `apps/api/vayujit_api/ads/marketing.py`
- `apps/api/vayujit_api/intelligence/portfolio_integration.py`
- `apps/api/tests/test_seller_wp7a4.py`
- `packages/shared/src/index.ts`
- `apps/web/src/app/ai/ai-artifact.component.ts`
- `apps/web/src/app/ai/ai.css`
- `apps/web/src/app/ai/ai-video-bulk.component.ts`
- `apps/web/src/app/ai/ai-image-bulk.component.ts`
- `apps/web/src/app/ai/brand-voice-workspace.component.ts`
- `apps/web/src/app/ai/preset-workspace.component.ts`
- `apps/web/src/app/publishing/destination-form.component.ts`
- `apps/web/src/app/publishing/publishing.css`
- `apps/web/src/app/workflows/workflow-timeline.component.ts`
- `apps/web/src/app/marketplaces/flipkart-workspace.component.ts`
- `apps/web/src/app/marketplaces/meesho-workspace.component.ts`
- `apps/web/src/app/ads/marketing-plan.component.ts`
- `apps/web/src/app/intelligence/trend-intelligence-workspace.component.ts`
- `apps/web/src/app/intelligence/supplier-portfolio-workspace.component.ts`

Focused Angular regressions are in ai-wp7a4.spec.ts, ai-wp7a3.spec.ts, ai-image-bulk.component.spec.ts, marketing-plan.component.spec.ts, the existing Flipkart/Meesho workspace specs, and trend-intelligence-workspace.component.spec.ts. QA foundation changes are the wp7a4-* modules, wp7a4_fixture.py, wp7a4_final_audit.py, five wp7a4 unit-test modules and scripts/test-seller-wp7a4.ps1. Shared harness extensions are in safety.mjs, server.mjs, seller-browser-session.mjs, seller-browser-explore.mjs, wp7-run.mjs, fixture_server.py, wp7a_fixture.py, wp7a2_fixture.py, wp7a3_fixture.py and wp4_final_audit.py. Other dirty-worktree edits are pre-existing and are not claimed as this package. No migration or new business authority was introduced.

## Final accessibility and remaining risks

192 latest per-entry/context scans; 0 violation occurrences; 59 incomplete-rule occurrences. Incomplete rule IDs: color-contrast, th-has-data-cells, aria-prohibited-attr, link-in-text-block. Incomplete nodes remain manual-review requirements, not passes.

The 16 partial IDs are required local evidence gaps, not approved exclusions or claims that live authorization prevents their execution. Three documented product gaps (activity-specific Video route, durable bulk-Video controls and complete SEO management UI) are retained separately. Unexecuted local permutations require further bounded work inside this same workstream; test totals do not establish them. The historical Ads502, unattributed PostgreSQL runtime timestamp discrepancy, unrelated Ads-router typing debt, incomplete/manual accessibility checks, financial-history/reconciliation limitations and parked backup certification remain open. Focused changed-module checks passed; they do not certify repository-wide typing or operational live readiness.

## Independent cleanup proof and audit caveat

Overall audit classification: DATABASES_ABSENT_ENVIRONMENT_BASELINE_DRIFT. The audit deliberately exits nonzero for the preserved historical Docker timestamp drift; only its database-absence subcheck is PASS. The original container's identity/image/mount/network structure remains unchanged. This does not establish who caused its old StartedAt/FinishedAt difference. No unrelated resource was restarted or removed.

| Exact task token | Signed lifecycle state | Database independently absent | Guarded recovery recorded |
|---|---|---|---|
| 16866647c1ffa6ee | DROPPED | true | false |
| 30acda7f64c5d746 | DROPPED | true | false |
| 346ac65c280b5d93 | DROPPED | true | false |
| 3d2009ecfa0515bf | DROPPED | true | false |
| 412436d33a219d5f | DROPPED | true | true |
| 4a7a4f9553134d95 | DROPPED | true | false |
| 691dde19ec6337de | DROPPED | true | false |
| a909d1776a7048ef | DROPPED | true | false |
| adc229c403da4d8b | DROPPED | true | false |
| ecbda835383b31a3 | DROPPED | true | false |
