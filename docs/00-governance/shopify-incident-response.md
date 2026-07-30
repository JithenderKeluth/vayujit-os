# Shopify incident-response runbook

Disable the connector or affected destination first. Preserve execution ID, correlation ID, safe
error code, remote product ID, and throttle summary. Never copy tokens, Authorization headers, full
GraphQL bodies, product descriptions, or media bytes into incident records.

For ambiguous timeouts, reconcile before retrying. For invalid credentials or scopes, replace the
custom-app token and validate before re-enabling. For throttling, allow the bounded retry window or
wait for capacity restoration. Do not force success, delete a remote product, or modify inventory
as part of recovery.
