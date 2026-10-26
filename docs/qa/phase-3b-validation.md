# QA Phase 3B — remaining correctness and usability

**Application certification: INCOMPLETE.** Final execution evidence is recorded
below; source inventory and passing bounded tests are not whole-application certification.

## Scope and actual root causes

The reviewed baseline is [Phase 3A](phase-3a-validation.md), the immutable
[reviewed finding source](phase-3-reviewed-findings.json), and the archived Phase 3
reports. Phase 3A actually resolved four P1 roots plus one P2, not five P1 roots.
Original evidence and priorities are preserved.

### QA-P3-SOURCE-001 — synthetic financial provenance

Fake-order ingestion already persists `totals_json.fake_provider=true` and fake
movement/event lineage. The first loss is the financial summary projection:
`synthetic_provider` used FinancialEvent source types only, ignoring canonical
orders/fees/refunds. The UI then treated false as “Canonical evidence”, turning
absence of a flag into an unjustified authenticity claim.

The bounded correction uses existing persisted authorities:

- Preserve positive fake markers, sandbox account context, event source types and
  linked-order ancestry. Batch owner-scoped account/parent lookups; no provider call.
- Stamp original account environment/fake status into new immutable financial
  events, so later account configuration cannot erase their synthetic origin.
- Expose SYNTHETIC / REPORTED / UNKNOWN / MIXED classification with source IDs.
  An explicit reported or even caller-declared `verified` source type is only a
  declaration, never independent verification authority. Missing canonical source
  provenance remains UNKNOWN; a production account alone is not live evidence.
- Carry classification through summary, current calculation lineage, canonical
  sales rows, refund ancestry and settlement projections. Existing amounts and
  arithmetic are unchanged. Current snapshots remain mutable projections.
- Replace false → real UI inference with explicit synthetic/reported/unknown
  wording and an accessible warning that figures are not independently verified
  real financial information. Older responses missing the new fields fail closed.

No historical source row is rewritten or upgraded. Legacy sources without enough
lineage cannot be retroactively certified. REPORTED is not a real-provider
certification, and deterministic branch fixtures never establish live acquisition.

### QA-P3-UX-001 — resolved filter and result consistency

The dropdown changed local `ngModel` only, while the initial API request excluded
resolved rows. Filtering the already loaded subset could never retrieve them.

All list filters now request the canonical owner-scoped API, with 25-item server
pages, filtered total counts, deterministic ID tie-breaking and request-version
protection against out-of-order responses. Filter changes reset pagination; removing
the last item on a page moves to the last valid page. Errors do not display a false
successful-empty state. Resolved/stale views are inspectable; stale evidence has
no mutation controls. Reopen reuses the existing HUMAN transition API.

The backend distinguishes resolved and stale briefing counts. It derives freshness
before querying filtered results, preserving the same owner and HUMAN authorities.
Filters are view state, not persisted business state: full browser refresh returns
to Active; explicitly reselecting Resolved retrieves the same persisted records.

## Execution evidence

Evidence reviewed on 26 October 2026. Counts are executions, not unique feature
coverage; API installations and repeated regression runs overlap.

| Check | Actual result / evidence |
| --- | --- |
| New Phase 3B persisted regressions | **16 passed** in final combined run `07f642c125fc44e8` |
| Phase 3A revalidation plus Action Center | **21 passed** in that same run: 17 Phase 3A + 4 Action Center; combined **37 passed**, 75 warnings, 501.68s |
| Broader adjacent backend run | **63 passed**, 125 warnings, 933.10s (`d1266fb1a7ce40f4`); before final stale/resolved briefing-count refinement, which the final 37-test run retests |
| Phase 2 persisted API / browser | **22 / 8 passed**, normal cleanup and child exit 0 for both installations (`d2325c9fd225057d`, `e7079a94ed8d0d2b`) |
| Phase 1 independent smoke | **8 passed**, normal cleanup and child exit 0 (`90389cc993651a12`, `95b528dd45a5f0c0`) |
| Angular | **249 passed**, 68 files; includes 7 added component/provenance/navigation regressions |
| QA self-tests | **32 Node + 28 Python passed**; the initial Python command used a nonexistent `qa/tests_python` path, ran zero cases, then was corrected to `qa/unit` |
| Focused Python quality | Ruff PASS; Black PASS (20 files unchanged); mypy PASS (9 source files, configured strict settings with `--follow-imports=silent`); compileall PASS |
| Frontend quality | Angular lint: 0 errors, 2 existing OnInit warnings; TypeScript no-emit PASS; QA ESLint and Prettier PASS after formatting the changed report generator |
| Production build | PASS; initial bundle **514.66kB** exceeds the existing 500kB warning budget by 14.66kB (baseline 514.48kB, about +0.18kB). Not a warning-free build. |

