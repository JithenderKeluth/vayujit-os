# Trends and Competition

Fixtures carry explicit trend state, velocity proxy, seasonality, freshness, competitor snapshots, ratings, review counts, and review-moat flags. Competition opportunity is the inverse of competition intensity, so higher is more favorable. A high review moat is an advisory launch objection, not a claim about live marketplace rank.

Observations are append-only snapshots tied to local evidence. Stale observations remain visible and reduce confidence. Seasonal demand is modeled separately from trend strength.

## Slice 2 local certification closure

The local provider is deterministic and external research remains disabled. Trend observations are append-only and carry candidate/opportunity lineage, market/category, velocity, acceleration, seasonality, confidence, source evidence IDs, timestamps, and correlation IDs. Physical rules normalize kg/g and cm/m/mm, derive volume and volumetric weight, and evaluate PASS/REVIEW_REQUIRED/BLOCK. Policy scopes resolve GLOBAL ? MARKET ? MARKETPLACE ? CATEGORY ? PROFILE ? MISSION, with hard blocks preserved unless an explicit auditable override is requested.

Economics are estimates, never supplier-confirmed: each input is OBSERVED, ASSUMED, ESTIMATED, or UNKNOWN with currency, evidence/assumption reason, and confidence. Outputs include landed-like basis, contribution, margin, break-even price, maximum CAC, ROAS, initial inventory, and preliminary capital. Source diversity and evidence quality are deterministic and visible. Supplier availability remains UNKNOWN / NOT SCORED, and legal output is always `LEGAL REVIEW MAY BE REQUIRED` rather than clearance.

Mission run-now and future schedules use owner-scoped idempotency keys. Worker lifecycle and recovery records are append-only; replaying the same key reuses the prior result. Reports expose bounded provenance only and do not include credentials, tokens, cookies, DSNs, local paths, or raw secrets. The Operations API consumes only the bounded Intelligence projection.
