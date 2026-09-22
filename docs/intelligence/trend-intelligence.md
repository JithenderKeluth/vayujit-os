# Trend Intelligence 12A foundation

The 12A slice provides a provider-independent, owner-scoped evidence layer for future trend analysis. It deliberately stores observations and immutable snapshots only; it does not calculate demand, momentum, seasonality, forecasts, scores, or recommendations.

## Boundary and lineage

`TrendContext` is the bounded subject and geography scope. `TrendSignalDefinition` describes the measurement contract. `TrendObservation` is append-only and links to the existing `IntelligenceSource` and optional `IntelligenceEvidence`. `TrendSnapshot` captures an immutable observation inventory and lineage summary. Duplicate provider identities and canonical fingerprints are idempotent.

Metadata is recursively redacted for credentials, tokens, cookies, sessions, keys, and authorization values. Numeric values use Decimal-backed columns and API contracts reject non-finite values. Timestamps are timezone-aware and period order is enforced.

## API

The authenticated API is under `/api/v1/intelligence/trends`: contexts, signal definitions, observations, snapshots, coverage, operations, and system doctor. All reads and writes are owner scoped; no provider calls or external writes are made by this slice.

The Angular workspace is `/intelligence/trends`. It exposes context creation, evidence observation inventory, and snapshot counts without predictive language.

## Future slices

Provider adapters and live ingestion are intentionally deferred. Trend derivation, demand and momentum, seasonality, forecasting, scoring, Product Channel, Calendar, recovery, workers, and agent integrations remain out of scope for 12A.

## 12B ingestion and normalization

12B adds a provider-neutral `TrendIngestionAdapter` seam and a synchronous ingestion ledger. Supported modes are `DISABLED`, `LOCAL_FIXTURE`, and `LIVE_READ_ONLY`; the latter fails closed unless a configured adapter exists. Local fixture candidates are bounded, recursively redacted, normalized deterministically, resolved to explicit 12A signal definitions, and either accepted into canonical observations or retained as rejected candidates with machine-readable reasons.

Each ingestion batch is owner/context/source scoped and idempotent. Candidate history preserves raw-safe input, normalized output, duplicate classification, quality, and rejection state. Authoritative source corrections are recorded in immutable observation revisions rather than overwriting facts or inflating independent observation counts. Replay does not create new snapshots or observations. Ingestion summaries expose descriptive coverage, quality, freshness, and data-gap information only; no demand, revenue, momentum, forecast, or score is derived.

The ingestion API is under `/api/v1/intelligence/trends/contexts/{context_id}/ingestions` with batch history, bounded candidates, rejections, and summaries. Live providers, workers, schedulers, retries, Product Channel, Calendar, Recovery, and certified intelligence integrations remain deferred to later slices.
