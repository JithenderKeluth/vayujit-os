# External source policy

Global, profile, and mission domain policy are intersected. Blocked domains always win. Robots and terms fields are operational classifications (`APPROVED`, `MANUAL_REVIEW_REQUIRED`, `NOT_APPROVED`, `UNKNOWN`) and make no unsupported legal claims. Consequential external research requires explicit mission policy and can be stopped globally, per provider, or per domain.

## Evidence intelligence handoff (Slice 6A.1D)

External fetch observations persist freshness windows (`fresh_until`, `stale_at`, `expires_at`) and verification metadata on the autonomous evidence row. Repeated fetches are idempotent by default; callers may opt into `refresh=true`. An unchanged refresh reuses the original observation, while a changed response receives a new fetch identity and remains append-only. Owner-scoped current and history views are available at `/api/v1/intelligence/external/observations/current` and `/api/v1/intelligence/external/observations/history`.

Only accepted (`SUPPORTED` or `VERIFIED`) evidence can project claims. The deterministic verifier records a versioned method, reason, verification timestamp, freshness at verification, and lineage. Diversity normalizes canonical URL/domain/provider/content hash so mirrors and duplicate pages cannot inflate source counts. Confidence is bounded by verification, freshness, diversity, completeness, contradictions, and unknowns.

The handoff services provide order-independent contradiction identities, server-derived materiality for external changes, and stable alert identities for review-worthy changes. Replays return existing rows instead of creating duplicates.
