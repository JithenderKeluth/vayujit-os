# External research security

The boundary rejects private/loopback/link-local/metadata addresses, embedded credentials, unsafe ports, unsafe redirects, oversized responses, unsupported MIME, malformed query input, and credential-like content. Prompt-injection markers are inertly classified and never executed. Audit metadata is allowlisted and excludes credentials, cookies, authorization, DSNs, paths, raw HTML, and private provider payloads.

## Evidence intelligence handoff (Slice 6A.1D)

External fetch observations persist freshness windows (`fresh_until`, `stale_at`, `expires_at`) and verification metadata on the autonomous evidence row. Repeated fetches are idempotent by default; callers may opt into `refresh=true`. An unchanged refresh reuses the original observation, while a changed response receives a new fetch identity and remains append-only. Owner-scoped current and history views are available at `/api/v1/intelligence/external/observations/current` and `/api/v1/intelligence/external/observations/history`.

Only accepted (`SUPPORTED` or `VERIFIED`) evidence can project claims. The deterministic verifier records a versioned method, reason, verification timestamp, freshness at verification, and lineage. Diversity normalizes canonical URL/domain/provider/content hash so mirrors and duplicate pages cannot inflate source counts. Confidence is bounded by verification, freshness, diversity, completeness, contradictions, and unknowns.

The handoff services provide order-independent contradiction identities, server-derived materiality for external changes, and stable alert identities for review-worthy changes. Replays return existing rows instead of creating duplicates.

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
