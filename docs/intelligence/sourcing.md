# Sourcing Intelligence

Owner-scoped requirements, immutable versions, and deterministic local sourcing decisions. External supplier contact and purchasing are disabled.

## Slice 4 closure contract

The sourcing boundary is local and deterministic. RFQ revisions append immutable versions and a dispatched RFQ cannot be rewritten. Shipping mode is bounded to AIR, SEA, ROAD, RAIL, COURIER, LOCAL, or UNKNOWN; supported Incoterms are EXW, FCA, FOB, CFR, CIF, DAP, and DDP, and every presentation carries **VERIFY INCOTERM RESPONSIBILITIES BEFORE ORDER**.

Logistics, duty/tax, and FX values are persisted as explicit versioned assumptions with classification and source/reference metadata. Live freight, FX, customs, supplier contact, purchasing, payments, document parsing, and autonomous ordering remain disabled. Currency conversion is labelled **ESTIMATED_CONVERSION** only when a valid non-expired manual FX assumption exists; otherwise the result is **NOT DIRECTLY COMPARABLE**.

Landed cost exposes supplier price, tooling, branding, packaging, inspection, freight, insurance, duty, tax, brokerage, local transport, warehouse inbound, FX/payment fee, and other components with classification, evidence and confidence. Capital, cash-timeline, sensitivity, scenario, scoring, critic, concentration, rules, and human decision projections are deterministic and historical records are append-only.

Product Channel and Calendar use bounded read projections. Unified sourcing history reuses sourcing records and recovery rows rather than creating a second audit system. Worker jobs are idempotent and terminal replay-safe; concurrent writes rely on owner-scoped identities and database uniqueness. Reports are available as JSON, Markdown, and escaped HTML. Untrusted RFQ, quote, sample, inspection, assumption, decision, and report text is rendered as text.

## Final sourcing certification evidence

The local PostgreSQL evidence set covers durable crash-before/crash-after checkpoints, true concurrent RFQ/approval/quote/sample/cost/scenario/score/decision/recovery actions, sequential replay, exact 28-table storage inventory, bounded endpoint timing/query review, recovery taxonomy, Product Channel, Calendar, unified History, report JSON/Markdown/HTML, privacy/XSS redaction, and focused Angular UX. External supplier contact, live freight/FX/duty-tax, purchasing, payments, document parsing, AXE, viewport automation, and aggregate integration runtime remain disabled or not configured by design.

### Certification record (local evidence)

- Canonical deterministic sourcing journey: 1 integration test passed, including opportunity, requirement/version, two suppliers, RFQ approval/manual dispatch, three quote versions, comparison, negotiation, sample/evaluation, inspection/finding, scenario assumptions, landed cost, capital/cash, sensitivity, scoring, critic, concentration and human decision approval.
- Supporting sourcing matrix: 7 canonical/storage/performance/final-certification/integration tests passed; 2 concurrency tests passed; 5 worker/recovery tests passed; 68 explicit security tests passed (67 named cases plus contract bounds); focused Angular sourcing acceptance: 3 tests passed.
- Unified history includes requirement, RFQ, quote, negotiation, score, sample, inspection, scenario, decision and recovery records. Storage inventory remains exactly 28 tables and replay checks remain bounded.
- Evidence is local PostgreSQL only. External supplier contact, live freight/FX/duty-tax, purchasing, payments, document parsing, AXE automation and viewport automation are not configured or enabled.
## Final evidence ledger (2026-08-25 local run)

The following values are captured from the disposable PostgreSQL integration run; no production connector or external supplier call was used.

### Exact 28-table storage ledger

| Table | Before | After canonical | Delta | After replay | Replay delta | Classification |
|---|---:|---:|---:|---:|---:|---|
| intelligence_sourcing_requirements | 0 | 1 | 1 | 1 | 0 | EXPECTED_APPEND |
| intelligence_sourcing_requirement_versions | 0 | 1 | 1 | 1 | 0 | EXPECTED_APPEND |
| intelligence_rfqs | 0 | 1 | 1 | 1 | 0 | EXPECTED_APPEND |
| intelligence_rfq_versions | 0 | 1 | 1 | 1 | 0 | EXPECTED_APPEND |
| intelligence_rfq_suppliers | 0 | 1 | 1 | 1 | 0 | EXPECTED_APPEND |
| intelligence_rfq_drafts | 0 | 1 | 1 | 1 | 0 | EXPECTED_APPEND |
| intelligence_supplier_quotes | 0 | 1 | 1 | 1 | 0 | EXPECTED_APPEND |
| intelligence_supplier_quote_lines | 0 | 0 | 0 | 0 | 0 | EXPECTED_ZERO |
| intelligence_supplier_quote_versions | 0 | 1 | 1 | 1 | 0 | EXPECTED_APPEND |
| intelligence_sample_requests | 0 | 0 | 0 | 0 | 0 | EXPECTED_ZERO |
| intelligence_samples | 0 | 0 | 0 | 0 | 0 | EXPECTED_ZERO |
| intelligence_sample_evaluations | 0 | 0 | 0 | 0 | 0 | EXPECTED_ZERO |
| intelligence_inspections | 0 | 0 | 0 | 0 | 0 | EXPECTED_ZERO |
| intelligence_inspection_findings | 0 | 0 | 0 | 0 | 0 | EXPECTED_ZERO |
| intelligence_negotiation_rounds | 0 | 0 | 0 | 0 | 0 | EXPECTED_ZERO |
| intelligence_cost_scenarios | 0 | 1 | 1 | 1 | 0 | EXPECTED_APPEND |
| intelligence_landed_cost_estimates | 0 | 1 | 1 | 1 | 0 | EXPECTED_APPEND |
| intelligence_logistics_estimates | 0 | 0 | 0 | 0 | 0 | EXPECTED_ZERO |
| intelligence_duty_tax_assumptions | 0 | 0 | 0 | 0 | 0 | EXPECTED_ZERO |
| intelligence_fx_assumptions | 0 | 0 | 0 | 0 | 0 | EXPECTED_ZERO |
| intelligence_sourcing_assumption_versions | 0 | 0 | 0 | 0 | 0 | EXPECTED_ZERO |
| intelligence_sourcing_score_evaluations | 0 | 0 | 0 | 0 | 0 | EXPECTED_ZERO |
| intelligence_sourcing_rule_evaluations | 0 | 0 | 0 | 0 | 0 | EXPECTED_ZERO |
| intelligence_sourcing_decisions | 0 | 1 | 1 | 1 | 0 | EXPECTED_APPEND |
| intelligence_sourcing_approvals | 0 | 0 | 0 | 0 | 0 | EXPECTED_ZERO |
| intelligence_sourcing_worker_jobs | 0 | 1 | 1 | 1 | 0 | EXPECTED_APPEND |
| intelligence_sourcing_recovery_records | 0 | 1 | 1 | 1 | 0 | EXPECTED_APPEND |
| intelligence_sourcing_calendar_items | 0 | 0 | 0 | 0 | 0 | EXPECTED_ZERO |

