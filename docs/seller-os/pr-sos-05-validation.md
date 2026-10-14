# PR-SOS-05 — Unified Sales, Marketplace Fees, Profitability & Financial Reconciliation

**Classification:** **PR-SOS-05 — IMPLEMENTED / LOCAL CERTIFICATION PENDING**

## A–Z certification report

**A — Roadmap reconciliation.** PR-SOS-05 adds a financial-evidence projection on top of the canonical marketplace order, fee, refund, settlement, Product, and inventory authorities. It does not create a second order system or marketplace connector.

**B — Authority reuse.** Existing owner-scoped `MarketplaceAccount`, `MarketplaceOrder`, `MarketplaceOrderItem`, `MarketplaceFee`, `MarketplaceRefund`, `MarketplaceSettlement`, and `Product` models remain authoritative. New records are immutable source events, cost/fee evidence, calculation snapshots, and reconciliation projections.

**C — Architecture and changed files.** Added `commerce/financial_models.py`, `commerce/financial_router.py`, migration `20261201_0143_pr_sos_05_financial_intelligence.py`, head merge `20261201_0144_merge_seller_and_intelligence_heads.py`, focused API tests, the Angular `FinancialWorkspaceComponent`, typed service methods, date/marketplace filters, fee/alert/Business Agent panels, route/navigation links, marketplace-home link, and this report.

**D — Financial terminology.** The API exposes GMV/gross sales, discounts, refunds, net sales, fees/deductions, known direct costs, contribution, and estimated profit. Labels state the event-effective-date basis. Contribution is not formal accounting or tax advice.

**E — Monetary precision.** Inputs are Pydantic `Decimal`; persistence uses PostgreSQL `Numeric(14,2)` and deterministic half-up cent rounding. Currency is explicit and non-INR inputs are rejected unless an explicit account currency matches; no implicit conversion occurs.

**F — Sales facts.** `/api/v1/financial/events` accepts bounded synthetic or seller-entered event facts and preserves source event identity, order/product/settlement references, timestamps, source type, and provenance. Duplicate `(owner, account, source_event_id)` replays are idempotent. Canonical PR-SOS-04 orders, lines, refunds, and fees are projected when no duplicate financial event exists; missing order totals remain UNKNOWN.

**G — Cost attribution.** `/costs` stores effective-dated cost evidence with cost type, source, verification status, currency, and provenance. UNKNOWN cost amounts are nullable, historical versions select the latest effective record, missing cost remains visible, and it is never converted to zero or used to qualify estimated profit.

**H — Fee engine.** `/fee-rules` stores explicit, versioned, synthetic/modelled fee assumptions. `/fees` reports observed event deductions by type and labels missing fee evidence. No unverified provider schedule is hardcoded.

**I — Profitability.** `/summary` and `/profitability` calculate Decimal revenue, discounts, refunds, fees, shipping/fulfilment/tax deductions, known costs, contribution, and qualified estimate only when required evidence exists. Product rows use financial events or canonical order lines, carry calculation version, evidence status, basis, and missing inputs. `/calculations/recalculate` persists a durable owner-scoped snapshot with lineage; `/calculations` reconstructs it.

**J — Refund handling.** Refund events are separate from sale facts and reduce net sales only when an explicit refund event is present. Return/cancellation inference and inventory restocking are not performed by this projection.

**K — Tax boundaries.** Tax is a separate event/deduction category. The UI and API do not claim GST compliance, file returns, or make payments; tax evidence remains observed/modelled/unknown.

**L — Settlement reconciliation.** `/settlements/reconcile` persists expected, reported, verified, difference, status (`matched`, `mismatch`, `missing_evidence`, `unknown`), provenance, and version. Revisions retain prior values in provenance history; canonical reported settlements are shown as reported/unknown until expected or verified evidence exists. A reported/verified payout is never inferred from order ingestion.

**M — Financial APIs.** Owner-scoped endpoints are available at `/api/v1/financial/summary`, `/sales`, `/events`, `/costs`, `/fee-rules`, `/profitability`, `/fees`, `/settlements`, `/reconciliation`, `/alerts`, `/business-agent`, `/calculations/recalculate`, and `/calculations`. Reads support marketplace/date filters where applicable and filter by authenticated owner.

**N — Angular sales dashboard.** `/marketplaces/financials` is a guarded Seller OS route linked under Sell → Financials and from Marketplace overview. It has filter, loading, empty, error, incomplete, evidence-status, synthetic-provider, and read-only boundary states.

**O — Profitability workspace.** The workspace displays product-level server calculations, gross sales, deductions, known costs, contribution, qualified estimate or `UNKNOWN`, calculation version, and missing-input guidance. Angular does not recompute financial totals.

**P — Settlement workspace.** Expected/reported/verified amounts, difference, status, evidence status, marketplace, and provenance are displayed. No settlement row is presented as a bank payout or payment action.

**Q — Business Agent integration.** `/business-agent` provides read-only next actions for missing cost/fee evidence and financial review. It explicitly declares `authority=read_only`, `external_writes=false`, and HUMAN review requirements for corrections or payout actions.

