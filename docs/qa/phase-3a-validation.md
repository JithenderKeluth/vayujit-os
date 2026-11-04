# QA Phase 3A — bounded remediation and independent retesting

25 October 2026. **QA PHASE 3A — BOUNDED REMEDIATION VALIDATED /
APPLICATION CERTIFICATION INCOMPLETE.**

## Scope and authority

This work implements the five explicitly named remediation roots, not a general
refactor. The reviewed ledger identifies **four P1 roots and one P2 root** within
that scope. `QA-P3-SOURCE-001` is the fifth baseline P1, but the instructions
explicitly exclude its remediation. It remains open; priorities are not relabelled.

The original reviewed findings remain immutable historical evidence in
[phase-3-reviewed-findings.json](phase-3-reviewed-findings.json). Current closure
must be demonstrated in the [resolution ledger](phase-3a-resolution.json), current
[Phase 3 report](phase-3-report.json), and active [backlog](defect-backlog.json).
Old failed reports are archived, not overwritten without history.

## Root causes and bounded fixes

| Finding | Priority | Root cause | Correction |
| --- | --- | --- | --- |
| QA-P3-FIN-001 | P1 | UNKNOWN revisions were excluded before latest-per-key selection; known zero was conflated with missing evidence. | Select the latest effective revision first. UNKNOWN blocks contribution/profit and recommendation qualification in summary and both profitability paths. Explicit UNKNOWN evidence cannot be replaced by the legacy product cost. Record selected cost IDs in current calculation lineage. |
| QA-P3-IDEM-001 | P1 | Item/key lookup returned a stock movement without comparing intent. | Under the existing item lock, compare movement type, delta, reason, HUMAN actor and captured expected version. Reject conflicts with 409; retain the original version for valid retries. |
| QA-P3-IDEM-002 | P1 | Financial-event preflight and uniqueness recovery acknowledged any source-event match. | Share normalized identity validation across both paths: account, source ID, marketplace, type, rounded amount, currency, references, source, evidence state, explicit effective time and semantic payload. Omitted server-assigned time does not become a new timestamp on replay. |
| QA-P3-IDEM-003 | P2 | Transition replay ignored signal, target, note and snooze expiry; old snooze replays could mutate later state. | Compare canonical HUMAN intent and expiry. Identical replay returns the persisted transition without reapplying its effect. Conflicting scope/target/intent returns 409. |
| QA-P3-SIGNAL-001 | P1 | Scans upserted matches but did not retire recovered stock claims; stock source versions were not current. | Re-evaluate current stock snapshots on scan, read and transition. Append SYSTEM STALE history, preserve old evidence, version new stock fingerprints and block new actions on stale evidence. Serialize derived signal transactions without adding inventory locks that invert canonical multi-line order lock order. |

No schema migration, shared idempotency framework, new approval authority, financial
formula, marketplace fee schedule, TTL policy or multi-tenant model was introduced.
Existing source events, cost versions, stock movements and HUMAN transitions remain
persisted. Stock SYSTEM transitions use the existing required owner FK as
installation context, explicitly labelled in metadata; they are not HUMAN approval.

The derived signal check is snapshot/version-based, not a reservation or guarantee
that stock cannot change after a response. Subsequent reads and intents revalidate
again; canonical stock/order authorities still control actual inventory changes.

The financial model has no cost-expiry field. Freshness tests therefore exercise
supersession, effective dates, future revisions and historical as-of queries, not
an invented expiration rule. Current calculation rows remain mutable projections;
cost IDs improve lineage but do not close the historical-version workflow gap.

## Execution results

