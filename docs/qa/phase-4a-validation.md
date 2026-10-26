# QA Phase 4A — bounded accessibility remediation and independent retesting

Application certification remains **INCOMPLETE**. This work does not implement initial-stock entry, certify live providers, certify every reachable control, or establish complete WCAG 2.2 AA conformance.

Final bounded classification: **ACCESSIBILITY_REMEDIATION_VALIDATED_BOUNDED_SCOPE**. Independent closure resolved **115 stable finding records**: 105 route/rule buckets (102 original + 3 retest discoveries), the clipping record, the exact historical target-review record, and eight overlapping failed-scenario records. These are **not 115 independent code defects**. All eight original failing scenarios now pass. **14 records remain open**: nine usability recommendations, three workflow gaps, one historical intermittent API suspect, and one explicit manual-accessibility follow-up. The launch-critical initial-stock gap remains unimplemented.

## Evidence and scope

The immutable [pre-fix baseline](phase-4a-baseline.json) retains all 125 existing records, the eight failed scenario occurrences, original screenshots/traces, and 34 source hashes. [Original full report](phase-4a-baseline-report.json) is retained byte-for-byte with its SHA-256. The original `qa/tests/phase4.spec.mjs` and `qa/explore.mjs` are unchanged. Prior runs are archived under `docs/qa/history`; raw browser evidence stays under ignored `tmp/qa-agent`, not promoted to business data.

Eight failed scenarios were overlapping area/view-state failures, not eight independent bugs. The [resolution ledger](phase-4a-resolution.md) maps each exact desktop/mobile scenario to stable IDs; its [JSON counterpart](phase-4a-resolution.json) includes original errors, element targets, roots, changed source, correction, before/after evidence and per-ID retest decisions. Three additional populated-state defects found during retesting are retained separately in [additional findings](phase-4a-additional-findings.json), not silently discarded.

## Production corrections

- Retain the sole application-shell `main`; routed pages use named sections. The generation summary is a named section, not a nested complementary landmark. Heading content and CSS classes remain intact.
- AI history has explicitly associated visible status/date labels, grouped with their fields, a meaningful Actions column header and announced load errors. Filtering and date/query semantics are unchanged.
- Video progress is a named progressbar with the actual bounded step and total; no invented completion or provider execution.
- Discovery empty states reuse darker existing-theme text. Website small state text inherits its appropriate state foreground instead of a lower-contrast unrelated muted color.
- Overflow containers have accurate, distinct region names, keyboard focus and visible theme-consistent focus indicators. Tables, columns, evidence and actions are retained.
- Marketplace Video terms/values use valid `dl` structure. Publishing history has a meaningful Actions header.
- Economics captions wrap within their actual inline-size container instead of taking the intrinsic width of wide tables. Due-diligence caption sizing and table focus are similarly bounded. Horizontal access to all data remains available.
- Populated Trend context list uses its own heading ID; product detail has a distinct workspace region name. External-research badge collections use named group semantics.

No backend domain, monetary calculation, data migration, approval authority, ownership model, or provider policy was changed. Component tests formerly requiring an embedded `main` now require a named section **and no nested main**; their other behavior assertions are retained. The original browser assertions and axe rules/thresholds are unchanged.

### Changed-file scope

The JSON resolution report lists the exact **32 changed production paths in its pre-fix hash set**, plus `apps/web/src/app/ai/ai.css` (the small filter-field layout addition). Most files change only the routed root tag or scroll-region semantics. There are no production backend changes.

Component regression files: AI history (new), AI Video, Alibaba, IndiaMART, TradeIndia, Global Sources, Autonomous Research, Competitor Intelligence, External Research, Intelligence, Supplier Shortlisting, Website Intelligence, Trend Intelligence and Product Opportunities.

QA implementation: `qa/tests/phase4a.spec.mjs`, `qa/unit/phase4a.test.mjs`, `qa/unit/phase4a-resolution.test.mjs`, `qa/capture-phase4a-baseline.mjs`, `qa/phase4a-resolution.mjs`, `qa/certify-phase4a.mjs`; bounded extensions to `qa/run.mjs`, `qa/playwright.config.mjs`, `qa/safety.mjs`, `qa/server.mjs`, `qa/phase4-report.mjs`, `qa/archive-reports.mjs`; and the `qa:phase4a` package script. Existing dependencies are reused, with no new package or lockfile dependency requirement. Documentation includes this validation, immutable baseline/history, resolution/extra-finding ledgers, current coverage, accessibility evidence and backlog. Unrelated working-tree changes are preserved.

