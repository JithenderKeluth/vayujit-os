# Winning Product Intelligence â€” Slice 9A

## Purpose

Slice 9A introduces an owner-scoped Product Opportunity foundation. A Product Opportunity is a candidate product concept for research and assessment; it is not a supplier, listing, SKU, order, or approval.

## Aggregate and lifecycle

The canonical aggregate is `ProductOpportunity`, linked to the existing owner and optionally to an existing Product, Brand, and Intelligence Research Run. Lifecycle values are `draft`, `researching`, `ready_for_assessment`, `assessed`, `watching`, and `archived`. Origins are extensible (`manual`, marketplace/trend/competitor/review/external/AI research, supplier discovery, and import).

Context is kept separate from evidence. Missing evidence is explicit through `unknown`, `partial`, and `insufficient_evidence` states; no unsupported claim is inferred.

## Constraints and assessment history

Constraints are immutable, append-only versions. Monetary and numeric values use decimal storage and monetary values require an explicit three-letter currency. Assessments are append-only and point to immutable input snapshots and a constraint version. The opportunity stores only current-version pointers for navigation; historical rows remain queryable.

## Integration and controls

Creation and assessment emit auditable opportunity events (`OPPORTUNITY_CREATED`, `OPPORTUNITY_RESEARCH_STARTED`, `OPPORTUNITY_ASSESSMENT_CREATED`, `OPPORTUNITY_CONSTRAINTS_CHANGED`, and `OPPORTUNITY_ARCHIVED`). The API is authenticated, owner-scoped, idempotent for creation, and returns safe 404s for unknown IDs. No autonomous approval, procurement, publishing, supplier contact, or external mutation is performed.

Product Channel and Calendar integration remain intentionally minimal in 9A; no meaningful recovery action exists for this foundation: **NO 9A RECOVERY ACTION REQUIRED**.

## API and UI

The API is under `/api/v1/intelligence/product-opportunities` for create/list/detail/update/archive, constraint versions, assessments, current assessment, operations counts, and System Doctor checks. The Angular workspace is available at `/intelligence/product-opportunities` and `/intelligence/product-opportunities/:opportunityId` with create, constraint-history, assessment-history, and archive controls.

System Doctor checks orphan rows, owner references, assessment pointers, orphan snapshots/constraints, cross-owner references, duplicate current pointers, and invalid evidence states.

## Certification boundary

This is a local foundation implementation only. External research, marketplace writes, autonomous decisions, and production certification are outside Slice 9A. Expected classification: **SLICE 9A â€” PRODUCT OPPORTUNITY FOUNDATION COMPLETE**; **NOT LOCAL CERTIFIED**; **NOT PRODUCTION CERTIFIED**.

## Slice 9B ï¿½ Demand and Competition Intelligence

9B adds deterministic, assessment-bound intelligence outputs without a winner score, ranking, or recommendation. Each output is immutable and stores the calculation version (`product-opportunity-intelligence-v1`), a snapshot of linked listing/price IDs, dimensions, evidence summary, and research gaps. Re-running a kind for the same assessment returns the existing output and does not create a second logical result.

Demand dimensions are `MARKET_ACTIVITY`, `DEMAND_STRENGTH`, `DEMAND_MOMENTUM`, `DEMAND_STABILITY`, `EVIDENCE_COVERAGE`, and `EVIDENCE_FRESHNESS`. Listing activity is an observed fact and is never presented as sales. Sales, search volume, trends, reviews, and stability remain explicitly unavailable or proxy-labelled when their authoritative observations are absent.

Competition dimensions are `COMPETITOR_DENSITY`, `BRAND_CONCENTRATION`, `SELLER_CONCENTRATION`, `PRICE_COMPETITION`, `REVIEW_BARRIER`, `RATING_BARRIER`, `LISTING_MATURITY`, `DIFFERENTIATION_OPPORTUNITY`, `EVIDENCE_COVERAGE`, and `EVIDENCE_FRESHNESS`. Concentration uses HHI (sum of squared shares) over the bounded linked sample; seller concentration is a proxy because canonical seller identity is not persisted. Price distributions are descriptive and grouped by currency, with mixed currencies never combined. Review, rating, maturity, and differentiation claims are unavailable without authoritative evidence.

