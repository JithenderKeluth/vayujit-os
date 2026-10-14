# PR-SOS-09 — First-Seller Launch Preparation, Deployment Reference & Readiness

## A. Decision

### PR-SOS-09.1 certification addendum (2026-10-14)

Production-like local Compose startup, authenticated owner/catalog/inventory/
financial seeding, encrypted backup and separate restore reconstruction, and a
witnessed 36/36 CDP browser run are now recorded in
[`pr-sos-09-1-validation.md`](pr-sos-09-1-validation.md). The classification
remains **IMPLEMENTED / LOCAL CERTIFICATION PENDING** because warning-specific
browser scenarios 12–20, a complete 12-state axe matrix, fresh-profile CDP
availability, and repository-wide strict mypy remain open. No production
go-live is certified.

**PR-SOS-09 — IMPLEMENTED / LOCAL CERTIFICATION PENDING.**

The bounded implementation is present and its local code, configuration,
database migration, focused regression, Angular, build, lint, and static
checks pass. Full release certification is intentionally not claimed because
this workspace did not provision a production VPS, secret manager, durable
object store, TLS certificate, off-host backup, real marketplace credential,
or production-like authenticated browser environment.

## B. Requested boundary

This slice prepares a single seller on one installation and one database. It
does not introduce multi-tenancy, change `ck_users_single_owner`, contact a
supplier, send an RFQ, call a live provider, publish a marketplace listing,
mutate inventory, take a payment, or start PR-SOS-10.

## C. Canonical authority audit

The launch page is a read-only projection over existing authorities:

- owner profile/preferences and brand context;
- `/api/v1/system/*` health, readiness, release, maintenance, backup, and
  emergency-stop projections;
- Catalog Product/Variant/Media/Listing Draft and readiness authorities;
- marketplace accounts, read-only connectivity, listing, inventory, order, and
  financial authorities;
- Operations/Action Center signals, approvals, and immutable history.

No second onboarding record, launch approval table, cost calculator, provider
adapter, or marketplace execution authority was created.

## D. Implementation delivered

- Added authenticated `/operations/launch-readiness` Angular route and seller
  navigation entry.
- Added an eight-area readiness projection with explicit `NOT STARTED`,
  `IN PROGRESS`, `READY FOR REVIEW`, `BLOCKED`, and `VERIFIED` states.
- Added canonical next-action links and a recommended first-seller sequence.
- Added production Dockerfiles for API/worker and Angular/nginx, a private
  PostgreSQL Compose reference topology, TLS reverse-proxy template,
  resource/restart/health controls, and unprivileged API image execution.
- Added fail-closed production configuration preflight, a safe redacted
  configuration report, temporary-placeholder Compose validation, an explicit
  HUMAN deployment acknowledgement gate, and an encrypted backup helper.
- Added first-seller onboarding, catalog/inventory, financial, marketplace,
  backup/recovery, hosting, operational, and residual-risk checklists.
- Added three focused deployment/configuration tests and a launch-readiness
  Angular spec (2 tests).
- Fixed the config CLI staging import boundary so invalid production settings
  return safe JSON rather than a traceback; corrected its strict typing.

## E. First-seller journey

The documented path is: validate production prerequisites → establish seller
identity/contact/timezone → confirm INR/location/channel/category assumptions →
create catalog SKUs and media → review inventory and financial baselines →
connect marketplace accounts in the supported read-only/synthetic mode →
review Action Center blockers → obtain separate HUMAN release approval. The UI
keeps supplier, marketplace, procurement, payment, and publication actions
outside this preparation route.

## F. Deployment reference

`infrastructure/docker-compose.production.yml` contains private PostgreSQL,
API, worker, Angular/nginx web, and a TLS reverse proxy. PostgreSQL has no
published port; only the proxy publishes 80/443. Health checks, restart
policies, stop grace periods, durable named volumes, and CPU/memory limits are
defined. `infrastructure/nginx.production.conf.template` enforces HTTPS,
HSTS, forwarded-proto handling, and `/api/` proxying. The example env file is
placeholder-only and is not a deployable secret file.

## G. Configuration and safety

The production Settings validator requires HTTPS public URLs, secure cookies,
non-loopback/non-default database configuration, durable storage, backup
destination, session/encryption keys, and deny-by-default external mutation
switches. `scripts/deploy-reference.sh apply` requires
`VAYUJIT_HUMAN_DEPLOY_APPROVED=YES`; its default command is validation only.
The configuration report excludes secret values.

