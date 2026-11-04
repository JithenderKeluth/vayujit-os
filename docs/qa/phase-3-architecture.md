# QA Phase 3 — operational architecture and seller contracts

This extends `qa/run.mjs`, the Phase 1 Playwright reporter, schemas, independent
oracles and token-marked PostgreSQL fixtures. It does not replace earlier tests
or authorize production fixes. See [actual execution](phase-3-validation.md).

## Audited capabilities

| Seller task / route | Canonical API / models | Supported and deliberately bounded |
| --- | --- | --- |
| Stock: `/marketplaces/inventory` | `/api/v1/inventory`; InventoryItem, InventoryMovement, InventoryReservation, ChannelSkuMapping | Create stock through API; adjust with version and reason; reserve/release/consume; inspect ledger and map SKU in UI. No inventory publication. Initial stock-record creation is not exposed in this workspace. |
| Orders: `/marketplaces/orders` | `/api/v1/orders/fake/events`, `/orders/{id}`, `/orders/reconciliation/summary`; MarketplaceOrder, OrderItem, OrderEvent | Local explicit synthetic events create pending orders and reservations; cancel releases holds, ship consumes stock, return does not silently restock. UI inspects/filters, not remote fulfilment/refund dispatch. |
| Sales: `/marketplaces/financials` | `/api/v1/financial/{events,costs,summary,profitability,refund-impact,settlements,calculations}`; FinancialEvent, FinancialCostEvidence, FinancialCalculationSnapshot, FinancialSettlementReconciliation | Explicit monetary evidence, effective dates, INR, event deduplication, fee/cost/refund arithmetic and reconciliation. No bank payout or inferred tax/fee schedule. |
| Operational Business Agent | `/api/v1/financial/business-agent`, `/orders/insights`, `/operations/action-center/briefing` | Read-only guidance, source evidence, confidence/freshness and missing-input disclosures. Not an autonomous execution or comprehensive financial-planning authority. |
| Action Center: `/operations/action-center` | `/api/v1/operations/action-center`; OperationalSignal, OperationalSignalTransition, OperationalBriefing | Scan; acknowledge, snooze, resolve/reopen; inspect source/history. Action request returns approval-required and does not execute. A complete persisted operational approve/reject/retry workflow is not implemented here. |
| Canonical commercial decisions | Existing PR-6 HUMAN recommendations/decisions, exercised by Phase 2 regressions | Reuse, never invent a parallel operational approval system. Keep ordinary signal acknowledgement distinct from commercial HUMAN approval. |

Actual implementation was read in `commerce/{inventory_router,orders_router,
financial_router,models,financial_models,schemas}.py`,
`operations/{action_center_router,operational_models}.py`, their Angular
workspaces and existing PR-SOS-04/05/06 tests. The repository inventory lists
154 routes; listing a route is not evidence that it was executed.

## Independent expected values

Inventory available-to-promise is on-hand minus reserved minus damaged,
nonnegative. Writes must respect version checks and stock conservation. A return
does not imply inspected sellable stock or a financial refund.

The existing financial event contract rounds **each evidence amount** to two
decimal places using ROUND_HALF_UP. The independent oracle imports only Python
Decimal, never a production calculator. It tests net sales = sale minus discount
minus refund; contribution = net sales minus explicit fee/shipping evidence
minus cost evidence; margin is contribution / net sales times 100. These are
the application's modeled contribution rules, not real net-profit accounting,
per-unit COGS policy, GST advice or a real provider fee schedule.

The fixed loss example independently yields sale 100.01, discount 0.01, refund
1.01, fees 2.02, cost 200.01, contribution -103.04, margin -104.09 percent.
Missing cost remains UNKNOWN; a recorded known zero is different from unknown.
Supported cost evidence has no explicit stale enum; the suite uses a newer
UNKNOWN revision rather than inventing a production freshness field.

## Execution and safety

Each desktop/mobile run gets a new random 16-hex token, fresh
`vayujit_qa<token>_test` database, project marker and suite token. `.env` is not
loaded. No existing application instance, Docker project or backup volume is
used. Canonical owner setup creates one owner; `ck_users_single_owner` is not
changed. Accounts are sandbox-only, named QA SYNTHETIC, disabled and contain no
credentials. Real provider kill switches and socket/DNS egress denial remain on.

The proxy allowlist adds only supported local writes. It rejects nonfixture
supplier modes, account credentials, production account setup and remote worker/
connector/marketplace actions. Negative tests target the non-dispatching Action
Center authority, never a real publication endpoint.

Phase 3's QA-only supervisor starts a dedicated API child and can restart **that
owned process only**. Its restart control requires the exact QA token and a
canonical authenticated session. A changed PID, persisted session and balances
are asserted. The parent retains database ownership and stops its child before
marker-protected cleanup. This adds no production endpoint or authentication
bypass. An independent subprocess also reconstructs persisted table counts and
stock invariants read-only. Neither test certifies Windows-service, database
server, publishing-worker or PC-first backup recovery.

If a runner crashes, `qa/cleanup_disposable.py --token <exact-token>` refuses
anything except the exact loopback QA name and matching project/suite markers.
It refuses active database sessions rather than terminating them. It records
recovery evidence separately and never rewrites a failed original cleanup gate.

## Browser scope and evidence

Six scenarios per viewport (1440x1000 and 390x844): stock/ledger/stale form;
order source/status/empty filter; rounded financial loss/unknown settlement;
signal lifecycle/history/resolved filter; network timeout, committed-response
loss, replay and owned API restart; four original mobile contrast states.

Console errors, failed requests, route/status errors, screenshots and failed
traces are retained. A failed assertion is SUSPECTED until source/evidence review;
axe findings are exact automated rule findings, not full WCAG certification.

The mobile review scrolls original affected elements into view and reruns the
established axe contrast rule on those targets. Targeted diagnostics supplement,
not replace, full-document scans. Some clipped captions/cells remain incomplete;
they are not automatically passed or declared compliant. No rules, severities or
thresholds are suppressed to turn a failure green.

## Reporting preservation

`phase-3-report.{json,md}`, `phase-3-coverage.json` and reviewed findings use the
existing finding schema with area, journey and business impact. IDs are stable
per root cause or scenario/viewpoint. Confirmed defects, suspected assertions,
missing flows and recommendations remain distinct. The six original usability
occurrences remain open; original Phase 1/2 findings and their resolution ledger
remain intact. Timestamped histories and SHA256 companions preserve prior runs.
No claim of independent third-party audit or complete application certification.
