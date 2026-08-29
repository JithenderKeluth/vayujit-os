# Manufacturer and supplier website intelligence (Slice 6D)

This slice provides a bounded, read-only, owner-scoped projection for public manufacturer and supplier websites. It never logs in, submits forms, sends email or WhatsApp, dispatches RFQs, or mutates supplier/product state.

## Source boundary

Supported classifications are `MANUFACTURER_WEBSITE`, `SUPPLIER_WEBSITE`, `DISTRIBUTOR_WEBSITE`, `WHOLESALER_WEBSITE`, `EXPORTER_WEBSITE`, `BRAND_WEBSITE`, `PUBLIC_BUSINESS_DIRECTORY`, and `PUBLIC_DOCUMENTATION`. Domains must remain explicitly allowlisted and HTTPS-safe. `example.org` is the deterministic local fixture domain; no live broad-web configuration is enabled by default.

## Evidence and claims

Extraction is deterministic and source-provided: business identity, business contacts, products, capabilities, MOQ, price, lead time, certifications, and risk signals. Website claims remain `UNVERIFIED`; certification logos are never treated as verified. Evidence remains `UNTRUSTED_EXTERNAL_DATA` and may enter the existing verifier only.

## Privacy and operations

Only public business contact metadata may be represented. Personal PII, credentials, cookies, raw HTML, and private headers are excluded. Refreshes, history, materiality, recovery, and alerts reuse existing intelligence ledgers. There is no supplier-contact capability in this slice.

## Local endpoints

`GET /api/v1/intelligence/websites/source-types`, `GET /api/v1/intelligence/websites/profiles`, `GET /api/v1/intelligence/websites/overview`, and authenticated `POST /api/v1/intelligence/websites/preview` expose the bounded workspace and deterministic preview path.

## PostgreSQL certification proof (6D.2A)

The disposable PostgreSQL baseline completed with **12 passed** focused tests; the final 6D.2A matrix adds **5 passed** proof tests. The fixture creates an owner, autonomous mission, source profile, manufacturer/supplier candidates, evidence, observations, and API-scoped projections. The current proof covers deterministic research, append/replay behavior, capability claim reviewability, certification removal, risk history, change/alert replay, owner scoping, and canonical lineage.

## Final 6D.2A proof closure (local PostgreSQL)

The five required final proof modules pass: **5 passed**. Reverse-pair capability contradiction is deduplicated and replays to zero delta with `REQUIRES_HUMAN_REVIEW`; the rejected/non-authoritative evidence matrix is 5/5 with zero changes; owner-forged profile/candidate mutation is safely rejected with owner-A rows unchanged; production change alerts retain change, evidence, source-profile, candidate, and correlation lineage across a 9-row matrix; and the canonical website flow replays with zero logical deltas and zero duplicate groups. The final security suite remains **82 passed**. Existing fixture warnings are framework deprecations only.

## 6D.2A final-four proof results

Owner mutation: profile/candidate forged-ID boundary checks pass; a complete eight-entity owner-B mutation matrix remains unavailable because the local owner model is singleton and several entities have no mutation endpoint. Alert types: the nine requested alert identities replay idempotently through the production alert helper, with one later identity creating exactly one new alert. Canonical lineage now records explicit orphan counters (all zero) and cross-owner lineage checks. Framework warnings are limited to FastAPI `on_event` deprecations and the existing Angular lifecycle warnings.

## Architecture-aware 6D.2A closure

Website observations, offerings, capability/facility/certification claims, and risk projections are immutable/read-only surfaces; no artificial mutation endpoints were added. Owner protection is enforced at existing profile/manufacturer/supplier lookup and update boundaries, with forged references returning safe not-found results. History is a derived `/history` projection over append-only observations, not a separate table. Canonical PostgreSQL verification records mission/profile/candidate/supplier/evidence/observation/offering/claim/contradiction/change/alert ownership and identity links. Explicit orphan and broken-reference counters are zero for all applicable persisted relationships; cross-owner lineage is zero. The nine alert identities replay with zero deltas, and a later identity creates one alert.

## Slice 6D.2B durable refresh, Product Channel, and Calendar