Evidence states and freshness accompany each dimension. Supporting listing/price references, observed timestamps, evidence diversity (marketplace, brand, and account counts), contradictions (when supplied by upstream evidence), and missing research gaps are preserved rather than hidden. No autonomous action is triggered, and no provider, connector, scheduler, approval, or publishing work is performed.

The authenticated owner-scoped API provides POST/GET demand and competition calculations, assessment intelligence history, and `/intelligence-system-doctor`. Unknown UUIDs and cross-owner references resolve safely without leakage. Doctor checks cover orphan outputs, broken assessment lineage, cross-owner references, invalid calculation versions, duplicate logical outputs, and impossible numeric states. The Angular Product Opportunity workspace now exposes assessment-bound calculation buttons and evidence-labelled dimension cards; it does not render a recommendation.

9B intentionally reuses existing marketplace listing and price observations rather than introducing a second research or evidence runtime. Outputs are currently a local analytical projection: they do not assert market-wide competitor identity, demand volume, predictive momentum, or commercial advice beyond the linked evidence sample.

Expected classification: **SLICE 9B ï¿½ DEMAND & COMPETITION INTELLIGENCE COMPLETE**; **NOT LOCAL CERTIFIED**; **NOT PRODUCTION CERTIFIED**.

## Slice 9C ï¿½ Commercial and Economic Viability Intelligence

9C adds deterministic, immutable commercial projections bound to a Product Opportunity assessment. Calculations use Decimal arithmetic and preserve explicit provenance: observed marketplace prices are evidence, while modeled selling price and per-unit fees are labeled assumptions. Landed cost is unknown unless a canonical `LandedCostEstimate` or `SourcingScenarioVersion` is supplied; supplier prices are never silently substituted.

The output records contribution per unit and contribution margin (not net profit), known inventory-at-MOQ and fixed/setup capital, break-even units only when the contribution and fixed-cost basis are known, versioned constraint comparisons, bounded price/cost sensitivity with `BASELINE`, `SCENARIO`, and `DELTA`, evidence references, freshness, and research gaps. Currency mismatches produce `UNKNOWN` rather than an implicit conversion; optional FX context is retained as input only. No winner score, ranking, recommendation, supplier selection, procurement, publishing, or external mutation is performed.

Authenticated owner-scoped endpoints are available for calculation/retrieval, unit economics, capital, constraint fit, sensitivity, evidence, gaps, history, and `/commercial-system-doctor`. The doctor checks orphan and cross-owner lineage, duplicate assessment outputs, invalid calculation/currency/numeric state, and broken landed-cost references. The Product Opportunity workspace exposes an Economics panel that restores assessment-bound output and allows an explicit deterministic calculation.

Expected classification: **SLICE 9C ï¿½ COMMERCIAL & ECONOMIC VIABILITY COMPLETE**; **NOT LOCAL CERTIFIED**; **NOT PRODUCTION CERTIFIED**.

## Slice 9D ï¿½ Supplier and Sourcing Feasibility

9D adds an immutable, assessment-bound feasibility projection for supplier availability and sourcing readiness. It reuses the existing supplier discovery/matching, verification, shortlist, due-diligence, sourcing-scenario, portfolio/resilience, and 9C commercial records; it does not create a second supplier, evidence, shortlist, due-diligence, scenario, or risk engine. The output stores the constraint snapshot, upstream lineage, candidate rows, explicit dimensions, evidence/freshness states, and research gaps under `product-opportunity-sourcing-feasibility-v1`.

The projection distinguishes discovered, matched, eligible, shortlisted, due-diligence-ready, and due-diligence-complete candidates. Feasibility states are `INSUFFICIENT_EVIDENCE`, `NO_ELIGIBLE_SUPPLIER`, `DUE_DILIGENCE_REQUIRED`, `PARTIAL`, and `AVAILABLE`; these are descriptive readiness states, not supplier recommendations, purchase approvals, or launch verdicts. MOQ and lead-time fit remain `UNKNOWN` unless comparable authoritative terms and constraints are available. Decimal supplier prices and explicit currencies are serialized safely; no FX conversion or commercial claim is invented.

Authenticated owner-scoped endpoints are available under `/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/sourcing-feasibility` for calculate/retrieve, supplier candidates, shortlist, due diligence, commercial, scenarios, alternatives, resilience, evidence, gaps, and history. `/sourcing-feasibility-system-doctor` reports orphan, duplicate, lineage, version, and numeric checks. Repeated calculation is assessment-idempotent and emits only a deduplicated `SOURCING_FEASIBILITY_UPDATED` audit event. The Angular Product Opportunity workspace exposes a Sourcing Feasibility panel with state, bounded candidate table, evidence dimensions, and explicit gaps; it has no winner ranking or autonomous action.

