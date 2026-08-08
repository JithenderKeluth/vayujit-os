# Amazon Marketplace integration

## Architecture and credential safety

Amazon is implemented as a transport-injected adapter on the existing Marketplace Commerce Core. The deterministic fake Selling Partner API is the only transport used by local tests and development. No live Amazon request is performed by this milestone.

Credentials are encrypted at rest and write-only. API responses never include credentials, signed requests, cookies, tokens, raw provider payloads, or request URLs. Resolution precedence is encrypted account credentials, deployment environment credentials, then unconfigured diagnostics. HTTPS endpoints are region-allowlisted.

## Regions and product types

India is first class: marketplace ID A21TJRUUN4KGV, INR, en-IN, eu-west-1. US and GB mappings are also available. Product-type and attribute definitions are bounded, paginated, and server-provided.

## Listing lifecycle

Listings require an approved Artifact, stable seller SKU, product type, typed attributes, valid media, variants, and price readiness before submission. The fake boundary models draft/ready/submitting/processing/active and rejected/error outcomes. Submission is asynchronous and reconciliation is required before active status.

Stable idempotency keys and seller-SKU lookup protect against duplicate submissions. Ambiguous results are reconciled before retrying. Remote drift is reported as typed fields and is never overwritten automatically.

## Media, variants, pricing, and inventory

Existing Media Assets are reused by checksum and owner scope. Amazon media policy validates MIME, dimensions, size, ordering, checksum, and main-image requirements without transforming files. Variant policy requires stable local keys, unique seller SKUs, variation themes, and prices. Pricing is marketplace-currency scoped and requires explicit confirmation for mutations. Inventory reads preserve unknown quantities as unavailable; updates require bounded quantities, confirmation, and durable idempotency.

## Orders, fulfilment, returns, financials, and profitability

Amazon orders are normalized into unified Marketplace Orders with masked buyer data and normalized fulfillment status. Returns and refunds are read-only imports. Financial events are normalized into fees and settlement projections; unknown safe classifications remain other. Profitability reports gross sales, fees, refunds, contribution, COGS availability, and Profit unavailable when required data is missing.

## Scheduler, worker, recovery, and diagnostics

Amazon jobs use the existing PublishingJob, lease, attempt, retry, correlation, and worker runtime. Job operations include submission, reconciliation, update, inventory read/update, order import, and financial import. Recovery exposes safe retry/reconcile classifications for throttling, ambiguity, authorization, policy rejection, SKU conflicts, media, variants, inventory, drift, orders, and financial imports. Diagnostics expose validation, throttles, ambiguity, and safe health summaries only.

## Fake acceptance

The guarded fake acceptance journey covers account validation, India marketplace selection, product type and attributes, approved-content readiness, media, variants, pricing, asynchronous submission, idempotent reuse, reconciliation, inventory, orders, fees, returns, and remote drift.

Real Amazon SP-API validation: NOT PERFORMED. Production use requires an operator-controlled transport implementation and explicitly supplied credentials. Flipkart, Meesho, Ads, automatic repricing, continuous inventory sync, remote fulfilment mutation, and remote refund initiation are intentionally out of scope.
## Completion notes

Amazon account lifecycle supports owner-scoped validation, revalidation, enable/disable, credential replacement, and credential removal. Disabled accounts remain readable while remote mutations require explicit re-enabling.

Order items and fulfilments use Commerce Core read models with masked buyer data. Financial imports persist idempotent settlement headers and normalized settlement lines with bounded categories, imported timestamps, and lifecycle metadata.

Drift reconciliation records typed paths and supports review, keep-remote, and explicitly confirmed overwrite only when a fresh remote check and approved Artifact are present. The Angular workspace provides account controls and server-driven attribute controls.

Fake-certified behavior includes crash-before-request and crash-after-success duplicate-prevention tests. These tests do not constitute live Amazon validation.
## Acceptance classification

- IMPLEMENTED + FAKE-CERTIFIED: account lifecycle, server-driven readiness, approved Artifact gating, product type attributes, variant editor/matrix, media ordering, pricing, explicit inventory, listing reconciliation, orders/fulfilment read models, returns/refunds import, settlement and fee normalization, profitability semantics, drift review/keep-remote/guarded overwrite, durable worker idempotency and crash-before/crash-after recovery.
- IMPLEMENTED + NOT LIVE-VALIDATED: Amazon SP-API transport boundary, marketplace credentials, signed request behavior, live throttling and remote authorization semantics.
- DEFERRED: Flipkart, Meesho, Amazon Ads, automatic repricing, continuous inventory synchronization, remote fulfilment mutation, refund initiation, AI image/video generation, Redis, and production packaging/update distribution.

The full API integration command can exceed the local command timeout because it runs the entire integration corpus serially; focused Amazon integration and E2E suites complete against the disposable PostgreSQL database.
