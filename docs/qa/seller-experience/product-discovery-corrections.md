# Product discovery category planning and feedback corrections

Date: 2026-10-29. Scope: the reported home-and-kitchen-organization discovery failure.

Status: **IMPLEMENTED / FOCUSED LOCAL VALIDATION PASSED. Live acquisition not executed or certified.**

## Confirmed causes and bounded corrections

1. `discover_local_product_candidates` admitted a hypothesis if **any** word of its category/subcategory overlapped the requested category. The supplied category produced a lunch container, wardrobe organizer, and cable case, in catalog order. Matching now requires every informative category qualifier, excluding conjunctions and category-label words. For this goal only the wardrobe-organization seed qualifies. No category/product/domain is special-cased. Unsupported taxonomies retain the existing category-led research scope; seeds are not live product evidence.
2. The nested search loop consumed the default three attempts on the first hypothesis. Query planning now searches every eligible hypothesis before refinements. Existing maximum attempts, candidate targets, cache reuse, approval pauses, quota stops, safe fetches, and network controls remain authoritative. No forced refresh or increased search budget was introduced.
3. The bounded JSON-LD projection discarded the observed `category` field before validation. It now preserves a nonempty bounded string category from the fetched Product metadata. Category matching requires all informative requested qualifiers across observed identity/description/category/URL fields; a hypothesis cannot supply missing evidence. Synonyms and unknown taxonomies are not guessed, so some genuinely relevant pages may still require better evidence.
4. Fetch records could remain `eligible: true` after category rejection. New records now carry the final failure and reason code. The UI also joins historical `rejected_results` to their exact fetched URL without mutating saved evidence. Fetch success, final eligibility, and rejection reasons are displayed separately.
5. Cached-plan exhaustion now explains that no new provider search occurred and that retry may reuse recent searches. Historical read projections gain this guidance without rewriting history. Recorded source approvals no longer instruct users to click a nonexistent Continue control. The ordinary retry is labelled **Retry product discovery**; actual source-review boundaries retain **Continue product discovery**.
6. The outcomes table has an accessible name, keyboard-focusable overflow region, visible focus indication, fixed readable columns, and guidance outside the clipping area. Mobile scrolling does not expand the document width.

## Actual validation

| Check | Final result |
| --- | --- |
| Offline discovery, boundaries, GP-7.5/7.6 tests | 67 passed, 0 failed (22 new planning cases) |
| Persisted source-approval replay and Business Agent orchestration | 15 passed, 0 failed |
| Full Angular suite | 294 passed, 73 files, 0 failed |
| Synthetic Chrome rendering/interaction at 1440px and 390px | 26 checks passed, 0 failed |
| QA infrastructure Python / Node self-tests | 54 / 51 passed |
| Strict mypy, three changed production Python modules | PASS, `--follow-imports=silent`; imported-module debt not certified |
| Focused Ruff, Black (API configuration), ESLint, Prettier | PASS |
| Python compileall, JavaScript syntax, PowerShell parser | PASS; PowerShell 0 errors |
| Production build | PASS; existing initial-bundle warning: 518.03 kB versus 500 kB |
| `git diff --check` | PASS |

Chrome uses the real production frontend build, a fresh isolated context per viewport, intercepted synthetic API responses, no real authentication session, no backend connection, and denied nonlocal requests. It verifies cached feedback, final rejection visibility, keyboard disclosure/focus/reverse navigation, no page overflow, original run ID on one intercepted retry, deep-link reload, and disabled approval until HUMAN confirmations. **These browser checks do not certify real login, database persistence, or live provider connectivity.** Persisted API tests independently exercise canonical authenticated authorities in disposable PostgreSQL with mocked provider/fetch transports and process-level egress denial.

Browser evidence: `tmp/qa-discovery-feedback/2026-10-29T02-44-38.612Z/report.json`, `cached-rejection-{1440,390}.png`, `exposed-table-{1440,390}.png`, `approval-required-{1440,390}.png`, and both viewport traces. No unexpected API requests or uncaught page errors were observed.

Axe full-panel scans had zero violations. The mobile full-panel scan retains a `color-contrast` incomplete result for horizontally clipped cells. Every actual table header/data cell was scrolled into its container's visible area and independently scanned with axe contrast: 8 cells per viewport, all exposed, all contrast passes, zero targeted violations/incomplete results. No axe rules were suppressed. This is scoped automated evidence, not complete WCAG compliance.

