# Seller OS implementation roadmap — PR-UX-01A

## Completed in PR-UX-01A

- Audited the Angular route table, shell, shared UX primitives, journey
  components, dashboard, domain workspaces, API services, and backend
  authorities.
- Added the capability matrix, journey map, information architecture,
  component architecture, and this roadmap.
- Extracted seller navigation into `SellerNavigationComponent`, reused by the
  desktop sidebar and mobile menu.
- Added accessible progressive disclosure for Advanced navigation, active-link
  semantics, keyboard focus styling, and focused component tests.
- Preserved the existing canonical dashboard/journey API integration and state
  components; no duplicate business or approval logic was introduced.

## PR-SOS-04 / 04.1 / 04.2 (fully validated locally; fake providers only)

- Added the canonical owner-scoped inventory balance, append-only movement
  ledger, reservation lifecycle, channel-SKU mapping, and marketplace order
  event authorities in migration `20261020_0160`.
- Added row-locked ATP reservation, overselling rejection, idempotent fake
  provider lifecycle events, conservative return handling, reconciliation
  summaries, and Business Agent read-only insights.
- Replaced the channel-only inventory/orders route projections with unified
  authenticated Angular workspaces at `/marketplaces/inventory` and
  `/marketplaces/orders`, including loading, empty, error, blocked/read-only,
  and HUMAN adjustment guidance.
- Focused disposable PostgreSQL tests pass (7/7, including final-unit,
  multi-unit, adjustment-versus-reservation, cross-channel, duplicate-event,
  ledger-reconstruction, reconciliation-summary, and invalid-state
  regressions); the event path now serializes account-level idempotency checks.
  The focused PR-SOS-01 through PR-SOS-03 adjacent matrix passes (14/14), and
  a fresh disposable Alembic chain reaches `20261020_0160 (head)`. Angular
  build/lint/tests and changed-router Ruff/Black/strict-mypy checks pass. The
  authenticated 30-step Chrome/axe matrix remains an explicit release gate and
  is not inferred.
- PR-SOS-04.2 closes that browser gate: the recovered direct Chrome/CDP
  harness passed all 30 authenticated scenarios, axe-core 4.11 reported zero
  violations/incomplete findings across inventory, ledger, mapping, orders and
  detail states, and responsive checks passed at 320/360/390/768/1024/1440px.
  The final focused PostgreSQL suite is 8/8 (including conflicting mapping
  rejection), adjacent PR-SOS-01..03 is 14/14, and Angular is 62 files / 223
  tests. No live marketplace calls or writes were made.
- See [`../seller-os/pr-sos-04-validation.md`](../seller-os/pr-sos-04-validation.md)
  for the A–Z evidence report and remaining limitations.
- See [`../seller-os/pr-sos-04-2-validation.md`](../seller-os/pr-sos-04-2-validation.md)
  for the final browser, accessibility, responsive, keyboard, and regression
  evidence.

## PR-SOS-05 (implemented; local certification pending)

- Added the owner-scoped financial-evidence projection over canonical
  marketplace orders, fees, refunds, settlements, Products, and existing
  economics. Financial events are immutable/idempotent, cost and fee evidence
  is effective-dated, calculations use Decimal/Numeric precision, and
  settlement reconciliation preserves UNKNOWN, mismatch, and verified states.
- Added `/marketplaces/financials`, Sell navigation, marketplace overview
  entry-point, owner-scoped summary/sales/profitability/fees/settlement/
  reconciliation/alerts/calculation APIs with marketplace/date filters, and a
  read-only Business Agent guidance projection. Synthetic fixture inputs are
  explicitly labelled and no external provider call or marketplace mutation is
  possible through this surface.
- Added read-only revenue-trend, marketplace-comparison, refund-impact,
  missing-cost, SKU-profitability, and order-profitability projections over the
  same canonical order and evidence authorities.
- Focused financial tests (4/4), PR-SOS-04 regressions (8/8), the pre-change
  Angular baseline (223/223), focused Ruff/Black/strict-mypy/compileall, fresh merged
  Alembic head `20261201_0144`, Angular build, lint, and `git diff --check`
  pass for the scoped implementation. Durable calculation snapshots and
  canonical order/line projections are covered. A post-template Angular rerun
  had two unrelated existing 5-second intelligence-test timeouts (221/223),
  and the fresh authenticated 30-scenario Chrome/axe financial matrix remains
  the release gate for certification closure.
