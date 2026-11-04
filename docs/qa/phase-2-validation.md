# QA Agent Phase 2 - implementation and actual validation

> Historical Phase 2 baseline. The original results below are preserved, not
> overwritten. Current authorized remediation and independent retest results are
> in [Phase 2 remediation validation](phase-2-remediation-validation.md). Original
> JSON/Markdown snapshots and hashes remain under `history/`.

Date: 25 October 2026. Classification: **QA FOUNDATION IMPLEMENTED / EXECUTED
WITH OPEN APPLICATION DEFECTS**. Application certification remains **INCOMPLETE**.
This is not comprehensive application coverage or production-release approval.

## Delivered

- Persisted canonical API fixtures and seller scenarios in `qa/phase2_api.py`.
- Desktop 1440x1000 and mobile 390x844 Chrome journeys in `qa/tests/phase2.spec.mjs`.
- Independent eight-place Decimal oracle and fixed arithmetic self-tests.
- Compatible finding schema requiring seller area, journey and business impact.
- Separate JSON/Markdown reports, executed coverage and prioritized backlog.
- Screenshots, failure traces, route/network/console evidence, real axe results,
  synthetic supplier provenance, tax snapshots and read-only database proofs.

Read [architecture and Windows commands](phase-2-architecture.md),
[generated execution report](phase-2-report.md), [JSON report](phase-2-report.json),
[shared coverage matrix](coverage-matrix.md), [coverage ledger](phase-2-coverage.json),
and [prioritized backlog](defect-backlog.json).

## Actual results

| Check | Result | Scope / qualifications |
| --- | --- | --- |
| Persisted HTTP/API scenarios | 20 passed, 2 failed, 0 errors, 0 skipped | 11 scenarios in each of two independent disposable installations; both failures are the same stale-cost context defect |
| Chrome Playwright | 2 passed, 6 failed, 0 skipped | Four scenarios per viewport; serious accessibility violations fail a scenario even when functional steps pass |
| Node QA self-tests | 16 passed, 0 failed, 0 skipped | Includes deny rules, report classifications, finding-schema compatibility and live-mode proxy rejection |
| Python QA self-tests | 15 passed, 0 failed, 0 skipped | Seven oracle cases plus marker/target, socketpair, DNS and outbound-connection safeguards |
| Angular/Vitest | 240 passed in 65 files | Existing full suite; not a substitute for real browser validation |
| Production Angular build | PASS with existing warning | Initial bundle 514.48 kB versus 500 kB warning budget; no budget was raised |
| Angular ESLint | PASS, 0 errors, 2 warnings | Existing missing OnInit interface warnings in catch-up and reschedule dialogs; no unrelated fixes |
| TypeScript no-emit | PASS | `apps/web/tsconfig.app.json` |
| Ruff | PASS | `qa` only |
| Black check | PASS | Nine Python QA files |
| Focused strict mypy | PASS | Four runtime/oracle QA modules, repository source import path, `--follow-imports=silent`; NOT repository-wide typing certification |
| compileall | PASS | `qa` only |
| Prettier check | PASS | `qa` JavaScript/JSON assets |
| git diff --check | PASS | Existing LF/CRLF notices are not whitespace failures |
| Disposable cleanup | PASS | Exact token-marker verification and database-absence proof for each installation; no shared Docker cleanup |

See the generated report for final run tokens, timestamps, individual scenarios
and evidence paths. These counts are one final matrix, not accumulated retries.
Earlier diagnostic attempts are retained locally but are not added to totals.

Final matrix: 2026-10-25T02:11:56.882Z (07:41:56 IST), desktop token
`7b04b3c8a2d65d4f`, mobile token `19d63dade5736dc4`. Both exact databases are
verified absent. All ten final axe state scans executed, including the reopened
HUMAN decision screen. No failure remains attributable to the repaired label locator.
There are 38 axe rule/state occurrences, not 38 distinct root-cause defects.
All finding evidence paths were checked and exist. The QA reporter's self-test
intentionally prints `desktop: FAILED QA-TEST failure`; that is a negative reporter
fixture, not a failure of the 16-passing Node self-test suite.

## Demonstrated financial behavior

