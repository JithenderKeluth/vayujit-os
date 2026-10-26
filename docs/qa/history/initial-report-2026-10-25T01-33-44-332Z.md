# QA Agent Phase 1 — executed report

Generated 25/10/2026, 7:03:44 am IST (2026-10-25T01:33:44.332Z).

## Executive summary

Classification: **INCOMPLETE**. QA foundation is implemented; application release certification is not implied.

- Browser tests: 6 passed, 2 failed, 0 skipped; 8 total.
- 8 recorded axe rule findings (viewport/state occurrences, not necessarily distinct root causes).
- 2 assertion-failure records requiring triage; 4 subjective usability recommendations.
- No production application fixes, provider calls or marketplace executions.

## Coverage matrix

154 Angular route declarations; 1610 static API declarations; 421 model tables; 388 backend test files; 65 Angular spec files inventoried. Runtime OpenAPI operations: 1629, 1629.

See [all route/spec coverage](coverage-matrix.md), [all API/model/service declarations](application-inventory.json), [executed route ledger](executed-coverage.json), and [structured run evidence](initial-report.json). 18 unique route paths were visited. A visit is not full feature coverage. Historical tests were inventoried, not all rerun.

| Scenario | Viewport | Result | Duration ms | Local evidence (ignored by Git) |
| --- | --- | --- | --- | --- |
| QA-SMOKE-01 | desktop | PASSED | 2293 | tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-01/0-readiness-orm-fixture-not-migration-certified.json<br>tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-01/1-axe-owner-validation.json<br>tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-01/2-axe-dashboard.json<br>tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-01/3-network-and-console.json<br>tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-01/4-final-screen.png |
| QA-SMOKE-02 | desktop | PASSED | 4530 | tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-02/0-axe-catalog-empty.json<br>tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-02/1-ux-observations.json<br>tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-02/2-axe-catalog-detail.json<br>tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-02/3-network-and-console.json<br>tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-02/4-final-screen.png |
| QA-SMOKE-03 | desktop | PASSED | 2416 | tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-03/0-recovery-context.txt<br>tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-03/1-axe-login.json<br>tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-03/2-network-and-console.json<br>tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-03/3-final-screen.png |
| QA-SMOKE-04 | desktop | FAILED | 2782 | tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/0-axe-goal-plan.json<br>tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/1-journey-boundary.txt<br>tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/test-failed-1.png<br>tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/3-network-and-console.json<br>tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/4-final-screen.png<br>tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/error-context.md<br>tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/trace.zip |
| QA-SMOKE-01 | mobile | PASSED | 2039 | tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-01/0-readiness-orm-fixture-not-migration-certified.json<br>tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-01/1-axe-owner-validation.json<br>tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-01/2-axe-dashboard.json<br>tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-01/3-network-and-console.json<br>tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-01/4-final-screen.png |
| QA-SMOKE-02 | mobile | PASSED | 4684 | tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-02/0-axe-catalog-empty.json<br>tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-02/1-ux-observations.json<br>tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-02/2-axe-catalog-detail.json<br>tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-02/3-network-and-console.json<br>tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-02/4-final-screen.png |
| QA-SMOKE-03 | mobile | PASSED | 2466 | tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-03/0-recovery-context.txt<br>tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-03/1-axe-login.json<br>tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-03/2-network-and-console.json<br>tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-03/3-final-screen.png |
| QA-SMOKE-04 | mobile | FAILED | 2627 | tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/0-axe-goal-plan.json<br>tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/1-journey-boundary.txt<br>tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/test-failed-1.png<br>tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/3-network-and-console.json<br>tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/4-final-screen.png<br>tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/error-context.md<br>tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/trace.zip |

## Confirmed automated accessibility findings

### QA-AXE-DESKTOP-AXE-GOAL-PLAN-COLOR-CONTRAST

P1 / MAJOR / CONFIRMED; route: /intelligence/business-agent.

Expected: No axe color-contrast violation in this state.