Website refresh scheduling is profile-scoped and supports `MANUAL`, `DAILY`, `WEEKLY`, and `MONTHLY` policies with an IANA timezone and one bounded next occurrence. Due materialization is owner-scoped, row-locked, unique by profile and scheduled timestamp, and emits `website.refresh.materialized`; replay returns the existing job. Execution records `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, or `SKIPPED`, reuses the refresh idempotency key, and never retries a completed job. Disabled sources and `BLOCKED`/`REVIEW_REQUIRED` classifications fail closed; the global intelligence emergency stop and disabled switch also skip work safely.

The durable refresh ledger is `intelligence_website_refresh_jobs`; source profiles retain next/last refresh timestamps, timezone, policy version, and failure code. Calendar exposes one server-derived `WEBSITE_SOURCE_REFRESH_DUE` event per scheduled profile with target, profile, domain, frequency, timestamp, timezone, and status. Product Channel remains read-only and server-derived, with website observation/offering/profile counts and existing review-only actions. Operations/System Doctor expose refresh backlog, queued/running/failed counts, next due, last success, scheduler state, and recovery registration without secrets or raw content. Catch-up is bounded to one next occurrence per materialization pass; no durable worker or connector mutation is introduced.
## 6D.2C Website Intelligence UX

The Angular Website Intelligence workspace is a single, authenticated, responsive surface at `/intelligence/websites`. Its navigation covers Overview, Manufacturers, Supplier Websites, Detail, Offerings, Capabilities, Certifications, Commercial Intelligence, Risk, Contradictions, Changes, Alerts, Source Profiles, Refresh, Recovery, History, Reports, Product Channel, Calendar, and Operations linkage. Counts, manufacturer lists, profiles, refresh jobs, calendar events, history, and recovery catalogs are loaded from the existing owner-scoped API; missing records render explicit empty states and API failures render safe user-facing errors.

The UI keeps the runtime boundary visible: website intelligence is local/controlled; live broad web, recursive crawling, and external AI are disabled/not configured; supplier contact is disabled; purchasing is not implemented. Public business contact fields are evidence only and never become contact actions. Source currencies are retained, claim verification/freshness/risk/match states are explicit, historical `NO_LONGER_OBSERVED` claims remain history-only, and reports are rendered as safe text rather than arbitrary HTML. Tables use captions and horizontal scroll containers; forms use labels, native controls, disabled submitting states, focus outlines, semantic landmarks, and responsive layouts for 390px, 768px, and desktop widths.

## 6D.2C server projections

The authenticated website router exposes owner-scoped read projections for `/contradictions` and `/contradictions/{id}`, `/changes` and `/changes/{id}`, `/alerts` and `/alerts/{id}`, `/reports` and `/reports/{id}`, and `/product-channel/{product_id}`. These reuse autonomous evidence, mission, change, alert, and report ledgers; foreign-owner identifiers return 404 and no raw provider payload, credentials, or unsafe HTML is returned. Website reports are limited to JSON, Markdown, and generated HTML formats (HTML is escaped for text rendering).

`GET /history` supports the bounded `candidate_id`, `event_type`, `source`, `date_from`, `date_to`, and `correlation_id` filters. Contradiction, change, and alert lists support candidate/type/materiality/severity/date/correlation filters where represented by existing fields. Product Channel fields are calculated server-side from owner-scoped website observations, offerings, missions, profiles, changes, contradictions, and alerts.

## Product Channel selected-product behavior

The Website Intelligence Product Channel projection is read-only and owner-scoped. The Angular workspace uses the existing Product-reference selection pattern: no Product means no projection request; selecting a Product calls the server endpoint and displays its bounded fields unchanged. The response contains no action contract, so no Product Channel actions are rendered. Empty, loading, 404, and server-failure states are safe and never expose persistence or provider details.
## 6D.2D hard-certification closure

The final local certification is recorded in [website-intelligence-certification.md](website-intelligence-certification.md). It verifies durable crash/replay recovery, real PostgreSQL concurrency, owner-scoped storage and lineage integrity, bounded operational projections, privacy-safe reporting, and the website refresh ledger. The authoritative table and integrity endpoints are `/api/v1/intelligence/websites/tables` and `/api/v1/intelligence/websites/integrity`; the existing Operations intelligence projection remains the bounded operational read model. Live provider behavior and production-scale guarantees remain outside this local certification boundary.
