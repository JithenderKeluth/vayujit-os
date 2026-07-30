# Shopify throttling, retries, and cancellation

The GraphQL wrapper captures Shopify cost metadata when present. Transient network failures,
throttling, and selected 5xx responses are retryable within the configured bounded attempt limit.
Authentication, permission, validation, and mutation user errors are not retried.

Timeouts during mutations are classified as ambiguous and require reconciliation before another
create. Cancellation is local: it stops lifecycle continuation but cannot cancel a completed
remote Shopify operation. A late remote success must be reconciled; it is never deleted or archived
automatically.