**R — Synthetic provider fixtures.** Focused tests use marked disposable PostgreSQL data and `source_type=synthetic_fixture`; no Amazon/Flipkart transport, supplier contact, RFQ, purchase, payment, or external write was performed.

**S — Idempotency and provenance.** Duplicate source event replay returns the original row; cost versions and settlement keys are unique per owner; event lineage retains source identity, timestamps, payload, and provenance. Calculations are deterministic for a fixed event set.

**T — Security and owner isolation.** Every endpoint uses `current_user`; account reconciliation validates owner scope; foreign account access is 404. External provider source types and unsupported currencies are rejected. `ck_users_single_owner` was not changed.

**U — Database migrations.** Fresh disposable database `vayujit_prsos05_test` reached merged head `20261201_0144`. The additive migration creates financial tables, constraints, indexes, foreign keys, and uniqueness rules. Existing `vayujit_test` was not modified by certification.

**V — Backend regression results.** PR-SOS-05 focused suite: **4 passed** (including canonical order/fee/refund/settlement projection, UNKNOWN cost, idempotent events, and durable snapshot replay). PR-SOS-04 focused regression: **8 passed**. Fresh adjacent reruns passed PR-SOS-01 **6/6**, Amazon authorization controls **3**, and Flipkart authorization controls **2**. A combined unfiltered Amazon+Flipkart attempt hung in the existing fixture startup path and was stopped; no PR-SOS-05 failure was observed. Earlier PR-SOS-01–03 evidence remains **14 passed** from the PR-SOS-04.2 certification matrix.

**W — Browser and accessibility evidence.** Angular production build and lint passed; the pre-change Angular suite baseline was green. The existing isolated Chrome/CDP + axe 4.11 infrastructure is available from PR-SOS-04.2. A dedicated 30-step authenticated PR-SOS-05 browser/axe run was **not executed in this turn**; therefore this report does not claim fresh browser certification beyond route/build coverage.

**X — Static quality gates.** Focused Black, Ruff, strict mypy, and compileall pass for the new backend modules. The pre-change Angular baseline was **62 test files / 223 tests passed**. The post-template-change rerun built successfully, but the current environment hit **2 unrelated 5-second async timeouts** in `intelligence-workspace.component.spec.ts` and `website-intelligence.component.spec.ts` (**60 files passed / 221 tests passed, 2 failed**); no financial workspace test failed. Angular lint has **0 errors and 2 pre-existing lifecycle warnings**, and production build passes with the existing initial bundle budget warning (**514.05 kB vs 500 kB**). `git diff --check` passed with exit code 0; Git emitted only existing LF/CRLF normalization warnings.

**Y — Golden database, external effects, and limitations.** No golden database modification, commit, push, external marketplace call, payment/refund, bank transfer, supplier contact, procurement, tax filing, or marketplace write occurred. Synthetic evidence is not provider fee certification, settlement ingestion, bank payout proof, production accounting, or tax compliance.

**Z — Final classification.** Local financial API, canonical order/fee/refund/settlement projection, durable snapshots, persistence, idempotency, owner-scope, migration, Angular, static-quality, repository-hygiene, and selected adjacent Seller OS gates are validated. The required fresh authenticated PR-SOS-05 Chrome/CDP + axe matrix was not executed in this turn because the isolated browser did not have a usable authenticated disposable owner session; the release gate remains pending. No code path enables live external writes.

## Focused commands

```text
apps/api/.venv/Scripts/pytest.exe tests/test_pr_sos_05_financials.py -q -o addopts=''
apps/api/.venv/Scripts/pytest.exe tests/test_pr_sos_04_inventory_orders.py -q -o addopts=''
npm.cmd run test --workspace @vayujit/web -- --watch=false
npm.cmd run build --workspace @vayujit/web
npm.cmd run lint --workspace @vayujit/web
```

All financial mutations are synthetic/local fixture ingestion or explicit seller-entered evidence. The workspace remains read-only toward external marketplaces.

## PR-SOS-05.1 closure

The follow-on PR-SOS-05.1 certification is complete. See
[`pr-sos-05-1-validation.md`](pr-sos-05-1-validation.md) for the full A–Z
evidence report: 7/7 focused financial tests, 22 adjacent regressions, 30/30
authenticated browser scenarios, and 12 axe scans with zero violations and
zero incomplete checks. Final classification:
**PR-SOS-05.1 — FULLY VALIDATED (LOCAL / SYNTHETIC / NO LIVE EXTERNAL
MUTATIONS)**.

## Endpoint coverage note

The read-only financial API also exposes `/profitability/sku`,
`/profitability/order`, `/missing-costs`, `/refund-impact`,
`/revenue-trends`, and `/marketplace-comparison` with the same owner, currency,
date-filter, provenance, and no-external-write boundaries.

The financial workspace renders the trend, channel comparison, refund-impact,
fee, product profitability, settlement, alert, and Business Agent panels while
preserving explicit `UNKNOWN` values for incomplete evidence.

### Final frontend rerun update

After the final analytics-panel changes, the full Angular suite completed with
**62 test files and 223/223 tests passed**. A prior diagnostic run had two
unrelated five-second intelligence-test timeouts; the clean final rerun passed
all tests. Build and lint remained green.
