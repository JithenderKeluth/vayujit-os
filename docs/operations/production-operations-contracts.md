# Production operations contracts

## Observability and monitoring

Structured JSON logs include timestamp, level, service, environment, request ID, correlation ID, route, status, duration, and safe owner/Product/Job identifiers where available. Metrics expose request totals/statuses/errors through the provider-neutral `/health/metrics` surface. Internal alert thresholds are normalized as: API 5xx rate >2% for 5 minutes; any readiness failure; queue backlog older than the lease; worker failures >=5 in 10 minutes; Recovery events >=10 in 10 minutes; provider failures >=5 in 5 minutes; any backup or migration failure; any storage error; and Ads spend at >=80% of a configured cap. Monitoring provider: **NOT CONFIGURED**.

## Retention

Audit and history are append-only and retained according to business/legal policy; job attempts and recovery records are retained for incident analysis. Logs are deployment-managed with a minimum 30-day target. Temporary files and checkpoints are bounded, owner-scoped, idempotently cleaned, and never remove approved lineage. Account/Product/Media/Artifact data uses archival/tombstone semantics where hard deletion would break immutable lineage. Legal/privacy review is required for final retention periods, export, deletion, consent, PII, provider terms, and cross-border storage.

## Runtime safety

API and workers stop accepting new work before shutdown, finish or roll back active transactions, release leases, and close DB pools. Worker concurrency is bounded to 1..32 with a default of 2; unbounded values are rejected. Network timeouts, exponential retry/backoff, idempotency, and provider-failure containment are bounded by configuration. Scheduler deployment is a single scheduler loop per deployment by default; multiple API instances may run, but only one scheduler process is enabled. Durable job claims and idempotency keys remain mandatory if that topology changes.

## Network and endpoints

Connector contracts require connect/read/total timeouts. Operational endpoints require owner authentication and redact secrets. Reverse proxies must terminate TLS, set trusted forwarded headers only from configured proxy IPs, enforce request/body/timeouts, and preserve WebSocket support if introduced. Production requires HTTPS and secure cookies. Container images must be pinned, non-root where practical, free of baked secrets, healthchecked, and writable only where required. CI currently has no repository workflow; the documented local gate inventory is the blocker until CI infrastructure is introduced.

## Compliance boundary

Legal/compliance review is required for privacy policy, consent, marketing/Ads consent, deletion/export, PII, data processing, provider and marketplace terms, cookie consent, and cross-border storage. This repository provides no legal certification.