| Gate | Final actual result | Evidence / qualification |
| --- | --- | --- |
| New targeted PostgreSQL regressions | **17 passed, 0 failed/errors/skips** | `87f95bbe87d146e7/backend-results.xml`; source hashes captured before execution, exact cleanup PASS |
| Existing operational backend cases | **19 passed** | Eight inventory/order, seven finance, four Action Center; combined regression run `5bc90798579b4a1f` |
| Adjacent economics / HUMAN regressions | **11 passed** | PR-5B: 2, PR-5C: 2, PR-6A: 3, PR-6C: 4; same combined run |
| Final affected Action Center rerun | **4 passed** | `e0477da39d6f480e`; after removing unnecessary all-inventory locks; these four are already included in the 19, not extra distinct tests |
| Phase 3 persisted API | **34 passed, 2 failed, 0 errors/skips** | The only failures are excluded synthetic-provenance test 17, once per installation |
| Phase 3 Chrome | **10 passed, 2 failed, 0 skipped** | The only failures are excluded resolved-filter QA-P3-04 on desktop/mobile |
| Phase 2 regression | **22 API and 8 browser passed** | Final sequential execution; both normal cleanup proofs and child exits PASS |
| Phase 1 smoke | **8 passed** | Retest output preserves original baseline; both normal cleanup proofs and child exits PASS |
| QA harness self-tests | **56 passed** | 28 Node + 28 Python; includes six new fail-closed closure tests |
| Existing Angular | **242 passed, 66 test files** | No Angular application component changed in Phase 3A |
| Production build | **PASS** | Current source rebuilt before each browser suite; existing 514.48 kB vs 500 kB initial budget warning |
| Angular lint / TypeScript | **PASS** | Two existing unrelated lifecycle warnings; no new lint errors; TypeScript no-emit passed |
| Focused strict mypy | **PASS: 11 source files** | Three changed production authorities, new regression test, seven QA Python modules |
| Ruff / Black / QA ESLint / Prettier / compileall | **PASS** | Project configuration retained; no rule, assertion or threshold suppressed |
| `git diff --check` | **PASS** | Existing LF/CRLF notices distinguished from whitespace errors |
| Final disposable cleanup | **PASS** | Marker-protected PostgreSQL databases absent; final browser child exits zero |
| Docker resource cleanup | **NOT APPLICABLE** | No Docker resources were created, deleted, stopped or used by this workstream |

Counts are per final execution, not accumulated retries. The earlier combined
47-case run (17 new + 30 existing) passed. After the final concurrency refinement,
the 17 new cases and four directly affected existing Action Center cases were
rerun successfully. Do not sum those reruns as additional distinct tests.

Final Phase 3 tokens: desktop `c679f23161944f0a`, mobile `843dd2863af31c62`.
Each retains API JSON, browser report, screenshots/trace references, sanitized
network evidence, fresh-process read-only database proof and cleanup JSON under
`tmp/qa-agent/<token>/`. The corrected restart completed in **21,001 ms** and
**19,729 ms**, with different real API PIDs and persisted stock/session assertions
passing. No production startup behavior was changed.

Final Phase 2: `6c513e21f44c66af`, `36deee4b3bc0c8e6`.
Final Phase 1: `ee70f72d32c4168c`, `29b53109b5f06066`.
The full machine summary is [phase-3a-report.json](phase-3a-report.json).

A final independent **read-only** PostgreSQL metadata audit checked the exact 18
database names created by this workstream (including failed/repeated attempts):
**zero remained**. The matching QA Python-process inventory was also zero. No
session termination or unrelated database/Docker cleanup was used by that audit.

The five authorized roots are RESOLVED in the evidence-gated ledger and removed
from the active backlog. The active backlog retains two reviewed defect roots,
four raw assertion-evidence records of those same failures (not four additional
bugs), three workflow gaps, six usability recommendations and one manual
accessibility task covering ten unresolved occurrences.

Final Phase 3 accessibility: **18 full-document axe scans, zero confirmed
violations, five incomplete rule/state occurrences**. Supplemental scrolling
examined all 107 original repeated-state targets: 101 passes and six incomplete
caption occurrences. Four separate financial-screen nodes remain incomplete.
They were not silently marked resolved.

## Regression coverage

`apps/api/tests/test_qa_phase3a_remediation.py` adds 17 PostgreSQL-backed cases:

- Known → UNKNOWN → known, historical/future applicability, unchanged delivery,
  repeated reads, mixed evidence, known zero, current snapshot cost lineage and
  Business Agent missing-evidence guidance.
- Canonical-order product-cost fallback cannot override explicit UNKNOWN.
- Sequential and concurrent identical/conflicting stock, financial-event and
  signal-transition replays, with persisted duplicate counts.
- Transition scope/note/expiry conflict, and replay after later resolution without
  reverting the current state.
- Stock recovery before a rescan, preserved evidence and SYSTEM history, repeated
  scans, recurrence, concurrent scan/replenishment, multi-line order/scan concurrency
  and stale-action rejection.
- Read-only persisted source revisions, HUMAN-only/default-deny and missing-resource
  checks through normal authenticated APIs.

