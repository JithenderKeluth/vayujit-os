# QA Agent Phase 3 — operational seller journey validation

25 October 2026. **QA PHASE 3 IMPLEMENTED / APPLICATION CERTIFICATION INCOMPLETE.**

Executable tests are delivered. Application defects remain open; no production
fix was authorized or performed in this phase. Passing old regressions does not
override the newly reproduced failures.

## Actual final results

| Gate | Actual result | Scope / qualification |
| --- | --- | --- |
| Phase 3 persisted API | **24 passed, 12 failed, 0 errors/skips** | 18 scenarios per fresh installation; six failures reproduced in both |
| Phase 3 Chrome | **10 passed, 2 failed, 0 skipped** | Six scenarios at 1440x1000 and 390x844; resolved status filter fails in both |
| Phase 2 regression | **22 API passed; 8 browser passed** | Existing financial lineage, supplier HUMAN replay, context and persistence assertions retained |
| Phase 1 smoke regression | **8 passed** | Separate retest output; original baseline unchanged |
| QA harness self-tests | **50 passed** | 22 Node and 28 Python; includes five new independent operational oracle tests and six new Node safety/schema/proxy checks |
| Existing Angular suite | **242 passed, 66 files** | Production Angular code was not changed |
| Existing operational backend regressions | **19 passed** | Eight inventory/order, seven financial, four Action Center tests, own disposable DB |
| Production Angular build | PASS | Actual source build before each browser run; existing 514.48 kB versus 500 kB initial-bundle warning remains |
| Angular lint | PASS with two existing warnings | Campaign catch-up/reschedule dialogs omit OnInit interface; no new Angular lint errors |
| TypeScript no-emit | PASS | Existing application configuration |
| Focused strict mypy | PASS | Seven new/extended QA Python runtime/oracle/cleanup modules; not whole-repository certification |
| Ruff / Black / QA ESLint / Prettier / compileall | PASS | Focused QA checks; no rules or quality thresholds disabled |
| git diff --check | PASS | Existing LF/CRLF conversion notices are not whitespace errors |
| Final disposable cleanup | PASS | Both Phase 3, Phase 1/2 and backend installations verified absent; final browser child exits 0 |

Counts describe final executions, not accumulated retries. The persisted and
browser scenario ledger, traces, screenshots and sanitized network records are
in [phase-3-report.json](phase-3-report.json) and
[phase-3-report.md](phase-3-report.md). That report remains **INCOMPLETE**.
Its execution timestamp is preserved separately from report/triage revision time.

Final Phase 3 tokens are `8257f720a79abebc` (desktop) and `d91eba766443fbe9`
(mobile). Each has `api-results.json`, `phase3-manifest.json`,
`fresh-process-proof.json`, `report.json`, `cleanup.json` and browser evidence
under `tmp/qa-agent/<token>/`. The backend JUnit/cleanup proof is under
`tmp/qa-agent/b3b9aaa47dc74e25/`; 19 passed with 39 existing startup/pytest warnings.
Duplicate OpenAPI operation-ID warnings are retained as historical API-tooling
debt, not hidden or declared production-safe solely because these tests pass.

Phase 2 regression tokens: `d78a23116696129c`, `6d99c1064a3156ce`.
Phase 1 regression tokens: `447fab78b4cff5e8`, `d28c590fb3ee5cd5`.

## Confirmed application defects

Seven root defects are reviewed. Repeated installation failures and their raw
assertion records are not seven additional bugs. Every structured record retains
expected/actual behavior, seller impact, reproduction, confidence, evidence,
proposed correction and retest status in
[phase-3-reviewed-findings.json](phase-3-reviewed-findings.json).

| Stable ID | Priority | Root cause / actual outcome |
| --- | --- | --- |
| QA-P3-FIN-001 | P1 | Cost selection filters UNKNOWN before latest-per-key selection. A newer UNKNOWN revision resurrects the old 200.01 cost and still qualifies contribution -103.04 with no missing inputs. |
| QA-P3-IDEM-001 | P1 | Stock movement replay checks item/key only; delta 99 under a key already used for delta 1 returns 200/original balance. It does not add 99 units, but silently acknowledges conflicting intent. |
| QA-P3-IDEM-002 | P1 | Financial ingestion and uniqueness recovery return an existing source event without semantic payload comparison. A conflicting sale amount 999999 returns 201/idempotent true with the old event. |
| QA-P3-IDEM-003 | P2 | A resolve request can reuse an acknowledge key and return 200/the old transition/ACKNOWLEDGED. Scope, target and intent are not compared. |
| QA-P3-SIGNAL-001 | P1 | Rescan does not retire no-longer-matching signals. After replenishment 0 -> 20, the old critical stock claim remains active/acknowledged with available 0 and confidence 0.90. |
| QA-P3-SOURCE-001 | P1 | Synthetic flag derives only from FinancialEvent, not fake-provider canonical orders. Fake-only fallback returns synthetic_provider false; the UI uses that flag for its evidence label. |
| QA-P3-UX-001 | P2 | Resolved status changes ngModel but does not reload the server dataset. A resolved card is absent despite persisted RESOLVED status and history. |

