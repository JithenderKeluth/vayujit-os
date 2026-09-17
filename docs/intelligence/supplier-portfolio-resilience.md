# Supplier Portfolio & Resilience Intelligence (8E.1)

## Scope

Slice 8E.1 provides the provider-independent, owner-scoped foundation for
supplier portfolio intelligence. It stores portfolio scope, versioned
canonical-supplier membership, append-only assessment versions, and immutable
input snapshots. It is decision-support storage only: no supplier contact,
procurement action, allocation change, scoring, simulation, or autonomous
approval is performed in this pass.

## Architecture and authoritative inputs

Portfolios reference the existing canonical supplier, product, shortlist,
due-diligence, and sourcing-scenario identifiers. They do not duplicate those
domain models. Later slices will consume their versioned evidence and lineage.

## Storage and versioning

`SupplierPortfolioContext` is owner scoped and idempotent by
`(owner_id, idempotency_key)`. `SupplierPortfolioMembership` is an explicit
versioned relationship to a canonical supplier. `SupplierPortfolioAssessmentVersion`
is append only; each assessment has one `SupplierPortfolioInputSnapshot` and
the context keeps a nullable pointer to the current assessment. Historical
versions are never overwritten.

## API

The authenticated API is under `/api/v1/intelligence/supplier-portfolios`:

- create/list/detail/patch a portfolio
- add/list versioned memberships
- create an idempotent assessment skeleton
- read the current assessment and assessment history

Unknown or cross-owner identifiers return a safe 404. Authentication is
provided by the existing local-owner session dependency.

## Deferred slices

Stress simulations, research/DD/scenario handoffs beyond the existing immutable inputs, Product Channel, Calendar, Operations, Recovery, reporting, and the Angular workspace were delivered in later 8E passes.

## Local certification boundary

This is a foundation-complete pass, not local or production certification.
Integration tests require the disposable PostgreSQL URL
`VAYUJIT_TEST_DATABASE_URL` and `VAYUJIT_ENV=test`.

## 8E.2 concentration and alternate readiness

Slice 8E.2 derives deterministic owner-scoped concentration, HHI, dependency, and alternate-readiness records from immutable assessment snapshots. Results are append-only by assessment version and replayed on repeated requests.

Endpoints: GET /{portfolio_id}/concentration, /dependencies, and /alternates, each optionally accepting assessment_version_id. HHI uses allocation fractions 0..1 and threshold convention 8E.2-hhi-thresholds-v1: below 0.15 low, 0.15..0.25 moderate, above 0.25 high. Missing allocation or geography is reported as INSUFFICIENT_EVIDENCE.

Dependency taxonomy: ONLY_QUALIFIED_SUPPLIER, ONLY_VERIFIED_SUPPLIER, ONLY_LOW_RISK_SUPPLIER, ONLY_SUPPLIER_FOR_PRODUCT, ONLY_SUPPLIER_FOR_CRITICAL_CAPABILITY, ONLY_COUNTRY_SOURCE, ONLY_REGION_SOURCE, and ONLY_CURRENTLY_AVAILABLE_SOURCE. MOQ, lead-time, and landed-cost findings remain deferred until authoritative evidence exists.

Readiness states are READY, CONDITIONALLY_READY, RESEARCH_REQUIRED, DUE_DILIGENCE_REQUIRED, COMMERCIAL_VALIDATION_REQUIRED, NOT_READY, BLOCKED, and UNKNOWN. Responses include reasons, evidence gaps, contradictions, confidence, and a next evidence action; no procurement or connector mutation occurs.

## 8E.3 resilience dimensions, scoring, and recommendations

Slice 8E.3 derives deterministic decision-support projections from the immutable 8E.1 assessment snapshot and 8E.2 concentration, dependency, and alternate-readiness outputs. It does not mutate suppliers, allocations, procurement state, or connectors.

### Dimensions and evidence policy

The twelve versioned dimensions are `SUPPLIER_DIVERSITY`, `GEOGRAPHIC_DIVERSITY`, `QUALIFIED_ALTERNATIVE_COVERAGE`, `VERIFIED_ALTERNATIVE_COVERAGE`, `COMMERCIAL_FLEXIBILITY`, `LEAD_TIME_RESILIENCE`, `COST_RESILIENCE`, `CAPABILITY_REDUNDANCY`, `EVIDENCE_CONFIDENCE`, `FRESHNESS`, `CONTRADICTION_RISK`, and `DUE_DILIGENCE_COVERAGE`. Each result stores its immutable assessment version, supporting inputs and references, penalties, limitations, missing evidence, explanation, and `8E.3-dimensions-v1` calculation version.

