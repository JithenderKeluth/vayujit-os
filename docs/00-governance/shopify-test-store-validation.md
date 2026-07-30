# Shopify development-store validation

Use only an operator-controlled Shopify development or test store. Start with draft creation.
Validate connection, collections, publications where permitted, media, update, reconciliation,
explicit activation, and archive only if separately approved.

Record only operation, success/failure, remote product ID, safe admin URL, latency, and correlation
ID. Never record the token or headers. Automated tests use a deterministic local GraphQL fake and
must not contact Shopify. No delete operation exists for test cleanup.
