# Competitor Intelligence foundation (10A)

The 10A foundation is an owner-scoped, evidence-first ledger for factual
competitor observations. It deliberately stops before discovery, matching,
pricing analytics, change detection, and recommendations.

## Reused architecture

- `Product`, `Brand`, and `ProductOpportunity` remain the canonical subject
  records.
- `IntelligenceSource` and `IntelligenceEvidence` are optional provenance
  links on observations.
- Audit events use the shared `record_event` service and owner identity.
- Existing research-engine tables (`intelligence_competitor_products` and
  `intelligence_competitor_snapshots`) remain unchanged. The 10A foundation
  uses `intelligence_competitor_foundation_products` and
  `intelligence_competitor_foundation_snapshots` to avoid changing that
  established runtime contract.

## Records and invariants

`CompetitorContext` attaches a bounded investigation to a Product Opportunity,
Product, or Brand. `CompetitorEntity` represents a brand, seller,
manufacturer, merchant, operator, or unknown entity. `CompetitorProduct`
stores marketplace identity and an explicit identity state, including
`AMBIGUOUS` and `UNRESOLVED`. `CompetitorObservation` is append-only factual
source data with Decimal numeric values, freshness, and optional source/evidence
lineage. `CompetitorSnapshot` is versioned and immutable by API design.

All writes require the authenticated owner, use owner-scoped idempotency, and
emit a namespaced audit event. Reads are bounded and random or cross-owner IDs
return a safe 404. Contradictory observations are retained as separate
observation keys; no winner is inferred.

## API and UI

The authenticated API is rooted at `/api/v1/intelligence/competitors` and
provides context, entity, product, identity, observation, snapshot, and
integrity endpoints. The Angular workspace is available at
`/intelligence/competitors`; it supports local context/entity/product entry,
identity confirmation, and integrity status without external calls.

System Doctor includes `checks.competitor_intelligence` with orphan,
subject/provenance-lineage, duplicate, enum, currency, freshness, numeric,
and snapshot-version counts. 10A does not register a durable worker, recovery
action, Product Channel, Calendar item, or Business Agent capability.