- A clean final Angular rerun after the analytics panels completed 62/62 files
  and 223/223 tests; the earlier timeout result was transient.
- See [`../seller-os/pr-sos-05-validation.md`](../seller-os/pr-sos-05-validation.md)
  for the A–Z evidence report and explicit synthetic-only limitations.

## PR-SOS-05.1 closure

Financial reliability, authenticated browser certification, keyboard/responsive
checks, and axe-core accessibility certification are complete locally with
synthetic PostgreSQL fixtures. The result is **FULLY VALIDATED (LOCAL /
SYNTHETIC / NO LIVE EXTERNAL MUTATIONS)**. See
[`../seller-os/pr-sos-05-1-validation.md`](../seller-os/pr-sos-05-1-validation.md).
Live provider fee/settlement, accounting, tax, banking, and marketplace
certification remain intentionally out of scope.

## Completed in PR-UX-01C (supplier discovery and due diligence UX)

- Added selected ProductOpportunity context to supplier discovery and preserved
  it through the supplier list, detail, comparison, and verification links.
- Restored supplier detail from an owner-scoped query ID only when it is present
  in the canonical product-scoped projection; stale or foreign IDs render an
  actionable error instead of leaking or selecting data.
- Added provider/research lifecycle copy for completed, no-candidate,
  unavailable, approval-required, blocked, failed, and stale states. The UI
  keeps `LOCAL_FIXTURE` and `LIVE_READ_ONLY` distinct and does not infer a
  supplier's readiness.
- Made due-diligence requests credentialed, filtered by selected supplier, and
  visibly attached to the selected product. Review and waiver remain canonical
  HUMAN actions; no external write is enabled.
- Added responsive authenticated browser evidence at 360, 390, 768, 1024, and
  1440 CSS pixels using a disposable PostgreSQL fixture.

See [`pr-ux-01c-validation.md`](pr-ux-01c-validation.md) for the A–Z
certification report, exact test counts, evidence paths, and limitations.

## PR-UX-01B–F backlog

| Slice | Backend authority | Existing frontend | Remaining work | Dependencies / acceptance |
| --- | --- | --- | --- | --- |
| 01B Goal and research clarity | Goal, plan, ProductOpportunity | Business Agent and Product Opportunities | Simplify goal review, research progress, evidence gaps, and selection language | Goal constraints survive refresh; keyboard and mobile tests; no fake evidence |
| 01C Supplier decision workspace | Supplier, shortlist, DD authorities | Supplier discovery and due diligence are implemented and locally validated | Future refinement: comparison density and live-provider certification | HUMAN shortlist remains explicit; provenance and owner isolation tests |
| 01D Commercial decision experience | Economics, quote, decision authorities | Sourcing economics and decision routes | Improve assumptions, sensitivity, capital fit, and decision readiness | No silent currency conversion; unknowns remain visible; approval gates preserved |
| 01E Sell/Create/Grow/Manage consistency | Product, content, marketplace, workflow authorities | Supplier engagement workspace is implemented; broader Sell/Create/Grow/Manage consistency remains | Apply shared page headers, tables, empty/error states, and responsive patterns across remaining routes | Engagement route certified locally; connector writes remain approval-gated |
| 01F Accessibility and responsive certification | Existing API authorities | Shared shell and feature components | Automated axe/keyboard checks, mobile/tablet layouts, screen-reader review | WCAG-oriented acceptance evidence at representative breakpoints |

## Completed in PR-UX-01D (commercial decisions)

- Reused the canonical PR-5A/B/C, PR-6A/B/C, and PR-8A/B/C authorities in the
  authenticated sourcing economics workspace. The UI now exposes known-cost
  breakdowns, assumptions, budget scope, capital fit, evidence gaps, partial
  and `NOT_COMPARABLE` states, and explicit HUMAN decision controls.
- Fixed journey goal scoping in decision briefs so an older/latest owner goal
  cannot supply the wrong budget or category context. Product-level requests
  keep the existing latest-goal fallback.
- Made HUMAN decision idempotency stable per journey/product/action and made
  launch preparation visibly unavailable until the canonical brief is ready.
- Validated the disposable persisted path with 36 PR-5B→PR-8C tests, 217
  Angular tests, strict checks on changed authority files, and authenticated
  Chrome responsive checks at 360, 390, 768, 1024, and 1440 CSS pixels.