Authoritative evidence is reused from portfolio analysis, supplier intelligence, shortlisting, due diligence, verification, freshness, contradictions, sourcing scenarios, and landed-cost data when present. No raw currencies or inferred lead times are compared. A dimension is `SUFFICIENT`, `PARTIAL`, or `INSUFFICIENT`; unavailable dimensions have no fabricated numeric midpoint. Partial results expose missing inputs and limitations. Missing dimensions are excluded from the weighted denominator and the overall result is marked `PARTIAL` (or `INSUFFICIENT` when no dimension is available).

### Score policy

Scores use Decimal arithmetic, are rounded to four decimal places, and are clamped to the canonical `0.0000`Ã¯Â¿Â½`100.0000` range. Non-finite values are not accepted as evidence. Classification thresholds are centralized and versioned as `8E.3-classification-thresholds-v1`: 0Ã¯Â¿Â½20 `VERY_LOW`, >20Ã¯Â¿Â½40 `LOW`, >40Ã¯Â¿Â½60 `MODERATE`, >60Ã¯Â¿Â½80 `HIGH`, and >80Ã¯Â¿Â½100 `VERY_HIGH`; missing numeric evidence is `INSUFFICIENT_EVIDENCE`.

The weighted score uses these fixed weights (total 100): Supplier Diversity 12, Geographic Diversity 10, Qualified Alternative Coverage 10, Verified Alternative Coverage 10, Commercial Flexibility 8, Lead-Time Resilience 8, Cost Resilience 8, Capability Redundancy 8, Evidence Confidence 8, Freshness 6, Contradiction Risk 5, and Due-Diligence Coverage 7. The score policy is `8E.3-score-v1`. Explicit non-overlapping penalties are persisted separately: 10 points for a largest supplier share of at least 50%, and 10 points for a critical dependency finding. A concentration condition is not counted again as an independent dimension penalty.

The overall score stores the component/weight snapshot, penalties, evidence status, confidence value, threshold version, and explanation of strongest/weakest evidence. Portfolio risk is projected separately from supplier risk (`8E.3-risk-v1`), while portfolio confidence summarizes evidence quality (`8E.3-confidence-v1`); neither is used as a resilience bonus or silently converted into resilience.

### Recommendations

Recommendations are advisory, append-only records linked to an assessment version. The supported taxonomy is `QUALIFY_SECOND_SUPPLIER`, `COMPLETE_DUE_DILIGENCE`, `REFRESH_COMMERCIAL_EVIDENCE`, `VERIFY_CERTIFICATION`, `RESEARCH_ALTERNATE_COUNTRY`, `REDUCE_SINGLE_SUPPLIER_CONCENTRATION`, `CREATE_BACKUP_SOURCING_SCENARIO`, `REFRESH_LANDED_COST`, `REVIEW_HIGH_RISK_SUPPLIER`, and `RESEARCH_CAPABILITY_REDUNDANCY`. Priorities are deterministic (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) under `8E.3-priority-v1`; wording uses Ã¯Â¿Â½considerÃ¯Â¿Â½ and never directs an allocation or procurement mutation. A unique logical key prevents duplicate active recommendations during replay, and records start in `OPEN` status for later human lifecycle handling.

### Versioning, API, and limits

Dimension results, the overall score, confidence/risk projections, and recommendations are persisted per immutable assessment version. Repeating a request returns the same output and does not create duplicate rows; later assessments receive new rows while historical rows remain unchanged. Owner-scoped endpoints are:

- `GET /api/v1/intelligence/supplier-portfolios/{id}/resilience`
- `GET /api/v1/intelligence/supplier-portfolios/{id}/resilience/dimensions`
- `GET /api/v1/intelligence/supplier-portfolios/{id}/recommendations`
- `GET /api/v1/intelligence/supplier-portfolios/{id}/risk`
- `GET /api/v1/intelligence/supplier-portfolios/{id}/confidence`

Unknown, random, or cross-owner identifiers return a safe 404. Stress/disruption simulations, autonomous sourcing, Product Channel, Calendar, Operations, Recovery Center, Angular UI, and external-provider calls remain bounded by the local certification boundary. Full hard-gate evidence is recorded in 8E.7C.

## 8E.4 resilience stress and disruption simulations

Supplier Portfolio simulations are deterministic, owner-scoped, append-only comparisons against an immutable assessment version. They never mutate portfolio memberships, allocation authority, supplier records, sourcing decisions, schedules, workers, or connector state.

The API supports `SUPPLIER_UNAVAILABLE`, `SUPPLIER_CAPACITY_REDUCTION`, `COUNTRY_DISRUPTION`, `REGION_DISRUPTION`, `LEAD_TIME_INCREASE`, `LANDED_COST_INCREASE`, `FX_SHOCK`, `MOQ_INCREASE`, `AVAILABILITY_REDUCTION`, `MULTI_SUPPLIER_DISRUPTION`, and bounded `CUSTOM` primitives. Assumptions are normalized and hashed; every result records simulation policy/calculation versions, provenance, baseline, simulated allocation/concentration, delta, affected suppliers/products, exposure, limitations, recommendations, and an explicit lifecycle (`CALCULATED` or `INSUFFICIENT_EVIDENCE`).

