# QA Agent — Phase 1 foundation

This is an executable, deterministic QA system, not a production-autonomous fixer.
One seller, one isolated installation and PostgreSQL database remain authoritative.
`ck_users_single_owner` is preserved. No production application code is changed.

## Repository and capability audit

Angular 22 standalone lazy-loaded pages live in `apps/web/src/app/app.routes.ts`.
Domain services use typed shared contracts (`packages/shared`) and cookie-authenticated
FastAPI authorities. SQLAlchemy models and Alembic migrations own persisted state.
The Electron desktop wrapper is a separate workspace; it is not browser-certified
by this phase. Source inventory is generated with TypeScript and Python ASTs.

The full machine-readable [inventory](application-inventory.json) records every
route declaration, redirect, page component, auth guard, direct spec, navigation
reference, API declaration/handler, model/table and backend test file. The
[coverage matrix](coverage-matrix.md) lists every declared route, not just sidebar
links. Reachability is a source-level candidate until a browser visits the route.
Parameterized routes need real disposable IDs; wildcard redirects are not pages.
Runtime OpenAPI is captured per disposable installation for registration evidence.
`runtime-api-inventory.json` records each actually registered OpenAPI method/path,
operation ID, tag, summary and any matching static handler source. The source AST
and runtime counts can differ; neither is silently substituted for the other.

Backend-to-UI matching uses conservative static service-reference candidates.
An unmatched API is **not automatically a missing feature**: provider transports,
workers, ledgers, CLI maintenance, internal projections and security controls are
legitimately backend-only. Every unmatched declaration is retained for triage.
The canonical existing capability assessment remains
`docs/ux/seller-os-capability-matrix.md`; it is not overwritten by inferred claims.

## Seller journeys and risk-based coverage

| Journey | Canonical pages / authorities | Phase 1 execution | Next deterministic cases / risk |
| --- | --- | --- | --- |
| First use → owner → dashboard | `/setup`, `/login`, `/dashboard`; auth router, User/session | UI setup, invalid input, keyboard, duplicate owner denial, axe | Expiry, lockout, interrupted setup, cross-installation IDs / P0 |
| Business goal → research → opportunities → HUMAN selection | Business Agent, product-opportunity, journey routers | Goal text → persisted canonical plan; does not click Start run | Category/cache integrity, provider unavailable, source review, zero/multiple candidates, stale HUMAN selection / P0 |
| Selected product → suppliers → shortlist → due diligence | sourcing, cross-marketplace, shortlisting, due-diligence | Inventory only | Product/goal lineage, one-supplier state, stale evidence, contradictions, unknown MOQ, explicit HUMAN decision / P0 |
| Commercial evidence → landed cost → economics → comparison → decision | sourcing-economics; PR-5–8 canonical assessments | Checks missing catalog economics stays unavailable | Decimal oracle, UNKNOWN != zero, fees/tax/FX assumptions, stale assessments, idempotency / P0 |
| Brand → product → catalog → listing preparation | `/brands/new`, `/products/new`, product/edit, `/catalog/:id` | UI create/edit INR values, API persistence, refresh/history, empty and blocked state | Variants, private images, duplicate SKU, stale versions, listing readiness and HUMAN review / P0 |
| Marketplace onboarding → authorization → controlled listing | Amazon/Flipkart/Meesho pages and backend connectors | Inventory only; all execution blocked | Fake transports only, revocation/expiry/replay, missing requirements, foreign IDs / P0 |
| SKU mapping → stock → reservation → order → cancellation | inventory and orders pages; append-only ledgers | Inventory only | Concurrency/overselling, duplicate/out-of-order events, partial fulfillment, stock reconciliation / P0 |
| Sale → fees → refund → settlement → profitability | financials, settlements, analytics | Inventory only | Decimal exactness, unknown costs, negative revenue, refund allocation, effective dates / P0 |
| Seller attention → evidence → safe action | dashboard, Action Center, launch readiness | Basic page navigation; synthetic API failure/retry | Warning dimensions, misleading empty/error combinations, severity/navigation correctness / P0 |
| Product assets → content → campaigns → workflow → HUMAN publishing | media, AI, campaigns, social, publishing, approvals | Inventory only | Private previews, MIME/size controls, fake AI, review/history, no external execution / P1 |
| Advertising preparation → optimization/experiment review | ads routes and canonical marketing authorities | Inventory only | INR budgets, fake ad transport, spend caps, HUMAN approval, explainability / P1 |
| Operations → workers → audit → maintenance/recovery | operations/settings/backups pages, CLI | Inventory only | Read-only status and recovery semantics / P0; PC-first backup certification explicitly excluded |