See [`pr-ux-01d-validation.md`](pr-ux-01d-validation.md) for the complete
A–Z report and evidence paths.

## Completed in PR-UX-01E (controlled supplier engagement)

- Added the focused authenticated Supplier Engagement workspace and navigation
  route while reusing PR-7A/7B/7C and PR-8C canonical authorities.
- Exposed selected product, supplier readiness, RFQ draft preparation and
  review, approval-versus-authorization boundaries, immutable supplier
  responses, evidence unknowns, and procurement-readiness handoff.
- Added focused Angular coverage and validated the persisted disposable
  PostgreSQL fixture with authenticated Chrome at 360, 390, 768, 1024, and
  1440 CSS pixels. No external supplier action was executed.

See [`pr-ux-01e-validation.md`](pr-ux-01e-validation.md) for the complete
A–Z report, browser evidence, and limitations.

## Completed in PR-UX-01F (platform stabilization)

- Repaired the authenticated shell landmark contract and dashboard semantic
  landmark so routed pages expose one main content region and preserve the
  skip-link target.
- Stabilized repeated economics evidence collections with unique Angular track
  expressions; browser smoke no longer reports NG0955 duplicate-key warnings.
- Certified the supported Seller OS journey on a disposable PostgreSQL fixture,
  including deep links, refresh, browser history, logout/protected redirects,
  responsive widths, semantic controls/tables, and no-send boundaries.
- Recorded measured Angular test/build/lint results, route rendering timings,
  bundle budget status, and the remaining manual accessibility/performance
  follow-up in [`pr-ux-01f-validation.md`](pr-ux-01f-validation.md).

## Completed in PR-9C (supplier intelligence continuation and operational readiness)

- Reused the canonical supplier discovery/search, ProductOpportunity, evidence,
  due-diligence, commercial, engagement, and HUMAN decision authorities. No
  parallel supplier state or scoring authority was introduced.
- Projected the durable supplier-search summary from the Business Agent's
  `supplier.discovery` step into both the run result and the immutable
  `BUSINESS_DECISION_BRIEF`. The projection preserves provider mode, counts,
  supplier IDs, contradictions, failures, freshness, budget observability,
  source-admission state, prompt-injection state, and the canonical
  `opportunity_id`.
- Added an opportunity-scoped continuation link from the Business Agent to the
  existing Cross-marketplace Supplier Intelligence workspace. The UI labels
  the data as source-backed observations requiring HUMAN review; it does not
  certify suppliers, rank demand, authorize engagement, or execute external
  writes.
- Added backend and Angular regression assertions for projection lineage,
  review boundaries, owner-scoped opportunity context, and continuation
  navigation. Validation uses the disposable PostgreSQL test database only.

See [`pr-9c-validation.md`](../supplier-intelligence/pr-9c-validation.md) for
the complete A–Z implementation and certification report.

## Completed in PR-SOS-01 (seller catalog and listing preparation)

- Added owner-scoped Seller Catalog records for product lineage, variants,
  supplier associations, and channel listing drafts while reusing canonical
  Product, ProductOpportunity, HUMAN shortlist, Supplier, and audit authorities.
- ProductOpportunity conversion requires explicit HUMAN shortlist selection;
  replays are idempotent and preserve opportunity, assessment, goal, and
  selection provenance.
- Added readiness checks that keep unknown price, currency, images, compliance,
  SKU, and claims visible as blockers. HUMAN approval is explicit and stale
  optimistic versions are rejected.
- Added authenticated `/catalog` and `/catalog/:id` workspaces with responsive
  product context, listing preparation, readiness blockers, and clear next
  actions. Marketplace publication remains disabled in PR-SOS-01.

## PR-SOS-01.1 closure scope (catalog certification)

- Added owner-scoped product image associations that reuse secure `MediaAsset`
  storage and private preview URLs. Primary ordering, alt text, replacement,
  removal, stale-version rejection, MIME/size/dimension validation, and
  cross-owner denial remain explicit.
- Added inline variant creation/edit/archive UX with blank-value and duplicate
  option-combination rejection, owner SKU uniqueness, and optimistic version
  safety.
- Added a catalog economics projection that calls the canonical Product
  Opportunity economics authority and renders `UNKNOWN`/unavailable/partial
  states without calculating or inventing commercial values. Business Agent
  guidance links back to the canonical HUMAN-reviewed research surface.
