# Supplier Due Diligence

Supplier Due Diligence is an owner-scoped, provider-independent orchestration
layer over Supplier Shortlisting, Website/Marketplace Intelligence, Evidence,
Verifier, Freshness, Risk, Contradiction, and the shared Autonomous Research
runtime. It detects explicit evidence gaps, assigns explainable severity and
priority, creates bounded idempotent research plans/tasks, and preserves
append-only assessment history.

The API is rooted at `/api/v1/intelligence/supplier-due-diligence`; every route
requires the authenticated owner and existing exact-Origin protection. Reports
and projections are sanitized. Supplier contact, messaging, RFQ, purchase,
payment, provider mutation, and autonomous supplier approval are not
implemented.

Gap dimensions include identity, legal entity, location, contactability,
manufacturing/product capability, certification, facility, specification,
commercial terms, shipping/export, risk, reputation, source diversity,
freshness, contradiction, and other. Gap states, readiness, plan states,
budgets, human waiver/reopen/research actions, integrity counters, and
owner-isolated history are persisted in migration `20261022_0101`.

Local fixture mode reuses existing deterministic provider/runtime controls; it
is not live-provider certification. Live due-diligence research remains
blocked until external provider configuration and allowlists are supplied.

## Closure behavior

A research plan creates a `SUPPLIER_VERIFICATION` mission and one shared
Autonomous Research task per due-diligence task. Completion projects task
status, evidence identifiers, verification/freshness states, and a new
assessment version back into the due-diligence ledger. `VERIFIED`/`SUPPORTED`
fresh evidence can resolve a gap; rejected, conflicting, stale, or merely
running evidence cannot silently resolve one. Claims and observations remain
owned by the shared research runtime and are referenced by durable IDs.

Required, recommended, and optional gaps are retained in each immutable
assessment version. Optional reputation evidence is informational and never
blocks sourcing readiness. Existing supplier risk state is consumed for risk
gaps; no second risk score is created.

The shortlisting Product Channel projection now includes due-diligence status,
readiness, critical/high and required-open counts, active research, and last
assessment time. The cross-marketplace Product Channel and Calendar projections
include owner-scoped due-diligence summaries and stable review/research event
identities. Plan execution and recovery routes delegate to the shared
Autonomous Research runtime; no parallel worker or retry loop is introduced.

Human actions are audited and owner-scoped: start/research-selected/request
more research, cancel/review aliases, waive, reopen, and mark-for-human-review.
A waiver requires a human reason and remains distinct from evidence resolution.
History, reports, gap detail, and integrity endpoints expose lineage and
redacted evidence metadata. Integrity counters are database-derived and report
orphan, duplicate, cross-owner, pointer, lineage, waiver, and calendar issues.

The due-diligence Angular workspace presents semantic gap tables, research-plan
status, and guarded Research/Waive/Reopen buttons. It is a local functional
workspace; full crash/concurrency/security/accessibility certification remains
out of scope for this pass.
## Slice 8C.2 functional closure

The completion projection follows the shared verifier-to-observation path:
only fresh `VERIFIED` or `SUPPORTED` evidence is projected into an immutable,
deterministic `WebsiteObservation`, and a new due-diligence assessment version
records evidence and observation lineage. Replaying the same shared mission is
idempotent and does not create another observation or assessment version.
`DISCOVERY_ONLY`, `UNVERIFIED`, rejected/contradicted, stale/expired, and
unknown evidence remain unresolved. Resolution metadata is explicit:
`resolution_type`, evidence IDs, observation IDs, `resolved_at`, and
`resolved_by`; a human waiver remains separate from evidence resolution.

Risk readiness is read from the existing supplier risk projection and is never
lowered by due diligence. Sourcing handoffs use the existing
`ALLOWED`/`REVIEW_REQUIRED`/`BLOCKED` guard and perform no external dispatch.
Human actions normalize aliases for start/research-selected,
cancel/request-more-research, waive, reopen, and mark-for-human-review;
illegal transitions return safe conflicts and accepted actions are audited with
their prior and resulting state.

Owner predicates apply to contexts, plans, tasks, evidence, claims,
observations, and action lookups. Focused due-diligence tests cover the local
functional path; final multi-owner/concurrency and provider certification remain
part of the later 8C.3 certification matrix.

## Slice 8C.2c functional proof closure

Reassessment summaries now retain the authoritative shared-risk reference plus
triggering evidence, claim, verification, observation, risk-before/risk-after,
and resulting assessment identifiers. Readiness responses expose structured,
server-derived blocker reasons for contradiction, stale evidence, and
unresolved required verification.

Human research actions validate owner/context/gap state, selected-gap
membership, closed-context rejection, bounded plan creation, and cancellation
of active shared tasks without deleting history. Product Channel due-diligence
summaries expose server-derived assessment, completion, material-finding, and
latest-human-action values. Calendar events include stable owner, supplier,
context, source, and due-date fields and remain deterministic on reprojection.