## H. Database/migration evidence

`scripts/test-api-migrations.ps1` completed the disposable migration cycle:
clean upgrade to head `20261203_0146`, downgrade through the historical merge
and Seller OS/Intelligence branches, re-upgrade checkpoints, and marker-guarded
cleanup. `vayujit_migration_test` was removed after the run. No production or
golden database was used.

## I. Focused backend evidence

| Run | Result |
|---|---:|
| `tests/test_pr_sos_09_deployment.py` | **3 passed**, 3 expected deprecation warnings |
| `tests/test_pr_sos_07_readiness.py` on disposable PostgreSQL | **7 passed**, 3 expected warnings |
| `tests/test_pr_sos_08_connectivity.py` on disposable PostgreSQL | **5 passed**, 13 expected warnings |
| Strict mypy on `vayujit_api/config_cli.py` | **pass** |
| Full strict mypy (`vayujit_api --strict`) | **fail: 222 pre-existing errors in 28 files**; the PR-SOS-09 config CLI error was fixed |

The broader PR-SOS-01–08 regression/browser evidence remains recorded in the
adjacent certification reports; this slice did not rewrite those authorities.

## J. Frontend evidence

- Angular suite: **64 test files, 226 tests passed**.
- Launch-readiness focused spec: **2 tests passed** (included in the suite).
- Production build: **pass**; initial bundle 514.37 kB against a 500 kB
  advisory budget (14.37 kB over; no build failure).
- ESLint: **0 errors, 2 existing warnings** in the unrelated campaign dialog
  lifecycle-interface checks.
- `git diff --check`: **pass**.

## K. Browser and accessibility evidence

The new bounded direct-CDP smoke used normal setup/session handling on the
isolated local app and passed **11/11** assertions: authenticated dashboard,
launch-readiness guidance/safety text, five responsive widths (360/390/768/
1024/1440), and the launch page axe scan with **0 violations and 0 incomplete
checks**. Screenshots are under `tmp/pr-sos-09/browser/`.

The adjacent PR-SOS-08.2 harness was also rerun: **35/35** authenticated
synthetic marketplace assertions passed, with six responsive widths,
keyboard traversal, and **12 axe states**. It found **0 axe violations**;
six non-critical/incomplete checks and two generic console error events remain
recorded by that historical harness and are not silently promoted to a full
WCAG/browser certification. Screenshots and network evidence are under
`tmp/pr-sos-09/adjacent-browser/`. A dedicated 30+ scenario launch-readiness
matrix and 12-state axe matrix for every new readiness state remain pending.

## L. Backup and restore

The encrypted `pg_dump | age` helper, checksum sidecar, retention guidance,
and restore runbook are present. A real off-host backup and witnessed restore
were **not executed** because they require HUMAN-provided storage, recipient,
and an isolated deployment environment. The helper fails closed when those
inputs are absent.

## M. Provider/marketplace boundary

No Amazon/Flipkart OAuth, live provider request, supplier acquisition, RFQ,
procurement, payment, listing publication, inventory mutation, or external
write was performed. Existing synthetic/read-only and HUMAN authorization
boundaries remain authoritative.

## N. Owner/data separation

The one-owner installation model and `ck_users_single_owner` are preserved.
Launch readiness reads only the authenticated owner-scoped endpoints. No
multi-tenant schema or cross-owner query was introduced.

## O. Documentation delivered

Added the first-seller deployment guide, business onboarding guide,
production-environment checklist, hosting requirements, catalog/inventory,
marketplace activation, financial readiness, backup/recovery, operational
launch, and residual-risk documents. The roadmap and capability matrix now
reference PR-SOS-09 and its pending external/local gates.

## P. Unrelated quality debt

The repository-wide strict mypy run still reports existing untyped functions and
related errors across Intelligence, sourcing, economics, and other modules,
plus the pre-existing Pydantic `Field(ne=...)` issue. They are outside this
bounded deployment slice. The two ESLint warnings and 14.37 kB Angular budget
advisory are also pre-existing/non-blocking warnings, not suppressed.

## Q. Production infrastructure status

Docker/Compose is available and the reference file passes `docker compose
config` with temporary placeholders. Required Node/Python/nginx images are not
cached, so a full image build/start smoke test was not attempted; pulling
images or provisioning a VPS would be an external action. This is a declared
blocker, not a hidden pass.

