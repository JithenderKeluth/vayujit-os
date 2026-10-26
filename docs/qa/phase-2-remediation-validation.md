# Phase 2 remediation and independent retesting

25 October 2026. **Known Phase 1/Phase 2 remediation gates passed in bounded local
synthetic testing. Comprehensive application/release certification is NOT established.**

This work implements the owner's explicit remediation authorization. It does not
weaken the original financial oracle, HUMAN controls, authentication, axe rules or
contrast thresholds. No actual supplier, marketplace or financial transaction ran.

## Final results

| Execution | Actual result | Qualification |
| --- | --- | --- |
| Phase 2 persisted HTTP/API | 22 passed, 0 failed/errors/skipped | 11 scenarios in each of two fresh installations, with stronger lineage and concurrent replay assertions |
| Phase 2 Chrome | 8 passed, 0 failed/skipped | Four journeys at 1440x1000 and 390x844; actual persisted owner/supplier/product context |
| Phase 1 Chrome smoke retest | 8 passed, 0 failed/skipped | Owner setup, catalog, error recovery, protected routes, goal/plan; original report preserved |
| QA self-tests | 39 passed | 16 Node tests and 23 Python tests, including eight new canonical lineage cases |
| Existing Angular suite | 242 passed, 66 files | Includes two new semantic/keyboard regressions; original 240 retained |
| Adjacent existing backend matrix | 11 passed | PR-5B landed cost, PR-5C unit economics, PR-6A readiness, PR-6C decision workflow |
| Affected backend rerun after final lineage changes | 4 passed | PR-5B/5C repeated; these are not four additional unique tests |
| Real Chrome axe | 24 state scans, 0 recorded violations | 12 Phase 1 plus 12 Phase 2; incomplete/manual-review items remain in evidence, not relabelled passes |
| Production build | PASS | Existing 514.48 kB initial-bundle warning against 500 kB; budget unchanged |
| Angular lint / TypeScript no-emit | PASS | Two existing OnInit-interface warnings in unrelated campaign dialogs |
| Focused strict mypy | PASS | Four changed backend services and four QA runtime/oracle modules; not whole-repository typing certification |
| Ruff / Black / compileall / Prettier | PASS | Changed backend services and QA; frontend formatting checked separately |
| git diff --check | PASS | Existing LF/CRLF notices are not whitespace errors |
| Disposable cleanup | PASS | Final browser and backend runs verified exact marker/token and database absence; child exits 0 |

Counts are final executions, not the sum of retries. Read timestamps, tokens,
individual outcomes, screenshots and network evidence in:

- [Phase 1 retest JSON](phase-1-retest-report.json)
- [Phase 2 report](phase-2-report.md) and [JSON](phase-2-report.json)
- [Finding-by-finding resolution ledger](remediation-retest.json)
- [Current open backlog](defect-backlog.json)
- [Executed coverage matrix](coverage-matrix.md)

The adjacent backend JUnit and cleanup proofs are:
`tmp/qa-agent/e97c5e76c4b34191/{backend-results.xml,cleanup.json}` (11 tests),
`tmp/qa-agent/7fcd937d4f6f4cbb/{backend-results.xml,cleanup.json}` (4-test rerun).
Warnings include existing FastAPI startup deprecations, pytest's already-imported
anyio notice and duplicate OpenAPI operation-ID registration. No warning was
disabled to obtain success. The operation-ID warning remains API-contract tooling
debt; actual affected routes and authorization were exercised successfully.

## A. Financial lineage: root cause and bounded fix

The canonical chain already persists:

`CommercialReadinessSnapshot -> EconomicCalculation -> ProductOpportunityUnitEconomics`.

`EconomicCalculation.commercial_readiness_snapshot_id` identifies its immutable
acquisition inputs. The defect was independently selecting **latest readiness**
and an **older requested landed calculation** without validating their relationship.
That could produce a new READY unit result after the supplier-price assumption changed.

The fix reuses PR-5B's known-before-assumed input precedence. Semantic comparison
includes owner/opportunity/assessment, supplier and scenario, supplier unit price,
currencies, freight, origin/destination, MOQ, unit/price basis, provenance, trust,
freshness, marker and source references. Decimal spelling and record ordering are
normalized; a new snapshot ID or changed explanation alone does not make equal
inputs stale. Missing/nonfinite amounts, unresolved contradictions, stale/expired
evidence and missing original lineage fail closed. Unknown optional costs remain
excluded and disclosed, not zero.

On material change:

- A new unit calculation returns BLOCKED with a specific acquisition-input code.
- The current GET projection of an old unit result becomes STALE/non-calculable,
  with original/current readiness IDs and an explicit recalculation instruction.
- Landed-cost GET retains the historical breakdown but does not present it as
  current calculable readiness.
- PR-6A decision readiness adds an `ECONOMIC_INPUTS_STALE` blocker. Neither capital
  fit nor positive historical contribution is used as current progression support.
- The UI labels historical landed cost and shows a stale/input-review message;
  current contribution figures are not displayed as calculable until refreshed.

No historical row is rewritten. History still contains the original READY result
and original amounts, with its original input lineage. A supported recalculation
at the new acquisition assumption produces a new result. No migration, second
calculation authority, invented quote, FX rate, tax schedule or supplier evidence
was introduced. Freshness is evaluated against persisted canonical evidence state;
this is not live supplier verification or automatic provider polling.

Regressions demonstrate price 100 -> 200 blocks reuse, old records stay unchanged,
recalculation restores cost 200, and a later change to 300 remains stale after a
browser reload. Equivalent assumptions `100.1250` / `2500.0` remain calculable.
Missing inputs, unknown tax, currency mismatch, negative/zero contribution and
capital shortfall retain their original deterministic assertions.

## B. HUMAN replay: root cause and bounded fix

The first decision inherited its supplier ID from the recommendation. On replay,
the old code compared that stored ID against the caller's omitted/default None,
and incorrectly returned 409.

The existing owner-scoped recommendation now resolves the supplier before replay
comparison. Identity still checks opportunity, target, action, resolved supplier,
explicit goal/synthesis and rationale. Explicit supplier mismatch is not treated
as a wildcard. A PostgreSQL transaction advisory lock on owner/key serializes
competing requests; the unique constraint remains the durable authority. The
IntegrityError recovery path also checks identity rather than blindly returning
a competing record. HUMAN-only provenance, owner filtering, stale review checks
for new actions and ineligible-PROCEED rejection remain intact.

Evidence includes:

- Identical direct and journey replays return the same HUMAN record.
- Eight concurrent direct submissions create one decision, with the canonical
  direct endpoint's 201 response.
- Four concurrent **supplier-scoped journey** replays return the existing record
  with HTTP 200 and history still containing one decision.
- Two competing rationales using one key yield one 201 and one 409.
- Changed action/reason/supplier and conflicting journey requests retain 409.
- Unauthenticated access remains 401; AI provenance remains rejected; existing
  owner-scope negative tests pass. No second database owner or tenancy model is added.

## C. Accessibility fixes and actual verification

The shared stepper applied opacity 0.72 to still-actionable links, reducing small
status text to the measured 3.52:1. Removing ancestor opacity restores the existing
theme's readable ink; a dashed border distinguishes blocked stages without changing
navigation authority or disabling links artificially.

The authenticated shell keeps its single main landmark. The four affected routed
workspaces use named sections, and the next-best-action card is a named task region
rather than a complementary landmark nested inside main. Economics scroll regions
are keyboard focusable, named and visibly outlined. The product loading/error
state retains a level-one heading. Further review corrected named generic control
groups, the active-goal description-list grouping, and the missing supplier
heading ID used by aria-labelledby.

Actual axe scans use the existing engine and unchanged thresholds. No rule,
element, viewport or violation was excluded. New detailed incomplete-check targets
and remediation text are retained for human follow-up. Keyboard evidence includes
Tab/Shift+Tab, Enter cancellation, Space submission, scroll-region focus and arrow
key use. Original loading/error/retry/logout/deep-link checks are preserved.

Zero recorded violations is **not** full WCAG conformance. Offscreen/overlapping
content, assistive technology, all modal focus traps and untested widths still
require manual and broader testing. Any axe incomplete item is a review task, not
a confirmed violation and not an automatic PASS.

The final runs retained four serious-impact `color-contrast` incomplete rule/state
entries, all on mobile: due diligence (6 affected nodes), current economics
(37), stale economics (27), and HUMAN decision (37). Axe could not determine
backgrounds for partially obscured table captions/cells in scroll regions.
These counts repeat some elements across states; they are not 107 distinct
confirmed defects. Exact selectors and remediation text remain in the four axe
JSON artifacts linked from the Phase 2 report. This manual-review scope remains
open; desktop and Phase 1 scans had no incomplete entries in the final runs.

## D. Long economics page: focused assessment, not a redesign