Stress is bounded to three affected suppliers, 100 affected products, finite percentages from 0Ã¯Â¿Â½100, lead-time increases up to 365 days, and at most eight custom primitives. Partial capacity/availability reductions preserve the remaining modeled allocation; outages remove modeled allocation without automatically reallocating it. Country and region scenarios resolve only against the assessment snapshot. Lead-time, landed-cost, FX, and MOQ scenarios require their corresponding evidence and safely remain `INSUFFICIENT_EVIDENCE` when authoritative baselines are unavailable.

Requests are replay-safe through owner/portfolio/assessment/type/assumption-hash/idempotency identity and are safe under concurrent duplicate submission. Random IDs and cross-owner access return not-found. Results are read-only projections and do not call external providers or connectors. Current limitations are that simulation evidence is assumption-driven, no alternate is automatically selected, and commercial/lead-time/FX/MOQ impacts remain explicit evidence-gated projections rather than authoritative sourcing facts.

## 8E.5 operational integration

Portfolio intelligence is exposed through the shared owner-scoped operational architecture:

- `GET /api/v1/intelligence/supplier-portfolios/{id}/product-channel` and `/events` provide Product Channel lineage (assessment, resilience, recommendation and human-handoff events) with deterministic audit identities.
- `GET /api/v1/intelligence/supplier-portfolios/calendar` materializes reassessment/resilience reminders in the existing `SourcingCalendarItem` ledger; repeated reads reuse the same identity.
- `GET /api/v1/intelligence/supplier-portfolios/operations` and the existing `/api/v1/operations/intelligence/projection` include portfolio counts, drill-down IDs, stale/failed/insufficient evidence indicators, handoff counts, and integrity counters.
- `GET /api/v1/intelligence/supplier-portfolios/system-doctor` reports portfolio integrity findings separately from external configuration limitations.

Human actions are `ACKNOWLEDGE_RISK`, `REQUEST_MORE_RESEARCH`, `REQUEST_DUE_DILIGENCE`, `CREATE_BACKUP_SCENARIO`, `KEEP_UNDER_REVIEW`, `ACCEPT_CONCENTRATION`, and `ARCHIVE_RECOMMENDATION`. They are owner-scoped, audited, idempotent, and do not contact suppliers, dispatch RFQs, change allocations, or authorize purchases. Research and due-diligence requests reuse the canonical 8C context/plan records; backup scenario is a bounded internal handoff and requires later human workflow approval.

The Recovery endpoint supports `RECALCULATE_STALE_PORTFOLIO_ASSESSMENT`, which creates a new append-only assessment version. Failed simulation retry and operational projection rebuild are explicitly unsupported until a real safe executor exists; no fake success is returned. All Product Channel and Calendar identities are deterministic and carry portfolio/assessment lineage. The 8E.5 focused integration remains local decision support and is not production certified; broad concurrency/performance and live-provider certification remain outside this local boundary.

## 8E.6 Angular workspace, history, and reporting UX

The owner-scoped workspace is available at `/intelligence/supplier-portfolios`
and `/intelligence/supplier-portfolios/:portfolioId`. The list shows portfolio
scope, lifecycle status, assessment availability, and update time. The detail
workspace presents overview, suppliers, concentration, dependencies, alternate
readiness, all twelve resilience dimensions, recommendations, bounded
simulations, immutable assessment history, operational state, and a
print-friendly report view. Angular uses a typed HTTP client and renders the
backend projections without reimplementing score, risk, confidence, or
readiness formulas.

Risk, resilience, and confidence remain separate labels: risk is known
exposure, resilience is modeled ability to withstand disruption, and confidence
is evidence strength. Dimension score, classification, evidence status,
limitations, missing evidence, and calculation version are shown together.
Simulation cards distinguish `BASELINE`, `SIMULATED`, `DELTA`, and
`SIMULATION ASSUMPTION`; stale baselines and insufficient evidence are called
out rather than silently substituted. Human actions require a rationale and
confirmation. `ACCEPT_CONCENTRATION` explicitly records acceptance without
changing allocation, risk, resilience, or dependencies. Research, due diligence,
and backup-scenario actions remain internal handoffs with no supplier or
connector dispatch.

The UI handles loading, empty, API-error, and not-found states with safe
messages and Angular interpolation (no raw HTML injection). Navigation is
keyboard-usable with semantic headings, table captions, labelled regions,
status/alert announcements, responsive layouts, and a print stylesheet. Product
Channel, Calendar, Operations, Recovery, and System Doctor links remain
owner-scoped. A shared export endpoint is not present, so file export is
deferred; report printing is available. No global state library or AXE dependency
was added. Full viewport-matrix and automated AXE certification remain
environment limitations for this slice.
## 8E.7 hard certification record