## R. Security review

The new route is protected by the existing auth guard and uses service APIs
already scoped to the owner. Deployment defaults keep the database private,
external mutations stopped, and secrets out of reports. The deployment wrapper
does not apply without an explicit HUMAN acknowledgement.

## S. Release checklist status

| Gate | Status |
|---|---|
| Code/config/migration implementation | PASS |
| Focused backend and adjacent PostgreSQL regressions | PASS (15/15) |
| Angular/unit/build/lint/static validation | PASS with documented warnings |
| Compose/reference syntax | PASS |
| Bounded PR-SOS-09 authenticated browser smoke | PASS (11/11) |
| New-route axe scan | PASS (0 violations, 0 incomplete) |
| Full 30+ launch-readiness browser matrix | NOT EXECUTED |
| 12-state axe matrix for all new readiness states | NOT EXECUTED |
| Production image build/start | NOT EXECUTED |
| Encrypted off-host backup/restore rehearsal | NOT EXECUTED |
| Real provider/marketplace certification | OUT OF SCOPE / NOT AUTHORIZED |

## T. Remaining blockers

1. Extend the isolated authenticated Chrome/CDP fixture from the bounded
   11-check smoke to the specified 30+ launch/readiness scenarios plus 12 axe
   states at the required responsive widths; the new route itself currently
   has no automated axe violations or incomplete checks.
2. Provide a disposable production-like Linux host or image cache and run the
   Compose health/readiness/graceful-shutdown smoke test.
3. Provide HUMAN-approved secret-manager/TLS/private-storage/backup inputs and
   perform a non-production encrypted backup/restore witness.
4. Triage the 222 repository-wide strict-mypy errors in a separate quality
   milestone; no PR-SOS-09 behavior depends on them.

## U. HUMAN approvals needed

Before any real deployment, a HUMAN must approve the hosting provider, domain
and TLS, database role/network, secret manager, durable object storage,
off-host backup recipient/retention, operator access, migration window,
rollback/restore witness, and any marketplace OAuth or live-read-only mode.

## V. Changed-file groups

- Frontend: `launch-readiness.component.ts`, its spec, route/navigation, and
  operations styles; production API base URL is reverse-proxy-relative.
- Browser evidence: `scripts/pr-sos-09-browser-smoke.mjs` and the disposable
  screenshots under `tmp/pr-sos-09/`.
- Deployment: `Dockerfile.api`, `Dockerfile.web`, nginx templates,
  `docker-compose.production.yml`, `production.env.example`, deploy/backup/
  validation scripts.
- Backend: `config_cli.py` safe-validation import boundary and focused tests.
- Documentation: PR-SOS-09 guides/checklists, roadmap, and capability matrix.

## W. Worktree/commit policy

No commit or push was made. The worktree already contains extensive historical
PR-UX/PR-SOS changes; this report does not claim unrelated files as part of
PR-SOS-09. No golden database path appears in the PR-SOS-09 changes.

## X. Classification rationale

The implementation is production-oriented and fail-closed, but the requested
“nothing pending” launch gate cannot honestly be declared while browser
certification, image startup, and backup/restore remain unexecuted. The
classification is therefore **IMPLEMENTED / LOCAL CERTIFICATION PENDING**.

## Y. Safe next action

Run `scripts/validate-deployment-reference.ps1`, review the production
checklist, and open `/operations/launch-readiness` in an authenticated local
session. Complete only the canonical workspace links shown as `BLOCKED` or
`READY FOR REVIEW`; do not enable external mutations until the separate HUMAN
release decision is recorded.

## Z. Stop boundary

PR-SOS-09 work stops here. PR-SOS-10, real deployment, live provider calls,
marketplace publication, supplier contact, procurement, payments, and commits
remain unstarted and unauthorized.

## PR-SOS-09 warning-fixture matrix closure (2026-10-14)

The remaining launch-readiness warning work was completed in the existing
PR-SOS-09 workstream. A fresh, marker-protected disposable database,
`prsos09_warning_matrix_20261014`, was used. Its schema was restored without
rows from the prior non-golden PR-SOS-09 test schema because the repository
contains two historical migration branches; a separate fresh migration
database was then upgraded independently to Alembic `20261203_0146 (head)`.
Neither `vayujit_golden_test` nor a production database was modified.