Final Phase 3 browser/API results and evidence-gated resolution are recorded in
the closing section below. No pending/unexecuted gate is reported as PASS.

### Earlier blocked execution attempts

The first Phase 3 attempts executed zero browser cases because cold fixture
startup exceeded the old approximately 60-second polling budget. Initial readiness
now has a bounded 120-second budget with a 2-second fetch timeout and a safe timing
diagnostic; this does not alter application requests or test assertions. Earlier
Phase 2 browser/API assertions passed but the old 20-second teardown budget expired.
The owned-child grace is now 45 seconds; cleanup and child-exit requirements remain
strict. A later mobile run (`87e7f2b69a1926ad`) passed all assertions but still
timed out during teardown. It remains **INCOMPLETE**, not certified by its passing
assertions. Exact-token independent recovery found its database already absent
and no QA fixture process remained; that does not manufacture a normal child exit.
The precise intermittent teardown delay is not established. The final isolated
rerun is evaluated independently after other test load has finished.

## Accessibility verification boundary

The original Phase 3 assertions remain unchanged. Supplemental tests retain full
document axe scans and revisit every caption in the four evidence states plus the
financial contrast targets. They use real scrolling, existing focusable table
regions, Home/ArrowRight keyboard input, and actual viewport screenshots.

Each diagnostic records route, exact HTML/text/selector, element/text rectangles,
viewport, axe rule results and screenshot references. No styles, DOM nodes, rules
or contrast thresholds are removed to obtain a pass. Supplemental focused scans
do not replace full-document scans. Incomplete results remain open manual tasks
unless the actual element is independently demonstrated readable and testable.

The six historical caption occurrences and four financial nodes remain explicitly
tracked; a zero-target rescan alone does not close historical evidence. Automated
results do not establish comprehensive WCAG or screen-reader compliance.

In the supplemental mobile economics evidence, the landed-cost caption's box is
680px wide in a 390px viewport and its text extends to x=414.64. Its screenshot
shows the horizontally scrolled container clipping the caption/heading; focused
axe still reports `color-contrast` incomplete, not a confirmed contrast ratio.
The selling-cost caption is similarly 680px wide. Real horizontal scrolling makes
table content inspectable, but does not independently prove every caption readable
at one position. Retain the manual/responsive review rather than hiding columns,
removing captions, or assigning PASS based on no confirmed violations.

Concrete retained evidence from the earlier all-assertions-passing run:

- `tmp/qa-agent/87e7f2b69a1926ad/evidence/mobile-QA-P3B-03/6-accessibility-completion-economics.json`
- `tmp/qa-agent/87e7f2b69a1926ad/evidence/mobile-QA-P3B-03/4-review-economics-0.png`
- `tmp/qa-agent/87e7f2b69a1926ad/evidence/mobile-QA-P3B-03/13-accessibility-completion-human-decision.json`
- The original financial scan retains four obscured header nodes in
  `axe-financial-loss-and-unknown`. A later state scan has zero incomplete nodes,
  but different state/scroll position is **not** proof those four historical nodes
  were individually cleared. Their review stays open with exact selectors in the
  current report's `manual_accessibility_reviews`.

## Six usability recommendation occurrences

Desktop/mobile occurrences below share underlying proposals; they are not six
different product features. Complexity is an engineering estimate, not measured
implementation time or an approval to expand scope.

