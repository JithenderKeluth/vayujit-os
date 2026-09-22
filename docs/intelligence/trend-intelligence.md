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

## 12D trend change and momentum intelligence

12D compares two existing immutable 12C analyses in chronological order. It never mutates observations, snapshots, analyses, or series. Comparisons are owner/context scoped, calculation-versioned, materiality-policy-versioned, fingerprinted, and idempotent. A comparison stores the exact baseline/current analysis and snapshot IDs plus safe summary and limitation metadata.

Each TrendChangeEvent is emitted for an observed cohort that increases, decreases, reverses, weakens, stabilizes, appears, disappears, changes freshness, or changes evidence quality. Old/new values, Decimal-safe absolute and relative deltas, and an explicit ZERO_DENOMINATOR reason are preserved. Added cohorts are EMERGING, removed cohorts are DISAPPEARED, and disappearance is not treated as a confirmed real-world absence without current evidence. Event status is deterministic (NEW, ONGOING, or RESOLVED) and links back to signal/source IDs, baseline/current series, observation IDs, evidence IDs, and freshness.

Momentum is descriptive state only: SUSTAINED_INCREASE, SUSTAINED_DECREASE, EMERGING_INCREASE, EMERGING_DECREASE, WEAKENING_INCREASE, WEAKENING_DECREASE, REVERSING, STABLE, MIXED, INSUFFICIENT_EVIDENCE, NOT_COMPARABLE, or UNKNOWN. Sustained states require at least three current observations, persistent 12C direction, and no missing periods. A single observation never establishes sustained momentum. Materiality is bounded by absolute/relative movement, state/reversal changes, comparability, and evidence sufficiency. Alert eligibility is only a stored descriptive classification (NO_ALERT, REVIEW, or ALERT); 12D sends no notifications.

The API adds comparison creation/list/current/detail, event filters, change-history, gaps, and system-doctor routes under /api/v1/intelligence/trends. Operations expose comparison/event counts and review-eligible activity. The Angular workspace renders comparison lineage and event old/new values, deltas, momentum, materiality, status, alert eligibility, freshness, and limitations with safe interpolation.

12D explicitly does not forecast, infer demand, sales, revenue, market size, commercial attractiveness, winning-product scores, recommendations, or external notifications. It does not modify Product Channel, Calendar, Recovery, workers, schedulers, publishing, marketplace connectors, agents, or frozen 12A-12C observation/ingestion/analysis semantics.
## 12E validation and cross-source confidence

12E adds an immutable, versioned validation ledger over a 12C analysis and optional 12D comparison. A validation is owner/context/snapshot scoped, fingerprinted, and idempotent. It records explicit evidence, source, time, freshness, quality, agreement, contradiction, materiality, and alert coverage without rewriting upstream facts.

Validation statuses are VALIDATED, PARTIALLY_VALIDATED, INSUFFICIENT_EVIDENCE, CONTRADICTORY, STALE, NOT_COMPARABLE, and RESEARCH_REQUIRED. Every validation emits explicit hypotheses with supporting and opposing source, signal, series, observation, evidence, and change-event lineage. Comparable cohorts are matched by signal, measurement, unit, scale, geography, granularity, and time coverage. Agreement requires comparable independent evidence; opposite movement is persisted as a blocking contradiction rather than averaged away. Source independence and source diversity are exposed separately from sample size.

Confidence is bounded to HIGH, MODERATE, LOW, or UNKNOWN and is derived only from evidence sufficiency, independent-source coverage, agreement, freshness, quality, completeness, and comparability. A single source, stale evidence, unresolved contradiction, missing history, or incomplete lineage prevents high confidence. Downstream readiness is explicit and remains evidence-only; validation never becomes a commercial, demand, sales, revenue, forecast, or product recommendation.

The API is under /api/v1/intelligence/trends/contexts/{context_id}/validations: create/list/current/detail plus hypotheses, contradictions, gaps, and source lineage. Operations and System Doctor expose validation counts and hard integrity checks for orphan lineage, duplicate fingerprints, stale/high-confidence combinations, single-source high confidence, unresolved contradictions, and semantic leakage. The Angular Trend workspace can validate the latest analysis and renders status, confidence, readiness, independent-source count, agreement, freshness, gaps, and limitations with safe interpolation.

12E does not modify Product Channel, Calendar, Recovery, workers, schedulers, publishing, marketplace connectors, Business Agent, Winning Product, Competitor, or Review intelligence. Research gaps and recommendations are persisted as bounded follow-up metadata only. Replaying the same analysis/comparison reuses the same validation; new evidence requires a new immutable upstream analysis/snapshot. Migration 20261123_0132_trend_validation_confidence follows 20261122_0131 and is reversible only through the repository disposable-database migration guard.