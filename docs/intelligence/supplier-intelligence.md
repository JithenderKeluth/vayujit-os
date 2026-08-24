# Supplier Intelligence

Supplier Intelligence is an Intelligence-owned, owner-scoped bounded context. It normalizes online and offline supplier records, offerings, evidence, verification, commercial terms, risk, score evaluations, matches, and human decisions.

The default provider is `LOCAL FIXTURE`. IndiaMART, Alibaba, TradeIndia, and Global Sources are represented as source types only; live connectors and unrestricted scraping are disabled.

Supplier searches are durable and idempotent. A bounded worker creates supplier candidates, offerings, evidence, matches, rule outcomes, risk assessments, and explainable scores. No supplier is contacted, purchased from, or automatically verified.

## Local certification and safety

- Crash-before recovery uses a leased `SupplierSearch`; the deterministic provider execution id is stable and replayed searches are idempotent.
- Crash-after recovery persists the provider checkpoint before finalization and never repeats a completed provider execution.
- Search, supplier, offering, evidence, score, decision, and recovery identities are owner-scoped and keyed by explicit logical/idempotency contracts. The local worker is bounded and does not contact external suppliers.
- Recovery actions are limited to executable retry, reconcile, review, refresh-evidence, and cancel paths. No outreach, RFQ, purchasing, payment, or autonomous supplier mutation is available.

## Commercial, verification, and history

Commercial terms are append-only by supplier offering and version. Unit price, currency, MOQ, fees, payment terms, Incoterm, validity, evidence ids, and sample/production/dispatch lead times are retained; historical versions are read-only. Currency values are never ranked as equivalent across currencies without an explicit conversion assumption.

Verification transitions are explicit and evidence-gated for strong states. Certification claims, score evaluations, risk assessments, contacts, communication status, and recovery actions are appended to the unified supplier history with correlation metadata. Contacts are business-only records; the application never sends messages.

## Evidence, freshness, and source boundaries

Evidence labels are bounded (`OBSERVED`, `MANUAL`, `SELF_REPORTED`, `VERIFIED`, `ASSUMED`, `DERIVED`). Price, MOQ, lead time, contact, certification, verification, capability, and offering freshness are tracked independently. Source diversity deduplicates mirrored references and reports independent/profile/commercial/verification counts.

The default provider is `LOCAL FIXTURE`. IndiaMART, Alibaba, TradeIndia, and Global Sources are source classifications only; live connectors and unrestricted scraping are disabled. Document ingestion is not enabled; only safe metadata references are retained.

## Storage and operations

Supplier-owned tables are listed in `supplier-security.md`; migrations are replay-tested through upgrade/downgrade/upgrade. Owner predicates and foreign keys prevent cross-owner and orphaned records. The worker, recovery projections, source registry, and bounded local provider are visible to the system doctor. Use `npm run intelligence:worker:once` for one bounded local worker pass.

## UX and accepted boundaries

The Angular workspace provides overview, local search, supplier list/detail, verification, decisions, report, and offline/manual entry surfaces. Unsafe text is rendered as text, not HTML. Static labels and responsive layout are covered by component checks; axe and automated viewport runs are not configured. External supplier connectors, autonomous contact, purchasing, payment, live scraping, and document ingestion remain intentionally deferred or disabled.
`n## Final certification record`n`nIndependent PostgreSQL sessions cover search, supplier identity, offerings, evidence, commercial versions, scores, shortlist decisions, certification claims, and recovery. Advisory transaction locks plus owner-scoped uniqueness prevent duplicate logical records; replay and crash-before/after paths remain bounded and idempotent.
