# Evidence verification

Claims reference persisted evidence ids. Evidence stores retrieval identity, content hash, source class, freshness, verification status, confidence, and provenance. Contradictions remain visible and require an explicit resolution strategy; the system never silently chooses a commercial outcome.
## Slice 5 hard-gate closure

Autonomous state changes use the append-only `AuditEvent` ledger with deterministic idempotency keys. Change detection compares successive certified states and stores prior/current values, deltas, evidence references, materiality, and correlation IDs; only material or review-worthy changes create alerts. Due schedules are materialized once with bounded `SKIP`, `RUN_LATEST`, or `BOUNDED_CATCH_UP` behavior. Worker checkpoints support crash-before and crash-after recovery, while owner-scoped uniqueness prevents duplicate evidence, changes, contradictions, reports, and recovery records. External research, live search, unrestricted scraping, external AI, and external mutations remain disabled by default.

Certification evidence is captured by the focused autonomous closure, security, and Angular acceptance suites. AXE and real viewport automation remain not configured by design.

## Final local certification evidence

- `apps/api/tests/test_intelligence_final_certification.py`: 14 passed, covering two-session mission/task/evidence/recovery idempotency, storage replay, duplicate/orphan/cross-owner integrity counters, endpoint inventory, ten-sample endpoint timing, execution timing, and SQLAlchemy query-count checks.
- `apps/api/tests/test_intelligence_autonomous_closure.py`: 5 passed for AuditEvent idempotency, change/materiality alerts, scheduler materialization, checkpoint recovery, recovery matrix, canonical history/report, and integrity.
- `apps/api/tests/test_intelligence_autonomous_security.py`: 71 passed (70 security cases plus URL boundary checks).
- `apps/api/tests/test_intelligence_autonomous_research.py -k prompt_injection`: 24 passed.
- Angular autonomous acceptance: 3 component tests; full web suite: 32 files/105 tests passed. Desktop suite: 4 tests passed.
- Migration upgrade/downgrade/upgrade reached head `20261002_0081`; Ruff, Black, mypy, lint, build, format, npm audits, System Doctor, and `git diff --check` pass.

Live web research, live search providers, external AI, unrestricted scraping, external mutations, purchasing, AXE, and viewport automation remain outside this local deterministic certification boundary.
### Exact ledger snapshot

Disposable autonomous ledger before execution was `missions=0, tasks=0, attempts=0, evidence=0, claims=0, contradictions=0, changes=0, schedules=0, recoveries=0, alerts=0, reports=0`. After one deterministic mission and report it was `missions=1, tasks=11, attempts=11, evidence=11, claims=11, contradictions=0, changes=0, schedules=0, recoveries=0, alerts=0, reports=1`; replay produced the identical counts (all replay deltas zero). The autonomous integrity endpoint returned `PASS` with all applicable duplicate/orphan/lineage/cross-owner counters zero.

The final timing harness recorded request-to-worker-claim at approximately 16 ms, worker-claim-to-first-candidate at approximately 82 ms, request wall time at approximately 1,147 ms, and run total at approximately 1,106 ms. Endpoint warm samples used ten iterations per endpoint; representative medians were overview 44.90 ms (p95 60.45), mission history 22.79 ms (p95 26.93), evidence 21.79 ms (p95 24.05), and report retrieval 19.60 ms (p95 21.84). Query instrumentation recorded opportunity detail 3, comparisons 5 for both 2- and 5-candidate fixtures, history 5, report retrieval 3, and evidence detail 3 queries, with no linear N+1 growth.
### Review, accessibility, and responsive proof

The bounded autonomous workspace renders explicit policy, mission status, review-required state, evidence/contradiction/change/alert summaries, and safe API errors using semantic headings, labelled controls, status/alert regions, keyboard-reachable buttons, and non-color status text. Existing contradiction resolution and mission pause/resume/cancel controls remain confirmation-gated; evidence acceptance/rejection and request-more-research mutation endpoints are intentionally not invented because they are not present in the current autonomous API. Static responsive checks cover 390px, 768px, and 1280px+ CSS breakpoints. Automated AXE and real viewport runs remain not configured.