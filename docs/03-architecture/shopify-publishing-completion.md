# Shopify publishing completion

The completion layer extends the existing Shopify connector without changing the generic
Publishing lifecycle.

## Variants

Products without structured Shopify input use the existing Product SKU, price, compare-at price,
barcode, weight, unit, and tracking metadata. Missing values are omitted rather than invented.
Destinations may require SKU or price. Structured Publishing input is limited to three options and
100 unique variants. Stable local keys are persisted in normalized remote-variant mappings.
Remote-only variants are reported as drift and are never deleted automatically.

## Media

Only owned, ready JPEG, PNG, and WebP Media Library assets may be selected. Publishing requests a
Shopify staged target, validates its HTTPS hostname against the documented Shopify/storage
allowlist, uploads at most 20 MiB without the Admin token, creates product media, and persists its
mapping. A matching ready checksum mapping is reused. `fail`, `draft_without_media`, and `degraded`
implement required, optional, and degraded-draft behavior respectively. Local paths, upload
parameters, bytes, and credentials are never returned or audited.

## Assignments and activation

Collections are assigned after the product exists. Activation requires configured publication
targets and succeeds only after the product update and publication mutation complete. Draft
creation never implies publication. Remote deletion and inventory-quantity writes remain
unavailable.

## Retry and reconciliation

Retry delay is bounded exponential backoff with 0.8–1.2 jitter, capped at ten seconds, and respects
larger bounded `Retry-After` guidance. Calculated and applied delays are persisted per transport
attempt. Reconciliation compares mapped product fields, variants, media, collections, and
publications. It does not automatically overwrite drift. An operator must refresh drift, preview
the supported fields, and confirm the overwrite; inventory, remote-only variants/media, and
unrelated metafields remain untouched.

## Local fake server

`apps/api/tests/fake_shopify_server.py` binds to a random loopback port, requires a deterministic
test token, rejects unknown operations, and maintains isolated in-memory Shopify state. It supports
the predefined validation, discovery, product, variant, media, collection, publication, and lookup
operations. It is for automated testing only and never uses real Shopify credentials.

## Manual readiness

Start PostgreSQL and the application, configure an operator-controlled fake/test connector, and
follow: Login → Shopify Settings → validate → discover collections/publications → create
destination → select approved Artifact → configure variants/media → preview → create draft →
inspect attempts → update → reconcile → review drift → preview/confirm overwrite → activate →
archive → Recovery → Health → Audit.

Repeat in browser desktop/tablet/mobile layouts, both themes, and keyboard-only navigation. In
Electron, additionally reload the renderer and verify external Shopify Admin links open outside the
renderer. Manual inspection and real test-store validation remain separate operator-controlled
activities; local automated tests never contact Shopify.
