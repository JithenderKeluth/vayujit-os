# Amazon Marketplace integration

The Amazon adapter is a transport-injected Selling Partner API boundary. Development and tests use a deterministic fake transport; no live Amazon request is made by this milestone.

India (A21TJRUUN4KGV, INR, en-IN) is the first-class default. US and GB mappings are available for region-aware configuration. Endpoint hosts are HTTPS-only and allowlisted by region; arbitrary URLs, credentials, paths, queries, and fragments are rejected.

Credentials are encrypted at rest and never returned by API responses. Resolution precedence is:

1. encrypted account credentials
2. deployment environment credentials
3. unconfigured (safe diagnostics and no live call)

Listing submission requires an approved content Artifact, explicit product type and attributes, a stable idempotency key, and an operator-triggered action. Amazon processing is asynchronous: submit returns PROCESSING, then reconcile promotes the listing to ACTIVE or records a safe rejection. Throttling and ambiguous results are retryable and never expose raw provider payloads.

Real Amazon validation: NOT PERFORMED. Supply operator credentials and an approved production transport implementation before enabling production traffic.