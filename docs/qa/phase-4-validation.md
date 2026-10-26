# QA Phase 4 — whole-application exploration and launch-gap assessment

26 October 2026. **QA Phase 4 executable exploration implemented; application
certification INCOMPLETE.** No production feature or remediation was implemented.
Earlier evidence is historical and preserved; a larger test count is not wider
functional certification.

## Read-first audit and implementation

Reviewed the current QA architecture, Phase 3B validation/report/resolution,
source/runtime coverage and active finding backlog. Reused existing Chrome
Playwright, axe-core, canonical fixture APIs, PostgreSQL markers, loopback proxy,
egress restrictions, single-owner model and report schema. No new dependencies.

Implemented:

- `qa/explore.mjs`: reusable observation, isolated browser telemetry, full-document
  axe and exact-node scrolling/focus/viewport evidence. It does not blindly click.
- `qa/phase4-surface.mjs`: route/context planning, DOM controls/forms/tables/dialogs,
  states, hidden-control visibility, stable fingerprints and a bounded action
  registry. UUID normalization makes finding IDs stable between disposable runs.
- `qa/tests/phase4.spec.mjs`: 18 source-derived route-area scenarios plus four
  explicit seller tasks, each executed on desktop and mobile.
- `qa/phase4-report.mjs`: route/control and 12-journey matrices, findings/backlog,
  accessibility subsets, actual counts and strict cleanup classification.
- Existing runner/config/proxy extend Phase 4 without replacing earlier suites.
  `audit({write:false})` and `--preserve-inventory` avoid resetting prior coverage.
  Focused reruns save separately and cannot replace the full exploratory result.
- Six new Node self-tests cover unavailable IDs, honest visit classification,
  stable IDs, action denial, forbidden execution and exact expected-case/cleanup
  gates. No production authority was duplicated or loosened.

## Actual execution

| Suite/check | Passed | Failed | Skipped / blocked | Evidence |
| --- | ---: | ---: | --- | --- |
| Phase 4 desktop browser | 19 | 3 | 0 skipped; 0 installation blockers | `87ebb85b0dc2c37b` |
| Phase 4 mobile browser | 17 | 5 | 0 skipped; 0 installation blockers | `2190f143d27bba01` |
| Existing Phase 3 persisted API scenarios used in Phase 4 | 36 | 0 | 0 errors/skipped | 18 per installation, unchanged assertions |
| Phase 2 persisted API / browser rerun | 22 / 8 | 0 / 0 | 0 | `4448c2b059717af9`, `a3d1fc976977e3d7` |
| Phase 1 fresh-owner smoke rerun | 8 | 0 | 0 | `228dd1d866aa62f7`, `e848e6c7ec35fb39` |
| Angular | 249 | 0 | 0; 68 files | Actual `npm.cmd run test:web` execution |
| Node QA self-tests | 38 | 0 | 0 | Includes six Phase 4 tests |
| Python QA self-tests | 28 | 0 | 0 | `pytest qa/unit`, 4.94s |
| Production Angular build | PASS | — | Existing warning | 514.66kB initial versus 500kB warning budget; unchanged production bundle |
| Focused Python quality | PASS | — | Not repository-wide certification | Ruff; Black 17 files unchanged; mypy six files with documented `MYPYPATH=apps/api`; compileall |

The initial focused mypy invocation omitted `MYPYPATH` and resolved the installed
untyped API package, yielding ten import/decorator errors. The documented source
path fixed resolution; no check, threshold, type or production code was weakened.
The 37/63 standalone backend runs from Phase 3B remain **prior evidence**, not
new Phase 4 executions. No migration-chain, live-provider or worker/backup
certification is claimed.

The full exploratory runner correctly exited **1** because eight area scenarios
failed. All four explicit seller tasks passed in both viewports. A passing
accessibility-investigation scenario means evidence was collected, not that every
node passed or that the application is WCAG-conformant.

## Dynamic surface and coverage boundaries

- **154 declarations**: 148 page declarations and six redirects.
- **120 declarations** have actual DOM/screenshot inventories in each project
  (240 default visits); two filtered-empty inventories are additional states.
- **26 parameterized declarations** lack legitimate persisted contexts and remain
  `REQUIRES_UNAVAILABLE_CANONICAL_CONTEXT`, rather than guessed-ID 404 visits.
- Login is exercised by explicit task; setup/owner onboarding is rerun by Phase 1.
  These two guest declarations have no Phase 4 route-crawler control snapshot.
- **30,597 control occurrences**, **24,004 fingerprints**, **17,650 visible
  occurrences**, 124 form occurrences and zero open dialog occurrences. Repeated
  navigation, responsive hidden duplicates and different fixture identifiers are
  included. These are not counts of distinct features or successfully used actions.