Product Channel, Calendar, Operations, and Recovery remain read-only consumers of this projection. Research or due-diligence gaps are surfaced for existing human-controlled workflows; no supplier contact, RFQ, procurement, publishing, or external mutation is triggered. Expected classification: **SLICE 9D ï¿½ SUPPLIER & SOURCING FEASIBILITY COMPLETE**; **NOT LOCAL CERTIFIED**; **NOT PRODUCTION CERTIFIED**.

## Slice 9E â€” Opportunity Risk, Evidence & Confidence Synthesis

9E adds an immutable, assessment-bound synthesis projection over the persisted 9B demand/competition, 9C commercial, and 9D sourcing outputs. It records a versioned input fingerprint, upstream lineage, material evidence-backed risks, domain readiness, consolidated research gaps, evidence coverage, confidence, and material changes since the prior assessment.

Risk is distinct from missing evidence: absent MOQ, demand, or verification data is represented as an evidence gap with UNKNOWN severity, not as a fabricated negative business result. Confidence describes support quality (coverage, freshness, and gaps), not opportunity attractiveness. Readiness is descriptive input readiness for the future 9F scoring layer and never a launch, purchase, supplier, or winner recommendation.

The authenticated owner-scoped API is available under `/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/risk-evidence-synthesis` with calculate, retrieve, history, risk, evidence, freshness, contradiction, confidence, readiness, gap, and change sections. The System Doctor checks duplicate logical outputs and invalid synthesis state. The Angular Product Opportunity workspace exposes a visually separate Risk & Evidence panel. Calculation is synchronous and idempotent; **NO 9E RECOVERY ACTION REQUIRED**.

Materiality and research prioritization are deterministic and bounded. No raw provider payloads, unsupported probabilities, final opportunity score, ranking, launch recommendation, supplier selection, procurement, or external mutation is produced. Expected classification: **SLICE 9E â€” OPPORTUNITY RISK, EVIDENCE & CONFIDENCE SYNTHESIS COMPLETE**; **NOT LOCAL CERTIFIED**; **NOT PRODUCTION CERTIFIED**.

## Slice 9F â€” Winning Product Scoring, Ranking & Decision Intelligence

9F adds a deterministic, explainable score over the authoritative 9B demand/competition, 9C commercial, 9D sourcing-feasibility, and 9E risk/evidence synthesis projections. It is an analytical decision-support layer only: it does not launch products, approve procurement, contact suppliers, publish listings, or mutate external systems.

The versioned model is `winning-product-score-v1` with calculation `winning-product-scoring-v1` and canonical profile `canonical-v1`. The seven dimensions and default weights are Demand 20%, Competitive 15%, Commercial 20%, Capital 15%, Supplier 15%, Resilience 10%, and Differentiation 5%. Each dimension stores its normalized score, weight, weighted contribution, evidence references, and unavailable state. Missing evidence is excluded from the denominator and remains explicit; it is never treated as zero. Decimal arithmetic, bounded inputs, finite-number validation, deterministic rounding, and a persisted input fingerprint make repeated calculations reproducible.

Eligibility is `SCORABLE`, `PARTIALLY_SCORABLE`, `INSUFFICIENT_EVIDENCE`, or `BLOCKED`. High-severity upstream risks block scoring; fewer than two available dimensions is insufficient evidence, and two through four available dimensions are partial. Score bands are `VERY_HIGH`, `HIGH`, `MODERATE`, `LOW`, and `VERY_LOW`. Confidence, assessment readiness, risk level, evidence state, blockers, positive/negative drivers, improvement areas, and bounded commercial sensitivity are separate fields; confidence is not attractiveness and missing evidence is not a negative score.

Authenticated owner-scoped endpoints expose the immutable score, history, explanation, drivers, sensitivity, gaps, model definition, bounded comparison/ranking, and human decisions (`watch`, `research_more`, `shortlist`, `reject`, `archive`). Comparison is `COMPARABLE` only for same model/profile and eligible scores; ranking is deterministic by score descending, then assessment UUID. Human decisions require a persisted score, preserve rationale and score lineage, and emit deduplicated audit events. Replays use idempotency keys and input fingerprints; System Doctor checks lineage, uniqueness, numeric bounds, model weights, and decision references. No recovery action is required because calculation is synchronous.