## Separately audited QA fixture issue

Page initialization for Trends, Reviews and Competitors automatically creates canonical owner-scoped local context metadata. Phase 4's proxy previously denied these three POSTs, independently of the accessibility failures. Their actual router/service paths were traced: linked-owner validation, existing idempotency, local persistence/audit, no provider/network execution.

The QA-only proxy now permits only these exact endpoints, reviewed field allowlists, canonical identifier/key shapes and local context status. Authentication and link/owner authorization still run in the backend. Credentials, URLs, provider execution modes, actor impersonation and approval fields are rejected before forwarding. Unit and HTTP proxy regressions verify denial and propagation of backend HTTP 401. Other phases and acquisition/approval/worker routes remain default-denied.

## Independent execution results

The sequential browser/API reruns and the final enhanced focused retest completed. Results below come from actual executions, not the implementation alone.

| Check | Actual result |
| --- | --- |
| Final focused accessibility suite | **6 passed**, 0 failed, desktop/mobile; `348bfd708180e800`, `2288c37d5d9d3198`; includes exact website status-text witnesses |
| Focused fixture API assertions | **36 passed**, 18 in each installation |
| Original full Phase 4 | **44 browser + 36 API passed**, 0 failures/skips; `703ad013ac6b8690`, `cb92a2bb0ab27f12`; **250 axe scans, zero violations** |
| Phase 3 browser/API | **18 browser + 36 API passed**, 0 failures/skips; `5e8954bda42f6d3b`, `20d288c49667c5a3` |
| Phase 2 browser/API | **8 browser + 22 API passed**, 0 failures/skips; `381ef415548baf9b`, `f03c47c9f0f265fc` |
| Phase 1 smoke | **8 passed**, 0 failures/skips; `2089de90e3b72510`, `61a405c21be04c7b` |
| Adjacent persisted backend regressions | **37 passed**, 75 warnings, 264.97s; `d2b26e833dfc44ab` |
| QA harness self-tests | **47 Node + 28 Python = 75 passed**, none skipped |
| Full Angular | **252 passed**, 69 files |
| TypeScript | App and test no-emit checks passed |
| QA lint / formatting | ESLint and Prettier passed |
| Python quality | Ruff passed; Black passed (17 unchanged files); focused configured strict mypy passed (6 files, imports followed silently); compileall passed |
| Angular lint | 0 errors; 2 existing lifecycle-interface warnings in campaign dialogs |
| Production build | Passed; initial bundle **515.08kB**, warning budget 500kB (about +0.42kB against the 514.66kB pre-fix baseline) |
| Git whitespace | `git diff --check` passed; existing LF/CRLF normalization notices remain |

These counts are executions, not unique feature coverage. Repeated fixture API assertions overlap. The adjacent backend matrix reuses actual canonical financial/stock/provenance/signal tests without changing their rules.

The QA reporter's negative self-test intentionally prints `desktop: FAILED QA-TEST failure` while verifying that a failed assertion cannot become a confirmed defect or passing report. The actual Node self-test summary is **47 passed, 0 failed**; that deliberate reporter fixture is not a failed application scenario.

Existing backend warnings remain: deprecated FastAPI startup-event handlers, pytest's already-imported assertion-rewrite notice, and a duplicate OpenAPI operation ID for external fetch preflight observed during fixture startup. No API-contract repair is claimed here. These and repository-wide historical typing/lint debt are separate from the scoped checks; this frontend remediation is not a production-release clearance.

An extra diagnostic `diff --check` invocation temporarily overriding `core.autocrlf=false` reported CR characters as whitespace across unrelated Windows working-tree files. It was not the repository's normal comparison configuration and was not used as a certification gate. The required normal `git diff --check` was rerun and passed; no repository setting or unrelated file was changed to obtain that result.

### Failed intermediate runs are retained