The original `qa/phase3_api.py` is unchanged. The browser spec changes only the
QA-owned restart request timeout to 45 seconds plus an explanatory comment:
the supervisor already waits over 30 seconds, and a real probe measured a successful
18.9-second cold restart. No financial, state, PID, locator, authorization or
persistence assertion changed. Baseline and retested SHA256s are recorded by the
closure tool. Six Node closure tests fail closed for
missing targeted evidence, failed cleanup, failed/missing/duplicate assertions and
duplicate installation proofs. Closure also checks source hashes against the
targeted evidence ledger; a future source change invalidates the recorded closure.

## Retained failures, limitations and accessibility

- **P1 QA-P3-SOURCE-001:** fake-order financial fallback loses synthetic
  classification. Not repaired or downgraded in this bounded scope.
- **P2 QA-P3-UX-001:** selecting Resolved does not reload the authoritative signal
  dataset. Its unchanged desktop/mobile assertions remain enabled.
- **P2 QA-P3-GAP-001/002/003:** immutable operational calculation reconstruction,
  durable operational approval/execution lifecycle, and initial inventory UI handoff
  remain missing workflows, not fabricated passes.
- Six inherited usability recommendations remain open. Long economics-page
  comprehension/navigation is not redesigned here.
- Six original mobile caption occurrences plus four financial-screen nodes still
  require manual accessibility review. Passing axe scans do not resolve incomplete
  results or establish comprehensive WCAG compliance.
- ORM disposable fixtures are not full migration certification. Real providers,
  marketplace writes, supplier contact, worker/database outage recovery and complete
  assistive-technology coverage remain unexecuted.
- Historical startup deprecations, duplicate OpenAPI operation-ID warning, initial
  Angular bundle budget warning and two unrelated Angular lifecycle warnings are
  reported separately, not suppressed. Focused static checks are not a claim of a
  clean whole-repository typing/lint baseline.

## Earlier attempts retained