The six API defects are checked in tests 05, 07, 08, 13, 15 and 17. Browser
QA-P3-04 checks the filter. These failures remain executable and are not xfailed,
skipped, removed or relaxed. No automatic application remediation was made.

## Supported positive workflows demonstrated

- Canonical stock creation and versioned adjustment; unchanged replay has no
  duplicate movement; insufficient/negative stock and stale form are rejected.
- Reserve, release and consume with duplicate replay and invalid-transition
  protection. Four concurrent duplicate order deliveries produce the same order.
- Competing orders for a final unit yield one success and one conflict; unmapped
  multiline input does not leave partial reservations.
- Cancel releases reservations; shipment consumes stock; returned units are not
  silently restocked. A return does not fabricate monetary refund evidence.
- Independent Decimal event rounding, explicit fees/shipping/refunds, negative
  contribution alert, missing settlement amounts, mismatch and matched revisions.
- A later refund updates the supported **current** calculation projection;
  event lineage and reconciliation revisions persist. This is not immutable
  historical-calculation reconstruction.
- Authenticated owner scope, anonymous 401, unknown resource 404, AI impersonation
  rejection, default-denied external action request and read-only Business Agent.
- Four concurrent identical signal acknowledgements return one transition.
  Acknowledgement is not a commercial HUMAN approval.
- Browser/API/independent PostgreSQL parity for persisted monetary event amounts
  and stock balances. A separate read-only process verifies one owner and no
  negative/conservation-invalid inventory balances.
- Network timeout/error retry, loss of an HTTP reply **after real local commit**,
  exact-key recovery without duplicate adjustment, new-tab reload and persisted
  session/balances after restarting the exact owned API process with a new PID.

Evidence does not establish that every seller workflow is complete. Source
creation is sometimes API-driven; the UI is tested for the features it actually
offers, not an invented order-entry, payout or operational approval screen.

## Mobile accessibility investigation

Final Phase 3 has **18 full-document axe scans, zero recorded violations, five
incomplete rule/state occurrences**: the four original table states plus one
new financial-loss state (four nodes). No rule or threshold was disabled.

All four original states now wait for populated evidence. The HUMAN state is
scanned after explicit KEEP_UNDER_REVIEW and reload using the normal journey
authority, not a fabricated approval. Real horizontal/vertical scrolling brings
the original incomplete targets into view before supplemental axe contrast tests.

| Original mobile state | Examined repeated-state targets | Axe passes after scrolling | Remaining incomplete |
| --- | --- | --- | --- |
| Due diligence | 6 | 5 | 1 caption |
| Economics | 37 | 35 | 2 captions |
| Stale economics | 27 | 26 | 1 caption |
| Saved HUMAN decision | 37 | 35 | 2 captions |
| Total occurrences, not unique elements | 107 | 101 | 6 |

No contrast violation was confirmed in those targeted checks. Six caption
occurrences remain incomplete/partially obscured and **open for manual review**.
Exact selectors, bounds, engine results and screenshots are retained in
[phase-3-mobile-contrast-review.json](phase-3-mobile-contrast-review.json).
The new financial-loss table's four incomplete nodes are also open. The stable
manual-review finding is QA-P3-A11Y-REVIEW-001 (P2, SUSPECTED, not a proven WCAG
failure). Do not claim complete WCAG or assistive-technology conformance.

Keyboard checks exercise Enter stock submission, focusable scroll regions,
ArrowRight and Tab escape. Phase 1/2 retain setup validation, Shift+Tab, Space,
cancel, protected deep links and logout. Exhaustive modal focus traps and actual
screen-reader use remain unexecuted.

## Missing flows / boundaries, not fabricated successes

1. **QA-P3-GAP-001:** Financial calculation API is a mutable current projection
   per scope/version. It does not expose retained calculation versions with all
   contributing cost identities. Source events persist, but exact historical
   calculation reconstruction is not supported. Final test 09 validates the
   real mutable contract; this gap is not mislabeled a broken immutable API.
2. **QA-P3-GAP-002:** Action Center has signal transitions and advisory action
   responses, not durable operational approve/reject/execute/retry records.
   External actions correctly default-deny. Reuse canonical approval authorities
   if this product capability is later authorized; do not duplicate them.
