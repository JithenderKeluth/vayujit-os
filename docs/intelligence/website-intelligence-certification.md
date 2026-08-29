# Website Intelligence 6D.2D Certification

## Scope

This document records the final local hard-certification contract for the manufacturer/supplier website intelligence slice. It covers deterministic extraction, durable autonomous missions, PostgreSQL refresh execution, replay, recovery, owner isolation, evidence lineage, projections, and operational reporting. It does not claim live-provider, production, or multi-region certification.

## Storage and lineage ledger

The website ledger uses owner-scoped rows and append-only version/event semantics. The implementation exposes `GET /api/v1/intelligence/websites/tables` with the authoritative inventory. Website-owned tables are:

- `intelligence_website_source_profiles` — canonical owner/domain/source identity.
- `intelligence_website_source_profile_versions` — immutable profile versions.
- `intelligence_manufacturer_candidates` — owner-scoped manufacturer identities.
- `intelligence_supplier_website_candidates` — supplier candidates linked to supplier, manufacturer, and source profile.
- `intelligence_website_observations` — immutable retrieval observations linked to mission/profile/candidate; replay reuses retrieval identity.
- `intelligence_website_offerings` — candidate/product/opportunity-linked commercial observations.
- `intelligence_website_claims` — append-only claim facts keyed by claim identity.
- `intelligence_website_refresh_jobs` — durable scheduled refresh work with lease/checkpoint state.
- `intelligence_website_refresh_recovery` — idempotent recovery records for refresh jobs.

Autonomous mission, task, attempt, evidence, claim, contradiction, change, alert, report, schedule, and recovery tables provide the durable execution ledger. `audit_events` records owner-attributed decisions and terminal outcomes. Foreign keys and owner predicates are verified by the website integrity projection.

## Crash and replay matrix

The certification tests exercise crash-before-fetch, crash-after-fetch/evidence checkpoint, lease expiry recovery, and replay. Recovery must produce one terminal mission/job, one evidence set per retrieval identity, no duplicate canonical identities, and no duplicate reports or alerts. Local artifacts are not required by this slice; filesystem certification therefore reports `N/A` rather than inventing a file ledger.

## Concurrency proof

`run_website_mission` and profile/extraction persistence use PostgreSQL transaction advisory locks for the owner-scoped logical identity. The certification test runs two real database sessions concurrently and asserts one mission, profile, manufacturer candidate, supplier candidate, and one canonical identity. Repeat the test three times for release evidence; SQLite is not accepted as concurrency evidence.

## Integrity and operations projection

`GET /api/v1/intelligence/websites/integrity` returns duplicate, orphan, cross-owner, broken-lineage, storage, and filesystem counters. A passing projection has all counters zero and `classification: PASS`. The existing `GET /api/v1/operations/intelligence/projection` consumes the same bounded integrity projection, so the Operations control center remains the operational read model. No credentials, tokens, cookies, database URLs, local paths, SQL, or tracebacks are returned.

## Performance and query safety

The existing external performance projection records ten warm samples per measured query and bounded timing. Certification records time-to-first-evidence, mission completion, and query counts when the integration environment is available. Results are baseline evidence for this repository only; no production SLO is inferred. Query-count regressions are investigated before release rather than hidden behind a permissive threshold.

## Security and UX regression gates

Run the website security/privacy tests and Angular tests for navigation, authenticated owner scope, XSS-safe reports, responsive layout, and empty/error states. Verify API CORS remains restricted to the local frontend origin and that report/export responses are safe text/HTML. Do not treat provider credentials or raw fetched content as UI-safe output.

## Local certification commands

```powershell
npm.cmd run test:intelligence:website:final
npm.cmd run test:api:integration
npm.cmd run lint
npm.cmd run build
npm.cmd run format:check
git diff --check
```

The focused command provisions the disposable PostgreSQL test database through the repository integration script. If Docker/PostgreSQL is unavailable, report the tests as pending; do not convert skips into passes. Static checks remain valid independently.

## Acceptance boundary

This is local deterministic and disposable-PostgreSQL certification. Live manufacturer/supplier sites, provider rate limits, production TLS/DNS, backup restore, multi-region failover, and external security assessment remain outside this slice and are explicitly not certified.
