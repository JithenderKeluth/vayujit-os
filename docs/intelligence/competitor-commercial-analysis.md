# Competitor commercial analysis (10C)

10C turns the authoritative 10A competitor observations and 10B discovery snapshots into an owner-scoped, immutable commercial analysis. It is deterministic and versioned by `calculation_version`; rerunning the same context with the same idempotency key reuses the existing analysis.

## Safety and semantics

- Only confirmed or probable product identities are included in the comparable cohort. Ambiguous and rejected identities are retained as research gaps and never silently promoted.
- Prices are kept as `Decimal` values and compared only when their currencies agree. Mixed currencies are reported as `MULTI_CURRENCY_NOT_COMPARABLE`; the service never performs an implicit conversion.
- Price distributions, percentile bands, positioning, concentration, ratings/reviews, assortment, differentiation, and gaps are explainable from the stored observation IDs and source references.
- Missing values remain unknown. Review counts are not sales estimates, and contradictions are surfaced rather than resolved by precedence.
- Each run stores a cohort snapshot, fingerprint, evidence coverage, freshness, research gaps, and audit event. History is append-only and owner scoped.

## API and UI

The API is mounted under `/api/v1/intelligence/competitors/commercial-analysis`:

- `POST /contexts/{context_id}/analyses/run` creates or reuses an analysis.
- `GET /contexts/{context_id}/analyses/current` returns the latest analysis.
- `GET /contexts/{context_id}/analyses` lists immutable history.
- Section endpoints expose pricing, concentration, ratings/reviews, assortment, positioning, differentiation, gaps, research gaps, evidence, and cohort entries.
- `/system-doctor` reports commercial lineage, comparability, cohort, and orphan checks.

The Competitor Intelligence workspace provides a guarded **Run commercial analysis** action and displays status, comparability, currency, calculation version, and evidence coverage summary. It does not expose credentials or provider payloads.

## 9B integration contract

10C publishes descriptive, versioned outputs for future 9B consumers: competitor density and cohort coverage, price distribution/position, brand and seller concentration, rating/review barriers, assortment differentiation, and evidence/freshness gaps. 9B must consume these as evidence-backed inputs without re-running a competing pricing or confidence formula, changing its certified scores, or double-counting observations.
## Limitations

This slice is local/deterministic. It does not call external providers, infer demand or sales, convert currencies, mutate marketplace data, or provide change monitoring. Live certification still requires separately configured external evidence and remains outside this local implementation.