3. **QA-P3-GAP-003:** Canonical inventory creation is available in the API but the
   inventory empty-state workspace offers no demonstrated creation/handoff.
   Product master inventory fields are not proven equivalent to the stock ledger.
4. Publishing-worker restart, physical database-server outage, full migration
   chain, bank reconciliation, real-provider ingestion, refund dispatch and live
   marketplace execution are NOT EXECUTED. They were not simulated as successful.
5. No real fee schedule, GST treatment or net-profit accounting is inferred.
   The oracle tests the documented evidence-level modeled contribution contract,
   not an invented per-unit COGS or tax formula.
6. Single-owner authentication and foreign/missing-resource rejection were
   exercised. No shared-database multi-owner model or bypass was introduced;
   complete cross-installation foreign-resource security remains broader work.

The six original P2/P3 usability recommendation occurrences remain open and
unchanged. Economics-page length, currency defaults, dual-active navigation and
pre-run mode clarity were not silently closed or redesigned in this phase.

## QA-only corrective work and imperfect intermediate runs

The first run exposed new-test issues: short idempotency keys yielded 422,
an absent refund was incorrectly expected to be zero, and exact label dropdown
locators were unsuitable. Corrections use valid keys, keep UNKNOWN unknown, and
use actual accessible combobox names. Later financial filtering checks explicitly
clear the January sales date filter before inspecting October settlement records.

Source inspection confirmed calculations are current projections. An initial
immutable-version expectation was unsupported; its failure is retained in earlier
evidence, while the final scenario tests the real contract and records a product
gap. Application assertions were not deleted to hide a confirmed defect.

The new restart scenario exposed an actual **QA proxy** bug: upstream disconnect
could attempt to write headers twice. The proxy now handles request/reply aborts
without writing headers again. A deterministic local-only regression proves it
survives a partial response and continues serving. This is infrastructure repair,
not a production application fix.

An intermediate shutdown exceeded the runner's existing timeout; another run
crashed before its finally cleanup completed. Neither was marked PASS. Recovery
checks retained original failure evidence, verified exact tokens and no owned
Python processes, and checked databases independently. The first database was
already absent by recovery time. The second was marker-verified, had zero active
sessions and was dropped without terminating sessions. Recovery proofs are
`tmp/qa-agent/c1cd0957876c8469/recovery-cleanup.json` and
`tmp/qa-agent/67823329070c3425/recovery-cleanup.json`. Final runs close normally
with child exit 0 and database absence. No timeout, marker or cleanup gate was
weakened. Intermediate results are not mixed into final pass counts.

## Changed-file / architecture impact

No production Python/Angular source, schema, migrations or ownership authority
was changed in this phase. No dependency was added. Existing unrelated worktree
changes were preserved.

- `package.json`: `qa:phase3` command.
- `qa/run.mjs`, `playwright.config.mjs`, `fixture_server.py`, `safety.mjs`,
  `server.mjs`: isolated Phase 3 orchestration, explicit local allowlist, sandbox/
  no-credential setup guard, authenticated owned-process restart and safe proxy.
- New `qa/phase3_api.py`, `tests/phase3.spec.mjs`: executable persisted operations,
  financial, security, recovery, seller and accessibility cases.
- New `qa/operational_oracle.py`, `operational_probe.py`, `phase3_runtime.py`,
  `runtime_supervisor.py`, `cleanup_disposable.py`: independent financial
  assertions, read-only reconstruction, dedicated runtime and exact cleanup.
- New `qa/unit/test_operational_oracle.py`, `unit/phase3.test.mjs`: independent
  examples, default-deny, certification, schemas, credentials/restart and proxy
  disconnection regressions.
- `qa/phase3-report.mjs` (new), `archive-reports.mjs`, `eslint.config.mjs`,
  `README.md`: structured reporting/preservation, error cause, legitimate browser
  globals and usage. No lint rule was disabled.
- `docs/qa/phase-3-{architecture,validation}.md`, reviewed findings, JSON/Markdown
  report, mobile review, coverage, backlog and existing architecture links.

The architecture remains one seller per installation/database, with existing
HUMAN authorities and `ck_users_single_owner`. No backup script, Docker project
or permanent/golden database was changed. No live credentials/provider calls,
marketplace writes, supplier contact, payments, RFQs, commits, pushes or branches.

## Exact Windows commands

Use an approved local PostgreSQL test administrator; no `.env` edit is required.
Commands are run from the repository root. Do not point them at a business DB.

