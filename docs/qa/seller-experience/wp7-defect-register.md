# WP7 — Defects, hypotheses and reconciliation

| ID | Priority | Root cause / impact | Minimal correction / required follow-up | Current disposition |
| --- | --- | --- | --- | --- |
| SE-WP7-HARNESS-003 | P3 | An older financial regression expected pr-sos-05-v1 after WP6B legitimately advanced the calculation contract to v2. Independent expected monetary values passed before that version assertion. | Update only the obsolete expected calculation version to v2; arithmetic and authority assertions retained. Rerun 7 finance plus 28 WP6B tests. | RESOLVED_35_FOCUSED_REGRESSIONS_PASS |
| SE-WP7-RESPONSIVE-001 | P2 | Table intrinsic minimum widths escape the panel; no bounded keyboard scroll region. | Named focusable scroll wrappers preserve all columns and explicit column scopes. | RESOLVED_IN_FOCUSED_BROWSER_RETEST |
| SE-WP7-RESPONSIVE-002 | P2 | Form grid/control intrinsic minimum width expands the form to 411.59px at 390px viewport. | Bounded shrinkable form track/labels/controls; no field or validation removed. | RESOLVED_IN_FOCUSED_BROWSER_RETEST |
| SE-WP7-RESPONSIVE-003 | P2 | AI grid/form intrinsic sizing and unbounded history table; long legitimate Product option widens the page. | Shrinkable grid/control boundaries; named focusable history table wrapper and preserved headers. | RESOLVED_IN_FOCUSED_BROWSER_RETEST |
| SE-WP7-RESPONSIVE-004 | P2 | Eight-column jobs table has no constrained scrolling container. | Local shrinkable page/card with named keyboard-scrollable region; no job action enabled. | RESOLVED_IN_FOCUSED_BROWSER_RETEST |
| SE-WP7-HARNESS-001 | P2 | Fixture host45s shutdown deadline can preempt existing90s guarded DROP. Separately, actual DROP encountered CheckpointDone wait and OperationalError under aggregate work. | Host waits configured bounded SQL timeout plus30s; guards and SQL timeout unchanged. Serial continuation and exact signed recovery; old failures retained. | GUARDED_RECOVERY_VERIFIED_INFRA_RELIABILITY_LIMIT_REMAINS |
| SE-WP7-HARNESS-002 | P3 | WP3 copy assertion predates WP4 truthful manual-product text; surface menu locator matches both Application and Advanced summaries. | Exact current manual-product qualification; direct-child menu summary, not weaker semantic assertions. | HARNESS_CORRECTED; SEE_ACCEPTED_REPLAY |
| SE-WP7-COVERAGE-001 | P1 | Whole-application supported artifact/action, recovery and manual accessibility matrix not fully executed. | Complete the explicitly enumerated missing local/deterministic states before certifying; do not promote route renders into feature passes. | OPEN_CERTIFICATION_BLOCKER_NOT_A_CONFIRMED_PRODUCTION_CODE_DEFECT |

## All original20 browser findings

| Original ID | Historical disposition | Resolution ledger | WP7 bounded retest | Evidence |
| --- | --- | --- | --- | --- |
| SE-BROWSER-001 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp1-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/d1dba7f1ef3fa603/wp1-final-browser.json |
| SE-BROWSER-002 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp1-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/d1dba7f1ef3fa603/wp1-final-browser.json |
| SE-BROWSER-003 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp1-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/d1dba7f1ef3fa603/wp1-final-browser.json |
| SE-BROWSER-004 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp1-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/d1dba7f1ef3fa603/wp1-final-browser.json |
| SE-BROWSER-005 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp2-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/03496e6c4077a837/wp2-browser.json |
| SE-BROWSER-006 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp3-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/623633c485ad56de/wp3-retest.json |
| SE-BROWSER-007 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp3-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/623633c485ad56de/wp3-retest.json |
| SE-BROWSER-008 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp2-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/03496e6c4077a837/wp2-browser.json |
| SE-BROWSER-009 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp6-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/21aca7c922ea66ca/wp6-retest.json |
| SE-BROWSER-010 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp4-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/223c79f17f3ffc99/wp4-retest.json |
| SE-BROWSER-011 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp2-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/03496e6c4077a837/wp2-browser.json |
| SE-BROWSER-012 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp5-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/c8e9f313baf2cbde/wp5-retest.json |
| SE-BROWSER-013 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp3-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/623633c485ad56de/wp3-retest.json |
| SE-BROWSER-014 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp2-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/03496e6c4077a837/wp2-browser.json |
| SE-BROWSER-015 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp3-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/623633c485ad56de/wp3-retest.json |
| SE-BROWSER-016 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp3-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/623633c485ad56de/wp3-retest.json |
| SE-BROWSER-017 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp6-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/21aca7c922ea66ca/wp6-retest.json |
| SE-BROWSER-018 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp4-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/223c79f17f3ffc99/wp4-retest.json |
| SE-BROWSER-019 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp4-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/223c79f17f3ffc99/wp4-retest.json |
| SE-BROWSER-020 | RESOLVED_BOUNDED_PRIOR_WP | docs/qa/seller-experience/wp6-resolution.json | BOUNDED_RESOLUTION_RETESTED | tmp/qa-seller-browser/21aca7c922ea66ca/wp6-retest.json |

