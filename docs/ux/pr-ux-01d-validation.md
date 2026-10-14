# PR-UX-01D — Supplier Economics, Comparison & HUMAN Commercial Decisions

## A. Scope and final result

PR-UX-01D was implemented and validated against the existing canonical
commercial authorities. The page now presents landed cost, modeled unit
economics, budget fit, evidence gaps, comparison limitations, decision
readiness, and HUMAN decision controls without calculating or ranking values in
Angular.

**Classification: PR-UX-01D — FULLY VALIDATED (LOCAL / EVIDENCE-CONSTRAINED).**

The disposable validation used deterministic local supplier/product evidence.
It did not contact suppliers, send RFQs, purchase, pay, or write to a
marketplace. Live-provider certification remains governed by PR-9A/PR-9B.

## B. Canonical authorities audited

- `economic_integration_service.py`: decision brief, budget scope, landed-cost
  projection, and journey decision recording.
- `decision_readiness_service.py`: target-specific blockers, UNKNOWN values,
  trust state, and HUMAN selection gates.
- `decision_synthesis_service.py` and `decision_recommendation_service.py`:
  explainable posture, advisory recommendation, and HUMAN decision history.
- `commerce_journey_router.py` / `commerce_journey.py`: owner-scoped journey
  context and goal-specific decision briefs.
- `product_opportunity_scoring_router.py`: canonical score and explicit
  `shortlist` decision authority.
- `product_opportunity_commercial_router.py` and PR-5B/5C services:
  immutable assumptions, landed cost, unit economics, and capital fit.

## C. Defect found and bounded fix

The journey decision-brief route did not pass its journey goal into the
economics authority, and the frontend always used the product-level brief
route. An older/latest owner goal could therefore supply the wrong budget or
context. The fix threads the requested `goal_id` through the journey brief,
economics budget calculation, readiness, synthesis, and recommendation
projections. Product-level requests retain their existing latest-goal fallback.

The UI also used a timestamp-based HUMAN decision idempotency key and exposed
launch preparation as an enabled-looking action while the canonical brief was
blocked. Decision keys are now stable per journey/product/action, and launch
preparation is disabled with an explanation until the canonical readiness is
`READY_FOR_HUMAN_DECISION`.

## D. Product/goal context proof

Disposable goal text:

> I have INR 300000 and want to start selling on Amazon India. Help me find a
> product in kids category.

The authenticated browser displayed `Kids Reusable Lunch Box`, category
`Kids`, marketplace `AMAZON_IN`, goal provenance `USER_PROVIDED`, budget
`300000.0 INR`, and `WITHIN_BUDGET`. The goal-scoped backend regression also
proved that two goals with different budgets produce different briefs.

## E. Evidence and trust presentation

The workspace renders canonical provenance, assumptions, freshness, warnings,
unknowns, risk, readiness, and limitations. It does not infer demand, sales,
conversion, supplier ranking, or profitability. `LOCAL_FIXTURE` and external
write-off states remain visible in the live-certification panel.

## F. Disposable persisted fixture

Fixture creation used supported local API mechanisms against the marked
`vayujit_test` database: owner setup, Kids opportunity/constraint/assessment,
local supplier research, commercial-readiness assumptions, landed cost, unit
economics, Business Agent goal/context confirmation, advisory assessment,
reviewable plan, canonical score, and explicit HUMAN shortlist. No raw rows or
fabricated live evidence were inserted.

## G. Goal and journey behavior

The page uses `journey_id` when present and shows the current guided journey,
marketplace, currency, and next action. Creating the supported reviewable plan
changed the browser projection from `0 of 8` to `1 of 8` stages complete and
`Research` ready next.

## H. HUMAN selection boundary

Product scoring and shortlist were created through the canonical score and
`/{opportunity}/assessments/{assessment}/decision` endpoints. The page treats
the selection as HUMAN provenance and leaves supplier selection and further
commercial decisions explicit.

## I. Idempotency and stale-context behavior

The stable frontend key is
`pr6c-ui-decision-{journey}-{opportunity}-{ACTION}`. PR-6C regressions cover
replay, owner scope, advisory-vs-HUMAN provenance, blocked proceed, and the
goal-scoped brief. No timestamp or hidden retry can create a second logical
decision.

## J. Decision UX

The Decision Brief groups readiness, supplier state, budget fit, known landed
cost, modeled unit economics, comparison availability, data gaps, synthesis,
and HUMAN decision controls. Research/reconsider actions stay available while
blocked; launch preparation is disabled and explains the prerequisite.

## K. Known economics

The fixture displayed INR 52,562.50 total modeled landed acquisition cost,
INR 105.125/unit, INR 250 selling price, INR 25.10 modeled selling cost,
INR 130.225 modeled total cost, INR 119.775 modeled contribution, and capital
headroom of INR 247,437.50. These are scenario outputs, not recommendations.

## L. Layout and accessibility

