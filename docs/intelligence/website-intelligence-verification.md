# Website intelligence verification

Website claims begin as `CLAIMED` or `UNVERIFIED`. A logo alone never becomes
`VERIFIED`; document references and independent verification are distinct
states. Public business contact data is allowed, while credentials, cookies,
authorization headers, private supplier data, raw HTML, and provider payloads
are excluded.

Refreshes remain single-page, read-only, and bounded. Supplier contact,
RFQs, purchasing, payments, authenticated crawling, broad web crawling, and
external AI are disabled boundaries.


## Certified local proof

Against the disposable PostgreSQL test database, the baseline focused DB modules passed (**12 passed**) and the final 6D.2A proof modules passed (**5 passed**). The existing website security/unit suite also passed (**82 passed**). The checks prove fixture safety, observation replay, capability reviewability and autonomous contradiction idempotency, certification removal, risk append-only history, change/alert replay, owner isolation, and canonical lineage. The final proof includes reverse-pair contradiction replay, rejected-evidence safety, owner mutation rejection, nine-row alert lineage, canonical replay, and duplicate-group checks.

## Final 6D.2A proof closure (local PostgreSQL)

The five required final proof modules pass: **5 passed**. Reverse-pair capability contradiction is deduplicated and replays to zero delta with `REQUIRES_HUMAN_REVIEW`; the rejected/non-authoritative evidence matrix is 5/5 with zero changes; owner-forged profile/candidate mutation is safely rejected with owner-A rows unchanged; production change alerts retain change, evidence, source-profile, candidate, and correlation lineage across a 9-row matrix; and the canonical website flow replays with zero logical deltas and zero duplicate groups. The final security suite remains **82 passed**. Existing fixture warnings are framework deprecations only.

## 6D.2A final-four proof results

Owner mutation: profile/candidate forged-ID boundary checks pass; a complete eight-entity owner-B mutation matrix remains unavailable because the local owner model is singleton and several entities have no mutation endpoint. Alert types: the nine requested alert identities replay idempotently through the production alert helper, with one later identity creating exactly one new alert. Canonical lineage now records explicit orphan counters (all zero) and cross-owner lineage checks. Framework warnings are limited to FastAPI `on_event` deprecations and the existing Angular lifecycle warnings.

## Architecture-aware 6D.2A closure

Website observations, offerings, capability/facility/certification claims, and risk projections are immutable/read-only surfaces; no artificial mutation endpoints were added. Owner protection is enforced at existing profile/manufacturer/supplier lookup and update boundaries, with forged references returning safe not-found results. History is a derived `/history` projection over append-only observations, not a separate table. Canonical PostgreSQL verification records mission/profile/candidate/supplier/evidence/observation/offering/claim/contradiction/change/alert ownership and identity links. Explicit orphan and broken-reference counters are zero for all applicable persisted relationships; cross-owner lineage is zero. The nine alert identities replay with zero deltas, and a later identity creates one alert.

## 6D.2D hard-certification closure

The final local certification is recorded in [website-intelligence-certification.md](website-intelligence-certification.md). It verifies durable crash/replay recovery, real PostgreSQL concurrency, owner-scoped storage and lineage integrity, bounded operational projections, privacy-safe reporting, and the website refresh ledger. The authoritative table and integrity endpoints are `/api/v1/intelligence/websites/tables` and `/api/v1/intelligence/websites/integrity`; the existing Operations intelligence projection remains the bounded operational read model. Live provider behavior and production-scale guarantees remain outside this local certification boundary.