Persisted calculations agree with independent expectations for explicit
same-currency landed cost, percentage and per-order allocation, fractional
rounding, positive/negative/zero contribution, margin, capital fit and shortfall.
Missing inputs, zero sale price, absent fees and mismatched currency remain
blocked; NaN is rejected. Unknown tax/GST is not treated as zero.

The explicit hypothetical tax-rate/basis scenario and unknown-basis exclusion
pass through canonical persisted contexts, evidence, snapshots and calculations.
It does NOT establish a real GST rate, category classification, recoverability or
marketplace fee schedule. Modeled contribution is explicitly not net profit.

The independent API process reopens a read-only database connection, verifies its
exact marker, and compares persisted monetary fields to the API values. It also
checks DD supplier/opportunity linkage, which is not exposed in full by the
current DD list response. Catalog cost edits do not rewrite immutable commercial
scenario snapshots; that separation is expected, not a numerical contradiction.

## Confirmed defects - no production fixes made

### QA-P2-FIN-001 - stale scenario presented READY (P1)

Reproduce with API test 06. Set the supplier-price assumption to INR 100 and
calculate landed cost. Create a new readiness snapshot at INR 200, then request a
new unit calculation referencing the previous landed result. The result returns
READY with cost/unit 100, contribution/unit 124.9 and no stale limitation or
contradiction. The new input snapshot combines the new readiness with the old cost.

The current service independently chooses latest readiness and the requested
EconomicCalculation without validating their version relationship. Arithmetic
for the old scenario is correct; disclosure/context integrity is the defect.
See `product_opportunity_unit_economics_service.py`, `calculate_unit_economics`.
Retain historical snapshots and distinguish them explicitly in any later repair.

### QA-P2-DEC-001 - supplier-scoped HUMAN replay rejected (P1)

Browser QA-P2-03 saves KEEP_UNDER_REVIEW with HTTP 200 and HUMAN provenance.
Replaying its exact request with the same key returns 409, "Idempotency key is
already bound to another decision." The initial persisted record remains present.

`record_journey_decision` omits supplier_id when delegating, while
`create_human_decision` compares the existing supplier ID to the caller's default
None before returning a replay. The initial supplier scope was resolved from the
recommendation. The mismatch is therefore reproducible with the unchanged request.
Preserve owner/target/supplier isolation and mismatch rejection in any later repair.
No duplicate HUMAN record or unauthorized Proceed is claimed.

### Shared accessibility defects (P1, existing root issue reproduced)

Actual axe scans reproduce serious small-text contrast failures around blocked
journey steps: measured 3.52:1 versus the applicable 4.5:1 threshold. Nested or
duplicate main/complementary landmarks are retained as separate automated findings.
New supplier, DD and economics evidence expands the known affected states; it does
not mean every occurrence is a distinct source-level bug. No rule was disabled.
Automated scanning alone does not certify WCAG compliance or all keyboard behavior.

## Usability recommendations, not functional-defect claims

The populated economics page is over 16,000px tall on desktop and over 43,000px on
mobile in the observed synthetic fixture, with extensive reason/evidence lists.
Capture-specific measurements and full screenshots are in QA-P2-02's observations.
Recommend a concise first-seller summary, grouped reasons, jump links and progressive
disclosure while preserving all provenance. This is a usability recommendation,
not proof that evidence should be removed or that calculations are incorrect.

INR edit/cancel/save, Tab/Shift+Tab, Enter cancellation, Space submission and reload
are exercised in the catalog workflow. This does not cover every focus trap,
modal, screen-reader interaction, mobile width or browser engine.

## Harness corrections and triage (not production defects)

- Canonical local supplier extraction validates DNS. The initially strict QA DNS
  guard denied `example.org`, so the fixture produced no supplier evidence. An
  exact synthetic DNS answer in the QA process now supports only that fixture;
  TCP remains denied and subdomain/external lookalikes remain blocked.
- The existing supplier fixture describes bottles. Fixture products now match
  bottles; no kids-category success is fabricated.
- Commercial readiness correctly rejects an opportunity without linked supplier
  evidence. Each independent financial context now obtains that evidence through
  the canonical local fixture API before calculating.
- DD list responses do not expose opportunity_id. The test checks supplier scope
  via the API and verifies the actual opportunity linkage in read-only PostgreSQL.