Existing pytest unit/integration/security/concurrency suites, Angular Vitest/jsdom
specs, axe-core and direct Chrome/CDP scripts are reused as source references.
Examples: `test_pr_sos_01_catalog.py`, `test_pr_sos_04_inventory_orders.py`,
`test_pr_sos_05_financials.py`, `test_auth_integration.py`,
`test_product_source_review_integration.py`, `test_external_true_concurrency.py`,
`scripts/pr-sos-09-2-browser-certification.mjs`. Test existence is not test success.
The initial Playwright runner does not rerun that entire historical matrix.

## Initial findings and disposition

The first completed synthetic browser run found a genuine serious axe
`color-contrast` issue in Business Agent's active journey links. The stepper's
`.blocked` opacity reduces small status labels to 3.52:1, below 4.5:1. The links
remain active rather than disabled UI controls. Axe also reports nested/duplicate
main landmarks and a nested complementary landmark on that page. These remain
open, with exact rule IDs, targets, screenshots and traces in the generated report.
No production fix is authorized by this phase. The per-viewport occurrences should
be deduplicated into source-level tickets before remediation.

The product form's USD default is recorded separately as a **recommendation** for
Indian-seller clarity, not as proof of incorrect monetary calculations. The smoke
suite explicitly enters INR and asserts persisted decimal price/cost values.

Two harness-only assumptions were repaired during validation: the Windows asyncio
socket pair needs a narrowly scoped loopback exception with native platform defaults;
and a brand selector may legitimately contain one option, not a placeholder plus
one option. Both fixes preserve production behavior and are not product defects.

## Executable architecture

`qa/run.mjs` → current production Angular build → fresh fixture API process →
loopback static/reverse proxy → isolated Playwright Chrome context → assertions,
screenshots, traces, console/network evidence → JSON + Markdown reports → guarded
database cleanup. Desktop 1440×1000 and mobile 390×844 run sequentially against
different fresh databases. Worker/test parallelism and retries are disabled.

`qa/fixture_server.py` creates only `vayujit_qa<16-hex-run-token>_test`. It refuses
reuse, verifies the canonical disposable marker and its run token, uses canonical
SQLAlchemy metadata, and exposes a test-only witness in this process. No new
production authority or auth bypass is introduced. Test data is created through
actual owner/brand/product/goal APIs or normal UI forms, not raw data inserts.
Only database creation and the standard disposable marker use infrastructure SQL.

The fixture does not read `.env`, removes inherited VAYUJIT settings, sets emergency
stop, disables external research, retains default-deny provider modes, uses private
per-run media paths, and rejects outgoing connections except its loopback PostgreSQL
port. Browser context and reverse proxy separately deny outside origins and all
mutations except the small explicit preparation allowlist. No marketplace accounts,
orders, financial events or suppliers are fabricated by the smoke suite.

Cleanup occurs on graceful stdin closure so Windows runs Python's `finally`, which
rechecks marker and token before dropping **only its newly created database**.
No generic reset, shared fixture database, Docker stop/down, volume deletion,
backup script, normal development API or golden database is used. A killed/crashed
parent can leave a disposable QA database: retain the name in the report and inspect
its marker before any owner-controlled cleanup. Do not use broad cleanup commands.

These are test-process TCP/DNS controls and canonical provider kill switches, not
an OS-level firewall or complete network-security certification.

Metadata fixtures deliberately do **not** stamp a fake Alembic head. Health-ready
can consequently report migration unavailable; actual output is attached and this
is an environment limitation, not automatically a production defect. A fresh
migration-driven QA profile is a follow-up, not a falsified readiness PASS.

## Findings and evidence rules

[finding.schema.json](../../qa/finding.schema.json) defines stable IDs, feature,
route, type, severity/priority, expected/actual behavior, steps, screenshot/trace
references, confidence, suggested fix and retest status. Assertion failures begin
as SUSPECTED until a human/source review distinguishes app bugs from harness defects.
USABILITY recommendations must not be labelled confirmed functional defects.
No issue is silently auto-fixed. Unexecuted and intentionally forbidden flows stay
explicit. Axe includes incomplete/manual-review results; scans are not complete
WCAG certification. Phase 1 keyboard coverage is Tab/Shift+Tab on owner setup only.

Raw artifacts live under ignored `tmp/qa-agent`. They contain only synthetic QA
sessions, but traces can include synthetic credentials/cookies. Treat them as local
sensitive artifacts; never commit or upload traces without review. Structured
network references omit query strings, headers and bodies. No real credential is
loaded into the disposable API. Reports contain actual test counts and limitations.