The focused canonical proof covers these additions. Full two-owner corruption
self-proof, exhaustive evidence outcome/recovery matrices, and PostgreSQL
concurrency/replay/performance/security certification remain deferred to 8C.3.
The development npm audit remains a pre-existing/transitive exception; the
production-only audit remains clean.
## Slice 8C.2d functional proof closure

The focused proof file `apps/api/tests/test_supplier_due_diligence_proof.py` now
covers the local four-outcome evidence matrix, action/idempotency behavior for
start, selected-gap research, cancellation, human review, waiver, reopen, and
plan execution, plus safe rejected/stale/contradictory evidence handling. It
also self-proves duplicate active plans/tasks, broken shared-execution lineage,
resolved gaps without evidence/waiver, current-assessment pointer corruption,
restoration to zero integrity counters, and direct-ID 404/owner predicates.

The canonical integration proof continues to cover immutable assessment lineage,
explanation/replay/recovery, Product Channel and Calendar projections, and
operations visibility. The focused regression matrix passed 82 selected tests
(4 deselected) across due diligence, shortlisting, autonomous research,
sourcing, supplier risk, Product Channel, Calendar, Operations, and Recovery.

The Angular focused proof covers all semantic states (`MISSING`, `WEAK`, `STALE`,
`CONTRADICTORY`, `INSUFFICIENT`, `RESEARCHING`, `RESOLVED`,
`WAIVED_BY_HUMAN`, `BLOCKED`, and `REVIEW_REQUIRED`), the required action request
paths including Review Evidence, empty-reason waiver rejection, successful
waiver request payload, and safe server rejection handling. The UI keeps the
server authoritative; human waiver remains distinct from evidence resolution.

One focused proof exposed a real defect: a research task from an earlier
assessment could reference a gap that was reopened into a newer assessment.
Completion now safely skips observation projection when that stale gap is absent
instead of raising `StopIteration`; no legacy dispatch or new worker behavior
was introduced. Integrity duplicate detection now uses canonical context/version
and plan/gap keys rather than idempotency keys.

Local quality gates for this closure were green for the focused Angular tests,
Black, Ruff, and mypy. Existing deprecation warnings remain. Full repository
functional gates and the production-only dependency audit remain governed by the
latest repository certification record. Crash/concurrency/performance/security
stress, live-provider, and external certification remain intentionally deferred
to 8C.3.
### Dependency audit boundary

`npm audit --omit=dev` reports `0 vulnerabilities`. Full `npm audit` reports five
transitive development-tool findings: high `js-yaml` via `electron-builder`,
moderate `@vitest/mocker` via `vitest`, moderate `hono` via Angular CLI's MCP
SDK, and low/moderate `joi` via `wait-on` (the audit groups two Joi advisories).
The available fixes require an out-of-range/forced update or unrelated tool
upgrades, so no dependency files were changed. These findings are not shipped
runtime dependencies; the development audit remains an accepted exception.
## Slice 8C.3 hard certification

Hard certification was executed on `feature/KAN-intelligence-supplier-due-diligence`
without changing the production authentication model. The disposable integration
harness creates deterministic OWNER_A and OWNER_B users only in the test database.
Owner isolation passed: foreign context, plan, mission, recovery, gap, and task
reads are safe 404/empty responses; cross-owner mutations are rejected; and the
second owner has zero durable deltas. A real defect found by that proof was fixed
in `due_diligence_router.tasks`: a foreign plan can no longer return an empty 200
list. No registry, worker, or research behavior changed.

The hard-certification suite passed 7 tests (16 expected FastAPI deprecation
warnings). The canonical due-diligence integration proof passed 1 test and the
proof suite passed 2 tests (10 expected warnings). Repeatability is 3/3 with
stable gap dimensions/classifications/status/severity and idempotent plan replay.
Crash/replay checkpoints `before_source` and `after_evidence` pass using the
existing fault-injection contract; later runtime stages have no separate
injection hook and are recorded as not independently configured. The suite also
proved no duplicate retrieval identities, no cross-owner leakage, safe malformed
and direct-ID behavior, escaped report output for hostile input, zero integrity
violations, and bounded list/detail/operations query volume under the local
threshold. A true PostgreSQL two-session harness now proves context and plan idempotency across
three repeated rounds. The remaining selected-gap, reassessment, completion, waiver,
and request-more-research race scenarios have no dedicated proof yet. AXE browser
scan and viewport matrix are not configured in this repository and are reported as
such rather than inferred.