This remains an open P2 usability recommendation. The populated fixtures produce
over 16,000px desktop and 43,000px mobile pages. No evidence or approval was removed
merely to shorten the page. Proposed follow-up:

1. A concise seller summary: current scenario, known versus assumed costs, unknown
   costs, capital fit, blockers and one safe next action.
2. In-page links to economics, decision and source evidence, with accessible focus
   targets; keep immutable IDs and provenance available.
3. Group repeated reason codes and progressively disclose technical payloads.
   Keep material contradictions and approval prerequisites visible.
4. Display a clearly labelled percentage alongside the underlying margin fraction;
   never relabel modeled contribution as net profit.
5. Keep HUMAN review controls near their evidence summary. Do not bypass review,
   hide unknowns or introduce automatic supplier rankings.

## E. Independent retest and preservation of original evidence

The original Phase 1 JSON/Markdown remain unchanged. The original Phase 2 report
is archived under `docs/qa/history/` with SHA256 companions before new reports are
generated. Current resolution records retain each original finding verbatim and
link it to independently executed browser/API evidence.

The comparison records **58 resolved finding occurrences**, not 58 distinct root
causes. Six recommendation occurrences remain open across four usability topics:
USD default (desktop/mobile), dual active navigation treatment, planned-goal mode
clarity, and long economics pages (desktop/mobile). Their priorities remain P2/P3.
No original recommendation is silently closed because a functional test passes.

The first remediation attempt exposed a new harness assertion expecting direct
decision HTTP 200 instead of the API's existing 201 contract. Only that new
assertion was corrected; original assertions were not relaxed. One loaded
intermediate run reported an owned-process shutdown timeout after verifying its
database absent. Its gate correctly stayed INCOMPLETE. Final runs have child exit
0 and verified cleanup; no timeout or cleanup safeguard was loosened.

This is independent **test execution using fresh processes and persisted data**,
not an assertion of third-party audit or complete platform certification.

## Changed files and architecture impact

Backend:

- `landed_cost_service.py`: semantic acquisition-state comparison and current versus
  historical landed-cost posture, reusing existing persisted snapshots.
- `product_opportunity_unit_economics_service.py`: fail-closed lineage gate and
  read-time stale projection without rewriting history.
- `decision_readiness_service.py`: authoritative stale-input decision blocker.
- `decision_recommendation_service.py`: resolved-supplier replay identity and
  owner/key concurrency protection, with mismatch validation on recovery.

Frontend:

- Commerce journey stepper, next action and summary components.
- Business Agent, supplier intelligence, DD and economics workspaces.
- Product detail loading/error heading; two focused component spec additions.
- Existing typed JSON views gain optional freshness metadata. Affected templates
  were also normalized by Prettier; no seller workflow redesign is hidden in formatting.

QA/reporting:

- Stronger persisted Phase 2 lineage, missing-input, concurrency and reload checks.
- Full axe rule output plus actionable incomplete-check targets in both smoke suites.
- Eight canonical lineage unit cases; report archive and evidence-based comparison.
- `fixture_server.py --pytest` runs only four allowlisted adjacent test modules in
  its own fresh guarded database, with the same network denial and finally cleanup.
- Phase 1 `--retest` writes separate artifacts, preserving the original report.
- Coverage, current backlog, reviewed findings and this validation are updated.

No schema, migration, ownership constraint or backend business authority is replaced.
`ck_users_single_owner` remains unchanged. Pre-existing unrelated worktree changes
were preserved. No commit, push or new branch was created.

### Remediation file inventory

Paths below identify this work, not every pre-existing dirty file in the repository.

