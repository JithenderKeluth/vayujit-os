# Cross-Marketplace Supplier Intelligence (Slice 8A)

Slice 8A adds a provider-independent, owner-scoped canonical Supplier projection. It consolidates
accepted records from IndiaMART, Alibaba, TradeIndia, Global Sources, supplier/manufacturer
websites, and manual/offline sources without adding another marketplace connector.

## Boundary

The projection is read-only with respect to external systems. It does not contact suppliers,
send RFQs, place orders, purchase, pay, scrape authenticated pages, or expose provider payloads.
External marketplace live connectors remain separately configured. Supplier contact is disabled;
RFQ dispatch is disabled unless a human uses the existing sourcing workflow.

## Canonical reconciliation

`POST /api/v1/intelligence/cross-marketplace/suppliers/reconcile` materializes canonical views from
existing owner-scoped Supplier, SupplierSource, SupplierProduct, SupplierEvidence, capability,
certification, and verification records. Exact domain, business-identifier, or normalized-name
matches are `MATCH`; similar names are `POSSIBLE_MATCH` and require human review. They are never
auto-merged. Source and listing lineage remains intact.

## API surface

- `GET /api/v1/intelligence/cross-marketplace/suppliers`
- `GET /api/v1/intelligence/cross-marketplace/suppliers/{id}`
- `GET /{id}/sources`, `/history`, `/ranking`, `/report`
- `POST /{id}/ranking`, `/sourcing-handoff`, and `/compare`
- `GET /operations`, `/calendar`, `/product-channel/{product_id}`, `/integrity`, `/system-doctor`

Reports are server-generated JSON, Markdown, or escaped HTML. Commercial disagreements and
currency differences are preserved; unlike currencies are never compared without an approved FX
assumption. Ranking evaluations are append-only and idempotent by model version and key.

## Local certification boundary

Local certification uses existing deterministic Supplier fixtures and disposable PostgreSQL. AXE
and viewport automation are not configured. Live marketplace behavior, live latency, purchasing,
payments, autonomous supplier contact, and external AI are not certified by this slice.