- Eight recorded action-outcome groups summarize asserted catalog save/cancel and
  inventory filter/cancel/recovery. They are **not a complete click count** or
  proof every discovered control was exercised. Browser history/auth and keyboard
  interactions are separately asserted. The catalog task's original title mentions
  duplicate submission, but it proves one save request, not a double-click race;
  true UI duplicate-click coverage remains missing. Existing API duplicate/concurrent
  delivery assertions are separate and do not substitute for that UI case.
- Tabs/buttons, unopened dialogs, image/variant editors and conditional paths are
  inventoried only when present in observed DOM. Zero open dialogs does not prove
  the application has none. Comprehensive dialog/trap/Escape/restoration coverage
  remains unexecuted. Required HTML/ARIA attributes are not the complete financial
  or server validation contract.
- 2,193 browser-observed API response occurrences are correlated with actual
  screen paths; per-installation runtime OpenAPI is separate. **1,026 unmatched
  static API declarations are conservative review candidates**, not 1,026 missing
  frontend features. Component-direct calls, providers, workers and internal
  authorities can legitimately lack service-name matches.

See [route/control matrix](phase-4-coverage.md), [full dynamic inventory](phase-4-surface-inventory.json),
[12-journey assessment](phase-4-journeys.json) and [architecture](phase-4-architecture.md).
No claim of exhaustive application discovery or complete journey execution.

## Eight failed area scenarios and triage

| Area | Viewports failed | Evidence-backed cause |
| --- | --- | --- |
| AI | Desktop/mobile | AI History date inputs/status selects lack accessible names; Video progress div uses prohibited ARIA semantics; additional moderate landmark/header findings |
| Intelligence | Desktop/mobile | Serious low-contrast source-empty/status text and keyboard-inaccessible overflow regions; moderate nested mains across multiple workspaces; three context initialization POSTs blocked by the QA allowlist |
| Marketplaces | Desktop/mobile | Invalid dt/dd structure on Marketplace Video; mobile Meesho overflow focus issue; one mobile proxy HTTP 502 for account list remains suspected transport/runtime issue |
| Ads | Mobile | Five overflow panels cannot receive keyboard focus |
| Social | Mobile | Overflow regions on Social overview/settings cannot receive keyboard focus |

Exact selectors and rule IDs are in [accessibility evidence](phase-4-accessibility.json).
The 250 full-document scans produce 194 rule/state violation occurrences, grouped
into **102 stable route/rule buckets** (21 P1, 81 P2). These are not 102 independent
source-code root causes; shared shells and aliases repeat the same structural
defect. Eight assertion records overlap these findings and remain suspected,
not eight extra confirmed bugs. One separate API 502 record is suspected P2.

The three denied initialization POSTs are `/intelligence/trends/contexts`,
`/intelligence/reviews/contexts`, `/intelligence/competitors/contexts`. Source
`ensureJourneyContext()` creates a local context on opening the page when the
selected product has none. No explorer click caused them. Guards prevented their
forwarding; this is **blocked context-creation coverage / allowlist limitation**,
not proof that canonical context creation is a production security defect. A
future explicit context scenario must review the canonical API and payload first;
do not broadly permit arbitrary initialization writes to obtain green tests.

No unexpected backend HTTP 500 was established. The one HTTP 502 is produced by
the QA proxy's upstream request-error path; the exact upstream reset cause is not
established. Its focused replay is documented separately below, without deleting
the original failed evidence or equating nonreproduction with resolution.

## Accessibility completion: original six plus four

32 exact-node reviews include repeated desktop/original/wide and mobile/wide
states: **26 contrast passes, six incomplete, zero confirmed targeted contrast
violations**. Full-document findings remain separate; no difficult nodes/rules
were removed. Screenshot and text rectangles were inspected.

| Historical subset | Current result | Disposition |
| --- | --- | --- |
| Four financial headers: Settlement, QA3-MISMATCH, QA3-UNKNOWN, QA3-SETTLEMENT | Each passes focused axe contrast after scrolling and has text fully in view on both desktop/mobile | **VERIFIED subset** (eight node executions); not a claim about every financial table/caption |
| Six DD/economics caption occurrences | Desktop and expanded 1440px pass; original 390px text extends beyond visible width, still axe-incomplete | **OPEN responsive clipping defect** `QA-P4-A11Y-CAPTION-CLIPPING` P2, not a fabricated contrast ratio |

Example mobile landed-cost caption extends to x=454.64 at a 390px viewport after
actual left-edge scrolling. The selling-cost caption extends to x=403.53. This is
visible clipping, not fixed by reporting wider-viewport success. Required bounded
fix: wrap/constrain caption independently of wide table columns while preserving
semantic captions, keyboard overflow, unknown values and all evidence columns.

