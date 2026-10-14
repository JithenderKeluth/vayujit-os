# PR-SOS-04 — Unified Inventory, Multi-Channel Orders & Overselling Protection

**Date:** 2026-10-12  
**Classification:** **PR-SOS-04 — FULLY VALIDATED (LOCAL / FAKE MARKETPLACE ORDER PROVIDERS / NO LIVE EXTERNAL MUTATIONS)**

This report records the bounded local implementation. It does not claim live
Amazon or Flipkart connectivity, provider acknowledgement, fulfilment, payment,
or marketplace mutation. No golden database, supplier, RFQ, procurement, or
external commercial system was touched.

## A–Z validation report

### A. Scope and authority audit

The existing `Product`, catalog variant, `MarketplaceAccount`, marketplace
listing, order, audit, owner-session, and connector authorities remain the
system of record. PR-SOS-04 adds the missing canonical local stock and event
boundaries; it does not duplicate the catalog or marketplace adapters.

### B. Backend implementation

Added owner-scoped `InventoryItem`, append-only `InventoryMovement`,
`InventoryReservation`, `ChannelSkuMapping`, and `MarketplaceOrderEvent`
models plus migration `20261020_0160_unified_inventory_orders.py`.

### C. Canonical inventory

`/api/v1/inventory` lists on-hand, reserved, damaged, ATP, version, location,
and reconciliation values. Opening balances and human adjustments are
idempotent, version-checked, owner-scoped, and recorded in the immutable ledger.

### D. Reservations

`/{item_id}/reserve` uses a row lock and ATP check. Release and consume are
explicit transitions and append ledger movements. Negative available stock is
rejected rather than coerced.

### E. Channel-SKU mappings

`/api/v1/inventory/mappings` validates account, listing, and owner context and
rejects conflicting mappings. Mapping provenance is local/read-only and human
configured.

### F. Fake provider boundary

`/api/v1/orders/fake/events` is explicitly synthetic and network-free. It
supports new-order, cancel, ship, and return events, preserving event payload,
version, status, and error/reconciliation state.

### G. Guarded order ingestion

New orders lock all mapped inventory rows before checking ATP. Insufficient
stock rejects the event without creating an order or reservation. Duplicate
event IDs and duplicate remote orders return the canonical order without
reapplying stock mutations.

### H. Human adjustment safety

Opening balance and adjustment records identify `HUMAN` actor type and retain
reason, idempotency key, before/after balances, and read-only provenance.

### I. Idempotency

Focused regression coverage proves opening balance replay, reservation replay,
fake order replay, and lifecycle replay do not double-count stock.

### J. Lifecycle and returns

Cancellation releases reservations; shipment consumes reserved/on-hand stock;
returns are recorded as an order state without automatically returning units to
sellable inventory. A return-receipt workflow remains a later evidence-backed
human action.

### K. Reconciliation

`/api/v1/orders/reconciliation/summary` and `/insights` expose low-stock,
out-of-stock, active reservation, failure, and next-action projections for the
Business Agent. They are read-only and do not rank or purchase inventory.

### L. Owner isolation

All new queries scope by the authenticated owner. Account, listing, product,
inventory, reservation, and order IDs are never accepted as proof of ownership.

### M. Migration

Fresh disposable PostgreSQL database `vayujit_pr_sos04_test` replayed all
migrations through `20261020_0160`. The marker-guarded fixture reset completed
before and after each focused test. A predecessor replay
`20261020_0160 -> 20261019_0159 -> 20261020_0160` also completed successfully.

### N. Focused tests

`tests/test_pr_sos_04_inventory_orders.py`: **8 passed** after PR-SOS-04.2. The
expanded suite covers
idempotent opening/reservation, stale version rejection, owner-scoped mapping,
atomic fake-order reservation, oversell rejection, cancellation release,
duplicate replay, conservative unshipped-return release, duplicate-line ATP
aggregation, out-of-order event rejection, final-unit and multi-unit races,
adjustment-versus-reservation version checks, cross-channel shared-stock
reservations, concurrent duplicate-event exactly-once behavior, ledger
reconstruction, and invalid lifecycle transition rejection.

### O. Quality checks

Compileall, Ruff on changed backend routers/models/schemas, strict mypy on both
new routers, Black, Angular production build, Angular lint, and the Angular
test command completed without a new PR-SOS-04 compiler or type error. Existing
deprecation warnings (`Field(ne=...)`, FastAPI `on_event`) remain unrelated.

### P. Frontend workspace

`UnifiedInventoryComponent` and `UnifiedOrdersComponent` replace the old
channel-only route projections at `/marketplaces/inventory` and
`/marketplaces/orders`. They provide loading, empty, error, low-stock,
read-only-provider, next-action, keyboard-visible form controls, and explicit
human-adjustment copy.

### Q. Responsive/accessibility intent

The screens reuse the existing shared page/state primitives, semantic table
captions and headers, labels, alerts, focusable scroll regions, and responsive
marketplace styles. PR-SOS-04.2 ran authenticated axe-core 4.11 scans across 12
inventory and orders states—including initialization, required-field
validation, empty and low-stock, reservation-failure, and reconciliation
states—with zero violations or incomplete findings.

### R. Browser scenarios

Status: **30/30 PASS** in the isolated direct Chrome/CDP run. The complete
ledger (routes, expected/observed outcomes, and screenshot references) is in
`docs/seller-os/pr-sos-04-2-validation.md`; browser evidence is not inferred
from backend tests.

### S. External-write confirmation

No provider transport is called by the canonical inventory or fake-event
routes. No Amazon/Flipkart API, supplier, RFQ, fulfilment, payment, or
marketplace mutation was performed.

### T. Known limitations

Provider webhook authentication/acknowledgement, background reconciliation,
evidence-backed return receipt, real channel quantity publication, and full
browser/axe certification are outside this bounded local implementation.

### U. Unrelated defects

Existing application-wide warnings and historical migration/offline JSONB
limitations were not changed. They do not prevent the focused PR-SOS-04 API
tests or Angular compilation.

### V. Database safety

Only the disposable `vayujit_pr_sos04_test` database was created/migrated and
reset. `vayujit_golden_test` was not modified.

### W. Worktree safety

No commit, push, reset, or destructive operation on the repository was made.

### X. Remaining acceptance gates

The PR-SOS-04.2 local gates are closed. Real Amazon/Flipkart transports,
provider webhook authentication, channel acknowledgement, fulfilment, refunds,
payments, and production operations remain intentionally out of scope.

### Y. Next safe action

Keep fake-provider mode and external-write kill switches enabled. Any future
real-provider certification is a separate milestone.

### Z. Final classification

**PR-SOS-04 — FULLY VALIDATED (LOCAL / FAKE MARKETPLACE ORDER PROVIDERS / NO LIVE EXTERNAL MUTATIONS)**
