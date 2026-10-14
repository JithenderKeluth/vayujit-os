# PR-SOS-05.1 — Financial Reliability, Browser and Accessibility Certification

**Classification:** **PR-SOS-05.1 — FULLY VALIDATED (LOCAL / SYNTHETIC / NO LIVE EXTERNAL MUTATIONS)**

This report is the closure addendum for PR-SOS-05. It supersedes the earlier
“local certification pending” status for the financial workspace. Validation used
the normal authenticated application routes, a disposable PostgreSQL database,
synthetic seller-entered financial facts, and direct Chrome/CDP automation. No
golden database, live provider, supplier, marketplace, banking, tax, or external
write was used.

## A–Z certification report

### A — Scope and authority

The financial workspace is an owner-scoped projection over the canonical
marketplace account, order, order-line, refund, fee, settlement, Product and
inventory authorities. It does not create a second order or marketplace system.

### B — Disposable environment

Validation ran against `vayujit_pr5_1_test`, a disposable PostgreSQL database
with the marker `vayujit-os-disposable-test-database-v1`. Alembic replay reached
head `20261201_0144` (mergepoint). The existing Angular dev server and an
isolated API process on `127.0.0.1:8025` were used; the API rewrites in the CDP
harness only target that local process.

### C — Corrective implementation

The bounded fixes were:

* `/financial/alerts` now treats nullable/unknown contribution as `UNKNOWN`
  instead of attempting a Decimal conversion and returning 500.
* Added an owner-scoped read-only `GET /api/v1/financial/fee-rules` projection
  for explicit, versioned assumptions; it never silently applies modeled rules
  to observed facts.
* Expanded focused financial tests for rounding, refunds, idempotency,
  effective-dated costs, negative contributions, fee-rule versions, settlement
  states, isolation, currencies, and durable lineage.
* Added accessible labelled, focusable regions around all financial tables and
  labelled the filter and summary regions.

### D — Financial arithmetic

Revenue, fees, costs, refunds, contribution, and reconciliation values use
Decimal arithmetic and deterministic half-up cent rounding. Missing evidence is
represented as `UNKNOWN`; it is never coerced to zero.

### E — Evidence states

Observed, modelled, derived, unknown, incomplete, and not-comparable states are
shown with source/provenance and guidance. The UI does not infer demand, rank,
tax compliance, profitability, or payout completion.

### F — Focused API regression

Command:

```text
VAYUJIT_TEST_DATABASE_URL=.../vayujit_pr5_1_test \
apps/api/.venv/Scripts/pytest.exe apps/api/tests/test_pr_sos_05_financials.py -q -o addopts=''
```

Result: **7 passed, 17 warnings**, 65.62 seconds. The seven tests cover the
financial lifecycle and the A–R requirements (sales facts, Decimal rounding,
unknown/incomplete evidence, costs, fees, refunds, idempotent replay,
settlements, owner/currency/snapshot boundaries, and alerts).

### G — Adjacent regression matrix

Command:

```text
apps/api/.venv/Scripts/pytest.exe \
  apps/api/tests/test_pr_sos_01_catalog.py \
  apps/api/tests/test_pr_sos_02_amazon_controls.py \
  apps/api/tests/test_pr_sos_03_flipkart_controls.py \
  apps/api/tests/test_pr_sos_04_inventory_orders.py -q -o addopts=''
```

Result: **22 passed, 47 warnings**, 127 seconds. No production or golden
database was used.

### H — Authenticated browser certification

The direct Chrome/CDP harness executed all **30/30 scenarios PASS**:

1. login; 2. financial route; 3. empty state; 4. Amazon account fixture;
5. Amazon summary; 6. Flipkart account fixture; 7. comparison; 8. order
profitability; 9. fee breakdown; 10. missing-cost state; 11. known-cost
contribution; 12. missing-cost warning; 13. missing-fee warning; 14. negative
contribution alert; 15. refund creation; 16. refund impact; 17. matched
settlement; 18. expected-payout display; 19. mismatch discrepancy; 20.
reconciliation; 21. marketplace filter; 22. date filter; 23. SKU filter; 24.
product filter; 25. Business Agent read-only state; 26. refresh preservation;
27. Back/Forward route and filter preservation; 28. deep link; 29. logout;
30. protected-route redirect.

Representative API outcomes were HTTP 200/201, Amazon gross `200.00`, fees
`20.00`, known-cost contribution `235.00`, negative-contribution alert after a
`500.00` cost, matched payout `175.00`, and mismatch difference `-5.00`.

### I — Accessibility engine