- Added disposable PostgreSQL regressions for image ownership, private
  previews, stale image updates, variant combinations, canonical economics
  gaps, and existing catalog conversion/listing/supplier boundaries.

See [`pr-sos-01-1-validation.md`](../seller-os/pr-sos-01-1-validation.md) for
the implementation and validation report.

## PR-SOS-01.2 certification infrastructure recovery

- Recovered post-change authenticated browser evidence with a disposable
  Chrome/CDP profile and a fresh marker-protected PostgreSQL database.
- Validated the catalog create/edit/detail journey, secure MediaAsset upload
  and product association, variant creation, listing draft completion,
  explicit HUMAN approval, deep-link refresh, logout/protected routes, keyboard
  skip-link activation, and responsive overflow at 320/360/390/768/1024/1440px.
- The canonical single-owner model prevents creating two independent owners;
  the cross-owner matrix therefore remains certification-pending. Automated
  axe-core was not available locally and was not downloaded under the
  network-safe validation boundary.

See [`pr-sos-01-2-validation.md`](../seller-os/pr-sos-01-2-validation.md) for
the complete A–Z certification report and exact gate results.

## PR-SOS-01.3 owner isolation and accessibility certification

- Confirmed the production topology is one owner per installation/database;
  `ck_users_single_owner` remains authoritative and same-database two-owner
  tests are not applicable to this topology.
- Passed focused authentication, catalog, private-media, stale-version,
  guessed-ID, migration, and static checks on fresh marker-protected
  PostgreSQL installations. A second installation returned 404 for foreign
  brand and private-media IDs.
- Audited local browser/package caches for axe-core and established equivalents;
  none were available offline, so automated WCAG certification remains
  pending rather than inferred from DOM heuristics.

See [`pr-sos-01-3-validation.md`](../seller-os/pr-sos-01-3-validation.md) for
the complete A–Z report, test counts, and limitations.

## PR-SOS-01.4 final accessibility and catalog release gate

- Installed the approved `axe-core@4.11.0` dependency with a lockfile update
  and ran authenticated scans over catalog list/empty, product create/edit and
  detail, image picker/preview, variants, listing drafts, readiness errors, and
  HUMAN approval states.
- Corrected shared muted-text contrast, skip-navigation landmark/focus
  restoration, duplicate breadcrumb labels, text-only status ARIA, and the
  product editor main landmark. All scanned states have zero axe violations.
- Verified keyboard focus, forward and reverse tab order, Enter skip-link
  activation, Escape menu handling, required-field errors, private media, stale
  optimistic replay rejection, and responsive widths at 360/390/768/1024/1440.
- Completed focused catalog/media/product/auth PostgreSQL regressions, Angular
  tests/build/lint, strict mypy, Ruff, Black, compileall, migration head, and
  `git diff --check`. No publication or external write is enabled.

See [`pr-sos-01-4-validation.md`](../seller-os/pr-sos-01-4-validation.md) for
the complete A-Z evidence report. **PR-SOS-01 is FULLY VALIDATED locally; the
release boundary does not authorize marketplace publication.**

## PR-SOS-02 Amazon India seller integration and controlled listing operations

- Reuses the existing MarketplaceAccount, MarketplaceListing, catalog,
  GeneratedArtifact, media, variant, pricing, inventory, audit, and worker
  authorities.
- Adds durable HUMAN listing review and separate one-time execution
  authorization with stale-context, expiry, revocation, owner-scope, and
  idempotency protections.
- Adds an Angular Amazon workspace sequence that makes the approval boundary
  and next action explicit while preserving the local-only provider label.
- Uses `FakeAmazonSPAPITransport` for deterministic local certification. Live
  Amazon SP-API transport and marketplace mutation remain separately
  authorized and are not claimed by this slice.

See [`pr-sos-02-validation.md`](../seller-os/pr-sos-02-validation.md) for the
implementation report and release decision.

PR-SOS-02.1 recovered the local certification environment and completed the
authenticated CDP browser/axe-core 4.11.0, four focused PostgreSQL control,
and adjacent Amazon adapter/E2E/worker validation. PR-SOS-02.2 then passed the
genuine incomplete-readiness blocker and stable back/forward/deep-link browser
assertions, including the durable drift-resolution regression. PR-SOS-02 is
now **FULLY VALIDATED / LOCAL FAKE-ONLY**. The provider boundary remains local
fake transport only; live SP-API and marketplace publication require separate
authorization.