The Angular Product Opportunity workspace now presents a Winning Product Score panel with eligibility, score band, dimensions, evidence, confidence, risk, drivers, improvements, sensitivity, and human decision controls. The UI does not expose provider payloads, secrets, credentials, or autonomous execution controls.

Expected classification: **SLICE 9F â€” WINNING PRODUCT SCORING, RANKING & DECISION INTELLIGENCE COMPLETE**; **LOCAL VALIDATION PENDING**; **NOT PRODUCTION CERTIFIED**.
## Slice 9I - Local Certification (2026-09-18)

Branch: `feature/KAN-intelligence-winning-products`. Slice 9A through 9F was certified against the local PostgreSQL test database and deterministic local providers; no live provider was called. The frozen inventory contains 32 nodes (27 API nodes and 5 Product Opportunity Angular nodes) with inventory hash `716fdef74e961ff5c79313fbffbbea07be43ef172bede5e4b7ea3641b697b405`.

Evidence executed:

- API inventory: 27 passed. The integration subset passed 12 tests and the feasibility-unit remainder passed 15 tests.
- Angular Product Opportunity spec: 5 passed. Full Angular suite: 43 files and 161 tests passed.
- Desktop suite: 1 file and 4 tests passed.
- Electron smoke: passed (`Electron 43.2.0 ready`, sandboxed BrowserWindow, renderer ready, smoke passed).
- Migration certification: 5/5 fixture stability runs passed through head `20261105_0114`. A PostgreSQL identifier-limit defect in the 9E migration was corrected by shortening only its two index names; no schema behavior changed.
- Focused 9F scoring regression after the migration correction: 3 passed.
- Ruff, Black, Prettier format check, build, and `git diff --check`: passed.
- System Doctor: passed; optional live image/video providers and credential-encryption keys remain unconfigured by design.

The executed tests cover owner isolation, authenticated API/UI access, assessment-bound lineage, evidence-labelled unknowns and sparse inputs, all-missing scoring, partial/blocked eligibility, currency-safe commercial outputs, deterministic arithmetic, idempotent calculation and decisions, model/profile safety, bounded comparison, score history, and safe errors. Existing 9D canonical supplier projection certification remains a separate integration proof rather than one monolithic 9A-to-9F journey.

Certification limitations remain: there is no dedicated Product Opportunity query-count/latency harness, automated AXE accessibility harness, or automated viewport/device harness in this repository; no live external-provider certification was attempted; repository-wide mypy is blocked by two errors in the unchanged baseline `apps/api/tests/test_supplier_portfolio_hard_certification.py` (`actions` lacks an annotation and `TEST_DATABASE_URL` is optional at a reset call); the new 9E/9F tests no longer produce a duplicate-module error, and the changed scoring service passes focused mypy. ESLint reports three pre-existing lifecycle-interface warnings and Angular build reports three pre-existing NG8102/NG8107 warnings.

Decision: **LOCAL CERTIFICATION BLOCKED**. No unexplained Product Opportunity failure was observed, but the missing certification harnesses and repository-wide mypy baseline prevent the stronger local-certified classification. This slice is **NOT PRODUCTION CERTIFIED** and **NOT LIVE CERTIFIED**. Slice 9G was not implemented.


## Slice 9I-B - Hard Certification Closure (2026-09-18)

The 9I-B hard-certification module is separate from the frozen 9A-9F inventory. Its collected inventory contains 3 nodes with SHA-256 `1781cfa78ad0106064ee122accce7f42cafe62ae4af116c7d917721c18ab11fd`:

- `test_canonical_9a_to_9f_evidence_rich_journey_and_reconciliation`
- `test_sparse_partial_currency_negative_and_missing_resilience_semantics`
- `test_blocker_history_owner_isolation_xss_and_query_measurements`

All 3 nodes passed against the disposable PostgreSQL test database (`3 passed, 16 warnings`). The module exercised the real owner-authenticated Product Opportunity APIs through demand, competition, commercial, sourcing-feasibility, synthesis, scoring, score explanation/history, human decisions (`watch`, `research_more`, `shortlist`, `reject`, `archive`), owner-scoped random-ID errors, JSON/XSS-safe responses, negative economics, currency mismatch, blocked scoring, and three-sample SQL query/latency measurements. Canonical arithmetic was checked with Decimal values against persisted dimension weights. No live provider or external connector was called.

