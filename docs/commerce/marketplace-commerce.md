# Marketplace Commerce Core

## Purpose

Marketplace Commerce Core is the shared foundation for Amazon, Flipkart, Meesho,
Shopify, and future social-commerce adapters. A VAYUJIT Product remains the
source of truth. A `MarketplaceListing` projects that Product into one account
and preserves remote identifiers, safe normalized status, synchronization time,
and drift separately from generic publishing executions.

## Domain

The commerce domain contains owner-scoped accounts, listings, category and
attribute definitions, SKU/identifier mappings, stable variants, prices,
inventory snapshots, buyer-safe order snapshots, fulfilments, returns,
cancellations, refunds, fees, settlements, settlement lines, drift records, and
durable mutation idempotency keys. Credentials are encrypted with the existing
AES-GCM credential service and never appear in response models or audit metadata.

Approved content artifacts may be attached to listings. The commerce API never
silently publishes unapproved AI content and never duplicates a Product per
marketplace. Existing Media assets remain the physical source; listing media
mapping is an extension point for future adapters.

## Connector and runtime

`CommerceConnector` is deliberately separate from generic content publishing.
It exposes account validation, category/attribute discovery, listing preview and
mutations, reconciliation, inventory, orders, fees, and settlements. The current
`DeterministicFakeCommerceConnector` is network-free and provides stable IDs for
tests and local development. Real Amazon, Flipkart, and Meesho adapters are not
implemented in this milestone.

Commerce mutations use durable owner/account/operation/idempotency keys. Listing
reconciliation records typed drift for review; remote changes are not silently
overwritten. Marketplace failures should project into the existing Recovery and
durable scheduler/worker architecture as adapters are added.

## API and UI

The owner-scoped API is under `/api/v1/marketplaces`: accounts, capabilities,
categories, listings, inventory, orders, settlements, and analytics. Writes
remain exact-Origin protected. Responses are bounded and buyer-safe.

Angular adds a top-level Marketplace navigation area with Overview, Accounts,
Listings, Inventory, Orders, Settlements, and Analytics. Views use progressive
disclosure and show empty/error states without exposing secrets.

## Profitability

Analytics calculates gross sales, fees, refunds, and net contribution from
imported settlement snapshots. Estimated profit is explicitly `unavailable`
when COGS or other required costs are missing; missing costs are never treated as
zero.

## Migration and future phases

Migration `20260813_0023` creates the normalized commerce tables as one logical
unit and supports clean upgrade/downgrade/re-upgrade validation.

Future phases, intentionally not implemented here: Amazon adapter, Flipkart
adapter, Meesho adapter, unified inventory/orders, AI Marketplace Content Studio,
AI Image Studio, Video/Social Studio, YouTube/Instagram/Facebook publishing,
ads, and cross-channel analytics/AI intelligence.