Actual: {"id":"color-contrast","impact":"serious","help":"Elements must meet minimum color contrast ratio thresholds","nodes":[{"target":[".blocked[data-status=\"BLOCKED\"][_ngcontent-ng-c2587382897=\"\"]:nth-child(3) > small"],"remediation":"Fix any of the following:\n  Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1"},{"target":[".blocked[href$=\"sourcing\"][data-status=\"BLOCKED\"] > small"],"remediation":"Fix any of the following:\n  Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1"},{"target":[".blocked[href$=\"due-diligence\"][data-status=\"BLOCKED\"] > small"],"remediation":"Fix any of the following:\n  Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1"},{"target":[".blocked[data-status=\"BLOCKED\"][_ngcontent-ng-c2587382897=\"\"]:nth-child(6) > small"],"remediation":"Fix any of the following:\n  Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1"},{"target":[".blocked[data-status=\"BLOCKED\"][_ngcontent-ng-c2587382897=\"\"]:nth-child(7) > small"],"remediation":"Fix any of the following:\n  Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1"},{"target":[".blocked[href$=\"listings\"][data-status=\"BLOCKED\"] > small"],"remediation":"Fix any of the following:\n  Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1"}]}

Reproduce: npm.cmd run qa:smoke → QA-SMOKE-04: axe-goal-plan (desktop)

Suggested fix: Review the recorded axe targets and remediation; authorize an application fix separately. Automated rule finding is not complete WCAG certification.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/0-axe-goal-plan.json, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/1-journey-boundary.txt, tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/test-failed-1.png, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/3-network-and-console.json, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/4-final-screen.png, tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/error-context.md, tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/trace.zip

### QA-AXE-DESKTOP-AXE-GOAL-PLAN-LANDMARK-COMPLEMENTARY-IS-TOP-LEVEL

P1 / MODERATE / CONFIRMED; route: /intelligence/business-agent.

Expected: No axe landmark-complementary-is-top-level violation in this state.

Actual: {"id":"landmark-complementary-is-top-level","impact":"moderate","help":"Aside should not be contained in another landmark","nodes":[{"target":[".commerce-next-action"],"remediation":"Fix any of the following:\n  The complementary landmark is contained in another landmark."}]}

Reproduce: npm.cmd run qa:smoke → QA-SMOKE-04: axe-goal-plan (desktop)

Suggested fix: Review the recorded axe targets and remediation; authorize an application fix separately. Automated rule finding is not complete WCAG certification.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/0-axe-goal-plan.json, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/1-journey-boundary.txt, tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/test-failed-1.png, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/3-network-and-console.json, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/4-final-screen.png, tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/error-context.md, tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/trace.zip

### QA-AXE-DESKTOP-AXE-GOAL-PLAN-LANDMARK-MAIN-IS-TOP-LEVEL

P1 / MODERATE / CONFIRMED; route: /intelligence/business-agent.

Expected: No axe landmark-main-is-top-level violation in this state.

Actual: {"id":"landmark-main-is-top-level","impact":"moderate","help":"Main landmark should not be contained in another landmark","nodes":[{"target":[".agent-page"],"remediation":"Fix any of the following:\n  The main landmark is contained in another landmark."}]}

Reproduce: npm.cmd run qa:smoke → QA-SMOKE-04: axe-goal-plan (desktop)

Suggested fix: Review the recorded axe targets and remediation; authorize an application fix separately. Automated rule finding is not complete WCAG certification.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/0-axe-goal-plan.json, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/1-journey-boundary.txt, tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/test-failed-1.png, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/3-network-and-console.json, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/4-final-screen.png, tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/error-context.md, tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/trace.zip

### QA-AXE-DESKTOP-AXE-GOAL-PLAN-LANDMARK-NO-DUPLICATE-MAIN

P1 / MODERATE / CONFIRMED; route: /intelligence/business-agent.

Expected: No axe landmark-no-duplicate-main violation in this state.

Actual: {"id":"landmark-no-duplicate-main","impact":"moderate","help":"Document should not have more than one main landmark","nodes":[{"target":["#main-content"],"remediation":"Fix any of the following:\n  Document has more than one main landmark"}]}

Reproduce: npm.cmd run qa:smoke → QA-SMOKE-04: axe-goal-plan (desktop)