- The tax engine's explicit-component precedence is respected by creating a
  separate canonical context; existing UNKNOWN cost components are not removed.
- JSON numeric values use Decimal(str(value)), not Decimal(float). This avoids a
  test-only binary floating-point artifact being reported as a production defect.
- Catalog conversion can legitimately change review context. Browser fixtures
  prepare a current canonical advisory assessment after fixture construction;
  no HUMAN approval or stale-context check is bypassed.
- A saved-decision assertion initially targeted its strong label instead of the
  containing paragraph. It now targets the actual persisted decision container.

## Prioritized backlog and next phase

1. P1: separately authorize and repair stale-cost posture, supplier-scoped replay
   and shared contrast/landmark defects; rerun the existing red assertions.
2. P2: review the long decision brief and first-seller guidance with real task
   completion measures, not arbitrary removal of evidence.
3. Phase 3: migration-driven fixtures; multi-supplier selection/switching;
   cross-installation foreign IDs; stale HUMAN approvals; supplier zero/error and
   interrupted-research cases; broader keyboard/focus coverage.
4. Phase 3 financial expansion: canonical orders, refunds, fee schedules and
   settlements with independently specified gross/net-profit oracles, effective
   dates and concurrency. No real financial event is created in this phase.

Live product discovery, category/cache integrity, real supplier acquisition,
real GST/marketplace contracts, orders/refunds/settlements net profit, full
migration replay, Electron and complete application coverage remain explicit gaps.
They are not labeled unsupported merely because they are unexecuted.

## Changed assets and preserved history

New: `qa/phase2_api.py`, `qa/financial_oracle.py`, `qa/phase2-report.mjs`,
`qa/tests/phase2.spec.mjs`, `qa/finding-v2.schema.json`,
`qa/unit/test_financial_oracle.py`, `qa/unit/phase2.test.mjs`, this validation,
the Phase 2 architecture, reviewed findings and generated reports/backlog/ledger.

Extended: QA runner/config, fixture server, network guard, proxy, safety module,
compatible base finding schema, guard/safety self-tests, root package QA script,
shared QA architecture and coverage matrix. Source/runtime inventories are refreshed.
No application implementation file is changed by this phase. The worktree already
contained unrelated user changes, which were preserved.

Phase 1 initial JSON SHA256:
`830B586609DE1F04C41D0968C86C3E54CB305AC008324690A2FCC5B04FBB028C`.
Phase 1 initial Markdown SHA256:
`4FD58002A5CE1B8706BF6EB2597A81ED0CEF26EDAC6B7DFC745718DE5F513EC4`.
All 14 inherited Phase 1 findings remain unchanged and open as recorded.

## Safety and reproduction

Single owner per installation remains canonical. Real providers, financial
transactions, supplier contact, publishing and marketplace mutations remain denied.
No permanent/golden data changes, PC-first backup interference, unrelated Docker
deletion, dependency installation, branch, commit or push was performed.

```powershell
$env:QA_DATABASE_ADMIN_URL = 'postgresql+psycopg://<test-admin>:<password>@127.0.0.1:5432/postgres'
npm.cmd run qa:phase2
npm.cmd run qa:unit
apps/api/.venv/Scripts/python.exe -m unittest discover -s qa/unit -p 'test_*.py'
npm.cmd run test:web
npm.cmd run lint --workspace @vayujit/web
node node_modules/typescript/bin/tsc -p apps/web/tsconfig.app.json --noEmit
$env:MYPYPATH = 'apps/api'
apps/api/.venv/Scripts/python.exe -m mypy --strict --follow-imports=silent qa/financial_oracle.py qa/phase2_api.py qa/fixture_server.py qa/network_guard.py
apps/api/.venv/Scripts/python.exe -m ruff check --config apps/api/pyproject.toml qa
apps/api/.venv/Scripts/python.exe -m black --check --config apps/api/pyproject.toml qa
apps/api/.venv/Scripts/python.exe -m compileall -q qa
node node_modules/prettier/bin/prettier.cjs --check qa
git diff --check
```

No `.env` update is needed. Failed application assertions intentionally keep
`qa:phase2` nonzero; do not weaken them to claim certification.