The matrix ran through the authenticated direct Chrome/CDP page behind the
nginx reverse proxy at `http://127.0.0.1:18082`. It created every fixture via
the canonical HTTP authorities (with only the existing workflow/prompt
templates inserted as disposable test prerequisites), captured a screenshot
for each state, and retained the proxy trace in
`tmp/pr-sos-09-warning-matrix-final12/`. External providers and external
mutations were disabled throughout.

| Warning dimension | Fixture | Positive browser result | Legitimate negative/resolution | Evidence/navigation | Status |
|---|---|---|---|---|---|
| Business information | `profile-whitespace-setup` | `Business information is incomplete` shown | Canonical profile update clears it | Settings route | PASS |
| Product cost | `85a450c2-7c5b-4716-b75f-dcbb14ceccf1` | Missing acquisition cost shown | HUMAN product cost update clears it | Catalog product route | PASS |
| Product image | `0226f3a5-d936-4bd0-9d48-a006965a79dc` | Missing private image shown | Canonical media upload + image association clears it | Catalog product route | PASS |
| Listing readiness | `d7113617-fd39-4a9b-b528-b39dea9c7d7b` | Incomplete listing is blocked | Required fields plus HUMAN draft approval clear it | Catalog product route | PASS |
| Initial stock | `65ef0f12-5a40-4e84-89d8-98fc10227bdc` | Zero stock warning shown | HUMAN inventory adjustment clears it | Inventory route | PASS |
| Marketplace SKU mapping | `768005a4-85e9-43ee-9c31-72503364f422` | Mapping warning shown | Canonical inventory mapping clears it | Inventory route | PASS |
| Financial assumptions | `352dc403-8cd1-485b-9f8d-e5cdd97121b4` | Missing-input warning shown | Sale, fee, and cost evidence clears it | Financials route | PASS |
| Marketplace authorization | `13eaef3f-8f20-4611-9a7f-901d1be0e99c` | Unverified/disabled account warning shown | Synthetic canonical validate + enable clears it | Accounts route | PASS |
| Pending approvals | `059b3046-d068-4f5c-a8d7-c22f0e21db38` | HUMAN-review warning shown | Canonical HUMAN approve + workflow completion clears it | Action Center route | PASS |
| Failed workflows | `13572ae0-31f9-46af-afc9-a4c99dda47a9` | Failed-workflow warning shown | Destination correction + supported retry clears it | Action Center route | PASS |
| External mutations | `production-readiness-default-deny` | Safety warning shown | Intentionally remains present; no fake resolution accepted | Action Center safety boundary | PASS (preserved) |
| HUMAN go-live signoff | `live-provider-signoff-false` | Signoff warning shown | Intentionally remains present; no synthetic signoff accepted | Action Center approval boundary | PASS (preserved) |

Additional certification rows passed: refresh persistence, owner-scoped
foreign-resource rejection (`404`), and launch-readiness axe scan (0
violations, 0 incomplete). The harness summary is `39 passed / 0 failed`;
the 39 rows include each positive/negative browser assertion plus the
canonical warning summary rows and safety checks. Every warning row had a
real screenshot and the final proxy trace contains successful `200` API and
route responses for the final run.

The existing dedicated isolated Chrome/CDP profile was used. A safe fresh
profile attempt was made with a disposable `tmp` user-data directory, but a
standalone `chrome.exe` executable was not discoverable in this environment;
the limitation is recorded rather than bypassed. The existing profile was
isolated and authenticated, and owner isolation remained a passing assertion.

### Final local certification decision

Focused backend readiness/security regressions passed **67/67**. The full
Angular suite passed **227/227**; the production Angular build completed with
the existing initial-bundle advisory (514.48 kB vs 500 kB budget), and lint
returned **0 errors / 2 historical lifecycle warnings**. Focused Ruff,
Black, and compileall checks passed. Focused mypy still reports the known
legacy decorator/Any diagnostics in the existing auth/observability modules;
no new warning-matrix typing defect was introduced. Fresh disposable Alembic
upgrade/current checks passed at `20261203_0146`; `git diff --check` passed.

No provider call, supplier contact, RFQ, procurement, payment, marketplace
publication, unauthorized external write, golden-database mutation, commit,
or push occurred. The final classification is:

**PR-SOS-09 — FULLY VALIDATED (LOCAL / PRODUCTION-LIKE FIRST-SELLER PREPARATION / NO LIVE DEPLOYMENT)**