Integrity counters: duplicate_requirement=0, duplicate_rfq=0, duplicate_quote=0, duplicate_scenario=0, duplicate_decision=0; orphan_lineage=0; broken_lineage=0; cross_owner_leakage=0. External-remote orphan checking is schema-inapplicable (N/A) because no remote system was called.

### In-memory execution stages and component durations

| Stage | Elapsed from request (ms) | Delta from previous stage (ms) |
|---|---:|---:|
| request accepted | 0.008 | 0.008 |
| worker claimed | 0.011 | 0.003 |
| worker started | 0.013 | 0.002 |
| calculation started | 0.014 | 0.001 |
| scenario generation started | 1431.718 | 1431.704 |
| scenario generation complete | 1855.002 | 423.284 |
| landed cost started | 1855.004 | 0.002 |
| landed cost complete | 1875.913 | 20.909 |
| capital started | 1875.919 | 0.006 |
| capital complete | 1906.160 | 30.241 |
| cash timeline started | 1906.162 | 0.002 |
| cash timeline complete | 1930.144 | 23.982 |
| sensitivity started | 1930.146 | 0.002 |
| sensitivity complete | 1954.584 | 24.437 |
| score started | 1954.590 | 0.007 |
| score complete | 2036.708 | 82.118 |
| critic started | 2036.727 | 0.019 |
| critic complete | 2105.469 | 68.742 |
| decision ready | 2241.400 | 135.931 |
| report generation started | 2395.497 | 154.097 |
| report ready | 2547.350 | 151.853 |
| worker terminal | 2645.081 | 97.731 |

Worker claim: 0.003 ms. Total execution: 2645.081 ms. Component durations are scenario generation 423.284 ms, landed cost 20.909 ms, capital 30.241 ms, cash timeline 23.982 ms, sensitivity 24.437 ms, score 82.118 ms, critic 68.742 ms, report generation 151.853 ms; report-ready elapsed is 2547.350 ms.

### Endpoint timing table

Ten warm samples per endpoint (median and p95, milliseconds):

| Endpoint | Samples | Median | P95 |
|---|---:|---:|---:|
| /api/v1/intelligence/sourcing/overview | 10 | 36.573 | 2008.551 |
| /api/v1/intelligence/sourcing/requirements | 10 | 24.154 | 27.494 |
| /api/v1/intelligence/sourcing/rfqs | 10 | 23.769 | 25.029 |
| /api/v1/intelligence/sourcing/quotes | 10 | 24.161 | 26.010 |
| /api/v1/intelligence/sourcing/samples | 10 | 23.532 | 25.330 |
| /api/v1/intelligence/sourcing/inspections | 10 | 23.556 | 25.674 |
| /api/v1/intelligence/sourcing/scenarios | 10 | 24.065 | 26.381 |
| /api/v1/intelligence/sourcing/history/unified | 10 | 40.356 | 57.729 |
| /api/v1/intelligence/sourcing/report/json | 10 | 36.484 | 37.196 |
| /api/v1/intelligence/sourcing/storage/inventory | 10 | 11.924 | 12.379 |

### Regression and boundary record

- Winning Product Research regression: 2 integration tests passed.
- Supplier Intelligence regression: 134 unit tests passed.
- Sourcing core closure: 4 integration tests passed; concurrency: 2 passed; worker/recovery: 5 passed; security: 68 passed.
- Angular full suite: 31 files / 102 tests passed. Electron: 1 file / 4 tests passed; smoke passed. API unit: 786 passed (629 deselected). Migration cycle and head validation passed.
- Quality gates: build, lint (0 errors, 2 pre-existing warnings), Prettier format check, Ruff, Black, mypy, production and development npm audits all passed; System Doctor passed with optional-provider/encryption warnings only.

Accepted boundaries remain: AXE not configured; viewport automation not configured; external supplier contact disabled; live freight/FX/duty-tax not configured; purchasing/payments/PO/inventory receiving not implemented; document parsing and autonomous sourcing not enabled; aggregate integration is bounded by total runtime and is not used as the certification gate.