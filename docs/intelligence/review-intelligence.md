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
