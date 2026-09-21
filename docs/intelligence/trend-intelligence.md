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
