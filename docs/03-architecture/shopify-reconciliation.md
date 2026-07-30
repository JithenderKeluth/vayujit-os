# Shopify reconciliation

Reconciliation reads the known Shopify product and compares title, status, handle, vendor, product
type, tags, SEO, and modification state with the immutable approved snapshot. Variant, price,
collection, publication, and media comparisons may be extended as their remote contracts mature.

Remote changes are review-only. Keeping remote changes records the decision. Updating from an
approved Artifact requires explicit overwrite confirmation. Missing products are recoverable but
never recreated automatically. Remote deletion is not supported.
