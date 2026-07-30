# Shopify Publishing connector

Shopify is registered as the `shopify` remote connector. It uses one configured Shopify Admin
GraphQL API version and predefined backend operations; browsers and Electron cannot submit
GraphQL or access the Admin API token.

Products are draft-first. Activation requires an approved Artifact, an activation-capable
destination, an explicit action, and user confirmation. Updates require a known remote product.
Deletion is never exposed. Inventory quantities are not written.

The connector supports bounded collection and publication discovery, safe HTML mapping, SEO,
application idempotency, attempt history, throttling metadata, local cancellation, reconciliation,
and field-level drift review. Remote drift is never overwritten automatically.