## Original audit and Phase4C identifiers

| ID | Disposition | Fresh correlated evidence, if available |
| --- | --- | --- |
| QA-AXE-DESKTOP-AXE-GOAL-PLAN-COLOR-CONTRAST | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-AXE-DESKTOP-AXE-GOAL-PLAN-LANDMARK-COMPLEMENTARY-IS-TOP-LEVEL | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-AXE-DESKTOP-AXE-GOAL-PLAN-LANDMARK-MAIN-IS-TOP-LEVEL | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-AXE-DESKTOP-AXE-GOAL-PLAN-LANDMARK-NO-DUPLICATE-MAIN | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-AXE-MOBILE-AXE-GOAL-PLAN-COLOR-CONTRAST | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-AXE-MOBILE-AXE-GOAL-PLAN-LANDMARK-COMPLEMENTARY-IS-TOP-LEVEL | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-AXE-MOBILE-AXE-GOAL-PLAN-LANDMARK-MAIN-IS-TOP-LEVEL | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-AXE-MOBILE-AXE-GOAL-PLAN-LANDMARK-NO-DUPLICATE-MAIN | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-P2-02 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-P2-UX-ECONOMICS-DESKTOP | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-P2-UX-ECONOMICS-MOBILE | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-P3-GAP-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-P3-GAP-002 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-P3-GAP-003 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-P4-API-67A1C8127DF2 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-P4-SURFACE-AI | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-P4-SURFACE-INTELLIGENCE | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-P4-SURFACE-MARKETPLACES | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-P4-UX-OVERFLOW-4A67C5636387 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-P4-UX-OVERFLOW-805927FDFA67 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-P4-UX-RESEARCH-LENGTH | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-P4A-A11Y-MANUAL-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-P4C-04 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-RUN-DESKTOP-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-RUN-MOBILE-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-SMOKE-02 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-SMOKE-04 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-UX-CURRENCY-DESKTOP | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-UX-CURRENCY-MOBILE | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-UX-NAV-CURRENT-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| QA-UX-PRE-RUN-MODE-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-AUTHORITY-001 | BOUNDED_CORRELATED_CORRECTION_RETESTED | tmp/qa-seller-browser/03496e6c4077a837/wp2-browser.json |
| SE-AUTHORITY-002 | BOUNDED_CORRELATED_CORRECTION_RETESTED | tmp/qa-seller-browser/03496e6c4077a837/wp2-browser.json |
| SE-BROWSER-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-CONTEXT-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-CONTEXT-002 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-CONTEXT-003 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-CONTEXT-004 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-CONTEXT-005 | BOUNDED_CORRELATED_CORRECTION_RETESTED | tmp/qa-seller-browser/d1dba7f1ef3fa603/wp1-final-browser.json |
| SE-CONTEXT-006 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-COVERAGE-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-ERROR-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-ERROR-002 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-HANDOFF-001 | BOUNDED_CORRELATED_CORRECTION_RETESTED | tmp/qa-seller-browser/03496e6c4077a837/wp2-browser.json |
| SE-HANDOFF-002 | BOUNDED_CORRELATED_CORRECTION_RETESTED | tmp/qa-seller-browser/623633c485ad56de/wp3-retest.json |
| SE-HANDOFF-003 | BOUNDED_CORRELATED_CORRECTION_RETESTED | tmp/qa-seller-browser/d1dba7f1ef3fa603/wp1-final-browser.json |
| SE-HANDOFF-004 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-IA-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-IA-002 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-IA-003 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-JOURNEY-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-METRIC-001 | BOUNDED_CORRELATED_CORRECTION_RETESTED | tmp/qa-seller-browser/c8e9f313baf2cbde/wp5-retest.json |
| SE-OPS-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-STATE-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-UX-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-UX-002 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-UX-003 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-WP4-A11Y-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-WP4-UX-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-WP5-PRICE-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-WP6-ADS-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |
| SE-WP6-VIDEO-001 | OPEN_OR_PARTIAL_OR_UNVERIFIED_NOT_SILENTLY_CLOSED | NOT TESTED |

A correlated correction is not a blanket closure of a broader original hypothesis. Currency-default UX, comprehension of long evidence pages, Trends/CampaignVideo/Ads-account detail identity hypotheses, generic action execution, accounting history and historical account-list502 remain explicitly open/partial/unverified unless the exact state was exercised. Original Advanced-link contrast suspicion has bounded prior measurements and fresh axe evidence, not all-theme/screen-reader certification.
