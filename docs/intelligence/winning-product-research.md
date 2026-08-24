# Winning Product Research

Slice 2 is a deterministic local research engine. It reads versioned internal fixtures, stores source evidence, derives normalized signals, applies restrictions and profile rules, scores candidates, and promotes only a reviewable `IntelligenceOpportunity`. It does not call the internet, marketplace APIs, suppliers, or AI providers.

Every observation is labeled as local fixture evidence. Derived metrics and assumptions are stored separately from evidence. Candidates remain distinct from VAYUJIT Products until a future human-approved handoff.

Run a mission with `POST /api/v1/intelligence/missions/{id}/run-now`, or execute pending work with `npm.cmd run intelligence:worker:once`. Re-running the same mission idempotency key reuses the existing run and candidate/evidence keys.

## Slice 2 local certification closure

The local provider is deterministic and external research remains disabled. Trend observations are append-only and carry candidate/opportunity lineage, market/category, velocity, acceleration, seasonality, confidence, source evidence IDs, timestamps, and correlation IDs. Physical rules normalize kg/g and cm/m/mm, derive volume and volumetric weight, and evaluate PASS/REVIEW_REQUIRED/BLOCK. Policy scopes resolve GLOBAL ? MARKET ? MARKETPLACE ? CATEGORY ? PROFILE ? MISSION, with hard blocks preserved unless an explicit auditable override is requested.

Economics are estimates, never supplier-confirmed: each input is OBSERVED, ASSUMED, ESTIMATED, or UNKNOWN with currency, evidence/assumption reason, and confidence. Outputs include landed-like basis, contribution, margin, break-even price, maximum CAC, ROAS, initial inventory, and preliminary capital. Source diversity and evidence quality are deterministic and visible. Supplier availability remains UNKNOWN / NOT SCORED, and legal output is always `LEGAL REVIEW MAY BE REQUIRED` rather than clearance.

Mission run-now and future schedules use owner-scoped idempotency keys. Worker lifecycle and recovery records are append-only; replaying the same key reuses the prior result. Reports expose bounded provenance only and do not include credentials, tokens, cookies, DSNs, local paths, or raw secrets. The Operations API consumes only the bounded Intelligence projection.

## Final local certification boundary

The final closure suite is `apps/api/tests/test_intelligence_final_certification.py` plus the deterministic unit and integration suites. It proves same-key run-now idempotency, concurrent Recovery identity, concurrent candidate/evidence/scoring deduplication, concurrent rule-evaluation identity, replay-stable storage counts, duplicate-group checks, and bounded endpoint timing against the disposable PostgreSQL test database. Score rows are keyed by candidate and immutable scoring model version; newer versions append new rows rather than overwrite prior evaluations.

The provider mode is `local_deterministic` only. External research, supplier integrations, autonomous multi-agent behavior, and live marketplace calls are disabled and are not certified. Accessibility is covered by semantic labels, headings, landmarks, alerts, keyboard-operable buttons, and responsive CSS tests; automated AXE and real viewport automation are not configured in this repository. System Doctor may continue to warn about optional live providers and absent production encryption keys in a local test environment.
## Final proof additions

The certification harness now inventories every intelligence_* table from SQLAlchemy metadata and prints exact before/after/replay deltas. The canonical deterministic run currently records: 1 project, 1 mission, 1 run, 5 sources, 40 evidence rows, 8 candidates, 64 signals, 11 competitor products/snapshots, 11 review themes, 11 pain points, 11 differentiations, 8 scores, 8 trend observations, 8 economic estimates, 6 opportunities, and one checkpoint. Claims, claim-evidence links, rule categories/rules/evaluations, profiles, schedules, reports, and recovery records remain zero in that scenario because those routes are not part of the provider fixture.

Score v1 and v2 are append-only evaluation rows keyed by owner, candidate, and scoring model version. The proof test verifies v1 snapshots remain unchanged after v2 insertion and concurrent v2 identity creation yields one row. Checkpoint payloads record worker claim, provider start, first candidate persistence, and scoring completion timestamps for local timing evidence.

The endpoint harness covers the repository's existing recovery, overview, project, mission-list, history, candidate, signal, trend, opportunity, ranking, comparison, source, evidence, rule-category, rule-simulator, profile, recovery-matrix, and report routes. No unsupported mission-detail endpoint is invented.

## Final hard-gate certification evidence

The final local hard-gate suite contains 14 integration tests and passed 14/14. Historical IntelligenceScoreEvaluation rows are guarded by an ORM before_update listener: mutation attempts fail with the safe immutable error, rollback cleanly, and concurrent creation of a newer scoring version remains valid. The full runtime integrity matrix covers 27 Intelligence tables and reports zero duplicate unique-identity groups, zero orphan foreign keys, and zero cross-owner references.

The complete mounted Intelligence inventory contains 59 routes across READ, MUTATION, REPORT, WORKER/SCHEDULER, and RECOVERY classifications. The endpoint harness runs 10 warm samples per route and records median/p95 timings. The heaviest observed read medians were overview 86.50 ms and mission history 47.57 ms; comparison was 48.09 ms median / 56.89 ms p95, rules simulation 48.54 / 58.69, and report retrieval 31.00 / 33.94. Query-count evidence is stable: opportunity detail 3, comparison with two candidates 5, comparison with five candidates 5, history 5, report retrieval 3, and evidence detail 3.

The report-ready ledger records worker claim, provider start, first candidate persistence, candidate processing, scoring, opportunity promotion, report generation start, and report-ready timestamps. In the certified run, the terminal run was 1,773.38 ms and report-ready was 1,869.82 ms. Storage replay before/after deltas remain zero for the canonical deterministic replay.

UX evidence remains bounded to the implemented local workspace: overview loading/success/failure states, semantic evidence labels, safe errors, keyboard-operable controls, and responsive layout are covered. Automated AXE and real viewport automation are not configured. Supplier confirmation, autonomous research, external research, live providers, and live marketplace calls remain explicitly outside this local certification boundary.
## UX hard-gate closure

The Angular Intelligence workspace now exposes owner-scoped navigation for overview, missions, candidates, opportunities, rules, profiles, comparison, reports, history, and sources/evidence. Mission creation validates project/name and posts the selected market, categories, frequency, timezone, ruleset, thresholds, and optional profile; existing missions support run-now, pause/resume, schedule, edit, and history actions with explicit confirmations and duplicate-click guards.

Candidate and opportunity views provide filter controls, detail retrieval, signal/trend history, score/recommendation/freshness states, evidence classification labels, competitor/review summaries, deterministic rule hierarchy/simulation messaging, profile editing with price-bound validation, candidate comparison (two to five), report/history panes, and safe evidence inspection. Loading, empty, and authenticated-API error states are visible; rendered report/evidence content uses Angular interpolation/JSON pipes rather than HTML injection. External research and AI interpretation remain visibly disabled.

Focused Angular acceptance coverage is in `apps/web/src/app/intelligence/intelligence-workspace.component.spec.ts` and validates navigation, overview rendering, mission create/run validation, duplicate run protection, candidate/opportunity detail calls, profile bounds, safe error boundaries, and evidence labels. The workspace uses semantic headings, landmarks, labels, alerts, keyboard-operable buttons, and responsive grid breakpoints. Automated AXE and real viewport automation remain unavailable in this repository and are reported as static/manual evidence only.
