# PR-SOS-04.1 - Inventory & Orders Reliability, Concurrency and Local Certification

**Date:** 2026-10-12  
**Classification:** **PR-SOS-04 - IMPLEMENTED / LOCAL CERTIFICATION PENDING**

This is the PR-SOS-04.1 closure report. It certifies the canonical local
inventory/order authorities against disposable PostgreSQL state and synthetic
provider events only. No Amazon or Flipkart transport, external acknowledgement,
fulfilment, refund, payment, supplier, RFQ, procurement, or marketplace write
was performed. `vayujit_golden_test` was not modified.

## A-Z evidence report

### A. Authority audit

`Product`, catalog variants, `MarketplaceAccount`, marketplace listings,
marketplace orders, audit events, authentication, and the single-owner
installation model remain canonical. Inventory and orders add no duplicate
catalog or marketplace authority.

### B. Canonical stock semantics

- **On hand:** physically recorded local units, including units currently held
  for an order until shipment consumption.
- **Reserved:** active order holds included in on hand and excluded from ATP.
- **Damaged/quarantined:** on-hand units excluded from ATP; no public mutation
  endpoint silently makes them sellable.
- **Available-to-promise (ATP):** `max(0, on_hand - reserved - damaged)`.
- **Shipped:** reservation transitions to `consumed`; on hand and reserved each
  decrease by the shipped quantity.
- **Returned:** provider return state is recorded without restocking ATP. A
  verified physical return receipt is deliberately outside this local slice.
- **Reconciled:** `last_reconciled_at` is reserved for an evidence-backed
  reconciliation process; provider conflicts remain visible as exceptions.

Executable invariants are non-negative quantities, reserved plus damaged never
exceed on hand, ATP never becomes negative, and every material transition has a
matching append-only movement with before/after balances.

### C. Concurrency repair

Fake-provider events now lock the owner-scoped `MarketplaceAccount` before
idempotency and remote-order checks. Inventory rows remain row-locked for ATP
allocation. This closes the concurrent duplicate-event race that could have
surfaced a database uniqueness error instead of a deterministic replay.

### D. Overselling scenarios

PostgreSQL-backed tests cover final-unit and 5-unit (3 versus 4) races. Exactly
one allocation succeeds when capacity is exhausted; ATP and reserved quantities
remain valid. Adjustment versus reservation races either both succeed in a
valid order or the stale HUMAN adjustment receives `409`.

### E. Duplicate events

Concurrent delivery of the same provider event returns one `201` and one `200`
replay, creates one order, one reservation, one reservation movement, and one
event lineage row. Equal-version state replays are no-ops; conflicting equal
versions are retained as `reconciliation_required`.

### F. Fake provider boundary

`POST /api/v1/orders/fake/events` is synthetic and network-free. It supports
`new_order`, `cancel`, `ship`, and conservative `return` events. Payload,
version, status, failure reason, and fake-provider provenance remain persisted.

### G. Guarded ingestion

Unmapped SKUs and insufficient stock are rejected before order/reservation
materialization. Duplicate lines are aggregated by canonical inventory item so
an order cannot reserve the same capacity twice through separate lines.

### H. Human stock authority

Opening balances and adjustments require the authenticated owner, a reason,
expected version, and an idempotency key. Movement actor type is `HUMAN` and
provenance is local/read-only. No Business Agent endpoint can adjust stock.

### I. Ledger integrity

Focused tests cover opening balance, positive and negative adjustments, invalid
negative adjustment, missing reason, stale versions, duplicate idempotency,
reservations, release, shipment consumption, cancellation release, unshipped
returns, and independent ledger reconstruction. The reconstruction sum of
movement quantities equals the materialized on-hand quantity.

### J. Order state machine

Valid synthetic transitions are pending/confirmed/processing -> shipped or
cancelled; pending/confirmed/processing/shipped/delivered -> returned. A ship
after cancellation and a cancellation after shipment now return `409` and
persist a reconciliation-required event without changing the order. Replaying
an already materialized state is idempotent.

### K. Channel mapping

Amazon and Flipkart mappings are account-scoped and share the same internal
inventory pool when they target one item. Account, listing, item, and owner
references are validated before persistence. Conflicting active mappings return
`409`.