## Windows commands

Requirements: Node 22/24, installed npm dependencies (`npm.cmd ci --ignore-scripts`
for a clean checkout), existing API virtualenv, local Chrome, and PostgreSQL on
127.0.0.1 with an account permitted to create disposable databases. Do not start or
restart Docker as part of QA while backup certification is using it. Use an already
running local PostgreSQL service; this runner never manages Docker resources.

```powershell
# Offline source inventory and Node harness regressions:
npm.cmd run qa:audit
npm.cmd run qa:unit
& .\apps\api\.venv\Scripts\python.exe -m unittest discover -s qa/unit -p 'test_*.py'

# Set this in the current shell only, using YOUR local disposable DB admin details.
# Database must be postgres on 127.0.0.1, never vayujit or vayujit_golden_test.
$env:QA_DATABASE_ADMIN_URL = 'postgresql+psycopg://LOCAL_QA_USER:URL_ENCODED_PASSWORD@127.0.0.1:5432/postgres'
npm.cmd run qa:smoke
# Equivalent wrapper (no system execution-policy change):
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-qa-phase1.ps1
Remove-Item Env:QA_DATABASE_ADMIN_URL
```

No `.env` change is needed. Use `npm.cmd` in Windows PowerShell to avoid `npm.ps1`
execution-policy failures. Browser collection without running fixtures:
`node node_modules/@playwright/test/cli.js test --config qa/playwright.config.mjs --list`.
The runner binds ephemeral loopback ports, so normal 4200/8000 sessions are untouched.

Read results in [initial-report.md](initial-report.md) and
[initial-report.json](initial-report.json). Inspect retained failure traces locally
with `node node_modules/@playwright/test/cli.js show-trace <trace.zip>`.

## Subsequent implementation phases

Phase 2 is now implemented as an extension of this foundation. See
[Phase 2 architecture](phase-2-architecture.md), [actual validation](phase-2-validation.md),
and [separate execution report](phase-2-report.md). Its persisted fixtures still use
ORM metadata; the migration-backed fixture goal below remains an explicit gap.
Phase 1 reports and findings are retained unchanged.

Authorized Phase 2 remediation is tracked separately in
[remediation validation](phase-2-remediation-validation.md). Phase 1 retests use
`npm.cmd run qa:smoke -- --retest` and do not overwrite the original report.
`node qa/retest-remediation.mjs` closes findings only after complete, passing
Phase 1 and Phase 2 browser/API runs with verified cleanup.

1. **Phase 2 — P0 seller journey and deterministic business oracles:** migration-
   backed fixtures; complete product/selection/supplier/due-diligence/economics flow
   with explicitly synthetic evidence; independent Decimal expectations; replay and
   fresh-process reconstruction; denied/empty/unknown/stale/recovery states.
2. **Phase 3 — operations/security:** inventory concurrency, order/finance lifecycle,
   cross-installation foreign-resource IDs, session expiry, private media and HUMAN
   impersonation. Keep production authorities unchanged and fake transports explicit.
3. **Phase 4 — platform usability/accessibility:** all route/ID states at 360/390/
   768/1024/1440, keyboard dialogs and focus restoration, axe state matrix, seller
   task completion review, screenshot baseline triage rather than pixel-only gates.
4. **Phase 5 — reusable regression orchestration:** domain tags and budgets, CI/local
   scheduling only with separate approval, historical finding/retest comparisons,
   risk-based selection and privacy-reviewed evidence retention. No autonomous
   production fixing or real-provider authorization is implied.
# Operational QA extension

The executable Phase 3 extension is documented in
[phase-3-architecture.md](phase-3-architecture.md). Run `npm.cmd run qa:phase3`
with the existing current-shell disposable PostgreSQL admin configuration.
Results and limitations are in [phase-3-validation.md](phase-3-validation.md).
Earlier inventories and Phase 1/2 evidence remain separate; Phase 3 does not
authorize automatic application fixes or real provider execution.

## Phase 4 exploratory extension

Run `npm.cmd run qa:phase4` using the same disposable-admin shell configuration.
See [Phase 4 architecture](phase-4-architecture.md), [actual validation](phase-4-validation.md)
and [route/control coverage](phase-4-coverage.md). Discovery is read-only; explicit
seller tasks are allowlisted and isolated. Unavailable parameter IDs and unopened
conditional states remain untested, not fabricated coverage. Full application
certification remains INCOMPLETE; no automatic production remediation is authorized.

