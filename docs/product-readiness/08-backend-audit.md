# Backend audit

FastAPI routers, domain services, SQLAlchemy models, workers, schedulers, provider adapters, evidence/provenance and owner-scoped authorities are present. Business Agent and live-search validation demonstrate functioning request/persistence boundaries.

Key findings:

- ApprovedWebFetcher correctly fails closed, but configuration currently prevents the first live artifact.
- Provider modes and kill switches are explicit; live capability must not be inferred from adapter existence.
- Durable checkpoints and recovery exist, but provider outage/quota/partial artifact UX needs milestone tests.
- ProductOpportunity, supplier, evidence and landed-cost authorities should remain single writers; projections should not recalculate facts.
- Validate pagination, bounded queries, retries and transaction boundaries on affected vertical slices rather than broad refactoring.
