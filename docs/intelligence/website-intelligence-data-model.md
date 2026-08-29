# Website intelligence data model

Website research is bounded to one approved HTTPS page and is persisted in
owner-scoped profile, candidate, observation, offering, and claim tables.
Observations are append-oriented: a changed value creates a new row linked to
the prior row; the prior row is never updated. Offerings retain source-profile,
candidate, observation, evidence, match, and correlation lineage. Capability,
facility, certification, commercial, and risk claims remain source-provided
and reviewable rather than being promoted to verified facts.

Autonomous mission changes and alerts use the existing change/alert tables,
with deterministic materiality and idempotency identities.


## PostgreSQL proof results

The baseline focused PostgreSQL run completed **12 passed** tests; the final 6D.2A proof run completed **5 passed** tests. Observations append with previous_observation_id; exact replay preserves logical row counts. Certification claims preserve nine historical identities and transition to NO_LONGER_OBSERVED; risk observations retain history; change/alert replay is idempotent; all persisted website rows remain owner-scoped; canonical offering lineage retains profile, observation, mission, and correlation references.

## Final 6D.2A proof closure (local PostgreSQL)

The five required final proof modules pass: **5 passed**. Reverse-pair capability contradiction is deduplicated and replays to zero delta with `REQUIRES_HUMAN_REVIEW`; the rejected/non-authoritative evidence matrix is 5/5 with zero changes; owner-forged profile/candidate mutation is safely rejected with owner-A rows unchanged; production change alerts retain change, evidence, source-profile, candidate, and correlation lineage across a 9-row matrix; and the canonical website flow replays with zero logical deltas and zero duplicate groups. The final security suite remains **82 passed**. Existing fixture warnings are framework deprecations only.

## 6D.2A final-four proof results

Owner mutation: profile/candidate forged-ID boundary checks pass; a complete eight-entity owner-B mutation matrix remains unavailable because the local owner model is singleton and several entities have no mutation endpoint. Alert types: the nine requested alert identities replay idempotently through the production alert helper, with one later identity creating exactly one new alert. Canonical lineage now records explicit orphan counters (all zero) and cross-owner lineage checks. Framework warnings are limited to FastAPI `on_event` deprecations and the existing Angular lifecycle warnings.

## Architecture-aware 6D.2A closure

Website observations, offerings, capability/facility/certification claims, and risk projections are immutable/read-only surfaces; no artificial mutation endpoints were added. Owner protection is enforced at existing profile/manufacturer/supplier lookup and update boundaries, with forged references returning safe not-found results. History is a derived `/history` projection over append-only observations, not a separate table. Canonical PostgreSQL verification records mission/profile/candidate/supplier/evidence/observation/offering/claim/contradiction/change/alert ownership and identity links. Explicit orphan and broken-reference counters are zero for all applicable persisted relationships; cross-owner lineage is zero. The nine alert identities replay with zero deltas, and a later identity creates one alert.

## Slice 6D.2B durable refresh, Product Channel, and Calendar

Website refresh scheduling is profile-scoped and supports `MANUAL`, `DAILY`, `WEEKLY`, and `MONTHLY` policies with an IANA timezone and one bounded next occurrence. Due materialization is owner-scoped, row-locked, unique by profile and scheduled timestamp, and emits `website.refresh.materialized`; replay returns the existing job. Execution records `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, or `SKIPPED`, reuses the refresh idempotency key, and never retries a completed job. Disabled sources and `BLOCKED`/`REVIEW_REQUIRED` classifications fail closed; the global intelligence emergency stop and disabled switch also skip work safely.

The durable refresh ledger is `intelligence_website_refresh_jobs`; source profiles retain next/last refresh timestamps, timezone, policy version, and failure code. Calendar exposes one server-derived `WEBSITE_SOURCE_REFRESH_DUE` event per scheduled profile with target, profile, domain, frequency, timestamp, timezone, and status. Product Channel remains read-only and server-derived, with website observation/offering/profile counts and existing review-only actions. Operations/System Doctor expose refresh backlog, queued/running/failed counts, next due, last success, scheduler state, and recovery registration without secrets or raw content. Catch-up is bounded to one next occurrence per materialization pass; no durable worker or connector mutation is introduced.
## 6D.2C read projections

No new tables or migrations are required. Website detail APIs project the existing owner-scoped `AutonomousResearchMission`, `AutonomousResearchEvidence`, `AutonomousResearchContradiction`, `AutonomousResearchChange`, `AutonomousResearchAlert`, and `AutonomousResearchReport` rows. Website history remains an append-only `WebsiteObservation` projection and accepts bounded `candidate_id`, `event_type`, `source`, `date_from`, `date_to`, and `correlation_id` filters. Product Channel detail aggregates existing website observations, offerings, profiles, and website-linked mission lineage server-side.

## 6D.2D hard-certification closure

The final local certification is recorded in [website-intelligence-certification.md](website-intelligence-certification.md). It verifies durable crash/replay recovery, real PostgreSQL concurrency, owner-scoped storage and lineage integrity, bounded operational projections, privacy-safe reporting, and the website refresh ledger. The authoritative table and integrity endpoints are `/api/v1/intelligence/websites/tables` and `/api/v1/intelligence/websites/integrity`; the existing Operations intelligence projection remains the bounded operational read model. Live provider behavior and production-scale guarantees remain outside this local certification boundary.