Exact evidence:

- `tmp/qa-agent/2190f143d27bba01/evidence/mobile-QA-P4-TASK-04/7-node-review-economics-0-original.json`
- `tmp/qa-agent/2190f143d27bba01/evidence/mobile-QA-P4-TASK-04/6-node-screen-economics-0-original.png`
- `tmp/qa-agent/2190f143d27bba01/evidence/mobile-QA-P4-TASK-04/30-node-review-financial-0.json`
- `tmp/qa-agent/2190f143d27bba01/evidence/mobile-QA-P4-TASK-04/29-node-screen-financial-0.png`

Original `QA-P3-A11Y-REVIEW-001` remains open as an aggregate historical task. The
financial subset is separately verified; captions now have a concrete clipping
ticket. No silent historical edit/closure and no WCAG conformance claim.

## Usability, missing workflows and launch blockers

[Initial stock-entry assessment](phase-4-stock-entry-assessment.md) traces actual
schema/authorization/persistence and contains the minimal proposal, fields, states,
security/financial implications, acceptance criteria and regression plan. A Product
already exists, but there is no UI handoff to canonical opening stock. Product-master
Quantity is a different authority. Supplier/cost/account are not prerequisites in
the existing stock API; no fictional prerequisites were introduced.

Prior five open usability occurrences remain proposals: currency desktop/mobile,
economics hierarchy desktop/mobile, and pre-run mode guidance. The navigation
recommendation already resolved by Phase 3B is not reopened. Actual current
economics heights are 16,260px desktop / 43,325px mobile, reinforcing rather than
silently closing the prior friction assessment.

New recommendations: filtered-empty inventory wording (small); whole-page desktop
overflow on Video (1664px/1440px) and Autonomous research (1469px/1440px), small to
medium; long External/Websites research pages (up to 19,327px/14,416px mobile),
medium hierarchy proposal. These are distinguished from confirmed calculation or
security defects. Source/route/rule recommendations include practical complexity.

**Release blockers:** initial stock-entry handoff; critical/serious accessible
names, contrast/keyboard/semantics findings on supported screens; incomplete
responsive/assistive verification and untested artifact contexts. The three prior
workflow gaps retain their Phase 3B classifications: stock handoff launch-critical;
historical operational reconstruction and generic advisory approval lifecycle
important but conditionally deferrable. No new generic approval authority proposed.

## Recommended bounded remediation (requires separate authorization)

1. Small AI History label associations and correct Video/Marketplace Video
   semantics; exact failing rule tests plus desktop/mobile retest.
2. Shared shell landmark structure and keyboard overflow regions, grouped by
   actual component rather than treating every alias as a separate redesign.
3. Source-workspace contrast and six caption responsive clipping; preserve source
   claims, unknowns and HUMAN boundaries. Retest all exact nodes and full scans.
4. Approve the isolated opening-stock workflow proposal, then implement through
   existing inventory authority with replay/concurrency/security/UI acceptance.
5. Separately approve currency/economics/research hierarchy improvements. Add real
   persisted artifact/dialog/variant/media fixtures and explicit UI duplicate-click
   cases; migration-driven fixture certification remains separate.

No bounded remediation or missing workflow was automatically implemented here.

## Windows commands

From repository root, with existing dependencies, local Chrome and local PostgreSQL.
No production `.env` change. Use a dedicated local QA role; never point this URL at
a business/golden database. Suites/builds sharing dist must run sequentially.

```powershell
$env:QA_DATABASE_ADMIN_URL = 'postgresql+psycopg://LOCAL_QA_USER:URL_ENCODED_PASSWORD@127.0.0.1:5432/postgres'
npm.cmd run qa:phase4
# Nonzero exit is expected while confirmed serious/critical findings remain.
# Risk-focused replay saves phase-4-focused-report.json; full report is preserved:
npm.cmd run qa:phase4 -- --focus QA-P4-SURFACE-MARKETPLACES
npm.cmd run qa:phase2 -- --preserve-inventory
npm.cmd run qa:smoke -- --retest --preserve-inventory
npm.cmd run qa:unit
npm.cmd run test:web
& .\apps\api\.venv\Scripts\python.exe -m pytest qa/unit -q -o addopts=
node node_modules/eslint/bin/eslint.js --config qa/eslint.config.mjs qa
node node_modules/prettier/bin/prettier.cjs --check qa
& .\apps\api\.venv\Scripts\python.exe -m ruff check --config apps/api/pyproject.toml qa
& .\apps\api\.venv\Scripts\python.exe -m black --check --config apps/api/pyproject.toml qa
$env:MYPYPATH = 'apps/api'
& .\apps\api\.venv\Scripts\python.exe -m mypy --config-file apps/api/pyproject.toml --follow-imports=silent qa/fixture_server.py qa/phase3_api.py qa/phase2_api.py qa/phase3_runtime.py qa/runtime_supervisor.py qa/cleanup_disposable.py
& .\apps\api\.venv\Scripts\python.exe -m compileall -q qa
git diff --check
Remove-Item Env:QA_DATABASE_ADMIN_URL
```