The hard-cert module does not claim evidence for every requested 9I-B gate. Ranking/tie/comparison success with two independently scored opportunities, replay/immutability proofs, aggregate integrity counters, AXE accessibility, viewport/device coverage, and a baseline mypy-clean repository remain outside this focused three-node module. AXE and viewport/device harnesses are not present and remain explicit non-blocking limitations for local certification. Existing repository-wide mypy remains limited to the two unchanged baseline errors in `tests/test_supplier_portfolio_hard_certification.py`; the new module adds no mypy errors. Existing warnings are FastAPI `on_event` and SQLAlchemy UTC deprecation warnings, plus the previously documented Angular ESLint warnings.

Decision: **LOCAL CERTIFICATION BLOCKED**. The focused hard-certification evidence passed, but the stronger 9I-B local-certified claim is not made because the missing ranking/replay/integrity/accessibility/viewport evidence and baseline mypy limitation remain unresolved. This slice is **NOT PRODUCTION CERTIFIED** and **NOT LIVE CERTIFIED**. Slice 9G was not implemented.

## Slice 9I-C - Final Local Certification Closure (2026-09-18)

The focused 9I-C closure inventory contains 1 node with the repository-local SHA-256 captured from the collected node list. It passed against the disposable PostgreSQL test database (`1 passed`, 8 expected framework/SQLAlchemy deprecation warnings). The closure exercises stale and contradictory evidence markers, deterministic replay of 9B/9E/9F, immutable V1/V2 constraint and assessment lineage, two independently scored comparable opportunities, deterministic ranking/tie ordering, owner-scoped unknown-ID rejection, aggregate row counts, and the Product Opportunity score System Doctor.

Ownership architecture is **MODE A - SINGLE-USER / SINGLE-OWNER LOCAL APPLICATION**. This is established by `users.singleton_key = 1`, the `ck_users_single_owner` check constraint, setup-owner conflict handling, and repository release documentation. Therefore the applicable boundary is **SINGLE-OWNER ISOLATION - CERTIFIED LOCALLY**; multi-owner/SaaS tenant isolation is not applicable and is not certified. No production code was changed for this closure. The 9I-B three-node hard-certification module remains valid and is rerun separately as the regression baseline.

Decision: **LOCAL CERTIFICATION BLOCKED**. The focused closure test passed, but it does not prove the full requested 3-run determinism matrix, confidence/risk independence pairs, all five ranking eligibility classes, or an Owner A/B matrix; the database intentionally enforces one owner. This is **NOT PRODUCTION CERTIFIED** and **LIVE PROVIDERS NOT CERTIFIED**. AXE automation and viewport/device automation are unavailable in the repository. Repository-wide mypy remains limited to the two unchanged baseline errors in `tests/test_supplier_portfolio_hard_certification.py`; no new mypy errors were introduced by the closure test. Existing FastAPI `on_event`, SQLAlchemy UTC, ESLint lifecycle, and Angular template warnings remain non-blocking.



## Final 9I Certification Gates (2026-09-18)

The final three local gates pass on `feature/KAN-intelligence-winning-products` against the disposable PostgreSQL database. The two-node final-gate inventory is SHA-256 `ab9d4f259650ab0b4fb9e4f332fac54427983396882fdc2bc32de8795a824cd7`.

- Clean-state determinism: three independent executions pass with semantic equality 3/3 after normalizing only generated IDs, timestamps, lineage, fingerprints, and idempotency metadata.
- Complete ranking matrix: strong and moderate `SCORABLE` candidates are comparable; `PARTIALLY_SCORABLE`, `INSUFFICIENT_EVIDENCE`, and `BLOCKED` candidates are excluded from ordinary comparable ranking. Repeated ordering and tie ordering are stable.
- Explicit integrity matrix: all duplicate, orphan, lineage, range, weight, model/profile reference, decision-lineage, and current-projection counters are zero. System Doctor passes separately.

Final decision: **WINNING PRODUCT INTELLIGENCE - LOCAL CERTIFIED**; **NOT PRODUCTION CERTIFIED**; **LIVE PROVIDERS NOT CERTIFIED**. Slice 9G was not implemented.
