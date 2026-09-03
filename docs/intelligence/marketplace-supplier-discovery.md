# Marketplace supplier discovery

IndiaMART Slice 7A provides the first marketplace supplier-discovery boundary.
It is disabled by default and locally certified with a deterministic fixture;
the provider never performs contact, RFQ, ordering, purchasing, or payment
actions.

## IndiaMART certification status

- Modes: `DISABLED`, `LOCAL_FIXTURE`, and fail-closed `LIVE_READ_ONLY`.
- Local discovery stores bounded requests/results and reuses the normalized
  Supplier, SupplierSource, SupplierProduct, and SupplierEvidence records.
- Results are owner-scoped, idempotent, advisory-lock protected, and labelled
  `DISCOVERY_ONLY`; commercial and verification values remain provider claims.
- Product Channel, Calendar, Operations, System Doctor, Integrity, history,
  report, and Angular discovery views expose only normalized safe fields.
- Normalized results can be handed to the existing autonomous Evidence verifier; provider-only claims remain `SUPPORTED` at most and retain owner/mission/task lineage. Observation history is append-only and replay-safe for bounded claims.
- Focused certification: 12 tests passed against disposable PostgreSQL,
  including mode/preflight, read-only boundary, claims/evidence safety,
  idempotency, quotas/kill switches, projections, and concurrent replay.

## Live and future boundaries

`LIVE_READ_ONLY` is currently blocked by external configuration. No official
IndiaMART endpoint, credential contract, authenticated scraping, CAPTCHA
bypass, or live provider validation is implemented. Shared autonomous contradiction/change/alert and recovery ledgers are available after accepted evidence handoff; a
complete provider-specific crash/recovery, performance, and browser automation
matrix remains future integration work and must not be inferred from local fixture results.



## IndiaMART lifecycle handoff

Normalized results may be sent to the existing autonomous Evidence verifier through the owner-scoped evidence-handoff endpoint. Provider-only claims remain SUPPORTED at most; VERIFIED requires independent verifier policy. Observation history is append-only and replay-safe for PRICE, MOQ, LEAD_TIME, VERIFICATION_CLAIM, and AVAILABILITY. Shared autonomous contradiction/change/alert and recovery ledgers are available after accepted evidence handoff; provider-specific crash and performance automation remain explicit follow-up gaps.

## Slice 7A.3 closure notes

IndiaMART lifecycle projections now consume the shared autonomous evidence, change,
alert, contradiction, recovery, and report ledgers. Exact observation replay remains
idempotent, while a changed normalized snapshot receives a distinct retrieval identity
so accepted evidence can participate in shared change/alert detection. Product Channel
counts accepted evidence and linked review signals rather than returning placeholders.

This is a local deterministic certification only. External IndiaMART credentials,
network behavior, full crash/concurrency/performance instrumentation, AXE, and viewport
automation remain unconfigured and are intentionally not claimed as certified.
## Slice 7A.4 proof ledger

The IndiaMART proof suite now records deterministic PostgreSQL identity/match matrices, observation replay, fail-closed evidence freshness, confidence/diversity, and recovery idempotency. Angular acceptance covers readiness, history, discovery-only state, claims, and safe API-error rendering. Live provider certification, crash/process concurrency, performance/query-count instrumentation, AXE, and viewport automation remain explicitly pending until their external or dedicated harnesses are available.

## Slice 7A.5 status

The final local proof adds PostgreSQL-backed identity/match and observation replay coverage plus Angular readiness/history/error acceptance. The implementation remains local deterministic and discovery-only. Required alert/risk/contradiction, crash/concurrency, performance/query, and browser security/accessibility certification remain open and are not represented as passing.

## Slice 7A.8 local evidence boundary

The IndiaMART LOCAL_FIXTURE suite contains 96 parameterized integration tests; 95 passes are captured from the full-suite run and 22 from the focused Recovery rerun. It proves
bounded Retry-After parsing, recovery action idempotency, checkpoint replay,
owner-scoped integrity projections, four contradiction cases, and static Angular
accessibility/responsive checks. It does not claim live-provider certification.

The remaining strict closure items are minute/hour quota exhaustion, route-level concurrent Recovery API submission, injected provider-stage crashes, three independent repeatability runs, and a single complete canonical E2E/lineage/replay proof. Service-level Recovery race handling and focused role/aria/table/focus accessibility assertions pass.

### 7A.9 evidence ledger

The route-level Recovery race is now covered by two synchronized authenticated HTTP requests (23 focused tests pass). Provider crash injection, the three-run repeatability proof, and the canonical E2E/lineage/replay scenario remain unclosed because the current IndiaMART implementation exposes no test-only crash hooks or single canonical orchestration entrypoint. Rate-limit evidence is limited to the implemented minute/day guards and bounded Retry-After parsing; no hour-window guard exists.
## Shared marketplace runtime closure evidence (2026-08-31)

The provider-neutral runtime now persists owner/provider execution identity,
mission/task correlation, nine checkpoints, bounded minute/hour rate windows,
retry metadata, safe lineage, and bounded counters. The LOCAL_FIXTURE crash suite
covers all six checkpoint boundaries with fresh-session recovery; canonical replay
reuses the existing execution and performs no second provider call. Focused runtime
certification is 11/11 and the full IndiaMART regression is 97/97. This evidence is
local and deterministic only; it does not certify live IndiaMART traffic, purchasing,
contact, RFQ, payment, or external credentials.

## Alibaba

See [Alibaba discovery](alibaba-discovery.md) for the read-only provider boundary and local fixture usage.

Alibaba Slice 7B.4 local evidence includes thirteen deterministic normalization cases (including a duplicate-provider input), owner-scoped supplier/evidence persistence, shared-runtime replay, evidence handoff/replay, and a five-test Angular accessibility/responsive specification. These are local fixture proofs only; cross-source contradiction, strict durability matrices, and live provider access remain unclaimed.

## TradeIndia Slice 7C

TradeIndia adds read-only supplier/listing discovery on the same normalized supplier intelligence and Marketplace Runtime contracts. Local fixtures cover incomplete source fields, duplicate and similar supplier identities, provider claims, changed/disappeared listings, commercial disagreement, and stale observations. No contact, RFQ, purchasing, payment, or provider mutation is implemented.

Global Sources supplier discovery (Slice 7D) is a thin read-only adapter over the shared Marketplace Runtime. Local fixtures cover normalized listings, identity/product/offering matching, evidence handoff, claims, freshness, changes, alerts, and replay; contact, RFQ, purchasing, payment, scraping, and mutations remain unavailable.

## Slice 8A — Cross-Marketplace Supplier Intelligence

A provider-independent canonical Supplier projection now consolidates accepted owner-scoped
Supplier, Source, Product, Evidence, verification, capability, certification, risk, and sourcing
records. It is server-derived and read-only against external systems. Exact identities may be
matched deterministically; possible matches remain review-only and are never auto-merged. Price,
MOQ, lead-time, availability, freshness, contradictions, confidence, source diversity, ranking,
reports, Product Channel contribution, Calendar reminders, and Operations/System Doctor summaries
remain lineage-preserving. Supplier contact, RFQ dispatch, purchasing, payments, and live connector
calls remain disabled or separately configured.