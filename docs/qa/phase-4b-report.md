# Phase 4B executed stock-entry browser report

PASS_BOUNDED_OPENING_STOCK; final combined decision: **INITIAL_STOCK_ENTRY_VALIDATED_BOUNDED_LOCAL_SCOPE**. Application certification **INCOMPLETE**.

| Scenario | Context | Result | Duration ms |
| --- | --- | --- | --- |
| QA-P4B-01: empty inventory to persisted opening, ledger and refresh | desktop | passed | 6008 |
| QA-P4B-02: invalid inputs, zero balance, cancel and keyboard review | desktop | passed | 4190 |
| QA-P4B-03: variant custom SKU review reload and explicit reapproval | desktop | passed | 2475 |
| QA-P4B-04: response lost after commit replays without duplicate stock | desktop | passed | 2402 |
| QA-P4B-05: stock appears after review conflict preserves balance | desktop | passed | 2461 |
| QA-P4B-06: unavailable product and API recovery remain fail closed | desktop | passed | 2253 |
| QA-P4B-07: filtered navigation and saved deep link history | desktop | passed | 2691 |
| QA-P4B-08: auth and unknown installation identifiers do not leak stock | desktop | passed | 1520 |
| QA-P4B-01: empty inventory to persisted opening, ledger and refresh | mobile | passed | 5549 |
| QA-P4B-02: invalid inputs, zero balance, cancel and keyboard review | mobile | passed | 3463 |
| QA-P4B-03: variant custom SKU review reload and explicit reapproval | mobile | passed | 2217 |
| QA-P4B-04: response lost after commit replays without duplicate stock | mobile | passed | 2142 |
| QA-P4B-05: stock appears after review conflict preserves balance | mobile | passed | 2276 |
| QA-P4B-06: unavailable product and API recovery remain fail closed | mobile | passed | 2012 |
| QA-P4B-07: filtered navigation and saved deep link history | mobile | passed | 2379 |
| QA-P4B-08: auth and unknown installation identifiers do not leak stock | mobile | passed | 1301 |

26 axe scans, 0 violations, 1 incomplete rule/state occurrences (not PASS). See [exact scans](phase-4b-accessibility.json), [JSON network/screenshot references](phase-4b-report.json), [control captures](phase-4b-route-control-coverage.json), and [validation](phase-4b-validation.md).