The first new regression attempt stopped at fixture setup: canonical product
creation correctly rejected a missing brand. The new fixture was corrected through
the supported brand API; production validation was not relaxed. The subsequent
17-case run passed at `tmp/qa-agent/7985934268cd46c0/manifest.json/` (the output
argument is a directory despite that early attempt's name).

The first Phase 3A full run used `3aedf529be333423` and `5792ffda28ff03ef`:
34 API passes / two excluded failures; eight browser passes / four failures.
In addition to the two excluded filter failures, both owned-API restart requests
hit the unchanged 12-second browser deadline. This is a recorded timeout, not
proof of a new application defect or an established resource-contention cause.
The mobile parent recorded a cleanup wait timeout. An independent exact-token
recovery check found its database already absent, no matching Python process,
and did not terminate any PostgreSQL session. Evidence is retained in
`tmp/qa-agent/5792ffda28ff03ef/recovery-cleanup.json`.

A sequential rerun (`d37c2127350b165e`, `f0a6a586429eb286`) reproduced the
restart request deadlines, but both normal teardown proofs passed with child exit
zero. The narrow fresh-installation probe `974f9e6a0ee5313a` then demonstrated
successful PID change in **18,871 ms**, beyond the browser's 12,000 ms request
deadline. Initial fixture creation/startup took 63,577 ms. Its restart, exact-token
cleanup and child exit all passed. This establishes a request-budget mismatch,
not failed application persistence or proof of a publishing-worker problem.

Reporting self-tests also caught inherited findings missing the Phase 2 context
fields, and then an attempted closure serialization with properties outside the
strict finding schema. The writer now normalizes inherited context and keeps
closure metadata in its separate ledger rather than adding undeclared finding
properties. The schema and assertions were not relaxed; the final 56 self-tests
passed after report regeneration.

## Changed files and architecture impact

Production changes are limited to:

- `apps/api/vayujit_api/commerce/financial_router.py`
- `apps/api/vayujit_api/commerce/inventory_router.py`
- `apps/api/vayujit_api/operations/action_center_router.py`

Test/report changes:

- `apps/api/tests/test_qa_phase3a_remediation.py`
- `qa/fixture_server.py` — allowlist the new regression module and capture tested
  source hashes before executing it.
- `qa/phase3a-resolution.mjs`, `qa/certify-phase3a.mjs`,
  `qa/unit/phase3a-resolution.test.mjs` — evidence-gated closure/reporting.
- `qa/phase3-report.mjs` — retain baseline findings while separating independently
  resolved roots from the active backlog.
- `qa/run.mjs`, `qa/probe-owned-runtime.mjs`, `qa/tests/phase3.spec.mjs` — narrow
  safe restart diagnostics and the measured QA-only request-budget correction.
- `qa/eslint.config.mjs` — declare the Node-provided `AbortSignal` global used by
  the bounded diagnostic probe; no lint rule disabled.
- This validation, resolution ledger and generated QA reports/coverage/backlog.

Existing unrelated worktree changes belong to the owner and were preserved.
No frontend business component, Docker configuration, backup script or `.env` was
changed in Phase 3A.

## Reproduce safely on Windows

Use the existing local PostgreSQL and installed dependencies. The QA runner does
not read the normal application `.env`. Set a current-shell admin URL for
`127.0.0.1`, database `postgres`, with permission to create disposable databases;
do not put credentials in reports or commits.

```powershell
$env:QA_DATABASE_ADMIN_URL = 'postgresql+psycopg://<qa-user>:<password>@127.0.0.1:5432/postgres'
$env:PYTHONPATH = 'apps/api;.'
$env:QA_PHASE = '3'
$env:QA_ORIGIN = 'http://127.0.0.1:4200'
$qaToken = [guid]::NewGuid().ToString('N').Substring(0,16)
& .\apps\api\.venv\Scripts\python.exe qa/fixture_server.py --port 0 --token $qaToken --output "tmp/qa-agent/$qaToken" --pytest test_qa_phase3a_remediation.py test_pr_sos_04_inventory_orders.py test_pr_sos_05_financials.py test_pr_sos_06_action_center.py test_pr5b_landed_cost.py test_pr5c_unit_economics.py test_pr6a_decision_readiness.py test_pr6c_decision_workflow.py

# Run sequentially; existing excluded failures keep Phase 3 exit code nonzero.
npm.cmd run qa:phase3
npm.cmd run qa:phase2
npm.cmd run qa:smoke -- --retest
npm.cmd run qa:unit
& .\apps\api\.venv\Scripts\python.exe -m unittest discover -s qa/unit -p 'test_*.py'
npm.cmd run test:web
npm.cmd run lint --workspace @vayujit/web
node node_modules/typescript/bin/tsc --noEmit -p apps/web/tsconfig.app.json

# After both original retests and targeted tests pass for the scoped roots:
node qa/certify-phase3a.mjs --token $qaToken
```

The closure command refuses failed/missing targeted cases, changed test contracts,
or unverified original-installation cleanup. It never changes application data.
Focused checks used:

```powershell
$qaSources = @('apps/api/vayujit_api/commerce/financial_router.py', 'apps/api/vayujit_api/commerce/inventory_router.py', 'apps/api/vayujit_api/operations/action_center_router.py', 'apps/api/tests/test_qa_phase3a_remediation.py')
& .\apps\api\.venv\Scripts\python.exe -m ruff check --config apps/api/pyproject.toml @qaSources qa
& .\apps\api\.venv\Scripts\python.exe -m black --check --config apps/api/pyproject.toml @qaSources qa
& .\apps\api\.venv\Scripts\python.exe -m mypy --config-file apps/api/pyproject.toml --follow-imports=silent @qaSources qa/fixture_server.py qa/phase3_api.py qa/operational_oracle.py qa/operational_probe.py qa/phase3_runtime.py qa/runtime_supervisor.py qa/cleanup_disposable.py
& .\apps\api\.venv\Scripts\python.exe -m compileall -q @qaSources qa
node node_modules/eslint/bin/eslint.js --config qa/eslint.config.mjs qa
node node_modules/prettier/bin/prettier.cjs --check qa
git diff --check
```

Do not run broad database-reset commands or stop unrelated Docker/backup processes.

## Recommendation

Next authorize a focused correction of the remaining provenance P1 and resolved
filter P2, followed by the unchanged Phase 3 tests. Separately review the ten
incomplete accessibility occurrences and plan the three missing workflows through
their canonical authorities. Do not treat this bounded remediation as release
certification, a new feature milestone, or authorization for real commerce.

No permanent/golden database was initialized or modified. No Docker resources,
backup certification services, real provider calls, commercial actions, branches,
commits or pushes were used.
