# Review Intelligence 11A foundation

## Reuse audit

Review Intelligence reuses the owner/authentication dependency, canonical `Product`, `Brand`, `ProductOpportunity`, `CompetitorContext`, `IntelligenceSource`, and `IntelligenceEvidence` models, the existing audit service, Operations projection, System Doctor, and the shared database/migration infrastructure. It does not create a second generic evidence store, scheduler, worker, recovery registry, Product Channel integration, or Calendar integration.

## Foundation boundaries

The 11A tables are `ReviewContext`, `ReviewSource`, `ReviewRecord`, and immutable `ReviewSnapshot`. Review records are customer-feedback evidence only; review counts and ratings never imply sales, demand, revenue, conversion, market size, or commercial success. Source verification, review verification, and provider-supplied verified-purchase state remain separate.

Review titles and bodies are stored and rendered as text. The API does not execute review content, persist credentials, tokens, or unnecessary personal data. Reviewer identifiers are optional and should be limited to permitted public lineage identifiers.

Provider mode is local/manual by default. No live scraper or external write capability is registered. No Product Channel or Calendar integration is required in 11A. No new Recovery action or Review-specific scheduler/worker is required.

## Migration

`20261113_0122_review_intelligence_foundation` creates the owner-scoped context/source/record/snapshot tables, ownership and lineage foreign keys, rating/helpful-count checks, identity/fingerprint uniqueness, and access-pattern indexes.

## Explicit non-goals

- NO PRODUCT CHANNEL INTEGRATION REQUIRED IN 11A.
- NO CALENDAR INTEGRATION REQUIRED IN 11A.
- NO NEW RECOVERY ACTION REQUIRED IN 11A.
- No review-specific scheduler or worker is registered.

# Review Intelligence 11B ingestion and evidence normalization

11B adds provider-neutral, deterministic ingestion around the 11A evidence model. `LOCAL_FIXTURE` is the only executable adapter. `DISABLED` and `LIVE_READ_ONLY` fail closed with safe status/error metadata; no live scraper, connector credential, cookie, session, or external write is used.

`ReviewIngestionBatch` is the idempotent request/processing ledger. `ReviewIngestionCandidate` stores bounded raw/normalized candidate state, quality, duplicate classification, and rejection reason. `ReviewObservation` is append-only history for changed facts; the current `ReviewRecord` is updated only through a new observation. Raw title/body are preserved separately from normalized Unicode/whitespace/date representations. No translation, sentiment, semantic rewrite, or business inference occurs.

Identity uses provider plus provider review ID first and a versioned structural fingerprint fallback. Exact replay, authoritative duplicate, fingerprint duplicate, possible duplicate, and distinct classifications are explicit. Possible cross-provider duplicates are retained independently and never merged. Invalid, oversized, malformed, or hostile payloads are rejected without creating a canonical review. Snapshots are accepted-record only and retain source/freshness/evidence lineage.

The API provides ingestion create, bounded batch history/detail, candidate/rejection views, and an ingestion summary under `/api/v1/intelligence/reviews`. Operations and System Doctor expose batch counts and lineage checks. Ingestion is not connected to Recovery, scheduler, worker, Product Channel, Calendar, Business Agent, or Winning Product intelligence. A future live provider requires a separately reviewed adapter, explicit configuration, and certification; it is not enabled by this slice.

Migration `20261114_0123_review_ingestion_normalization` adds the ingestion batch, candidate, observation tables and the `ReviewRecord.ingestion_batch_id` lineage column.

# Review Intelligence 11C topics, sentiment, themes, and pain points

11C adds immutable, owner-scoped analysis snapshots over accepted `ReviewSnapshot` evidence. `LOCAL_FIXTURE` runs a deterministic lexical engine; `DISABLED` and `LIVE_READ_ONLY` fail closed without external calls. A request is idempotent for the same owner, context, snapshot, and version tuple; a changed snapshot creates a new analysis version.

The cohort records every accepted review as included or excluded with an explicit reason (`UNSUPPORTED_LANGUAGE` or `INSUFFICIENT_TEXT`). Reviews without ratings remain eligible for text analysis. Unsupported languages are not translated; annotations retain input language, analysis language, and translation lineage for future providers. Sentiment is limited to POSITIVE, NEGATIVE, MIXED, NEUTRAL, or UNKNOWN. Topics, recurring themes, pain points, praised attributes, feature requests, and quality/defect signals are derived only from deterministic lexical matches and retain support counts, confidence, severity, evidence review IDs, and a calculation method version. Rating distributions include count/min/max/mean/median/buckets and an evidence-backed text/rating disagreement summary.

The API exposes create/list/current/detail and item-type-filtered analysis views under `/api/v1/intelligence/reviews/contexts/{context_id}/analyses`. Operations projections and System Doctor expose analysis counts, excluded/unsupported reviews, unknown sentiment, gaps, annotations, and items. Analysis rows and annotations/items are append-only; no business inference is made about sales, demand, conversion, revenue, market size, or commercial success. This slice does not add Product Channel, Calendar, Recovery, scheduler, worker, Business Agent, Winning Product, or external provider behavior.

Migration: `20261115_0124_review_analysis` (down revision `20261114_0123`).


# Review Intelligence 11D product gaps and opportunity signals

11D derives immutable, deterministic product-gap analyses from completed 11C review analyses only. Each analysis is owner- and context-scoped, bound to its review snapshot and input fingerprint, and replay-safe. Product gaps use a bounded taxonomy and retain support/cohort counts, source distribution, review/evidence lineage, freshness, confidence, limitations, and explicit evidence strength. Positive evidence is represented as PRESERVE_ATTRIBUTE/PRESERVE_STRENGTH; mixed positive and negative evidence is represented as a TRADE_OFF with both sides preserved.

Opportunity signals are review-derived hypotheses, not demand, sales, revenue, market-size, or winning-product scores. Signals expose support status and required follow-up contracts such as DEMAND_VALIDATION_REQUIRED, COMPETITOR_VALIDATION_REQUIRED, COMMERCIAL_VALIDATION_REQUIRED, and SUPPLIER_FEASIBILITY_REQUIRED; no external competitor, supplier, or marketplace call is made automatically. No Product Channel, Calendar, Recovery, scheduler, worker, or Business Agent integration is added.

The API exposes create/current/history/detail plus product-gap and opportunity-signal views under /api/v1/intelligence/reviews/contexts/{context_id}/gap-analyses. Operations and System Doctor report gap-analysis, gap, signal, contradiction, preserve, lineage, evidence, and validation-integrity counters. Migration 20261116_0125_review_opportunity_signals adds the immutable analysis, gap, and signal tables.

## 11E Review change intelligence

Review change comparisons are immutable, deterministic comparisons between two
owner-scoped historical analyses in the same Review Context. They describe
changes in observed or derived review evidence only: support, proportions,
sentiment, themes, pain points, praise, feature requests, source coverage,
freshness, contradictions, product-gap hypotheses, and opportunity-signal
states. They never infer demand, sales, revenue, market growth, or commercial
attractiveness.

The API provides comparison creation/history/current/detail, bounded event
filters, material/unresolved/alert-eligible event views, and research-gap
views. Replay is idempotent and events retain baseline/current lineage,
denominators, sample-size limitations, freshness, confidence, materiality,
and evidence references. The Angular workspace exposes this as “Review
evidence changed”.

Review changes do not emit Calendar events, Review-specific worker jobs,
Recovery actions, external alerts, or Product Channel writes. Product Channel,
Business Agent, Winning Product, and durable scheduling integrations remain
owned by their later slices.