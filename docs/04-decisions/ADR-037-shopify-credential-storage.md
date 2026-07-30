# ADR-037: Shopify credential storage

Status: Accepted.

Owner credentials use the platform authenticated-encryption service. The Admin API token is
write-only and application configuration takes precedence over deployment fallback.
