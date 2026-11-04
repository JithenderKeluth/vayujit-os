# WP7A-3 — Coverage closure decision

Date: 2026-10-31. **WP7A INCOMPLETE. Application certification remains INCOMPLETE.**

Final report review resumed on 2026-11-01: report/gate consistency and `git diff --check` passed; the independent read-only cleanup/evidence audit was repeated. The test-suite counts below are the retained 2026-10-31 execution results, not a claim that every suite was rerun on 2026-11-01. No new database or fixture was created for this final review.

Nine evidenced application defects were corrected, and the final nine scoped subjourneys pass in all four real-browser contexts. The complete requested matrix is not closed. This report does not convert route renders, backend-only assertions or missing live integrations into successful seller workflows.

## Scope reconciliation

The original report/matrix/defect register and earlier WP7A/A2 evidence were inspected and preserved. All156 original route rows are enumerated in [the traceable addendum](wp7-journey-coverage-matrix-wp7a3-addendum.md). There are32 literal original NOT_TESTED route leaves and124 bounded route-review records. Existing B/G/H follow-ups are inherited only at their earlier demonstrated scope. Original family L still has other supported actions unexecuted.

Actual exposed routes/components/APIs identify17 creative action groups L-09–L-25, not merely the nine initially automated groups. The prioritized closure ledger therefore contains49 entries (32 route leaves plus17 action groups). **Before49; after48 open. Exact bounded full closure: L-11.** Fifteen entries have partial additional evidence;33 remain NOT_TESTED. No NOT_SUPPORTED exclusions were invented. These overlapping route/action dimensions are not a unique-screen count or a comprehensive count of every possible application operation.

[Machine-readable requirements](wp7a3-required-coverage.json) record stable IDs, routes, capability, why, required evidence, fixtures/dependencies, safe-provider limits, closure criteria, observed evidence and remaining work. The addendum retains all124 inherited route-review caveats rather than declaring them full functional passes. The gate requires the exact49 audited identities, all mandatory checks, cleanup and no open blockers; its regression tests reject narrowed/empty/partial scope.

## Actual final results

| Check | Result | Evidence / qualification |
| --- | --- | --- |
| Persisted backend and adjacent regressions | **94 passed, 0 failed/errors/skipped** | `tmp/qa-wp7a3-backend/431e5e4d04a84f79/backend-results.xml`;373.037s. Nine new regression cases. |
| Authenticated Chrome/Edge1440/390 | **36 passed, 0 failed/skipped** | `tmp/qa-seller-browser/95a8b3bab0282fa7/wp7a3-browser.json`; nine scoped groups/context. |
| Full Angular suite | **400 passed**,86 test files | Thirteen added tests; includes exact revision, source version, retry-job identities, private image review and persisted bulk operation. |
| Node QA self-tests | **89 passed** | Eight added safety/gate/report tests; assertions preserved. |
| Python QA self-tests | **80 passed** | Existing guard, lifecycle, lineage and financial oracle tests. |
| Axe | **36 scans, 0 violations;18 incomplete occurrences** | Serious/incomplete ARIA/contrast nodes remain manual review, not WCAG PASS. |
| Production build | PASS | Real Angular production build; no new bundle limit was raised. |
| Angular lint | PASS,2 existing warnings | Existing lifecycle-interface warnings in catch-up/reschedule dialogs; no new lint errors. |
| TypeScript app and test checks | PASS | `tsconfig.app.json`, `tsconfig.spec.json`, no emit. |
| Focused strict mypy | PASS,0 errors in4 changed backend modules | provider, image_service, studio_router, activity_service; no ignores/check weakening. |
| Focused Ruff / Black | PASS | Black explicitly uses API pyproject config for mixed QA/API paths. |
| compileall / JS / PowerShell parsing | PASS | Changed Python modules, harness JS, new PS runner. |
| Migrations | PASS within exercised scope | Fresh disposable upgrade to existing Alembic head for each run. No migration/schema change introduced. No downgrade or production migration claimed. |
| `git diff --check` | PASS | Existing unrelated worktree changes preserved. No commit/push/branch. |
| Independent cleanup | **12/12 task databases absent** | Signed DROPPED records rechecked in a fresh read-only process; no recovery exception used. |
| Evidence integrity | PASS |18 traces CRC checked;265 JSON/Markdown/XML evidence/document files and all18 trace archives scanned,0 protected-secret matches;12 historical reports unchanged. |