Authenticated `axe-core` scans at populated and filtered-empty states across
320, 360, 390, 768, 1024, and 1440 pixels produced **12 scans, 0 violations,
0 incomplete, 7,718 passes**. The first scan exposed four serious
`scrollable-region-focusable` findings; labelled focusable table regions fixed
them. A second pass exposed 12 incomplete prohibited-ARIA checks; the bounded
group/region roles fixed those, and the final run is the result above. Automated
axe results are not presented as a complete WCAG claim.

### J — Keyboard and responsive browser checks

At every required width (320/360/390/768/1024/1440), document overflow was
false. The 18-step Tab sequence reached the skip link, menu, navigation,
filters, Refresh Evidence, and all four table regions; Shift+Tab returned to the
previous region. Enter activation of Refresh Evidence and Space activation of
the marketplace select retained `/marketplaces/financials`; Escape retained the
route. No keyboard trap was observed.

### K — Security and isolation

All financial reads and writes remain owner-scoped. Synthetic account fixtures,
financial events, fee rules, costs, settlements, alerts, and snapshots cannot be
read across owners. Currency mismatches are rejected, replay keys are
idempotent, and no external provider transport is called.

### L — Lineage and snapshots

Events preserve source event identity, account/order/product/settlement
references, timestamps, source type, provenance, calculation version, and
evidence status. Recalculation snapshots reconstruct from durable rows.

### M — Refunds and settlements

Refunds are explicit events and reduce net sales only when present. Settlement
reconciliation persists expected/reported/difference/status and distinguishes
matched, mismatch, missing-evidence, and unknown states.

### N — Business Agent boundary

The Business Agent panel is explicitly read-only. Browser evidence confirmed
`external_writes: false`; no sourcing, supplier contact, RFQ, purchase, payment,
or marketplace mutation can be initiated from this workspace.

### O — Frontend quality

The final Angular suite passed **62 test files / 223 tests**. Production build
completed successfully. Lint completed with **0 errors and 2 pre-existing
warnings** in unrelated `catch-up-dialog` and `reschedule-dialog` lifecycle
interfaces. The initial bundle is 514.04 kB against a 500 kB warning budget;
this is a warning, not a build failure.

### P — Python quality

Black check: 2 files unchanged. Ruff: all checks passed. Strict mypy on the
financial router: no issues. `compileall` completed successfully.

### Q — Migration validation

The full disposable Alembic chain replayed successfully and current head was
verified as `20261201_0144`.

### R — Defect history

The only PR-SOS-05.1 defect discovered was the `UNKNOWN` Decimal conversion in
alerts, plus the accessibility findings documented above. Each was fixed in the
smallest bounded scope and the focused/browser suites were rerun.

### S — Safety

No supplier or provider was contacted. No RFQ, purchase, payment, procurement,
tax filing, banking operation, marketplace mutation, commit, or push occurred.

### T — Test evidence index

Browser result JSON and screenshots are under `tmp/ux-browser/`, including
`prsos051-browser-results.json`, `prsos051-axe-results.json`,
`prsos051-empty.png`, and `prsos051-populated-1440.png`. Reproducible harnesses
are `cdp-prsos051-financial.mjs`, `cdp-prsos051-axe.mjs`, and
`cdp-prsos051-keyboard.mjs`.

### U — Trust limitations

This certifies local synthetic behavior only. Live provider fee schedules,
settlements, bank reconciliation, accounting, GST/tax compliance, and external
marketplace data remain outside scope.

### V — Documentation updates

This report is the PR-SOS-05.1 closure document. The prior PR-SOS-05 report,
roadmap, and capability matrix receive closure addenda pointing here.

### W — Worktree policy

The repository was not reset or cleaned because it contains historical work from
earlier milestones. Only the bounded PR-SOS-05.1 changes are attributed here;
unrelated existing modifications remain untouched.

### X — External-write confirmation

The test database, API, Angular app, and browser are local. CDP request routing
was restricted to the local API; no network request to Brave, Amazon, Flipkart,
or any supplier was made.

### Y — Final decision

**PR-SOS-05.1 — FULLY VALIDATED (LOCAL / SYNTHETIC / NO LIVE EXTERNAL MUTATIONS)**

All applicable local financial, browser, accessibility, keyboard, isolation,
migration, and quality gates passed. The remaining limitations are explicitly
live-provider and accounting certifications, not PR-SOS-05.1 blockers.

### Z — Reproduction summary

Use the disposable database URL, start the isolated API on port 8025, run the
focused and adjacent pytest commands above, run the Angular test/lint/build
commands, then execute the three CDP harnesses. The resulting counts and
classification should match this report.

