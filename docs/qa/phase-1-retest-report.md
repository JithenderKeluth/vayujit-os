# QA Agent Phase 1 — executed report

Generated 26/10/2026, 10:51:37 pm IST (2026-10-26T17:21:37.007Z).

## Executive summary

Classification: **PASS_BOUNDED_SMOKE**. QA foundation is implemented; application release certification is not implied.

- Browser tests: 8 passed, 0 failed, 0 skipped; 8 total.
- 0 recorded axe rule findings (viewport/state occurrences, not necessarily distinct root causes).
- 0 assertion-failure records requiring triage; 4 subjective usability recommendations.
- This QA execution makes no external provider calls or marketplace executions. Application remediation preceding a retest is documented separately.

## Coverage matrix

155 Angular route declarations; 1610 static API declarations; 421 model tables; 391 backend test files; 71 Angular spec files inventoried. Runtime OpenAPI operations: 1629, 1629.

See [all route/spec coverage](coverage-matrix.md), [all API/model/service declarations](application-inventory.json), [executed route ledger](executed-coverage.json), and [structured run evidence](initial-report.json). 18 unique route paths were visited. A visit is not full feature coverage. Historical tests were inventoried, not all rerun.

| Scenario | Viewport | Result | Duration ms | Local evidence (ignored by Git) |
| --- | --- | --- | --- | --- |
| QA-SMOKE-01 | desktop | PASSED | 2908 | tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-01/0-readiness-orm-fixture-not-migration-certified.json<br>tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-01/1-axe-owner-validation.json<br>tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-01/2-axe-dashboard.json<br>tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-01/3-network-and-console.json<br>tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-01/4-final-screen.png |
| QA-SMOKE-02 | desktop | PASSED | 8129 | tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-02/0-axe-catalog-empty.json<br>tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-02/1-ux-observations.json<br>tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-02/2-axe-catalog-detail.json<br>tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-02/3-network-and-console.json<br>tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-02/4-final-screen.png |
| QA-SMOKE-03 | desktop | PASSED | 6626 | tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-03/0-recovery-context.txt<br>tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-03/1-axe-login.json<br>tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-03/2-network-and-console.json<br>tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-03/3-final-screen.png |
| QA-SMOKE-04 | desktop | PASSED | 6795 | tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-04/0-axe-goal-plan.json<br>tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-04/1-journey-boundary.txt<br>tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-04/2-network-and-console.json<br>tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-04/3-final-screen.png |
| QA-SMOKE-01 | mobile | PASSED | 2558 | tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-01/0-readiness-orm-fixture-not-migration-certified.json<br>tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-01/1-axe-owner-validation.json<br>tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-01/2-axe-dashboard.json<br>tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-01/3-network-and-console.json<br>tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-01/4-final-screen.png |
| QA-SMOKE-02 | mobile | PASSED | 5365 | tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-02/0-axe-catalog-empty.json<br>tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-02/1-ux-observations.json<br>tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-02/2-axe-catalog-detail.json<br>tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-02/3-network-and-console.json<br>tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-02/4-final-screen.png |
| QA-SMOKE-03 | mobile | PASSED | 2686 | tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-03/0-recovery-context.txt<br>tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-03/1-axe-login.json<br>tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-03/2-network-and-console.json<br>tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-03/3-final-screen.png |
| QA-SMOKE-04 | mobile | PASSED | 3004 | tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-04/0-axe-goal-plan.json<br>tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-04/1-journey-boundary.txt<br>tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-04/2-network-and-console.json<br>tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-04/3-final-screen.png |

## Confirmed automated accessibility findings

None recorded; do not infer unscanned states are accessible.

## Suspected defects / failed assertions

These can overlap confirmed axe findings. A failed test is not automatically a functional product defect.

None recorded.

## Usability recommendations

### QA-UX-CURRENCY-DESKTOP

P2 / MINOR / RECOMMENDATION; route: /products/new.

Expected: A seller should understand and explicitly confirm the intended pricing currency.

Actual: The new product form defaults to USD even in this Indian-seller journey; INR must be entered manually.

Reproduce: Create a brand → Open /products/new → Inspect Currency before entering a price