Repeated earlier runs are retained, not summed into unique coverage. A prior92-test pass preceded the new concurrency/campaign cases. Failed intermediate tests and harness corrections are described in the browser/defect reports; no initial green assertion set is passed off as proof of missing states.

## Fixes and authoritative behavior

See [root causes and exact changed files](wp7a3-defect-resolution.md). Repairs cover deterministic keyword contract validation; persisted Studio status/recovery; revision navigation/source-version pinning; image preview/UNKNOWN facts/regeneration identity; production no-autoflush bulk planning; bulk URL/reload/status; concurrent human-edit serialization; image decision summary/detail contract; and campaign duplicate-sequence conflict handling.

No provider authentication, approval, publication, financial or ownership authority was duplicated. New image/content revisions do not inherit approval. Backend conflicts remain authoritative. Local deterministic outputs are synthetic fixtures, not real-provider evidence. The application single-owner constraint remains unchanged.

## Outstanding gates — not external authorization excuses

- All32 original route-leaf entries remain open at full-contract scope, including parameterized publishing/workflow/approval/worker/portfolio, creative details and channel listing routes. Seven gained bounded action evidence but are not fully certified.
- L-09/L-10/L-12–L-17 retain broader regeneration/history/changed-context/image-failure/bulk-cancel-retry/SEO-keyword-tag/campaign-binding/creative-authorization permutations beyond the passing subjourneys.
- L-18–L-25 require populated voice/preset/usage/bulk-video/social-draft/marketing/provider-configuration/localization browser evidence.
- Eighteen axe incomplete occurrences, obscured mobile table nodes and complete keyboard/modal permutations need further review. No accessibility rule was suppressed.
- Historical SE-WP7-COVERAGE-001/P1 therefore remains open. Historical Ads502 remains **UNREPRODUCED / CAUSE UNCLASSIFIED**.
- Read-only Docker inspection preserves the original timestamp drift warning. Initiator remains unattributed; no row-level data-integrity conclusion is justified. See [infrastructure review](wp7a3-infrastructure-review.md).

The remaining safe local tests do not require a new live-provider approval. Real connectivity/credentials/publication would require separate authorization and are not treated as passing or silently excluded. This package stops without starting WP7B, WP7C or WP8.

## Historical static debt and production implications

All four changed backend modules pass focused strict mypy. The Studio router baseline before its row-lock change also had0 errors. Untouched Ads-router diagnostics remain in earlier evidence:63 in the historical focused CLI check;78/78 with0 additions in its separate nonincremental comparison. Those entry points are not summed or presented as current WP7A3 failures. Repository-wide typing was not recertified. Dynamic/nullable behavior outside the exercised paths remains a production risk and is one reason not to promote these local results into a release decision.

## Reproduction and artifacts

[Browser evidence and commands](wp7a3-browser-evidence.md), [defect resolution](wp7a3-defect-resolution.md), [infrastructure investigation](wp7a3-infrastructure-review.md), [computed gate](wp7a3-gate.json).

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a3.ps1 -Action Backend
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a3.ps1 -Action Browser
node --test qa/unit/*.test.mjs
apps/api/.venv/Scripts/python.exe -m pytest qa/unit -q
npm.cmd test --workspace @vayujit/web -- --watch=false
npm.cmd run lint --workspace @vayujit/web
npm.cmd run build --workspace @vayujit/web
apps/api/.venv/Scripts/python.exe -m qa.wp7a3_final_audit
```

The last audit intentionally exits1 for the historical Docker runtime-baseline drift while separately recording database-absence PASS. Do not restart or recreate an unrelated container to force that audit green. No production/golden database, real-provider operation, backup certification, supplier action or external marketplace write was performed.