The component keeps panels, grids, tables, inputs, buttons, and long evidence
values within the content box. Labels, captions, headings, `role=status`,
`role=alert`, disabled state, and explanatory text are present. Existing
navigation and skip-link semantics remain intact.

## M. Missing-data behavior

The page explicitly lists unknown brokerage, fulfilment, tax, insurance,
packaging, warehousing, customs, marketplace fees, returns, advertising,
storage, and overhead. UNKNOWN is never rendered as zero. Partial landed cost
keeps the recommendation blocked.

## N. Network/write safety

The local fixture ran with no external supplier acquisition and no external
writes. The live-source panel remained blocked by local policy (`LOCAL_FIXTURE`,
external research disabled, approved fetch disabled). No supplier contact or
RFQ action was executed.

## O. Owner isolation

All authority routes remain authenticated and owner-scoped. Existing PR-6C,
PR-8B, and PR-8C integration tests cover foreign-owner access and stale
decision contexts. The browser used a disposable owner account only.

## P. Automated tests

- Full Angular suite: **60 files, 217 tests passed**.
- Focused economics Angular suite: **3 tests passed**.
- PR-5B→PR-8C regression matrix: **36 passed, 66 warnings**.
- Focused PR-6C rerun: **4 passed, 10 warnings**.
- Focused strict mypy on four changed backend authorities: **0 issues**.
- Ruff on changed backend authorities: **pass**.
- Black `--check`: **4 files unchanged**.
- `compileall`: **pass**.
- Angular production build: **pass** (507.67 kB initial bundle; existing 7.67 kB budget warning).
- Angular ESLint: **0 errors, 2 pre-existing lifecycle warnings**.
- Clean disposable Alembic certification harness: **1/1 migration stability run
  passed** (upgrade-to-head, focused downgrade to `20261021_0100`, re-upgrade,
  marker preservation, and disposal).

## Q. Authenticated Chrome validation

Chrome CDP validated the authenticated route
`/intelligence/sourcing-economics?opportunity_id=...&journey_id=...` with the
disposable account. The page loaded the goal/product context, decision brief,
landed-cost breakdown, unit economics, unknowns, and blocked-action copy.

## R. Responsive results

At CSS widths **360, 390, 768, 1024, and 1440**, DOM checks reported no
horizontal overflow (`scrollWidth <= innerWidth`), the `Review sourcing
economics` heading remained present, and the blocked launch action remained
disabled. Captures are retained locally in `tmp/ux-browser/prux01d-*.png`.

## S. Static and formatting checks

Changed backend authority files pass Ruff, Black, compileall, and strict mypy.
`git diff --check` is run as the final handoff check.
The clean marker-protected migration harness passed independently of the
application fixture database.

## T. Warnings and limitations

Angular ESLint retains two unrelated lifecycle-interface warnings. The Angular
build is 7.67 kB above its existing initial warning budget. FastAPI emits its
existing `on_event` deprecation warning in integration tests. None is a
PR-UX-01D regression. A direct Alembic check against the long-lived
`vayujit_test` fixture database reports schema drift because that database is
created by the integration fixture's SQLAlchemy metadata path while the
repository's migration head is independently certified by the clean harness;
the disposable migration certification itself passed and no production schema
was changed.

## U. UNKNOWN semantics

Unknown and excluded cost components remain visible with their reason and
provenance; missing inputs are not coerced to zero and do not create a false
margin or recommendation.

## V. Verification of controlled actions

The controlled panel keeps `Proceed` unavailable when the canonical synthesis
is not recommendation-eligible. `Keep under review`, `Do not proceed`,
research, and reconsider paths remain HUMAN actions and preserve history.

## W. Changed files

- `apps/api/vayujit_api/intelligence/economic_integration_service.py`
- `apps/api/vayujit_api/intelligence/commerce_journey_router.py`
- `apps/api/vayujit_api/intelligence/commerce_journey.py`
- `apps/api/vayujit_api/intelligence/decision_recommendation_service.py`
- `apps/api/tests/test_pr6c_decision_workflow.py`
- `apps/web/src/app/intelligence/sourcing-economics-workspace.component.ts`
- `apps/web/src/app/intelligence/sourcing-economics-workspace.component.spec.ts`
- this validation report and the three UX coverage documents.

The worktree also contains earlier PR-5 through PR-9 and UX changes from the
workspace history; no unrelated changes were reset or committed.

## X. External provider boundary

This milestone validates the commercial UX and canonical local evidence path.
It does not claim live Brave/provider or real supplier evidence. PR-9A/PR-9B
remain the controlled live-source certification boundary.

## Y. Golden database safety

Only `vayujit_test` was reset and used. `vayujit_golden_test` was not modified,
queried for fixture creation, or used for destructive operations.

## Z. Classification

**PR-UX-01D — FULLY VALIDATED (LOCAL / EVIDENCE-CONSTRAINED).**

No PR-UX-01D implementation blocker remains. The next UX slice is outside this
request; no PR-UX-01E/F or PR-9C work was started, and no commit or push was
performed.