## Failed attempts retained and explained

- Two new positive category tests initially failed because observed JSON-LD category was discarded. The production projection was corrected; the assertions and fetched fixtures were not weakened. Final offline suite: 67 passed.
- The first integration wrapper attempt stopped on missing `QA_ORIGIN` **before database creation** (`be748caa4a384c7d`). The wrapper now sets the same QA-only origin/profile as the existing WP2 wrapper.
- The first persisted run (`585222551ec548a0`) had 13 passed / 2 failed because these existing mocked-provider tests inherited the QA-wide search kill switch. Each affected test now explicitly configures its fake search provider, while socket egress denial and production safeguards remain unchanged. No production switch was relaxed. Final run `76c89e3daf3c48cb`: 15 passed.
- An initial browser pass exposed visually squeezed mobile columns despite passing structural assertions. The table layout was corrected. An intermediate scan then retained offscreen contrast incompletes; the final harness preserves that full scan and tests every exposed cell instead of hiding nodes or claiming the initial scan was complete.
- A root-level Black invocation including QA files selected default formatting settings. Rechecking all six Python files with `--config apps/api/pyproject.toml` passed without changes.

## Disposable isolation and cleanup

Only the previously approved QA instance was used: container `vayujit-qa-postgres`, instance `389b97d2-a4cd-4d9b-972e-6bb2bf5785eb`, endpoint `127.0.0.1:55432`, role `vayujit_qa_admin`. Both created databases have signed `DROPPED` lifecycle state and independently verified catalog absence:

- `vayujit_qa585222551ec548a0_test` — failed test attempt, normal marker-verified cleanup PASS.
- `vayujit_qa76c89e3daf3c48cb_test` — final passing test attempt, normal marker-verified cleanup PASS.

The preflight token's database was also verified absent. Full existing migrations ran on the disposable databases; no new migration was needed. Permanent/golden business databases were not targeted. No live supplier/marketplace calls, source approvals in the real installation, supplier contact, commercial actions, backup-certification work, commits, pushes, or branches were performed. Existing unrelated worktree changes were preserved.

## Changed files in this correction

- `apps/api/vayujit_api/intelligence/product_discovery.py`
- `apps/api/vayujit_api/intelligence/product_research.py`
- `apps/api/vayujit_api/intelligence/business_agent_service.py` (bounded failure message only; prior changes preserved)
- `apps/api/tests/test_product_discovery_planning.py` (new)
- `apps/api/tests/test_product_source_review_integration.py` (explicit mocked-provider configuration)
- `apps/web/src/app/intelligence/product-discovery-review.component.ts`
- `apps/web/src/app/intelligence/product-discovery-review.component.spec.ts`
- `apps/web/src/app/intelligence/business-agent-workspace.component.ts` (retry label only; prior changes preserved)
- `apps/web/src/app/intelligence/business-agent-workspace.component.spec.ts`
- `qa/fixture_server.py` (allowlisted existing source-review test only; prior changes preserved)
- `qa/discovery-feedback-browser.mjs` (new, synthetic rendering regression)
- `scripts/test-product-discovery.ps1` (new, safe reusable test invocation)
- This report.

## Windows reproduction

From the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/test-product-discovery.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/test-product-discovery.ps1 -Integration
npm.cmd run test --workspace @vayujit/web
npm.cmd run build --workspace @vayujit/web
node.exe qa/discovery-feedback-browser.mjs
```

The integration command requires the already approved, attested QA instance and private profile; it must stop rather than select another database. The PowerShell flag is confined to the child invocation, not a machine execution-policy change.

To use the correction in the existing development installation, restart the API and web dev processes using `npm.cmd run dev:api` and `npm.cmd run dev:web` in their respective terminals, refresh the saved goal, and choose **Retry product discovery** once. **No `.env` changes or database migration are required for this correction.** Do not run a second API/web process over occupied ports. The user-triggered retry follows the normal configured read-only provider and source-approval controls and may consume its bounded search allowance. No successful live product result is promised. Existing historical opportunities and evidence were not rewritten.

Remaining warnings: existing FastAPI/Pydantic deprecations, duplicate external-fetch preflight OpenAPI operation ID, pytest plugin rewrite warning, and initial bundle-size warning. These were not repaired or certified repository-wide in this bounded correction. Live acquisition, provider quota/credentials, unsupported taxonomy quality, and whole-application certification remain outside demonstrated coverage.
