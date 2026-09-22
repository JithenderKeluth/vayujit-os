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

## 12C signal and time-series intelligence

12C creates immutable `TrendAnalysis` records bound to an owner, context, and immutable `TrendSnapshot`. A deterministic calculation version and input fingerprint make repeated analysis requests idempotent; a new snapshot produces a new analysis version. `TrendAnalysisSeries` preserves each exact signal/source/measurement/unit/scale/geography/granularity cohort instead of averaging incompatible evidence. `TrendAnalysisGap` records bounded evidence limitations.

Series are ordered by `period_start`, then `period_end`, then `observed_at`, with observation ID as a deterministic tie-breaker. Daily, weekly, monthly, quarterly, and hourly gaps are detected from explicit granularity; missing values are never interpolated. Numeric statistics use Decimal-safe count, minimum, maximum, mean, median, first, latest, range, and mean absolute change. Absolute change is latest minus first. Relative percentage change is omitted with `ZERO_DENOMINATOR` when the baseline is zero.

Direction is descriptive only: at least two comparable numeric observations are required; all positive movements are `INCREASING`, all negative `DECREASING`, all zero `STABLE`, otherwise `MIXED`. Persistence requires at least three observations and classifies uninterrupted movement as `PERSISTENT_INCREASE` or `PERSISTENT_DECREASE`, all-flat as `FLAT`, sign reversals as `REVERSING`, and other movement as `INTERMITTENT`. Variability uses historical range: zero is `STABLE`, up to 5% of absolute mean is `LOW_VARIABILITY`, up to 20% is `MODERATE_VARIABILITY`, otherwise `HIGH_VARIABILITY`; fewer than two numeric points are `UNKNOWN`.

Readiness is evidence-based (`AVAILABLE`, `PARTIAL`, `INSUFFICIENT_EVIDENCE`, `NOT_COMPARABLE`, `UNSUPPORTED`). One observation can describe current state but cannot establish direction, persistence, or variability. Two observations can establish simple change and movement, but not persistence. Boolean and category values remain transitions/sequences and do not receive numeric statistics. Freshness is aggregated as `CURRENT`, `STALE`, `MIXED`, or `UNKNOWN`; no commercial confidence score is produced.

The 12C API adds `POST /contexts/{context_id}/analyses`, analysis history/current retrieval, bounded series and gap retrieval, and analysis-scoped diagnostics. Operations expose analysis, series, and gap counts. The Angular Trend workspace renders source/signal IDs, window, sample size, change, direction, persistence, variability, and missing periods using safe interpolation; no forecast line or interpolation is shown.

12C has a hard no-forecast, no-seasonality, no-demand, no-sales, no-revenue, no-market-size, no-momentum-score, no-generic-score, and no-Winning-Product boundary. It does not modify Product Channel, Calendar, Recovery, workers, schedulers, agents, or certified Competitor/Review/Winning Product systems. Every series retains observation and evidence IDs for lineage back to the snapshot, 12B candidate/batch records, source, and provenance where present.
