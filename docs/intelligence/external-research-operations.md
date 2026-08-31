# External research operations

System diagnostics expose mode, provider health, quota, allowlist state, kill switches, and failure taxonomy without secrets. Recovery is limited to retry, retry-after, review-source, disable-source, refresh-search, skip-optional-source, and cancel. Live provider and approved live fetch certification require external credentials and approved domains; local fixture certification does not.

## Slice 6A.2 durability contract

External missions use bounded budgets for searches, fetches, independent domains, results, per-response bytes, total bytes, elapsed time, retries, and provider requests. Counters are persisted in `intelligence_external_budgets`; consumption locks the budget row and fails closed when a limit is reached. The effective policy is deterministic and capped by platform limits; mission values cannot create unbounded work.

Each logical search and fetch has an owner-scoped execution identity in `intelligence_external_executions`. Durable checkpoints cover claim, pre-provider/pre-fetch, provider/fetch completion, result/evidence persistence, verification, and terminal state. Replays reuse completed identities and never repeat a completed provider transport. Recovery records are owner-scoped and idempotent; only executable retry/retry-after/refresh/review/disable/skip/cancel/reconcile actions are advertised for the failure class.

Search and fetch attempts re-check global/provider/domain policy, quota, emergency stop, and budget immediately before outbound work. Kill-switch changes therefore fail closed without a provider call. Audit events use deterministic idempotency keys and allowlisted metadata (`external.search.*`, `external.fetch.*`, and `external.recovery.executed`); credentials, authorization headers, cookies, DSNs, paths, raw HTML, and provider payloads are never persisted or returned. Bounded execution history and Operations/System Doctor projections expose status, checkpoints, counters, failures, Recovery, and correlation IDs without secrets.

## Slice 6A.2B concurrency evidence

The durability harness starts two independent SQLAlchemy sessions against PostgreSQL and releases both through a threading.Barrier immediately before the operation. A database uniqueness constraint claims each owner-scoped logical identity; row-level locks serialize budget, quota, and recovery decisions. A waiting caller re-reads the committed execution and receives the same bounded result.

The concurrency acceptance matrix covers identical search and fetch replay, search/fetch/byte/provider-request budgets, per-minute and per-hour provider quotas, retry-token consumption, checkpoint races, and idempotent Recovery. Exactly one token is consumed when a capacity is one; counters never become negative or exceed configured limits, and duplicate provider transport/evidence/audit records are not created. Recovery actions are validated against the advertised failure-code contract and the complete 21-code catalog.

Repeat the focused suite three times when certifying a release. The test output is bounded to counts, status, failure code, checkpoint, and idempotency state; it never includes credentials, provider payloads, or raw external content.

## Slice 6A.3 storage and operational proof

The external research boundary now exposes an owner-scoped table inventory (`/api/v1/intelligence/external/tables`) covering 18 persisted ledgers: external search requests/results, fetches, source profiles, provider state, budgets, executions, recovery, and autonomous missions/tasks/schedules/recovery/evidence/claims/contradictions/changes/alerts/reports. `/integrity` derives duplicate, orphan, broken-lineage, and cross-owner counters from PostgreSQL and classifies the current state; replaying a completed search or fetch does not grow canonical rows.

`/performance` reports at least ten warm local-fixture samples per read route, median/p95 timings, a local execution-stage ledger, and time-to-first-evidence fields. Live provider latency is explicitly `NOT_MEASURED` until a permitted external certification run. Product Channel projection is owner-scoped and read-only; Calendar entries are informational only; Alerts expose review state without acknowledgement side effects. Operations and System Doctor surface provider/search/fetch readiness, quotas and budgets, integrity/performance classifications, and live-timing status without credentials, raw content, SQL, DSNs, paths, or tokens.


## Slice 6A.4 ? External Research UX

The `/intelligence/external` workspace provides owner-scoped navigation for Overview, Providers, Source Policy, Searches, Fetches, Evidence, Contradictions, Changes, Alerts, History, and Recovery. It includes explicit LOCAL FIXTURE and live-validation boundaries, loading/empty/error states, escaped plain-text external content, safe HTTP(S) links, accessible tables/status labels, responsive layouts, Product Channel and Calendar projections, and Operations/System Doctor linkage. Live search and live approved fetch remain NOT VALIDATED until deployment credentials and allowlists exist.

## Slice 6B live-provider boundary

Brave Web Search is the single official live adapter. It is restricted to `LIVE_READ_ONLY`, uses the subscription-token header, normalizes results through the existing URL and discovery-result boundary, and fails closed when credentials or live switches are absent. See `live-search-provider.md` for configuration and certification evidence.

## Slice 6C operations

The approved-fetch preflight endpoint reports mode, approved/blocked/review-required domain counts, TLS, redirect and byte limits, user-agent, and switch readiness without making an outbound request.

## Slice 6D website intelligence

Manufacturer and supplier website projections reuse the approved read-only fetch boundary, deterministic extraction, existing supplier verification, owner scoping, and no-contact/no-RFQ policy. See [manufacturer-supplier-web.md](manufacturer-supplier-web.md).

## Slice 6D.2B durable refresh, Product Channel, and Calendar

Website refresh scheduling is profile-scoped and supports `MANUAL`, `DAILY`, `WEEKLY`, and `MONTHLY` policies with an IANA timezone and one bounded next occurrence. Due materialization is owner-scoped, row-locked, unique by profile and scheduled timestamp, and emits `website.refresh.materialized`; replay returns the existing job. Execution records `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, or `SKIPPED`, reuses the refresh idempotency key, and never retries a completed job. Disabled sources and `BLOCKED`/`REVIEW_REQUIRED` classifications fail closed; the global intelligence emergency stop and disabled switch also skip work safely.

The durable refresh ledger is `intelligence_website_refresh_jobs`; source profiles retain next/last refresh timestamps, timezone, policy version, and failure code. Calendar exposes one server-derived `WEBSITE_SOURCE_REFRESH_DUE` event per scheduled profile with target, profile, domain, frequency, timestamp, timezone, and status. Product Channel remains read-only and server-derived, with website observation/offering/profile counts and existing review-only actions. Operations/System Doctor expose refresh backlog, queued/running/failed counts, next due, last success, scheduler state, and recovery registration without secrets or raw content. Catch-up is bounded to one next occurrence per materialization pass; no durable worker or connector mutation is introduced.

## Marketplace runtime integration

Marketplace providers use the shared owner/provider execution and rate-window ledgers documented in marketplace-runtime.md. IndiaMART remains read-only and provider-specific normalized records are preserved.