```powershell
$env:QA_DATABASE_ADMIN_URL = 'postgresql+psycopg://<test-admin>:<password>@127.0.0.1:5432/postgres'
npm.cmd run qa:phase3
# Exit 1 is expected while the documented application defects remain open.
npm.cmd run qa:phase2
npm.cmd run qa:smoke -- --retest
npm.cmd run qa:unit
$env:PYTHONPATH = 'apps/api;.'
apps/api/.venv/Scripts/python.exe -m unittest discover -s qa/unit -p 'test_*.py'
npm.cmd run test:web
npm.cmd run lint --workspace @vayujit/web
node node_modules/typescript/bin/tsc -p apps/web/tsconfig.app.json --noEmit
node node_modules/eslint/bin/eslint.js --config qa/eslint.config.mjs qa
node node_modules/prettier/bin/prettier.cjs --check qa
apps/api/.venv/Scripts/python.exe -m ruff check --config apps/api/pyproject.toml qa
apps/api/.venv/Scripts/python.exe -m black --check --config apps/api/pyproject.toml qa
$env:MYPYPATH = 'apps/api'
apps/api/.venv/Scripts/python.exe -m mypy --config-file apps/api/pyproject.toml --follow-imports=silent qa/phase3_api.py qa/operational_oracle.py qa/operational_probe.py qa/fixture_server.py qa/phase3_runtime.py qa/runtime_supervisor.py qa/cleanup_disposable.py
apps/api/.venv/Scripts/python.exe -m compileall -q qa
git diff --check

# Existing backend regression matrix in its own fresh guarded database:
$env:QA_PHASE = '3'
$env:QA_ORIGIN = 'http://127.0.0.1:4200'
$qaOperationalToken = [guid]::NewGuid().ToString('N').Substring(0,16)
apps/api/.venv/Scripts/python.exe qa/fixture_server.py --port 0 --token $qaOperationalToken --output "tmp/qa-agent/$qaOperationalToken" --pytest test_pr_sos_04_inventory_orders.py test_pr_sos_05_financials.py test_pr_sos_06_action_center.py
```

Do not run two browser suites/builds concurrently against the shared dist
directory. Evidence contains synthetic sessions and traces and should remain
local, not be automatically committed or uploaded.

## Recommended remediation and Phase 4

First authorize bounded remediation of the five P1 roots: UNKNOWN cost version
selection, financial/stock semantic replay, obsolete operational signals and
synthetic provenance. Then address signal transition conflicts and resolved
filter behavior. Rerun these exact failing scenarios and broader adjacent tests;
do not close a finding merely because a proposed fix exists.

Phase 4 should add migration-backed disposable fixtures, multi-product and
multi-quantity financial attribution, return/fee/settlement reconciliation
lineage, controlled worker recovery in a separate empty-queue fixture, complete
foreign-resource/stale-approval matrices, and first-seller task-completion plus
manual caption/screen-reader testing. Define missing approval/history/stock
onboarding product flows before writing tests that assume those features exist.

**Final decision: Phase 3 executable QA is implemented. Application certification
is INCOMPLETE; release-blocking P1 defects and documented coverage gaps remain.**

## Subsequent authorized Phase 3A remediation

The figures above are the preserved Phase 3 baseline, not current failure counts.
See [Phase 3A validation](phase-3a-validation.md) and
[resolution ledger](phase-3a-resolution.json) for the bounded authorized fixes.
Five explicitly named roots (four P1 and one P2) are independently resolved.
Current Phase 3 execution is **34 API passed / two excluded failures** and
**10 browser passed / two excluded failures**. The synthetic-provenance P1 and
resolved-filter P2 remain open, together with all documented gaps, usability
recommendations and incomplete accessibility review. Certification remains
**INCOMPLETE**; the original reviewed source and baseline report hashes are retained.

## Subsequent authorized Phase 3B remediation

The Phase 3A figures immediately above are historical. The two remaining
correctness roots and the duplicate-current-navigation recommendation are now
independently resolved. Final Phase 3: **36 API passed / 0 failed** and
**18 desktop/mobile browser passed / 0 failed**, with normal marker-verified
cleanup and child exit 0 for both installations. Final targeted backend run:
**37 passed** (17 Phase 3A, 16 Phase 3B, 4 Action Center). Angular: **249 passed**.

See [Phase 3B validation](phase-3b-validation.md), [resolution ledger](phase-3b-resolution.json)
and [structured assessment](phase-3b-assessment.json). Original assertions and
historical evidence are retained. Six mobile captions and four historical financial
nodes remain unclosed accessibility review, five usability occurrences remain
proposals, and all three workflow gaps remain open. Initial canonical stock UI
handoff is classified launch-critical. **Application certification remains INCOMPLETE.**
