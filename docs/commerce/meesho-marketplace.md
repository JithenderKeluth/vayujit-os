# Meesho Marketplace

## Status

Meesho is implemented through the shared Marketplace Core using a typed,
transport-injected deterministic fake adapter.

- IMPLEMENTED + FAKE-CERTIFIED: account lifecycle, categories, attributes,
  listing preview/submit/reconcile, variants, media, pricing, inventory,
  orders, fulfilment projections, cancellations, returns, refunds, fees,
  settlements, profitability projections, drift actions, diagnostics, and
  durable worker dispatch.
- IMPLEMENTED + NOT LIVE-VALIDATED: all real Meesho authentication, hosts,
  endpoint semantics, permissions, throttling, catalog rules, and seller
  capabilities.
- DEFERRED: live transport activation, continuous inventory sync, automatic
  repricing, fulfilment mutations, refund initiation, and production
  credential validation.

No current Meesho seller contract is assumed. The fake transport is local and
network-free, with stable identifiers, bounded policies, idempotency,
throttling, ambiguous-result modeling, and reconciliation behavior.

## Shared architecture

Meesho uses the existing canonical Product, marketplace account, listing,
variant, media, inventory, order, settlement, profitability, scheduler,
Recovery, Audit, and Operations models. Historical normalized records remain
available when credentials are disabled or removed. Credentials are write-only,
encrypted by the existing account boundary, and never appear in logs, Audit,
diagnostics, or browser responses.

The Angular workspace reuses the shared Marketplace Overview, Product Channel
View, Inventory, Orders, Settlements, profitability, and drift surfaces. The
Meesho workspace is a channel adapter over the same seller UX; it does not
introduce a parallel publishing stack or queue.
## Video attachment

Meesho uses the normalized Marketplace Video contract and deterministic fake transport. Exact Video identity, readiness, preview/confirmation, durable jobs, reconciliation, replacement safety, and recovery are local-only certifications. No live Meesho API call is made.


## Marketplace Video certification boundary

The local fake-certified Marketplace Video workflow supports exact-version Amazon, Flipkart, and Meesho attachment, explicit preview/confirmation, durable jobs, replacement, reconciliation, ambiguity and crash-safe recovery, Product Channel and Product Media projections, safe history and diagnostics, security/privacy checks, and responsive/keyboard-accessible operational UX. Live marketplace Video APIs are not validated; Campaign Video, Bulk Video, Ads, and live connector calls remain out of scope.