Suggested fix: Review the recorded axe targets and remediation; authorize an application fix separately. Automated rule finding is not complete WCAG certification.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/0-axe-goal-plan.json, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/1-journey-boundary.txt, tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/test-failed-1.png, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/3-network-and-console.json, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/4-final-screen.png, tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/error-context.md, tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/trace.zip

### QA-AXE-MOBILE-AXE-GOAL-PLAN-COLOR-CONTRAST

P1 / MAJOR / CONFIRMED; route: /intelligence/business-agent.

Expected: No axe color-contrast violation in this state.

Actual: {"id":"color-contrast","impact":"serious","help":"Elements must meet minimum color contrast ratio thresholds","nodes":[{"target":[".blocked[data-status=\"BLOCKED\"][_ngcontent-ng-c2587382897=\"\"]:nth-child(3) > small"],"remediation":"Fix any of the following:\n  Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1"},{"target":[".blocked[href$=\"sourcing\"][data-status=\"BLOCKED\"] > small"],"remediation":"Fix any of the following:\n  Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1"},{"target":[".blocked[href$=\"due-diligence\"][data-status=\"BLOCKED\"] > small"],"remediation":"Fix any of the following:\n  Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1"},{"target":[".blocked[data-status=\"BLOCKED\"][_ngcontent-ng-c2587382897=\"\"]:nth-child(6) > small"],"remediation":"Fix any of the following:\n  Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1"},{"target":[".blocked[data-status=\"BLOCKED\"][_ngcontent-ng-c2587382897=\"\"]:nth-child(7) > small"],"remediation":"Fix any of the following:\n  Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1"},{"target":[".blocked[href$=\"listings\"][data-status=\"BLOCKED\"] > small"],"remediation":"Fix any of the following:\n  Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1"}]}

Reproduce: npm.cmd run qa:smoke → QA-SMOKE-04: axe-goal-plan (mobile)

Suggested fix: Review the recorded axe targets and remediation; authorize an application fix separately. Automated rule finding is not complete WCAG certification.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/0-axe-goal-plan.json, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/1-journey-boundary.txt, tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/test-failed-1.png, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/3-network-and-console.json, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/4-final-screen.png, tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/error-context.md, tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/trace.zip

### QA-AXE-MOBILE-AXE-GOAL-PLAN-LANDMARK-COMPLEMENTARY-IS-TOP-LEVEL

P1 / MODERATE / CONFIRMED; route: /intelligence/business-agent.

Expected: No axe landmark-complementary-is-top-level violation in this state.

Actual: {"id":"landmark-complementary-is-top-level","impact":"moderate","help":"Aside should not be contained in another landmark","nodes":[{"target":[".commerce-next-action"],"remediation":"Fix any of the following:\n  The complementary landmark is contained in another landmark."}]}

Reproduce: npm.cmd run qa:smoke → QA-SMOKE-04: axe-goal-plan (mobile)

Suggested fix: Review the recorded axe targets and remediation; authorize an application fix separately. Automated rule finding is not complete WCAG certification.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/0-axe-goal-plan.json, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/1-journey-boundary.txt, tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/test-failed-1.png, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/3-network-and-console.json, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/4-final-screen.png, tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/error-context.md, tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/trace.zip

### QA-AXE-MOBILE-AXE-GOAL-PLAN-LANDMARK-MAIN-IS-TOP-LEVEL

P1 / MODERATE / CONFIRMED; route: /intelligence/business-agent.

Expected: No axe landmark-main-is-top-level violation in this state.

Actual: {"id":"landmark-main-is-top-level","impact":"moderate","help":"Main landmark should not be contained in another landmark","nodes":[{"target":[".agent-page"],"remediation":"Fix any of the following:\n  The main landmark is contained in another landmark."}]}

Reproduce: npm.cmd run qa:smoke → QA-SMOKE-04: axe-goal-plan (mobile)

Suggested fix: Review the recorded axe targets and remediation; authorize an application fix separately. Automated rule finding is not complete WCAG certification.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/0-axe-goal-plan.json, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/1-journey-boundary.txt, tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/test-failed-1.png, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/3-network-and-console.json, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/4-final-screen.png, tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/error-context.md, tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/trace.zip