### L. Owner isolation

Every inventory, reservation, mapping, order, and event query is scoped to the
authenticated owner. The installation retains `ck_users_single_owner`; no
same-database multi-owner fixture was created. Cross-installation isolation is
covered by the marker-protected disposable database harness and existing
owner-isolation regressions.

### M. Reconciliation and Business Agent projection

The read-only reconciliation/insights projection reports low stock, out of
stock, active reservations, rejected events, unmapped persisted order lines,
and reconciliation-required provider events. It emits actionable next steps
without ranking, purchasing, acknowledging, or publishing externally.

### N. Focused test ledger

`tests/test_pr_sos_04_inventory_orders.py`: **7 passed** (including the three
original tests plus four PR-SOS-04.1 regressions). The suite ran against the
approved disposable PostgreSQL database `vayujit_test`, with marker-guarded
reset before and after each test. The expanded scenarios cover all six required
concurrency families and the independent ledger/state-machine proofs.

### O. Migration and database validation

The complete migration chain passed on a fresh disposable database
(`vayujit_pr_sos041_fresh2`) through `20261020_0160 (head)`. The pre-existing
`vayujit_test` database is stamped at `20261010_0151` while later tables already
exist; upgrading that reused database therefore reports a duplicate-table drift
and was not altered. Constraints and unique idempotency/event keys remain
unchanged. The historical offline Alembic revision-0007 JSONB `--sql`
limitation remains separate technical debt.

### P. Frontend surface

`/marketplaces/inventory` and `/marketplaces/orders` remain authenticated,
owner-scoped workspaces with loading, empty, error, low-stock, read-only fake
provider, semantic table, and next-action states. No frontend business logic
was duplicated for this reliability slice.

### Q. Accessibility intent

The Angular suite, production build, and lint pass. The dedicated authenticated
Chrome/axe run for the 30 scenarios was not available in this execution
environment; automated accessibility closure is therefore not claimed.

### R. Browser matrix (30 scenarios)

All 30 authenticated Chrome/CDP scenarios are **NOT EXECUTED** in this turn:
login, inventory initialization/ledger/adjustment, Amazon and Flipkart mapping,
fake order lifecycle, reconciliation, Business Agent guidance, responsive
breakpoints, keyboard traversal, refresh/deep-link, logout, and protected-route
behavior. Backend tests are not presented as browser substitutes.

### S. Adjacent regressions

The focused PR-SOS-01 catalog, PR-SOS-02 Amazon, and PR-SOS-03 Flipkart
regression matrix ran unchanged: **14 passed**. No tests were weakened. A
broader all-milestones matrix was not rerun in this turn.

### T. Static quality

Ruff and Black pass on the changed router and focused tests. Strict mypy passes
for the changed inventory/order routers. Compileall and `git diff --check` pass
(Git reports only normal LF/CRLF conversion warnings). Angular tests pass
(62 files / 223 tests); production build and lint pass, with the existing
509.17 kB initial-bundle budget warning and two pre-existing lifecycle-interface
lint warnings. A fresh browser/axe run remains outstanding.

### U. External-write safety

No real Amazon/Flipkart API calls, channel acknowledgement, inventory
publication, fulfilment, refunds, payments, supplier contact, RFQs, or
procurement actions were performed. Fake events do not call transports.

### V. Database safety

Only marker-protected disposable PostgreSQL databases were used. The golden
database was not opened for mutation.

### W. Worktree safety

No commit, push, reset, or broad destructive filesystem operation was run.

### X. Known limitations

Provider webhook authentication, retry/timeout transport adapters, background
reconciliation, verified return receipts/damage quarantine, real channel
quantity publication, and full browser/axe evidence are outside PR-SOS-04.1's
bounded local fake-provider implementation.

### Y. Remaining release gates

The exact remaining gates are the authenticated 30-scenario Chrome matrix,
axe-core scans at the required states and widths, keyboard/responsive evidence,
and the full adjacent regression matrix. They must be executed before claiming
the specification's `FULLY VALIDATED` classification.

### Z. Final classification

**PR-SOS-04 - IMPLEMENTED / LOCAL CERTIFICATION PENDING**