| Area | Paths |
| --- | --- |
| Financial/replay services | `apps/api/vayujit_api/intelligence/landed_cost_service.py`, `product_opportunity_unit_economics_service.py`, `decision_readiness_service.py`, `decision_recommendation_service.py` (all in the same directory) |
| Shared journey semantics | `apps/web/src/app/commerce-journey-stepper.component.ts`, `commerce-journey-summary.component.ts`, `commerce-next-action.component.ts` |
| Angular regressions | `apps/web/src/app/commerce-journey-stepper.component.spec.ts`, `commerce-next-action.component.spec.ts` |
| Intelligence workspaces/types | `apps/web/src/app/intelligence/business-agent-workspace.component.ts`, `cross-marketplace-supplier.component.ts`, `supplier-due-diligence.component.ts`, `sourcing-economics-workspace.component.ts`, `intelligence.service.ts` |
| Product state heading | `apps/web/src/app/products/product-details.component.ts` |
| Persisted/API/browser regressions | `qa/phase2_api.py`, `qa/tests/phase2.spec.mjs`, `qa/tests/smoke.spec.mjs`, `qa/fixture_server.py`, `qa/unit/test_lineage.py`, `qa/unit/phase2.test.mjs` |
| Reports and preservation | `qa/run.mjs`, `qa/report.mjs`, `qa/phase2-report.mjs`, `qa/archive-reports.mjs`, `qa/retest-remediation.mjs` |
| Documentation/generated evidence | `docs/qa/architecture.md`, `phase-2-validation.md`, `phase-2-remediation-validation.md`, `phase-1-retest-report.{json,md}`, `phase-2-report.{json,md}`, `phase-2-coverage.json`, `coverage-matrix.md`, `phase-2-reviewed-findings.json`, `defect-backlog.json`, `remediation-retest.json`, timestamped `history/` copies and hash companions |

## Exact Windows commands

Use a local disposable PostgreSQL administrator. No `.env` change is required.

```powershell
$env:QA_DATABASE_ADMIN_URL = 'postgresql+psycopg://<test-admin>:<password>@127.0.0.1:5432/postgres'
npm.cmd run qa:smoke -- --retest
npm.cmd run qa:phase2
node qa/retest-remediation.mjs
npm.cmd run qa:unit
$env:PYTHONPATH = 'apps/api;.'
apps/api/.venv/Scripts/python.exe -m unittest discover -s qa/unit -p 'test_*.py'
npm.cmd run test:web
npm.cmd run lint --workspace @vayujit/web
node node_modules/typescript/bin/tsc -p apps/web/tsconfig.app.json --noEmit

# Existing backend matrix; no shared test/business database is reused.
$env:QA_PHASE = '2'
$env:QA_ORIGIN = 'http://127.0.0.1:4200'
$qaRegressionToken = [guid]::NewGuid().ToString('N').Substring(0,16)
apps/api/.venv/Scripts/python.exe qa/fixture_server.py --port 0 --token $qaRegressionToken --output "tmp/qa-agent/$qaRegressionToken" --pytest test_pr5b_landed_cost.py test_pr5c_unit_economics.py test_pr6a_decision_readiness.py test_pr6c_decision_workflow.py

$env:MYPYPATH = 'apps/api'
apps/api/.venv/Scripts/python.exe -m mypy --config-file apps/api/pyproject.toml --follow-imports=silent apps/api/vayujit_api/intelligence/landed_cost_service.py apps/api/vayujit_api/intelligence/product_opportunity_unit_economics_service.py apps/api/vayujit_api/intelligence/decision_recommendation_service.py apps/api/vayujit_api/intelligence/decision_readiness_service.py
apps/api/.venv/Scripts/python.exe -m ruff check --config apps/api/pyproject.toml qa apps/api/vayujit_api/intelligence/landed_cost_service.py apps/api/vayujit_api/intelligence/product_opportunity_unit_economics_service.py apps/api/vayujit_api/intelligence/decision_recommendation_service.py apps/api/vayujit_api/intelligence/decision_readiness_service.py
apps/api/.venv/Scripts/python.exe -m black --check --config apps/api/pyproject.toml qa apps/api/vayujit_api/intelligence/landed_cost_service.py apps/api/vayujit_api/intelligence/product_opportunity_unit_economics_service.py apps/api/vayujit_api/intelligence/decision_recommendation_service.py apps/api/vayujit_api/intelligence/decision_readiness_service.py
node node_modules/prettier/bin/prettier.cjs --check qa
git diff --check
```

## Remaining scope / Phase 3 recommendation

No confirmed release-blocking defect from the executed Phase 1/2 matrix remains
open. This does not certify 154 inventoried routes, real-provider connectivity,
GST applicability, every browser/width, complete accessibility, private media or
real orders/refunds/settlements. Disposable fixtures still use canonical ORM
metadata rather than replaying the complete migration chain.

Phase 3 should prioritize migration-backed fixtures, financial order/refund/fee/
settlement oracles, supplier switching and foreign-resource/stale-approval tests,
then broader keyboard/assistive-technology and first-seller task-completion review.
Keep real provider execution a separately authorized milestone. Do not infer real
business or live marketplace readiness from these local synthetic results.

All execution used disposable synthetic state. Permanent/golden data, PC-first
backup resources, marketplace accounts, supplier contact, RFQs, payments and
publishing were untouched. No unrelated Docker resources were deleted.
