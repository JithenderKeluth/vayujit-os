# Flipkart Marketplace

## Scope and live-validation status

Flipkart uses the shared Marketplace Commerce Core tables and lifecycle. The
adapter is transport-injected and the local boundary is deterministic and
network-free. Current Flipkart API contracts, authentication details, hosts,
permissions, rate limits, and seller capabilities have not been verified here.

**Live Flipkart validation: NOT PERFORMED.**

## Local fake workflow

1. Configure a Flipkart account under Marketplace and validate it.
2. Enable the account after validation.
3. Activate a canonical Product and attach an approved Artifact.
4. Create a Flipkart draft listing with a seller SKU and category.
5. Save variants, ordered Media mappings, and INR pricing.
6. Run the server readiness preview and resolve all blocking issues.
7. Submit with a durable idempotency key, then reconcile the asynchronous
   processing state.
8. Import orders and financial events as often as needed; repeated imports are
   idempotent. Review profitability only when COGS inputs are available.
9. Use listing drift review before any keep-remote or local-overwrite action.

Orders, inventory, and financial imports use the existing normalized Commerce
Core records. Cancellation, return, refund, fulfilment, fee, settlement, and
profitability projections are replay-safe and store only normalized seller-safe
values. Drift is classified for review, keep-remote, or explicitly confirmed
local overwrite. Connector credentials are encrypted, write-only, removable, and
never included in logs, Audit events, diagnostics, or browser responses.

## Architecture

`flipkart.py` owns the typed transport boundary, auth strategy, host policy,
fake transport, category/attribute mapping, readiness policies, idempotency,
and safe issue classification. `flipkart_router.py` owns owner-scoped API
projection and delegates persistence to the shared Marketplace Core models.
No parallel Flipkart tables or queue are introduced.

The shared Marketplace Overview, Product Channel View, Inventory, Orders, Settlements, Analytics, and profitability surfaces consume these normalized records. The variant matrix reuses the deterministic Amazon-compatible matrix utility and caps generated combinations at 100 while preserving matching row values.

## Classification

- IMPLEMENTED + FAKE-CERTIFIED: account lifecycle, categories, typed attributes,
  listing draft/preview/submit/reconcile, SKU and variant validation, media and
  pricing persistence, explicit inventory, order/fulfilment/cancellation/return/
  refund projections, settlement and fee normalization, profitability availability
  semantics, drift actions, safe diagnostics, Audit events, and Angular workspace
  foundation.
- IMPLEMENTED + NOT LIVE-VALIDATED: real authentication, seller/catalog transport,
  current Flipkart endpoint compatibility, and live seller certification. Fake
  throttling, ambiguous-result handling, and bounded retry signals are covered
  locally.
- DEFERRED: continuous inventory sync, remote fulfilment mutations, refund
  initiation, automatic repricing, and production connector activation.