### QA-AXE-MOBILE-AXE-GOAL-PLAN-LANDMARK-NO-DUPLICATE-MAIN

P1 / MODERATE / CONFIRMED; route: /intelligence/business-agent.

Expected: No axe landmark-no-duplicate-main violation in this state.

Actual: {"id":"landmark-no-duplicate-main","impact":"moderate","help":"Document should not have more than one main landmark","nodes":[{"target":["#main-content"],"remediation":"Fix any of the following:\n  Document has more than one main landmark"}]}

Reproduce: npm.cmd run qa:smoke → QA-SMOKE-04: axe-goal-plan (mobile)

Suggested fix: Review the recorded axe targets and remediation; authorize an application fix separately. Automated rule finding is not complete WCAG certification.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/0-axe-goal-plan.json, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/1-journey-boundary.txt, tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/test-failed-1.png, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/3-network-and-console.json, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/4-final-screen.png, tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/error-context.md, tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/trace.zip


## Suspected defects / failed assertions

These can overlap confirmed axe findings. A failed test is not automatically a functional product defect.

### QA-RUN-DESKTOP-001

P1 / MAJOR / SUSPECTED; route: See screenshot/trace; failure may be in test harness.

Expected: Scenario assertions pass using canonical disposable data.

Actual: Error: goal-plan: no serious/critical axe violations

expect(received).toEqual(expected) // deep equality

- Expected  -  1
+ Received  + 51

