# Marketplace Commerce Core

Marketplace Commerce Core is the shared foundation for Amazon, Flipkart, Shopify, Meesho, and future channel adapters. A VAYUJIT Product remains the source of truth; a MarketplaceListing projects that product into one account while normalized inventory, orders, settlements, and profitability records remain owner-scoped.

## Current implementation

Amazon, Flipkart, and Meesho each have transport-injected, deterministic, network-free adapters. Their account lifecycle, listing draft/readiness/submit/reconcile flow, idempotency, inventory/order/settlement projections, drift handling, safe diagnostics, and fake-worker paths are covered by focused tests. Live seller certification and production credentials are intentionally not claimed.

The shared Angular marketplace workspace provides:

- per-marketplace overview cards with currency-safe totals;
- product channel view;
- filtered inventory, orders, and settlements;
- sales and profitability projections;
- channel-specific workspaces and deterministic variant matrices.

The UI uses a bounded marketplace registry so adding Meesho does not require duplicating shared screens. Channel-specific behavior stays behind the connector and route adapter.

## Safety and data boundaries

Connector credentials are encrypted, write-only, removable, and never returned in browser responses, logs, Audit events, or diagnostics. Fake transports use stable IDs and idempotency keys. Remote drift requires explicit review or confirmation before overwrite. Aggregates never perform implicit FX conversion: combined totals are shown only when currencies are compatible.

## Migration and future phases

Migration 20260813_0023 creates the normalized commerce tables as one logical boundary.

Future phases intentionally deferred: Meesho live transport and seller certification, continuous inventory synchronization, remote fulfilment mutations, refund initiation, automatic repricing, and production activation of marketplace credentials.
## Marketplace Video (Slice 3B)

Amazon, Flipkart, and Meesho share the normalized Marketplace Video mapping/job architecture. The local fake-certified flow is Approved Video -> readiness -> preview -> explicit confirmation -> durable job -> deterministic connector -> remote mapping -> reconciliation/Product Channel. Exact Video versions are immutable; newer approvals only report update availability. Live marketplace policy/API capability is not certified.


## Marketplace Video certification boundary

The local fake-certified Marketplace Video workflow supports exact-version Amazon, Flipkart, and Meesho attachment, explicit preview/confirmation, durable jobs, replacement, reconciliation, ambiguity and crash-safe recovery, Product Channel and Product Media projections, safe history and diagnostics, security/privacy checks, and responsive/keyboard-accessible operational UX. Live marketplace Video APIs are not validated; Campaign Video, Bulk Video, Ads, and live connector calls remain out of scope.
