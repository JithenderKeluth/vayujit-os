# Website Intelligence UX (Slice 6D.2C)

The workspace renders server-backed website intelligence projections with safe empty/error states, semantic tables, keyboard-accessible detail buttons, and text-only report rendering. Contradictions, changes, alerts, reports, Product Channel state, and bounded history filters are loaded from `/api/v1/intelligence/websites`; no client-side derivation of risk, confidence, verification, counts, or refresh due state is used.

## Product Channel UI closure

The Product Channel panel accepts the same owner-scoped Product reference used by the Intelligence workspace. With no reference it shows an empty guidance state and makes no request. A valid reference loads GET /api/v1/intelligence/websites/product-channel/{product_id} and renders the returned research status, counts, timestamps, freshness, confidence, risk, verification, contradiction/change/alert counts, refresh due state, and follow-up state directly. Loading and owner-safe error states are explicit; the endpoint currently advertises no actions, so the UI exposes no contact, RFQ, purchase, or payment controls. Products without website research remain NOT_RESEARCHED/UNKNOWN rather than fabricated conclusions.
## 6D.2D hard-certification closure

The final local certification is recorded in [website-intelligence-certification.md](website-intelligence-certification.md). It verifies durable crash/replay recovery, real PostgreSQL concurrency, owner-scoped storage and lineage integrity, bounded operational projections, privacy-safe reporting, and the website refresh ledger. The authoritative table and integrity endpoints are `/api/v1/intelligence/websites/tables` and `/api/v1/intelligence/websites/integrity`; the existing Operations intelligence projection remains the bounded operational read model. Live provider behavior and production-scale guarantees remain outside this local certification boundary.