- First focused attempt: **2 passed / 4 failed** (`bc309a9580d5fa4f`, `5946266a3e20ca37`). Captions passed; exact-name filter targeting and uncompleted table wrappers failed.
- Second focused attempt: **4 passed / 2 failed** (`7b35fbf72d0b2fc0`, `10148514e1582dab`). A duplicate table-region name remained; this was corrected, not suppressed.
- Pre-witness focused pass: **6 passed** (`41844a20d3d4d3c2`, `4737ba0ae3cce0b1`). The later final focused run adds direct checks for the two original website text selectors; it does not change production source or weaken any rule.
- First full retest: **42 passed / 2 failed**, **36 API passed** (`463ad3c679d589bc`, `d307e20c763219b7`). It exposed three populated intelligence semantics defects: Trend heading ID, product-region name, badge-group role. Six rule/state violations were retained across two viewports. Corrected with the bounded changes above.
- First adjacent pytest invocation lacked the required `QA_ORIGIN` and failed before database creation (`85b0fda68fad45ed`, safe initialization diagnostic). A subsequent invocation used a different allowed origin from the tests' fixed `http://127.0.0.1:4200`, correctly producing **1 pass / 36 setup errors** with HTTP 403 (`6ffed5774eb54ca3`). Correctly configured rerun passed all 37; no CSRF/auth relaxation or test assertion change.
- Initial Angular run: **242 passed / 10 failed** because old unit selectors asserted nested `main`; assertions now require proper section semantics and absence of nested main. Initial new test lint found one `any` assignment; a typed DOM reference fixed it. Final full suite/lint results above supersede, not erase, those attempts.

## Caption, keyboard and accessibility evidence

The focused suite asserts each of the six caption occurrences at **360, 390, 768 and 1440 CSS pixels**, in both desktop and mobile Chrome contexts: **48 targeted node reviews**. Every review requires full text in view, fit inside the actual scroll-container clip, a real axe contrast PASS, no targeted violation and no targeted incomplete result. Original Phase 4 separately revisits the captions and the four historical financial headers in both default viewports. Original screenshot/trace paths are preserved.

Combined [exact accessibility evidence](phase-4a-accessibility.json): **322 full-document state scans, zero violations; 84 targeted node executions, all contrast PASS with zero targeted incomplete results**. The 84 include repeated caption executions, eight historical financial-header executions and four exact website state-text executions; they are not 84 distinct controls. Full-document incompletes remain visible in the same artifact and are not included in that targeted PASS claim.

Keyboard verification includes Tab/Shift+Tab, Escape, actual ArrowRight scroll movement on overflowing regions, visible outlines and Tab escape. Adjacent Phase 2 additionally exercises Enter on Cancel and Space on Save with canonical persisted data. No traps are inferred absent outside the tested controls/dialog states.

The final focused run exercised **24 rendered scroll regions per context** across 12 routes. Actual ArrowRight movement was verified in **2 desktop and 23 mobile overflowing regions**; every rendered region's focus outline and Tab escape passed. Unrendered conditional regions are not claimed tested. Chrome mobile emulation was used, not physical-device or cross-browser certification.

Visual review compared pre-fix and post-fix 390px economics/due-diligence screenshots: caption text is now readable and scroll focus visible. Wide table columns and financial precision remain present. The existing sparse/tall due-diligence table presentation was also present in the baseline; it was not introduced by this correction and is not redesigned here.

The unchanged original Phase 4 targeted review completed **32/32 contrast PASS, zero targeted incompletes, zero targeted violations and zero clipped text reviews**, including eight historical financial-header executions. Full-document axe `incomplete` results for other obscured/offscreen table nodes and empty tables remain recorded. A full-page incomplete is not a PASS; only the exact separately exposed nodes can be cleared by targeted evidence. The original website status-text finding additionally requires explicit scrolled checks of `.state-high > small` and `.state-expired > small` in both contexts; unrelated website table incompletes remain unclosed. Screen-reader reading order, complete keyboard coverage, zoom/reflow beyond tested widths, all themes/high-contrast settings and every conditional dialog still require manual review. No automated result is labelled complete WCAG conformance.

## Safety and cleanup

Only fresh token-named, marker-protected disposable PostgreSQL databases were used. Provider egress and external mutation controls remain enforced. Normal runner cleanup validates the exact marker and database, then records absence and child exit; failed intermediate executions are also retained. No Docker resources were touched, and PC-first backup/restore certification was not invoked. No permanent/golden database writes, live providers, supplier contact, commercial writes, branches, commits or pushes.

Final [independent cleanup verification](phase-4a-cleanup-verification.json): a read-only `pg_database` query checked **21 exact task-specific targets; zero remain**. Twenty databases were actually created and all twenty marker/absence cleanup proofs passed. The twenty-first target failed initialization before creation. No QA runner, fixture or supervised runtime process remained. This includes failed intermediate attempts, not just final passing installations.

The original/full and focused reruns verify the changed production templates/CSS and shared QA proxy against pre-build hashes. The full run does not execute the Phase 4A test script; the focused run separately hashes and executes that script. Original Phase 4 assertions/helper additionally match their immutable baseline byte-for-byte. No broad repository-wide typing, migration or live-provider certification is implied.

