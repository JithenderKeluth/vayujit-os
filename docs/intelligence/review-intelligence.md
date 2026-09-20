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