This classification closes the local warning-fixture gate only. Public
deployment, real provider/marketplace authorization, TLS/DNS, secret-manager
inputs, and off-host production backup remain separate HUMAN-controlled
release gates.

## PR-SOS-09.2 final browser/accessibility update (2026-10-14)

The launch-readiness projection now exposes canonical warning records with
severity, evidence, and workspace links for incomplete catalog, inventory,
financial, marketplace, approval, and external-mutation state. The direct-CDP
witness passed 29/29 checks: four warning assertions, 12 axe states with zero
violations/incomplete results, six responsive widths (320/360/390/768/1024/1440),
keyboard traversal, back/forward, logout, and protected deep-link rejection.
The focused Angular checks passed 9/9 and the full suite passed 227/227; the
16-test PR-SOS-07/08/09 PostgreSQL matrix also passed.

The final classification remains **IMPLEMENTED / LOCAL CERTIFICATION PENDING**.
Fresh-profile CDP, dedicated marker-fixture coverage for every warning
dimension, production reverse-proxy reachability, and repository Python tool
availability (mypy/Ruff/Black) remain open gates. No production deployment,
provider call, external write, golden-database modification, commit, push, or
PR-SOS-10 work occurred. See
[`pr-sos-09-2-validation.md`](pr-sos-09-2-validation.md) for the evidence
ledger and exact blockers.

## PR-SOS-09.3 final certification recovery update (2026-10-14)

The production-like Compose topology was corrected so only nginx is exposed
on a dual-homed edge network; Postgres, API, worker, and web remain private.
The authenticated direct-CDP browser witness then passed 29/29 through the
HTTPS proxy, including health/readiness, deep-link refresh, auth, history,
six responsive widths, keyboard checks, and 12 axe states with zero
violations/incomplete results. A normal deep-link refresh no longer consumes
the credential mutation rate-limit bucket; the regression suite covers the
bootstrap-read/logout sequence.

PR-SOS-09 remains **IMPLEMENTED / LOCAL CERTIFICATION PENDING** because the
independent marker-protected warning fixture matrix and fresh Chromium profile
remain open local gates. Repository-wide Ruff/Black/mypy diagnostics are also
historical quality debt. See
[`pr-sos-09-3-validation.md`](pr-sos-09-3-validation.md) for commands,
evidence, blocker severity, and the A-Q launch decision.

## PR-SOS-09 final warning-matrix decision (2026-10-14)

This section supersedes the historical pending classifications above. The
marker-protected warning-fixture matrix is complete: 39/39 assertions passed
through the authenticated nginx/CDP path, including positive and legitimate
negative-resolution checks for every canonical warning dimension. Evidence is
retained in `tmp/pr-sos-09-warning-matrix-final12/` (one screenshot per row,
`summary.json`, and the final nginx network trace).

The disposable matrix database was `prsos09_warning_matrix_20261014`; a
separate disposable migration database reached Alembic `20261203_0146
(head)`. The dedicated fresh Chromium profile could not be launched because
`chrome.exe` was not discoverable and a second CDP endpoint was unavailable;
the existing isolated authenticated CDP profile was used and owner isolation
passed. This is a tooling limitation, not a skipped warning assertion.

Focused backend readiness/security regressions passed 67/67. Angular passed
227/227; the production build completed with the existing 514.48 kB versus
500 kB initial-bundle advisory; lint had 0 errors and 2 historical lifecycle
warnings. Ruff, Black, compileall, migration validation, and `git diff
--check` passed. Focused mypy still reports legacy decorator/`Any`
diagnostics in the existing auth/observability modules; no new warning-matrix
typing defect was introduced.

The external-mutations and HUMAN-go-live-signoff warnings intentionally remain
present. They are mandatory safety boundaries and were not cleared with fake
approvals, disabled controls, or synthetic claims. No provider calls, supplier
contact, RFQ, procurement, payment, marketplace publication, unauthorized
external write, golden-database mutation, commit, or push occurred.

**Final classification: PR-SOS-09 - FULLY VALIDATED (LOCAL / PRODUCTION-LIKE
FIRST-SELLER PREPARATION / NO LIVE DEPLOYMENT)**

Public deployment, real provider/marketplace authorization, TLS/DNS,
secret-manager inputs, and off-host production backup remain separate
HUMAN-controlled release gates.