## Exact Windows reproduction

Run from the repository root with existing dependencies, local PostgreSQL and Chrome. Use a dedicated local QA administrator permitted to create/drop **only disposable test state**; do not substitute a business database. No `.env` update is needed for these QA commands.

```powershell
$env:QA_DATABASE_ADMIN_URL = 'postgresql+psycopg://LOCAL_QA_USER:URL_ENCODED_PASSWORD@127.0.0.1:5432/postgres'
npm.cmd run qa:phase4a
npm.cmd run qa:phase4
npm.cmd run qa:phase3 -- --preserve-inventory
npm.cmd run qa:phase2 -- --preserve-inventory
npm.cmd run qa:smoke -- --retest --preserve-inventory
npm.cmd run qa:unit
& .\apps\api\.venv\Scripts\python.exe -m pytest qa/unit -q -o addopts=
npm.cmd run test:web
npm.cmd run lint --workspace @vayujit/web
npm.cmd run build --workspace @vayujit/web
node node_modules/typescript/bin/tsc --noEmit -p apps/web/tsconfig.app.json
node node_modules/typescript/bin/tsc --noEmit -p apps/web/tsconfig.spec.json
node node_modules/eslint/bin/eslint.js --config qa/eslint.config.mjs qa
node node_modules/prettier/bin/prettier.cjs --check qa

$env:PYTHONPATH = 'apps/api;.'
$env:QA_ORIGIN = 'http://127.0.0.1:4200'
$env:QA_PHASE = '3'
$qaPhase4aToken = [guid]::NewGuid().ToString('N').Substring(0,16)
& .\apps\api\.venv\Scripts\python.exe qa/fixture_server.py --port 0 --token $qaPhase4aToken --output "tmp/qa-agent/$qaPhase4aToken" --pytest test_qa_phase3a_remediation.py test_qa_phase3b_remediation.py test_pr_sos_06_action_center.py

$env:MYPYPATH = 'apps/api'
& .\apps\api\.venv\Scripts\python.exe -m ruff check --config apps/api/pyproject.toml qa
& .\apps\api\.venv\Scripts\python.exe -m black --check --config apps/api/pyproject.toml qa
& .\apps\api\.venv\Scripts\python.exe -m mypy --config-file apps/api/pyproject.toml --follow-imports=silent qa/fixture_server.py qa/phase3_api.py qa/phase2_api.py qa/phase3_runtime.py qa/runtime_supervisor.py qa/cleanup_disposable.py
& .\apps\api\.venv\Scripts\python.exe -m compileall -q qa
git diff --check

# Evaluate only after required executions; fails closure on missing/stale/failed evidence.
node qa/certify-phase4a.mjs
Remove-Item Env:QA_DATABASE_ADMIN_URL
```

Do not rerun the one-time baseline capture: it refuses to overwrite original evidence. The closure generator verifies original hashes, pre-build execution hashes, unique expected scenarios, exact caption/header matrices and normal isolated cleanup. The final backlog keeps all unrelated findings and original evidence; a resolved ID receives `retest_status: PASS` only from independent execution gates and links to the detailed resolution ledger.

## Remaining launch work and Phase 4B recommendation

Initial inventory entry is still **launch-critical and unimplemented** (`QA-P3-GAP-003`); no stock-entry workflow was added. Keep financial recalculation and generic Action Center execution gaps, currency and economics UX recommendations, provider-mode guidance, filtered-empty wording, desktop overflow/long-page proposals, and the intermittent historical accounts HTTP 502 suspect open according to their existing classification. A non-reproduction does not prove the 502 fixed.

`QA-P4A-A11Y-MANUAL-001` explicitly retains **85 original full-document rule/state incomplete occurrences**, with exact targets. They include color contrast, empty-table data association, conditional ARIA attributes and calendar children. These are **manual-review requirements, not 85 confirmed defects**. Screen-reader and broader keyboard/theme/conditional-state checks remain pending. The prior narrow caption/header review is resolved only for its exact verified targets; this new follow-up does not silently clear the rest.

Recommend a separately authorized Phase 4B focused on the canonical initial-stock entry handoff and its validation/approval requirements, followed by bounded usability proposals and assistive-technology/manual accessibility review. Do not start that workflow or an unrestricted redesign as part of Phase 4A. Local synthetic accessibility success alone cannot close whole-application launch certification.
