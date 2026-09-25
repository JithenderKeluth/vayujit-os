# Provider-neutral supplier discovery

Phase 14F reuses the existing SupplierSearch ledger, Website Intelligence extraction and observation lineage, supplier identity/source/evidence persistence, Business Agent capability registry, audit events, and Operations views.

## Local mode

`POST /api/v1/intelligence/suppliers/research` accepts a bounded product query. The current authorized mode is `PROVIDER_NEUTRAL` backed by deterministic local fixtures. It is owner-scoped, idempotent, capped at 20 candidates, read-only with respect to external systems, and persists source-provided claims as unverified evidence. Duplicate identities remain one supplier while each distinct approved website observation and source lineage is retained. Contradictory observations remain reviewable through the existing Website Intelligence lineage.

The local fixture exercises successful, duplicate, contradiction, prompt-injection, access-blocked, timeout, and zero-result outcomes. Prompt-injection text is treated as untrusted source data and is never executable.

## Live boundary

No authorized live discovery provider is configured by this slice. Requests are therefore deterministic and report `live_discovery: PENDING`; unsupported modes fail closed with `DISCOVERY_PROVIDER_UNAVAILABLE`. No marketplace connector, external write, unrestricted scraper, or credential path is invoked.

The Angular Supplier Intelligence workspace exposes the opt-in **Research approved supplier websites** action and refreshes the existing supplier list. Business Agent `supplier.discovery` uses the same bounded execution path and records `supplier.discovery_invoked`.