| Stable ID / screen | User problem and evidence | Business impact | Minimal proposal / complexity | Priority / disposition |
| --- | --- | --- | --- | --- |
| QA-UX-CURRENCY-DESKTOP — `/products/new` | Baseline DOM observation says new product defaults USD; seller manually changes INR. See archived Phase 1 UX evidence referenced in backlog. | Incorrectly retained units could confuse price/cost entry. | Use an explicitly configured business currency plus visible confirmation; never silently infer INR. Small UI work, medium configuration/contract validation. | P2; proposal, not implemented. Requires a canonical currency preference contract. |
| QA-UX-CURRENCY-MOBILE — same journey | Same default on mobile; repeated viewport occurrence. | Extra input and potential currency mistake on a compact form. | Same shared currency proposal, with keyboard/mobile confirmation testing. | P2; proposal, not implemented. |
| QA-UX-NAV-CURRENT-001 — Business Agent | `/intelligence` prefix matching highlighted My Research and Business Agent together; baseline screenshot and source matcher establish cause. | Seller cannot tell which page is current. | Exact-match only the My Research root, retaining parent matching for legitimate detail routes. Small; implemented, closure requires browser retest. | P2; low-risk correction, no route/guard changes. |
| QA-P2-UX-ECONOMICS-DESKTOP — economics | Baseline page 16,260px at 1000px viewport; evidence/reason lists surround the decision. Source UX JSON/screenshots in backlog. | Finding the decision and next action requires extensive scrolling. | Concise current-status summary, jump links to existing sections and deduplicated reasons without hiding provenance. Medium design and responsive testing. | P2; proposal requiring product approval. |
| QA-P2-UX-ECONOMICS-MOBILE — economics | Baseline page 43,301px at 844px viewport; same repeated information-hierarchy issue. | High navigation/comprehension burden on a phone. | Same shared proposal; mobile keyboard/focus and evidence disclosure testing. | P2; proposal requiring approval, not a redesigned workflow. |
| QA-UX-PRE-RUN-MODE-001 — first research plan | Baseline shows global DISABLED mode, per-run mode not recorded, context confirmation and Start run simultaneously. No live-provider flow was exercised. | A first-time seller may mistake distinct configuration and approval states for contradictory instructions. | Explain configured mode vs not-yet-run mode and show the supported next action. Small copy work, medium state/authority review. | P3; proposal until wording is verified against every supported state. |

No currency defaults, economics calculations, research policy or approval behavior
was changed. The navigation recommendation closes only after its actual desktop
and mobile current-page assertions pass. The other five occurrences stay open.

## Three missing workflows — product assessment, not implementation

| ID | Classification | Rationale / dependencies |
| --- | --- | --- |
| QA-P3-GAP-001 — exact historical operational calculation reconstruction | **Important but deferrable** | Current projections are not immutable history. Existing source events/cost revisions and canonical economics snapshots are retained, but the exact prior operational projection cannot be reopened. Deferrable only while the UI is explicitly current/estimated and not represented as the sole financial/audit ledger. Requires approved versioning/retention requirements and complete input lineage. No new history system implemented. |
| QA-P3-GAP-002 — generic operational approval/reject/execution lifecycle | **Important but deferrable** | Action Center is advisory; external actions remain default-denied and existing canonical commercial HUMAN workflows remain authoritative. A generic duplicate approval system would be unsafe. Dependencies: enumerate supported action types and route to existing authorities before any approved implementation. A low-risk truthful message now says no approval/execution was recorded; the missing durable workflow stays open. |
| QA-P3-GAP-003 — initial canonical stock-record UI handoff | **Launch-critical missing workflow** | A real first seller must create canonical SKU stock before mapping/orders. The creation API exists, but the inventory empty state has no demonstrated UI handoff; product-master stock fields are a separate authority. Requires approved opening-balance/provenance UX using the existing inventory API. Not automatically implemented. |

These classifications do not rewrite historical finding severity. In particular,
the launch-critical inventory assessment is a release-planning escalation, not a
fabricated passing workflow or an authorization to implement it.

## Changes and safety

Production changes: financial router/provenance projection and event metadata;
Action Center filtering/sorting/counts and factual advisory message; Angular Action
Center, financial provenance labels/service types, and the My Research navigation
matcher. No migration, financial formula, new approval authority or multi-tenancy.

Tests/reporting: Phase 3B persisted regressions, Angular regressions, three
supplemental browser scenarios, source-hash capture, evidence-gated Phase 3B closure
and current coverage/backlog generation. Phase 3A's original resolution ledger is
retained; its five roots must pass again against current sources before inheriting
closure. The original Phase 3 API and six browser scenario assertions are retained.

