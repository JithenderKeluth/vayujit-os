# Search provider contract

The provider-neutral contract accepts query, market, language, result bounds, safe-search, source categories, domain controls, and correlation ID. `LOCAL_FIXTURE` is deterministic and safe for local certification. `LIVE_READ_ONLY` requires an explicitly configured endpoint and API key and remains fail-closed when absent. Quotas and idempotency are owner/provider scoped.

## Slice 6A.2 durability contract

External missions use bounded budgets for searches, fetches, independent domains, results, per-response bytes, total bytes, elapsed time, retries, and provider requests. Counters are persisted in `intelligence_external_budgets`; consumption locks the budget row and fails closed when a limit is reached. The effective policy is deterministic and capped by platform limits; mission values cannot create unbounded work.

Each logical search and fetch has an owner-scoped execution identity in `intelligence_external_executions`. Durable checkpoints cover claim, pre-provider/pre-fetch, provider/fetch completion, result/evidence persistence, verification, and terminal state. Replays reuse completed identities and never repeat a completed provider transport. Recovery records are owner-scoped and idempotent; only executable retry/retry-after/refresh/review/disable/skip/cancel/reconcile actions are advertised for the failure class.

Search and fetch attempts re-check global/provider/domain policy, quota, emergency stop, and budget immediately before outbound work. Kill-switch changes therefore fail closed without a provider call. Audit events use deterministic idempotency keys and allowlisted metadata (`external.search.*`, `external.fetch.*`, and `external.recovery.executed`); credentials, authorization headers, cookies, DSNs, paths, raw HTML, and provider payloads are never persisted or returned. Bounded execution history and Operations/System Doctor projections expose status, checkpoints, counters, failures, Recovery, and correlation IDs without secrets.

## Slice 6A.3 storage and operational proof

The external research boundary now exposes an owner-scoped table inventory (`/api/v1/intelligence/external/tables`) covering 18 persisted ledgers: external search requests/results, fetches, source profiles, provider state, budgets, executions, recovery, and autonomous missions/tasks/schedules/recovery/evidence/claims/contradictions/changes/alerts/reports. `/integrity` derives duplicate, orphan, broken-lineage, and cross-owner counters from PostgreSQL and classifies the current state; replaying a completed search or fetch does not grow canonical rows.

`/performance` reports at least ten warm local-fixture samples per read route, median/p95 timings, a local execution-stage ledger, and time-to-first-evidence fields. Live provider latency is explicitly `NOT_MEASURED` until a permitted external certification run. Product Channel projection is owner-scoped and read-only; Calendar entries are informational only; Alerts expose review state without acknowledgement side effects. Operations and System Doctor surface provider/search/fetch readiness, quotas and budgets, integrity/performance classifications, and live-timing status without credentials, raw content, SQL, DSNs, paths, or tokens.