Existing provider/runtime regressions remain local-fixture only; live external
provider calls remain disabled unless explicitly configured. Production dependency
audit remains clean (`npm audit --omit=dev`: 0); the full development audit has
five accepted transitive tooling advisories and no dependency change was made.
The final local classification is `SLICE 8C.3 â€” CERTIFICATION INCOMPLETE` because the
true PostgreSQL race matrix and three provider suites were not completed. The
implemented boundary is locally proven; unavailable browser/viewport gates are explicitly
not configured and external-provider certification remains blocked by credentials.

## Slice 8C.3c final certification reconciliation

The final reconciliation was run on the existing branch without changing production due-diligence behavior. The integration inventory collected 2,277 tests, of which 1,159 are integration-selected and 1,118 are deselected unit tests. The API unit suite passed 1,118 tests. Ruff, Black, mypy, Prettier format checking, and `git diff --check` passed. Angular passed 40 files/149 tests; the desktop suite passed 1 file/4 tests; Electron smoke passed with renderer `app://vayujit` and sandbox enabled. The test-only integration fixture now seeds the default `product-content-publish` workflow template required by shared integration fixtures.

The crash contract remains certified only for the two repository-supported stages (`before_source` and `after_evidence`). The requested stages 1, 2, 4, and 6 do not exist in the production checkpoint contract; no production fault-injection hook was added solely to manufacture certification coverage. Context/plan PostgreSQL concurrency passed three repeated rounds. The selected-gap, reassessment, completion, waiver, and request-more-research race matrix, full six-stage crash matrix, full replay ledger, explicit entity-by-entity storage delta ledger, and local benchmark harness therefore remain unproven and are not represented as green gates.

The full integration collection was inspected, but broad execution was not completed after interrupted long-running runs left disposable PostgreSQL sessions contending on fixture resets. The migration full-cycle attempt also hit PostgreSQL `out of shared memory` while dropping tables (`max_locks_per_transaction`), which is an environment ceiling rather than an application assertion. Provider suites remain local-fixture/external-credential constrained; no live provider call was made. The production dependency audit remains clean (`npm audit --omit=dev`: 0 vulnerabilities); the full development audit retains five transitive tooling advisories accepted at the existing boundary. Accordingly, Slice 8C.3 remains `CERTIFICATION INCOMPLETE`, not `LOCAL CERTIFIED` or production-certified.
## Slice 8C.3d certification infrastructure stabilization

This infrastructure-only closure keeps Registry-only/runtime production behavior
unchanged. The test database reset now validates the disposable marker, disposes
the active SQLAlchemy engine, and terminates sessions only in the exact approved
disposable database before recreating metadata. The integration runner supports
an explicit marker and disposable database name; the default vayujit_test
name remains allowed. The five focused migration cycles each completed
upgrade head, downgrade 20261021_0100, and upgrade head without lock
exhaustion. The prior historical downgrade failure is classified as the
PostgreSQL max_locks_per_transaction environment ceiling, not a product
migration defect; the focused current-branch cycle does not require a global
lock-limit change.

The test-only checkpoint controller now covers
DD_BEFORE_PLAN_DISPATCH, DD_AFTER_PLAN_PERSIST, DD_BEFORE_SOURCE,
DD_AFTER_EXECUTION, DD_AFTER_EVIDENCE, and DD_AFTER_REASSESSMENT.
Checkpoint smoke passed 6/6. The reusable two-session PostgreSQL harness
opens independent sessions, synchronizes at one barrier, rolls back and closes
each session, and ran the context, plan, selected-gap, reassessment, completion,
waiver, and request-more-research scenarios; harness availability passed 7/7.
The disposable fixture lifecycle proof passed 20/20.

The deterministic integration manifest contains 1,159 selected tests in 12
contiguous shards of 100 (the final shard is smaller), with membership total
1,159, missing 0, duplicates 0, and extras 0. The manifest records a SHA-256
inventory hash and the shard runner writes a machine-readable result checkpoint
per shard, including inventory and node hashes, so resume is permitted only
for the same source, branch, inventory, and configuration. Provider grouping
remains visible through the collected node IDs; no provider or full 1,159-test
execution was started in this slice.

Warnings are limited to the existing FastAPI on_event deprecation (and its
TestClient propagation). No production module was changed; core/test_database.py
is test-only lifecycle infrastructure.

## Slice 8C.3e final certification execution

The focused Due Diligence hard-certification suite passed 7/7, the canonical
integration/proof suites passed 3/3, the API unit suite passed 1,118 tests, the
Angular suite passed 40 files and 149 tests, the desktop suite passed 1 file and
4 tests, Electron smoke passed with `app://vayujit` and sandbox enabled, the
current-branch migration fixture passed 5/5 cycles, and Ruff, Black, mypy,
Prettier, build, lint, System Doctor, and `git diff --check` passed. The frozen
integration inventory still verifies 1,159 selected tests in 12 shards with
missing 0, duplicates 0, and extras 0.