Suggested fix: Consider using an explicitly configured business currency or a prominent currency confirmation; do not infer currency silently.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-02/0-axe-catalog-empty.json, tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-02/1-ux-observations.json, tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-02/2-axe-catalog-detail.json, tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-02/3-network-and-console.json, tmp/qa-agent/a373cbfc14cb7ea6/evidence/desktop-QA-SMOKE-02/4-final-screen.png

### QA-UX-CURRENCY-MOBILE

P2 / MINOR / RECOMMENDATION; route: /products/new.

Expected: A seller should understand and explicitly confirm the intended pricing currency.

Actual: The new product form defaults to USD even in this Indian-seller journey; INR must be entered manually.

Reproduce: Create a brand → Open /products/new → Inspect Currency before entering a price

Suggested fix: Consider using an explicitly configured business currency or a prominent currency confirmation; do not infer currency silently.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-02/0-axe-catalog-empty.json, tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-02/1-ux-observations.json, tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-02/2-axe-catalog-detail.json, tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-02/3-network-and-console.json, tmp/qa-agent/49e7bebb7ccd109c/evidence/mobile-QA-SMOKE-02/4-final-screen.png

### QA-UX-NAV-CURRENT-001

P2 / MINOR / RECOMMENDATION; route: /intelligence/business-agent.

Expected: The seller can distinguish the current page from its broader research section.

Actual: In the reviewed 25 October 2026 synthetic desktop screenshot, Business Agent and My Research both use the same active sidebar treatment. The navigation uses prefix matching for the parent /intelligence link. This is a usability recommendation, not an authorization or navigation failure.

Reproduce: Run the QA smoke suite → Create a goal and plan → Review the sidebar on /intelligence/business-agent

Suggested fix: Consider exact matching for the current page or a visually distinct parent-section state. Preserve all routes and access guards.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/27830f8ae482803a/evidence/desktop-QA-SMOKE-04/4-final-screen.png

### QA-UX-PRE-RUN-MODE-001

P3 / INFO / RECOMMENDATION; route: /intelligence/business-agent.

Expected: A first-time seller understands what is known before the first run and the single next action.

Actual: The reviewed synthetic planned-goal state displays a provider-mode-not-recorded warning, a DISABLED research-mode banner, journey research links, a separate confirm-context action and Start run. These describe different authorities, but their relationship may be unclear to a first-time seller. No blocked live-provider flow was executed.

Reproduce: Use a fresh synthetic owner → Create the kids-category goal → Create a versioned plan without starting it → Review the journey header and goal card together

Suggested fix: Review pre-run wording and action hierarchy with a seller. Distinguish global configured mode from not-yet-recorded per-run mode; do not hide actual provider restrictions.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/27830f8ae482803a/evidence/desktop-QA-SMOKE-04/4-final-screen.png


## Accessibility and keyboard scope

12 real Chrome axe scans; 0 rule occurrences; 0 incomplete rule/state occurrences retained for manual review. No rules were disabled. Critical/serious findings fail the scenario even when soft assertions allow later evidence collection. Keyboard checks cover Tab/Shift+Tab during owner setup, not all dialogs or assistive technology. This does not certify WCAG conformance.

## Missing flows / blocked tests

See [journeys and phased architecture](architecture.md). Full discovery → HUMAN selection → supplier → due diligence → economics, inventory/order/financial Decimal oracles, private-media, marketplace controls, cross-installation foreign IDs and desktop Electron remain pending. Real providers and all external execution are deliberately forbidden, not unblocked by test fixtures.

Fresh disposable schemas are created from canonical ORM metadata, not a migration replay. Health-ready output is attached; no fake Alembic head is stamped. Migration readiness can therefore be unavailable and is not certified. Original PC-first backup/restore certification remains untouched.

## Disposable cleanup

- desktop: PASS; vayujit_qaa373cbfc14cb7ea6_test; child exit 0; verified absent=true.
- mobile: PASS; vayujit_qa49e7bebb7ccd109c_test; child exit 0; verified absent=true.

Only fresh token-matched QA databases are eligible for removal. Private synthetic media/evidence folders remain locally under ignored tmp/qa-agent. No shared Docker resources were changed.

## Runtime blockers

No runner startup blocker in this attempt. Failing assertions and remaining scope above remain open.

## Next implementation phase

Risk-first persisted seller journey, financial oracle and foreign-ID matrices; no autonomous production fixes.