Traces exist for failed area scenarios in each local report's evidence references.
View locally with `node node_modules/@playwright/test/cli.js show-trace <trace.zip>`.
They contain synthetic session data; do not commit/upload automatically.

## Deliverables, changes and safety

[Executed report](phase-4-report.md) / [JSON](phase-4-report.json),
[dynamic inventory](phase-4-surface-inventory.json), [coverage](phase-4-coverage.md),
[journeys](phase-4-journeys.json), [accessibility](phase-4-accessibility.json),
[stock assessment](phase-4-stock-entry-assessment.md), [current backlog](defect-backlog.json),
[preserved pre-Phase-4 backlog](phase-4-prior-backlog.json).

Task changes are QA-only modules/tests/config/reporting, `package.json` script and
QA docs/generated evidence. No application production source, DB migration,
dependency/lockfile or approval system was changed. Earlier source/report hashes
are verified separately. Existing unrelated working-tree changes are preserved.

Both full-run databases and all earlier-suite rerun databases report normal
marker-verified cleanup, absent DB and child exit 0. Focused replay/independent
cleanup and final quality results are recorded in the closing note below.

No permanent/golden DB changes, real marketplace/provider calls, supplier contact,
publishing, external commercial writes, Docker resource operations, backup/restore
interference, branches, commits or pushes.

## Closing evidence and final decision

Focused marketplace replay: desktop `9294643e82e07cab`, mobile
`8bda54bfa5c92199`; **0 browser passed / 2 failed** because the original serious
accessibility assertions still fail, plus **36 existing API assertions passed**.
All eight account-list reads returned 200, no unexpected 5xx occurred, and the
single earlier 502 did not reproduce. It remains suspected/open, not resolved.
See [separate focused report](phase-4-focused-report.json). Both databases cleaned
up normally with verified markers and child exit 0; the full report was preserved.

The current backlog has **125 schema-valid records**: nine preserved prior records,
102 confirmed axe route/rule buckets, one confirmed responsive-caption clipping
finding, nine suspected records (eight overlapping failed-area assertions plus
the API 502), and four new usability recommendations. Shared aliases are not
independent code roots. No old finding was silently closed.

The complete [seller task review](phase-4-seller-review.md) explains discoverability,
next steps/inputs, financial trust, persistence/correction, completion and supported
versus missing boundaries for all twelve journeys. Remaining source/context/dialog
gaps and actual block counts are in the machine-readable report, not inferred PASS.

Final JavaScript QA ESLint/Prettier pass; Angular lint has **0 errors and two existing
OnInit warnings**; TypeScript no-emit passes. `git diff --check` passed (existing
LF/CRLF normalization warnings only). Independent read-only metadata checked all
eight exact task-owned databases: **zero remain**; no QA fixture/runtime Python
process remained. Prior production-source/original-test hashes still verify. No
repository-wide unrelated lint/type-debt clearance is implied. Full and focused
failed runs keep their nonzero exits and original traces.

Final classification: **QA PHASE 4 — EXECUTABLE EXPLORATION IMPLEMENTED /
APPLICATION CERTIFICATION INCOMPLETE**. Request separate authorization for the
bounded remediation groups above. Do not begin a broad redesign or assume live
operational readiness from these local synthetic results.

<!-- PHASE4A -->
## Phase 4A independent remediation follow-up

2026-10-26T03:59:12.493Z. **ACCESSIBILITY_REMEDIATION_VALIDATED_BOUNDED_SCOPE**; application **INCOMPLETE**. Original Phase 4: 44 passed / 0 failed. Focused accessibility: 6 passed / 0 failed. 115 stable finding records independently resolved; 14 remain open, including the launch-critical initial-stock gap and retained manual-review requirements. No original browser assertions or axe thresholds weakened. Counts above this section remain historical execution evidence, not the current resolution ledger.

[Full validation and Windows commands](phase-4a-validation.md), [per-finding resolution](phase-4a-resolution.md), [exact accessibility evidence](phase-4a-accessibility.json), [current backlog](defect-backlog.json). No stock workflow implemented; no whole-application or WCAG PASS.