The full IndiaMART local-fixture run completed 98 tests with 93 passed and 5
failures. The first full-suite traceback was PostgreSQL deadlock contention in
disposable fixture reset; isolated reruns passed the affected functional cases.
The remaining deterministic failure is the pre-existing IndiaMART performance
gate (`Evidence projection` p95 5,829.4 ms against the existing 5,000 ms
threshold). IndiaMART production code is unchanged on this branch, so no
speculative provider change was made. The requested six-stage crash contract is
also not exposed by production: only `before_source` and `after_evidence` are
runtime controls; the other four names remain test-only trigger points. The
full 1,159-shard matrix was not started after this hard-gate failure.

Development audit remains five transitive tooling findings (1 high, 3 moderate,
1 low); `npm audit --omit=dev` remains 0 vulnerabilities. Local classification
is `SLICE 8C.3e â€” CERTIFICATION INCOMPLETE`; production remains not certified
and live research remains blocked by external configuration.
## Slice 8C.3f final hard-gate reconciliation

IndiaMART was rerun on the exact merge-base production and test files
(`ec5df91ed35c30575db84c70af116e7fb1c9e56c`). The full run collected 98 tests,
with 95 passed and 3 deadlock failures during concurrent disposable-fixture
reset. Each failed node passed when rerun in isolation on a clean disposable
database, proving a PostgreSQL test-harness contention limitation rather than
an IndiaMART behavior regression. Alibaba, TradeIndia, and Global Sources
LOCAL_FIXTURE runs each passed 50/50; Cross-Marketplace passed 4/4; Website
final certification passed 9/9.

Due-diligence hard certification passed 10/10 for the focused hard,
integration, and proof files. Existing true PostgreSQL concurrency proof covers
context and plan idempotency; dedicated selected-gap, reassessment, completion,
waiver, and request-more-research race tests were not present and therefore are
not claimed. Existing production checkpoint controls prove `before_source` and
`after_evidence`; the other four requested crash-composition stages have no
production hook and remain composition-only/unproven. The sourcing suite passed
13/14, with the sole repeatable failure being the cold first `/overview` request
(4.1-4.8 s p95, warm requests about 40 ms), an environment-sensitive benchmark
artifact with no production change made.

Workflow passed 5/5, Scheduler integration 11/11, Marketplace Runtime 28/28,
Cross-Marketplace 1/1, external recovery 6/6, API unit 1,118 tests, desktop
4/4, migrations 5/5, Electron smoke, build, lint, Ruff, Black, mypy, format,
System Doctor, and `git diff --check` passed. The frozen inventory is 1,159
selected tests in 12 shards with SHA-256
`e1d609a7d6fadd77323c08391a4747e5608a0413a4e86c117e174a4a649e5206`.

`npm audit --omit=dev` reports zero vulnerabilities. Full `npm audit` reports
five transitive development-tool advisories (1 high, 3 moderate, 1 low) in
`js-yaml`, `vitest`/`@vitest/mocker`, `hono`, and `joi`; the attempted lockfile-only
fix was blocked by peer-resolution conflicts, so no dependency files changed.
The development-only exception is accepted; production dependency audit is
PASS. Because the six-stage crash composition, five additional concurrency
races, full 1,159-shard execution, and sourcing cold-start benchmark remain
unproven, Slice 8C.3f is `CERTIFICATION INCOMPLETE`.

## Slice 8C.3g certification-closure evidence

The three targeted certification defects are closed without production changes.
The real due-diligence integration suite passed 1/1, the complete four-test
proof suite passed 4/4, the six-boundary crash-composition matrix passed 6/6
within the 14-test infrastructure suite (14/14), and API unit coverage passed
1,118/1,118. The crash contract explicitly records all six test-only boundaries
and preserves the two production-native controls (`before_source` and
`after_evidence`); no production crash hooks were added.

The replay proof now exercises every exposed due-diligence input and emits an
explicit entity-level expected-vs-actual storage ledger. Replay deltas were zero
for contexts, assessments, gaps, gap versions, research plans/tasks, autonomous
missions/executions, evidence/claims/references, observations, risk history,
human actions/waivers, projection placeholders, calendar placeholders, and
recovery references. The integrity self-proof independently exercised and
restored all fourteen counters to zero.

Focused regressions also passed: Recovery 6/6, Autonomous Research 30/30,
Marketplace Runtime 28/28, Product Channel 1/1 (AI contract) plus 1/1 (final
acceptance), and Calendar 1/1. Ruff, Black, mypy, and `git diff --check` pass.
The unchanged 1,159-test/12-shard integration matrix remains deferred to its
prewarmed dedicated environment; no full provider matrix was run in this pass.
STORAGE LEDGER - PASS. INTEGRITY SELF-PROOF - PASS.
Local classification: `SLICE 8C.3g - CERTIFICATION DEFECTS CLOSED`.
Production remains not certified and live research remains blocked by external
configuration.