- Array []
+ Array [
+   Object {
+     "help": "Elements must meet minimum color contrast ratio thresholds",
+     "id": "color-contrast",
+     "impact": "serious",
+     "nodes": Array [
+       Object {
+         "remediation": "Fix any of the following:
+   Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1",
+         "target": Array [
+           ".blocked[data-status=\"BLOCKED\"][_ngcontent-ng-c2587382897=\"\"]:nth-child(3) > small",
+         ],
+       },
+       Object {
+         "remediation": "Fix any of the following:
+   Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1",
+         "target": Array [
+           ".blocked[href$=\"sourcing\"][data-status=\"BLOCKED\"] > small",
+         ],
+       },
+       Object {
+         "remediation": "Fix any of the following:
+   Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1",
+         "target": Array [
+           ".blocked[href$=\"due-diligence\"][data-status=\"BLOCKED\"] > small",
+         ],
+       },
+       Object {
+         "remediation": "Fix any of the following:
+   Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1",
+         "target":

Reproduce: npm.cmd run qa:smoke → Inspect QA-SMOKE-04 (desktop)

Suggested fix: Triage assertion, locator and application evidence before requesting a production fix.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/0-axe-goal-plan.json, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/1-journey-boundary.txt, tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/test-failed-1.png, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/3-network-and-console.json, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-04/4-final-screen.png, tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/error-context.md, tmp/qa-agent/5c2928f8ef249c37/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-desktop/trace.zip

### QA-RUN-MOBILE-001

P1 / MAJOR / SUSPECTED; route: See screenshot/trace; failure may be in test harness.

Expected: Scenario assertions pass using canonical disposable data.

Actual: Error: goal-plan: no serious/critical axe violations

expect(received).toEqual(expected) // deep equality

- Expected  -  1
+ Received  + 51

- Array []
+ Array [
+   Object {
+     "help": "Elements must meet minimum color contrast ratio thresholds",
+     "id": "color-contrast",
+     "impact": "serious",
+     "nodes": Array [
+       Object {
+         "remediation": "Fix any of the following:
+   Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1",
+         "target": Array [
+           ".blocked[data-status=\"BLOCKED\"][_ngcontent-ng-c2587382897=\"\"]:nth-child(3) > small",
+         ],
+       },
+       Object {
+         "remediation": "Fix any of the following:
+   Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1",
+         "target": Array [
+           ".blocked[href$=\"sourcing\"][data-status=\"BLOCKED\"] > small",
+         ],
+       },
+       Object {
+         "remediation": "Fix any of the following:
+   Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1",
+         "target": Array [
+           ".blocked[href$=\"due-diligence\"][data-status=\"BLOCKED\"] > small",
+         ],
+       },
+       Object {
+         "remediation": "Fix any of the following:
+   Element has insufficient color contrast of 3.52 (foreground color: #748b91, background color: #fcfdfc, font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1",
+         "target":

Reproduce: npm.cmd run qa:smoke → Inspect QA-SMOKE-04 (mobile)

Suggested fix: Triage assertion, locator and application evidence before requesting a production fix.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/0-axe-goal-plan.json, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/1-journey-boundary.txt, tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/test-failed-1.png, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/3-network-and-console.json, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-04/4-final-screen.png, tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/error-context.md, tmp/qa-agent/3b66a14fad8e8648/browser-artifacts/smoke-QA-SMOKE-04-business-a185d-plan-no-discovery-execution-mobile/trace.zip


## Usability recommendations

### QA-UX-CURRENCY-DESKTOP

P2 / MINOR / RECOMMENDATION; route: /products/new.

Expected: A seller should understand and explicitly confirm the intended pricing currency.

Actual: The new product form defaults to USD even in this Indian-seller journey; INR must be entered manually.

Reproduce: Create a brand → Open /products/new → Inspect Currency before entering a price

Suggested fix: Consider using an explicitly configured business currency or a prominent currency confirmation; do not infer currency silently.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-02/0-axe-catalog-empty.json, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-02/1-ux-observations.json, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-02/2-axe-catalog-detail.json, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-02/3-network-and-console.json, tmp/qa-agent/5c2928f8ef249c37/evidence/desktop-QA-SMOKE-02/4-final-screen.png

### QA-UX-CURRENCY-MOBILE

P2 / MINOR / RECOMMENDATION; route: /products/new.

Expected: A seller should understand and explicitly confirm the intended pricing currency.

Actual: The new product form defaults to USD even in this Indian-seller journey; INR must be entered manually.

Reproduce: Create a brand → Open /products/new → Inspect Currency before entering a price

Suggested fix: Consider using an explicitly configured business currency or a prominent currency confirmation; do not infer currency silently.

Retest: NOT_RETESTED. Evidence: tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-02/0-axe-catalog-empty.json, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-02/1-ux-observations.json, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-02/2-axe-catalog-detail.json, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-02/3-network-and-console.json, tmp/qa-agent/3b66a14fad8e8648/evidence/mobile-QA-SMOKE-02/4-final-screen.png

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

12 real Chrome axe scans; 8 rule occurrences; 2 incomplete rule/state occurrences retained for manual review. No rules were disabled. Critical/serious findings fail the scenario even when soft assertions allow later evidence collection. Keyboard checks cover Tab/Shift+Tab during owner setup, not all dialogs or assistive technology. This does not certify WCAG conformance.

## Missing flows / blocked tests

See [journeys and phased architecture](architecture.md). Full discovery → HUMAN selection → supplier → due diligence → economics, inventory/order/financial Decimal oracles, private-media, marketplace controls, cross-installation foreign IDs and desktop Electron remain pending. Real providers and all external execution are deliberately forbidden, not unblocked by test fixtures.

Fresh disposable schemas are created from canonical ORM metadata, not a migration replay. Health-ready output is attached; no fake Alembic head is stamped. Migration readiness can therefore be unavailable and is not certified. Original PC-first backup/restore certification remains untouched.

## Disposable cleanup

- desktop: PASS; vayujit_qa5c2928f8ef249c37_test; child exit 0; verified absent=true.
- mobile: PASS; vayujit_qa3b66a14fad8e8648_test; child exit 0; verified absent=true.

Only fresh token-matched QA databases are eligible for removal. Private synthetic media/evidence folders remain locally under ignored tmp/qa-agent. No shared Docker resources were changed.

## Runtime blockers

No runner startup blocker in this attempt. Failing assertions and remaining scope above remain open.

## Next implementation phase

Risk-first persisted seller journey, financial oracle and foreign-ID matrices; no autonomous production fixes.