## PR-SOS-03 Flipkart seller integration and controlled listing operations

- Reuses the canonical Seller Catalog, Product, Variant, Media, Artifact,
  MarketplaceAccount, MarketplaceListing, audit, idempotency, and worker
  authorities.
- Adds Flipkart-specific account/category/attribute/listing projection and a
  deterministic fake transport. Listing submission remains local-only and
  explicitly distinguishes readiness, HUMAN review, single-use authorization,
  provider acknowledgement, and reconciliation.
- Uses shared marketplace-scoped review and execution-authorization tables so
  Flipkart does not create a weaker parallel approval system. Authorization is
  owner/account/listing/marketplace/fingerprint bound, expiring, revocable,
  replay-safe, and protected by the emergency stop and live-mode deny gate.
- Draft pricing is persisted locally before submission; no provider call is
  made until a current HUMAN review and execution authorization are consumed.

See [`pr-sos-03-1-validation.md`](../seller-os/pr-sos-03-1-validation.md) for
the closure report. PR-SOS-03 is **FULLY VALIDATED locally** with the
deterministic fake provider, 26 authenticated browser scenarios, axe scan,
responsive/keyboard evidence, migration replay, and regression matrix. Official
Flipkart API/sandbox/publication verification remains a separate external
milestone; no real Flipkart access or marketplace mutation is authorized here.

## Delivery rules

Each slice must reuse the capability authority already listed in the matrix,
add focused regression tests before broad visual changes, and document live or
local fixture state. No slice authorizes supplier acquisition, supplier contact,
RFQ delivery, procurement, payment, marketplace mutation, golden database
changes, PR-9C, or a commit/push.

## PR-UX-01B validation note

The dashboard, Business Agent, and Product Opportunities journey now expose
seller context and the canonical next action together. Goal creation keeps
backend validation and idempotency authoritative, while the form provides
inline, screen-reader-visible feedback. Product opportunity comparison and
selection remain HUMAN-controlled and render evidence classifications returned
by the existing ProductOpportunity service. Supplier decision, commercial,
engagement, and accessibility-certification expansion remain in PR-UX-01C–F.

## PR-SOS-06 certification closure

Operational Intelligence and the authenticated Action Center now project
owner-scoped Catalog, Inventory, Orders, and Financial evidence with
deterministic priority, lifecycle history, briefing, notifications, filters,
pagination, and conservative HUMAN-only action boundaries. Migration,
PostgreSQL regressions, Angular tests/build/lint, responsive keyboard checks,
and axe-core 4.11.0 browser scans passed. **PR-SOS-06 is FULLY VALIDATED
(LOCAL / ADVISORY & CONTROLLED INTERNAL AUTOMATION / NO LIVE EXTERNAL
MUTATIONS).** See [`../seller-os/pr-sos-06-validation.md`](../seller-os/pr-sos-06-validation.md).

## PR-SOS-07 single-seller production infrastructure and operational readiness

- Hardened production configuration rejects loopback/default database roles,
  disposable filesystem media, missing backup destinations, and non-HTTPS
  public URLs. Safe configuration reports remain redacted.
- Health/readiness and release checks now compare the live Alembic revision to
  the deployment-pinned `VAYUJIT_EXPECTED_MIGRATION_REVISION` instead of stale
  historical revisions. Existing Operations Control Center, backup, restore,
  maintenance, correlation, and emergency-stop authorities remain canonical.
- Added a secret-free production environment template and a bounded validation
  report. No production infrastructure was provisioned and no external
  mutation was performed.

See [`../seller-os/pr-sos-07-validation.md`](../seller-os/pr-sos-07-validation.md)
for the implementation and validation evidence. External hosting, secret
manager, object-storage, monitoring, signing, and live-provider certification
remain explicit deployment gates.

## PR-SOS-08 authorized Amazon India and Flipkart connectivity

- Added a shared owner-scoped read-only connectivity center backed by the
  existing `MarketplaceAccount`, provider adapters, Catalog, Orders, Inventory,
  and Financial authorities. It persists import checkpoints, safe evidence,
  correlation IDs, idempotency, stale state, and reconciliation summaries in
  `MarketplaceImportJob`.
- `SYNTHETIC` imports are deterministic and local. `SANDBOX` and
  `LIVE_READ_ONLY` fail closed until separately authorized provider transports,
  seller permissions, and credentials are configured. Live writes remain
  denied.