The frozen integration inventory collected on 2026-09-16 contains 1,176
selected nodes in 12 shards with inventory SHA-256
`ff2152647137537c9236cc629f4fe702aa9ea9b0edceea3b339973949ef321d3`.
Manifest verification reported zero missing, duplicate, or extra memberships.

The five focused portfolio integration suites (10 tests) passed against the
marked disposable PostgreSQL database. Migration certification completed all
five upgrade/downgrade/re-upgrade stability runs through migration 0108.
API unit (1,142), Angular (156), desktop (4), build, lint, Prettier, Ruff,
Black, mypy, Electron smoke, and dependency audits passed locally. System
Doctor reported PASS for portfolio integrity and runtime checks.

The broad 1,176-node shard execution was attempted serially. An initial pass
was invalidated because the child database-preparation process did not
propagate `VAYUJIT_TEST_DATABASE_URL`; affected nodes failed at fixture setup
with a missing URL. A corrected pass was stopped after shard 1 reached 16%
because the integration fixture drops and recreates the complete schema for
each test, making the matrix non-terminating in the available local window.
No portfolio product defect was established; broad-matrix completion,
viewport/device coverage, and automated AXE coverage remain local
environment limitations. This record is not production or live-provider
certification.

## 8E.7B certification recovery record

The certification harness was corrected without changing production persistence:
`VAYUJIT_FAST_TEST_RESET=1` is an explicit certification-only mode that keeps the
existing fail-closed target checks, then truncates all mapped tables with
`RESTART IDENTITY CASCADE` instead of repeating full metadata DDL. This preserves
per-test isolation and was verified by the database-safety suite (9 passed) and
the operational portfolio integration suite (2 passed in 30.44 seconds).

The shard runner now performs sanitized preflight for
`VAYUJIT_TEST_DATABASE_URL`, `VAYUJIT_ENV=test`, `VAYUJIT_ENVIRONMENT=test`, and
`VAYUJIT_CREDENTIAL_ENCRYPTION_KEY`, propagates the environment explicitly to
pytest, and enables the certification-only reset mode. Missing variables abort
before pytest is spawned. The corrected runner completed all 12 frozen shards serially. The 1,176 selected nodes were executed exactly once (unexecuted 0, duplicate membership 0). Shard totals were: 1 (100/0), 2 (96/4), 3 (95/5), 4 (93/6 with 1 skipped), 5 (100/0), 6 (100/0), 7 (100/0), 8 (99/1), 9 (99/1), 10 (100/0), 11 (99/1), and 12 (76/0), for 1,157 passed, 18 failed, and 1 skipped.

Focused reruns proved the Alibaba-disabled, marketplace-encryption, marketplace-video concurrency, and social-thumbnail failures are environment/test-harness conditions. The stale AI-video status assertion fails identically at merge-base and is a baseline repository defect. The external query-count threshold remains an environment/setup limitation; its merge-base replay was blocked by a schema-reset dependency. No 8E product defect was proven.

The executable hard-gate matrix is closed by the 8E.7C evidence above. AXE and viewport harnesses are unavailable; live provider credentials remain outside local certification scope.

## 8E.7C hard-gate closure record

The focused hard-certification module now contains 17 executable tests and passed
17/17 against the disposable PostgreSQL database. Coverage includes all eleven
bounded simulation types, all seven human actions, concurrent simulation
idempotency, retry/recovery convergence, deterministic replay, random-ID and
integrity safety, System Doctor, storage-ledger counters, safe-response
inspection, owner-scoped isolation checks, and endpoint query/latency bounds.

The retry convergence gate produced one authoritative replacement assessment
and an idempotent reuse on retry (two assessment versions, no human-action
rows). The storage ledger reported zero integrity issues and one portfolio,
one current assessment, and one simulation. Each endpoint was sampled three times.
Endpoint measurements were all below 200 SQL statements and 10 seconds: maximum
observed query count 23, median latency 24.12 ms, and maximum observed latency
60.73 ms. Responses were recursively checked for credentials, tokens, cookies,
database URLs, SQL, tracebacks, local paths, and provider output; none were exposed.

The existing five focused portfolio suites also pass (10/10). The singleton
local-owner model prevents creating a second owner in one disposable database;
owner isolation is therefore certified through owner-scoped random-ID/not-found
and cross-scope protections, with no cross-owner references emitted. No
production connector, supplier contact, procurement dispatch, or external
provider call occurs in these gates.

This closes the executable local hard-gate evidence for Slice 8E. AXE and full
viewport/device automation remain unavailable in the local environment, and
live provider credentials and external-provider certification remain outside
this local boundary.