Only marker-protected disposable PostgreSQL state and synthetic fixtures are used.
No permanent/golden database changes, real provider/marketplace calls, publication,
supplier activity, payments, Docker cleanup, backup interference, branch, commit
or push is authorized or performed.

## Proposed Phase 4

1. Obtain product approval for the canonical inventory-onboarding handoff; implement
   and test it before a UI-only first-seller launch.
2. Complete remaining manual caption/assistive-technology review; fix demonstrated
   responsive/accessibility defects without hiding evidence.
3. Approve currency-preference and economics-information-hierarchy requirements.
4. Add migration-backed disposable fixtures, multi-product/quantity attribution,
   and return/fee/settlement lineage. Keep live-provider and worker-recovery
   certification separate and explicitly authorized.

No Phase 4 workflow is implemented here. Full application certification stays
INCOMPLETE while launch-critical gaps and required verification remain.

## Final bounded decision and current evidence

**QA_PHASE_3B_BOUNDED_GATES_VALIDATED_APPLICATION_INCOMPLETE**.

Final isolated Phase 3 run: **36 API passed, 0 failed, 0 errors; 18 browser
passed, 0 failed, 0 skipped**. Desktop `20801a4ca066cfbe` and mobile
`71783c286d84ef4b` each used separate persisted disposable PostgreSQL installations.
Both marker-verified cleanup proofs report database absent and child exit 0.
The runner exited 0. This replaces neither the preserved baseline nor earlier
incomplete attempts.

Final independent read-only PostgreSQL metadata audit checked all **15 exact
task-owned disposable database names**: zero remained. No QA fixture/runtime
Python processes remained. No unrelated database/session or Docker resource was
terminated. Final QA formatting/ESLint and `git diff --check` passed; Git emitted
existing LF/CRLF normalization warnings, not whitespace errors.

The [resolution ledger](phase-3b-resolution.json) checks current source hashes,
the unchanged original API/browser assertion hashes, all 37 targeted JUnit cases,
and two distinct normal-cleanup browser installations. It independently closes the
two Phase 3B correctness roots and the navigation recommendation, and revalidates
the five Phase 3A roots. Original reviewed findings and Phase 1 baseline hashes
remain unchanged. No assertion, axe rule or contrast threshold was weakened.

Current full-document accessibility execution: **32 state scans, zero confirmed
axe violations, 9 incomplete rule/state occurrences involving 218 node
occurrences**. These are repeated state occurrences, not 218 unique defects.
The original scrolled investigation examined **107** nodes across four mobile
states: **101** passed focused contrast checks, **six captions remain incomplete**.
Supplemental scans retain all six caption diagnostics/screenshots. Four historical
financial header nodes remain explicitly unclosed; a later zero-target scan is not
equivalent to individual retesting. Keyboard evidence covers actual table-region
focus/ArrowRight/Tab and navigation, not exhaustive assistive-technology compliance.

The active backlog has **nine records**: five usability occurrences (four P2,
one P3), three historical P2 workflow gaps, and one P2 manual-accessibility task.
Zero confirmed correctness roots currently reproduce in the executed matrix.
The inventory handoff is escalated as **launch-critical** despite its preserved
historical P2 label. This gap and incomplete verification prevent application-wide
certification. Two existing lint warnings and the bundle warning are not hidden;
repository-wide unrelated typing/lint debt was not reclassified as passing by
these focused checks.

See [machine-readable summary](phase-3b-report.json), [structured usability/gap
assessment](phase-3b-assessment.json), [current execution](phase-3-report.json),
[coverage](coverage-matrix.md), and [active backlog](defect-backlog.json).

## Task-specific changed files

- Backend: `apps/api/vayujit_api/commerce/financial_router.py`,
  `apps/api/vayujit_api/operations/action_center_router.py`.
- Frontend: `apps/web/src/app/operations/action-center.component.ts`,
  `apps/web/src/app/marketplaces/financial-workspace.component.ts`,
  `apps/web/src/app/marketplaces/marketplace.service.ts`,
  `apps/web/src/app/shared/seller-navigation.component.ts`.