- The Accounts screen exposes connection/permission state, transport mode,
  read-only import actions, durable history, and the next reconciliation action.

See [`../seller-os/pr-sos-08-validation.md`](../seller-os/pr-sos-08-validation.md)
for evidence and the activation checklist. Real seller-account OAuth, provider
certification, and live API calls remain outside this local milestone.

### PR-SOS-08.1 browser and accessibility certification

The current Connection Center exposes provider capabilities, synthetic-only
status, refresh/loading feedback, accessible import controls, and durable
reconciliation history. PostgreSQL/API, Angular, static, migration, and
adjacent PR-SOS regressions pass. This historical note was superseded by the
PR-SOS-08.2 browser closure after the CUA harness ACL failure was bypassed with
the repository-local direct-CDP runner; see
[`../seller-os/pr-sos-08-1-validation.md`](../seller-os/pr-sos-08-1-validation.md).

### PR-SOS-08.2 final local browser certification

The CUA ACL failure was closed with a reusable direct Chrome/CDP runner using
explicit isolated API/web origins and the existing axe-core bundle. A fresh
marker-protected PostgreSQL database, authenticated synthetic Amazon/Flipkart
accounts, 35 browser assertions, six responsive widths, keyboard traversal,
and 12 axe states passed. Local synthetic connectivity is fully validated;
official provider OAuth, live calls, and marketplace writes remain separately
authorized deployment gates. See
[`../seller-os/pr-sos-08-2-validation.md`](../seller-os/pr-sos-08-2-validation.md).

## PR-SOS-09 first-seller launch preparation and deployment reference

### PR-SOS-09.1 local witness update (2026-10-14)

The disposable production-like Compose witness now starts healthy API, worker,
web, proxy, and PostgreSQL services. It includes canonical catalog,
inventory, financial, listing, owner, and audit records, an encrypted
`pg_dump | age` backup with separate restore/reconstruction proof, and a
witnessed 36-check authenticated CDP run. Warning-state browser scenarios,
the full launch axe matrix, fresh-profile CDP availability, and strict-mypy
cleanup remain explicit follow-up gates; public deployment and live providers
remain out of scope.

PR-SOS-09 adds the first-seller launch-readiness projection at
`/operations/launch-readiness`. It composes the existing owner profile,
catalog/listing, inventory, marketplace connectivity, financial, backup,
operations, and Action Center authorities; it does not create a parallel
onboarding or approval store. Each readiness card links to the canonical
workspace and keeps unknown, blocked, and HUMAN-review states explicit.

The release includes a Linux VPS reference topology (private PostgreSQL,
FastAPI API/worker, Angular behind nginx, private network, durable volumes,
resource limits, health checks, and encrypted-backup runbook), production
configuration preflight, and a fail-closed deployment wrapper. Compose syntax
is validated locally with disposable placeholders; no production host, secret
manager, object store, TLS certificate, provider credential, or marketplace
account is provisioned by this repository change.

See [`../seller-os/pr-sos-09-validation.md`](../seller-os/pr-sos-09-validation.md)
for the A–Z implementation and validation report. The local code/tests are
validated, while production-like container startup, fresh authenticated
browser certification of the new route, restore rehearsal, and external
provider/hosting gates remain pending HUMAN-controlled deployment work.

### PR-SOS-09.2 browser/accessibility certification update (2026-10-14)

Launch readiness now renders canonical warning evidence and next-action links.
The local authenticated direct-CDP witness passed 29/29 checks, including 12
axe states with zero violations, six responsive widths, keyboard traversal,
history navigation, logout, and protected deep-link rejection. Full Angular
tests passed 227/227 and the adjacent PR-SOS-07/08/09 matrix passed 16/16.
Dedicated warning marker fixtures, fresh-profile CDP, production-proxy browser
coverage, and Python quality-tool execution remain explicit follow-up gates;
the capability is still **IMPLEMENTED / LOCAL CERTIFICATION PENDING**. See
[`../seller-os/pr-sos-09-2-validation.md`](../seller-os/pr-sos-09-2-validation.md).

### PR-SOS-09.3 final certification recovery (2026-10-14)

The production-like reference topology now publishes only the nginx edge
proxy; private services use an internal Docker network. The authenticated
proxy witness passed 29/29 checks, 12 axe states with zero violations or
incomplete results, six responsive widths, keyboard traversal, history,
logout, and protected deep-link refresh. The auth bootstrap regression keeps
normal read-only refreshes separate from credential mutation throttling.

