# WP6B — Monetary precision and financial-history decision

2026-10-30, Asia/Calcutta. Local operating policy, not tax/accounting advice or
marketplace fee certification. No permanent database or persisted numeric scale changed.

## Trace and policy

| Boundary | Actual implementation / policy |
| --- | --- |
| Order source | `FakeOrderLine.unit_price` is Decimal; canonical event JSON retains its decimal string. Fake ingestion is explicitly synthetic. Raw source precision is not rewritten from a display. |
| Order projection | `MarketplaceOrderItem.unit_price/total_price` are Numeric(12,2). Source unit100.125 ×2 yields line200.25, stored unit100.13. This is early **projection/storage** rounding, not FX and not merely a formatter defect. Never reconstruct the line total from the rounded unit. |
| Catalog prices | Existing two-decimal operational prices remain unchanged. Catalog estimates are not automatically verified Finance costs. |
| Quotations/components | Existing economic inputs use Numeric(24,8). Preserve decimal strings, explicit quantity/basis/currency/provenance and UNKNOWN. Do not round a small unit cost to paise before multiplying quantity. |
| Landed cost/unit economics | Existing services use Python Decimal, eight-place ROUND_HALF_UP result boundaries, immutable input/calculation authorities and explicit FX evidence. Rates use Numeric(30,16); unsupported/missing pairs return missing evidence, never1:1 or a fabricated rate. Decimal context remains finite, not arbitrary mathematical precision. |
| Finance events/costs | Numeric(14,2); explicit ROUND_HALF_UP to paise. Nonnegative event/cost input constraints remain; negative calculated profit is valid. UNKNOWN helper input now rejects422 instead of supplying0. Nullable cost inputs remain NULL/unknown. |
| Allocation | For known positive line-total weights, allocate the **recorded order deduction** using Decimal largest remainder in paise. Stable order-line ID ordering breaks ties. Allocation sums exactly to the recorded rounded deduction; negative totals are symmetric. No binary float arithmetic. |
| Zero allocation basis | A nonzero recorded deduction with zero line totals is retained **once** at explicitly unknown product allocation/order scope. Missing `deduction_allocation_basis` blocks profit. Never duplicate the whole deduction per line, invent weights or silently lose it. |
| Margins | Finance percent values use explicit ROUND_HALF_UP to two places (formerly implicit HALF_EVEN). Zero net sales makes the margin undefined/NULL, not a fabricated0%. A known zero profit with nonzero sales is legitimately0%. Sourcing margin remains a canonical ratio; the existing BigInt presentation converts it to percent without a binary float round trip. |
| API/UI | Canonical Decimal amounts serialize as strings. Prefer decimal-string writes. `seller-financial-format.ts` uses BigInt rounding/grouping for display; it is not a calculation authority. Money summaries display two places; exact eight-place economics remain in existing detail disclosures. A displayed0.00 for a known sub-paise amount is display rounding, not evidence of a free unit. |

No amount, missing currency, fee schedule, GST treatment, exchange rate or source
verification is invented. No INR/USD amounts are summed without explicit compatible
currency evidence. Currency mismatch remains a calculation/readiness limitation.

## Current limitation and migration analysis

**SE-WP5-PRICE-001 remains P2 / policy-defined projection limitation**, not a claim
that two-decimal order units preserve sub-paise source prices. Exact raw event input
and independently recorded totals remain authoritative; the Orders UI explicitly
labels the rounded projection and warns against reconstruction. The persisted
source/rounded-unit/total distinction and reload are regression-tested.

Changing the unit column to eight places would not recover precision already lost
on historical rows. It would require verified source-line correlation, currency
scales, provider rounding rules, overflow/quantity bounds, row-preserving migration,
existing-data reconciliation and a safe rollback plan. No such data migration was
necessary or performed here. Do not reconstruct lost digits or promote fake order
fixtures to production. Independent line and order rounding bases can differ;
this application is not certified to reconcile those differences as an accounting
ledger. That is a real-business activation limitation, not permission to alter totals.

## Calculation version and preservation

Summary/profitability projection policy is now `pr-sos-05-v2`. Existing source-event
and fee-rule format identifiers remain unchanged. The existing unique key
`(owner_id, scope_key, calculation_version)` permits a new v2 working snapshot
without rewriting an existing v1 snapshot. A persisted regression proves old v1
metrics/lineage survive and repeated v2 recalculations reuse the v2 identity.

This is **not immutable revision history**: subsequent v2 recalculation replaces
v2 metrics/lineage for that scope. The model documentation now states this honestly.
No general ledger, audit-revision subsystem or new approval authority was built.

## Independently expected regression values

Examples tested with literal independent expected results:

-0.005 →-0.01;0.005 →0.01;100.125 →100.13;
999999999999.994 →999999999999.99;1.00499999 →1.00.
0.01 across two equal weights →[0.01,0.00];0.05 across three →[0.02,0.02,0.01];
negative allocation is symmetric and sums exactly. Invalid/NaN/negative/zero-only
allocation weights reject rather than fabricate a distribution.

0.000001 ×1000000 →1.00000000;1/3 →0.33333333 at the eight-place result boundary;
USD0.0015 ×83.125 →INR0.1246875 with explicit synthetic FX input; missing EUR pair
stays unknown. Finance sales200, deductions197.99, known cost0 →profit2.01 and
margin1.01%; deductions200 →zero profit;201 →negative1.00. Removing cost knowledge
returns UNKNOWN profit. None of these values is a real commercial quotation or rate.

## Financial-history architecture recommendation

Current distinctions:

1. Catalog/commercial estimates: modeled inputs, not business transactions.
2. Sourcing input/calculation snapshots: existing evidence lineage and calculation
   versions, distinct from Finance operational projections.
3. Finance calculation snapshots: mutable per scope/version, not append-only revisions.
4. Financial source events: service-level append/idempotency and provenance; actual
   canonical order/fee/refund/settlement projections remain their own authorities.
5. No demonstrated double-entry journal, immutable accounting correction/reversal
   history, period close, tax reconciliation or tamper-proof accounting trail.

**WP7 comprehensive testing may proceed only under the quality gate's final GO**;
these bounded estimate/projection workflows can be tested without a ledger.
**Real-business activation as the sole financial/accounting system is NO-GO.**
Read-only planning use must continue to disclose incomplete evidence and cannot
be called verified accounting. Backup/activation and provider gates remain separate.

Minimum future scope requiring separate authorization: append-only projection
revisions with input hashes/timestamps/policy identifiers, stable source-line and
currency correlation, explicit correction/reversal links, reconciliation against
recorded totals/settlements, import deduplication and owner-approved retention/
export/recovery tests. Integrating an appropriate external accounting system may
be preferable to building a general ledger. No such work is started by WP6B.