- Regression tests: `apps/api/tests/test_qa_phase3b_remediation.py`,
  `apps/web/src/app/operations/action-center.component.spec.ts`,
  `apps/web/src/app/marketplaces/financial-provenance.spec.ts`,
  `apps/web/src/app/shared/seller-navigation.component.spec.ts`,
  `qa/tests/phase3b.spec.mjs`, `qa/unit/phase3b-resolution.test.mjs`.
- QA foundation/reporting: `qa/run.mjs`, `qa/playwright.config.mjs`,
  `qa/fixture_server.py`, `qa/phase3-report.mjs`, `qa/phase3b-resolution.mjs`,
  `qa/certify-phase3b.mjs`; this validation, assessment, resolution and summary;
  generated Phase 1 retest/Phase 2/Phase 3 reports, inventories and coverage,
  immutable report archives, canonical Phase 3 validation and current backlog.

The broader working tree already contains unrelated changes. This is a scoped
change list, not a claim that every repository diff belongs to Phase 3B.

## Exact Windows reproduction commands

Run from the repository root with dependencies installed and local PostgreSQL
available. Use a dedicated local QA role capable of creating disposable databases;
the admin URL must target `postgres` on `127.0.0.1`, never a business/golden database.
Do not put credentials in reports or change production `.env` files for QA.
Run browser suites sequentially because they share the build output directory.

```powershell
$env:QA_DATABASE_ADMIN_URL = 'postgresql+psycopg://LOCAL_QA_USER:URL_ENCODED_PASSWORD@127.0.0.1:5432/postgres'
npm.cmd run qa:phase3
npm.cmd run qa:phase2
npm.cmd run qa:smoke -- --retest
npm.cmd run qa:unit
& .\apps\api\.venv\Scripts\python.exe -m pytest qa/unit -q -o addopts=
npm.cmd run test:web
npm.cmd run lint --workspace @vayujit/web
npm.cmd run build --workspace @vayujit/web
node node_modules/typescript/bin/tsc --noEmit -p apps/web/tsconfig.app.json

$env:QA_PHASE = '3'
$env:QA_ORIGIN = 'http://127.0.0.1:4200'
$env:PYTHONPATH = 'apps/api;.'
$qaPhase3bToken = [guid]::NewGuid().ToString('N').Substring(0,16)
& .\apps\api\.venv\Scripts\python.exe qa/fixture_server.py --port 0 --token $qaPhase3bToken --output "tmp/qa-agent/$qaPhase3bToken" --pytest test_qa_phase3a_remediation.py test_qa_phase3b_remediation.py test_pr_sos_06_action_center.py
# Run after successful Phase 3 and targeted execution; fails closed otherwise:
node qa/certify-phase3b.mjs --token $qaPhase3bToken

node node_modules/eslint/bin/eslint.js --config qa/eslint.config.mjs qa
node node_modules/prettier/bin/prettier.cjs --check qa
& .\apps\api\.venv\Scripts\python.exe -m ruff check --config apps/api/pyproject.toml apps/api/vayujit_api/commerce/financial_router.py apps/api/vayujit_api/operations/action_center_router.py apps/api/tests/test_qa_phase3b_remediation.py qa
& .\apps\api\.venv\Scripts\python.exe -m black --check --config apps/api/pyproject.toml apps/api/vayujit_api/commerce/financial_router.py apps/api/vayujit_api/operations/action_center_router.py apps/api/tests/test_qa_phase3b_remediation.py qa
& .\apps\api\.venv\Scripts\python.exe -m mypy --config-file apps/api/pyproject.toml --follow-imports=silent apps/api/vayujit_api/commerce/financial_router.py apps/api/vayujit_api/operations/action_center_router.py apps/api/tests/test_qa_phase3b_remediation.py qa/fixture_server.py qa/cleanup_disposable.py qa/phase3_api.py qa/phase2_api.py qa/runtime_supervisor.py qa/phase3_runtime.py
& .\apps\api\.venv\Scripts\python.exe -m compileall -q qa apps/api/vayujit_api/commerce/financial_router.py apps/api/vayujit_api/operations/action_center_router.py apps/api/tests/test_qa_phase3b_remediation.py
git diff --check
Remove-Item Env:QA_DATABASE_ADMIN_URL
```