The capability remains **IMPLEMENTED / LOCAL CERTIFICATION PENDING** until
the marker-protected warning-dimension fixture matrix and a fresh Chromium
profile witness are completed. External hosting, secrets, off-host backup,
public TLS/DNS, and marketplace/provider authorization remain separate launch
gates. See [`../seller-os/pr-sos-09-3-validation.md`](../seller-os/pr-sos-09-3-validation.md).

### PR-SOS-09 final warning-fixture closure (2026-10-14)

The marker-protected warning-dimension matrix is complete: 39/39 authenticated
nginx/CDP assertions passed, including legitimate negative-resolution checks,
refresh persistence, owner isolation, and launch-readiness axe (0 violations,
0 incomplete). The capability is **FULLY VALIDATED (LOCAL / PRODUCTION-LIKE
FIRST-SELLER PREPARATION / NO LIVE DEPLOYMENT)**. External provider and
marketplace authorization, public deployment, TLS/DNS, secret-manager inputs,
and off-host backup remain separate HUMAN-controlled release gates. Evidence is
recorded in [`../seller-os/pr-sos-09-validation.md`](../seller-os/pr-sos-09-validation.md).

### PC-first live business operation package (2026-10-15)

Prepared a dedicated Windows Docker Desktop/WSL2 profile for the first VAYUJIT
seller: production web/API/worker/PostgreSQL/nginx, loopback-only binding,
internal no-egress network, unique persistent volumes and generated secrets,
real owner onboarding without fixtures, guarded migrations, and encrypted
database/media backup with isolated restore verification. Startup, shutdown,
health, backup, scheduled-task registration, security, and VPS migration
instructions are documented under `docs/seller-os/pc-first-*`.

The persistent owner database was intentionally not created or activated. The
disposable production-image runtime passed 17/17 deployment, security, and
persistence checks; authenticated Chrome passed 25/25 checks across sign-in,
dashboard, product list/detail/editor, and catalog detail. Six axe scans had
zero violations (one serious color-contrast probe remained incomplete on two
textareas); five dashboard widths had no horizontal overflow. Compose
stop/start preserved owner/catalog/cost/stock/media records, the worker became
healthy, only loopback proxy access was published, and the proxy egress probe
was denied. Evidence is recorded in
[`../seller-os/pc-first-disposable-certification.json`](../seller-os/pc-first-disposable-certification.json)
and screenshots under `docs/seller-os/artifacts/`.

The permanent backup path and a marker-protected disposable backup/restore
rehearsal are implemented. The disposable mode creates canonical owner,
product, inventory, finance, media, and audit fixtures using the application,
encrypts database/media artifacts with `age`, rejects wrong keys and corrupted
ciphertext, restores into a separately marked no-network PostgreSQL target,
restores media independently, compares canonical rows/decimal precision, and
checks that the source was unchanged. Backup destination is configurable and
writable-path tested; same-volume paths are rejected where host-addressable.
Physical independence now compares the Docker PostgreSQL/media volume backing
storage to the destination, and deliberately remains `UNVERIFIED` if the
Docker Desktop WSL backing VHDX cannot be identified unambiguously.

The encrypted rehearsal could not be executed in the current shell: Docker,
`age`, `age-keygen`, Python, and Node are unavailable; WSL enumeration returns
`E_ACCESSDENIED`; and physical-disk inspection is denied by the sandbox. The
PowerShell scripts parse successfully, but this is not backup/restore test
evidence. The existing randomized runtime PASS does not satisfy the backup
gate. Do not initialize or activate the permanent owner database until the
owner runs the optional disposable rehearsal with approved age tooling and an
independent physical destination, and the report proves both
`backup_restore.status = PASS` and
`destination_independence = VERIFIED_DIFFERENT_PHYSICAL_DISK`. Daily Task
Scheduler registration and Docker Desktop/Windows-reboot recovery remain
HUMAN-controlled/unwitnessed; no task was registered and the unrelated running
PostgreSQL service was not interrupted. Therefore retain
**PC-FIRST DEPLOYMENT — IMPLEMENTED / CERTIFICATION PENDING**. Existing
frontend lint warnings and the initial-bundle budget overage remain recorded;
PR-SOS-09's earlier local certification is unchanged.
