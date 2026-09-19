# Competitive Change Intelligence (Slice 10D)

Slice 10D compares two immutable, owner-scoped Slice 10C commercial analyses. A comparison stores the exact analysis and discovery-snapshot references, a stable input fingerprint, and a versioned `competitor-change-v1` calculation. It never compares mutable provider state.

## Deterministic semantics

- Product entry and exit are identity- and cohort-based. A product missing from one observation is `POSSIBLY_REMOVED` and `UNRESOLVED`; missing evidence is never treated as a confirmed removal.
- Price deltas use `Decimal`, require the same known currency, and omit percentage deltas for unknown prices, a zero denominator, stale/contradictory evidence, or currency mismatch.
- Ratings and review counts are descriptive. Review growth is never interpreted as sales or demand.
- Concentration, assortment, and positioning changes are derived only from the referenced 10C calculation and preserve that lineage.
- Materiality uses `competitor-change-materiality-v1`: price 5/10/20%, rating 0.2/0.5/1.0, review-count 25/50/100%, concentration share 0.05/0.10/0.20. Results are `IMMATERIAL`, `LOW`, `MODERATE`, `HIGH`, or `UNKNOWN`.
- Replays are idempotent by owner/context/input fingerprint and event fingerprint. Persistent observations become `ONGOING`; a reverse movement is `REVERTED`; unresolved evidence stays unresolved.

## API

- `POST /api/v1/intelligence/competitors/change-intelligence/contexts/{context_id}/comparisons/run`
- `GET /api/v1/intelligence/competitors/change-intelligence/contexts/{context_id}/changes`
- `GET /api/v1/intelligence/competitors/change-intelligence/contexts/{context_id}/history`
- `GET /api/v1/intelligence/competitors/change-intelligence/comparisons/{comparison_id}`
- `GET /api/v1/intelligence/competitors/change-intelligence/changes/{event_id}`
- `POST /api/v1/intelligence/competitors/change-intelligence/changes/{event_id}/review`
- `GET /api/v1/intelligence/competitors/change-intelligence/contexts/{context_id}/material-changes`
- `GET /api/v1/intelligence/competitors/change-intelligence/contexts/{context_id}/unresolved`
- `GET /api/v1/intelligence/competitors/change-intelligence/contexts/{context_id}/alert-eligible`
- `GET /api/v1/intelligence/competitors/change-intelligence/system-doctor`

Alert eligibility is persisted separately and is local-only; no external notifications or competitor refresh worker are introduced. Calendar remains unchanged because a historical comparison does not create a future review date. Meaningful moderate/high changes are recorded for the existing Product Channel/audit boundary when the context has a product.

The System Doctor reports orphan lineage, duplicate logical events/alerts, invalid deltas, currency mismatches, invalid materiality/alert states, derived events without 10C lineage, and unsafe resolution states.
