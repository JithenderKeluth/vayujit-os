# VAYUJIT OS seller capability matrix

Status is based on the repository as audited for PR-UX-01C. `BACKEND_ONLY` and
`NOT_APPLICABLE` are deliberate outcomes, not defects: provider adapters,
background workers, audit ledgers, and security controls do not need a seller
page of their own.

| Milestone | Capability | Intended user | Backend authority / route | Angular route / component | Integration | Status | UX location | Priority / slice | Validation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PR-0 | Authentication and owner session | Seller | `/api/v1/auth/*`, `AuthService` | `/login`, `/setup`, `AuthPageComponent` | `apiCredentialsInterceptor` | COMPLETE | Entry and account shell | P0 / 01A | Auth and owner-isolation tests |
| PR-0 | Brand/business context | Seller | `/api/v1/brands`, `BrandService` | Shared shell, brand selectors | `BrandService` | COMPLETE | Shell context header | P0 / 01A | Shell tests and refresh checks |
| GP | Dashboard and workspace metrics | Seller | `/api/v1/dashboard`, `OperationsService` | `/dashboard`, `DashboardComponent` | Dashboard + journey APIs | COMPLETE | Overview | P0 / 01B | First-use, active-goal, attention, metric-link, and journey tests |
| GP-1/2 | Business goals and research runs | Seller | `/api/v1/intelligence/business-agent/goals`, `/runs` | `/intelligence/business-agent`, `BusinessAgentWorkspaceComponent` | `BusinessAgentService` | COMPLETE | Business goals | P0 / 01B | Business Agent regression suite |
| PR-1/2 | Product opportunities | Seller | Product-opportunity routers | `/intelligence/product-opportunities`, `ProductOpportunityWorkspaceComponent` | `ProductOpportunityService` | COMPLETE (supported scope) | Product research | P0 / 01B | Empty/loading/list/detail/evidence/comparison/selection tests |
| PR-3 | Supplier discovery | Seller | Supplier discovery/research routers | `/intelligence/cross-marketplace`, `CrossMarketplaceSupplierComponent` | Supplier research services | IMPLEMENTED / LOCAL-VALIDATED | Suppliers | P0 / 01C | PR-3/PR-4.2 regressions; authenticated responsive browser checks |
| PR-4.2 | Due diligence and HUMAN shortlist | Seller | Shortlisting and due-diligence routers | `/intelligence/supplier-shortlisting`, `/intelligence/due-diligence`, `SupplierDueDiligenceComponent` | Supplier services | IMPLEMENTED / REVIEW-GATED | Suppliers / Decisions | P1 / 01C | Due-diligence integration + authenticated responsive browser checks |
| PR-5A/B/C | Commercial evidence and economics | Seller | Commercial readiness, landed-cost, unit-economics routers | `/intelligence/sourcing-economics`, `SourcingEconomicsWorkspaceComponent` | Sourcing services | IMPLEMENTED / LOCAL-VALIDATED | Profitability | P0 / 01D | 36-test PR-5B→PR-8C matrix; 217 Angular tests |
| PR-6A/B/C | Decision readiness and HUMAN decision | Seller | Decision readiness/synthesis/recommendation routers | `/intelligence/sourcing-economics`, `SourcingEconomicsWorkspaceComponent` | Intelligence services | IMPLEMENTED / REVIEW-GATED | Decisions | P0 / 01D | Goal-scoped brief, stable idempotency, HUMAN decision regressions |
| PR-7A/B/C | Engagement drafts and supplier responses | Seller | Engagement, email-delivery, response routers | `/intelligence/supplier-engagement`, `SupplierEngagementWorkspaceComponent` | Sourcing services | IMPLEMENTED / LOCAL-NO-SEND | Supplier engagement | P1 / 01E | Focused engagement tests; authenticated responsive browser checks |
| PR-8A/B/C | Reassessment, comparison, procurement readiness | Seller | Reassessment/comparison/procurement routers | `/intelligence/sourcing-economics`, `SourcingEconomicsWorkspaceComponent` | Sourcing services | IMPLEMENTED / REVIEW-GATED | Decisions / Readiness | P1 / 01D | PR-8 regression matrix; no automatic ranking or purchase |
| PR-9A/B | Controlled live-source certification | Seller | `/api/v1/intelligence/live-supplier-certification/*` | Sourcing economics workspace | PR-9A/B APIs | PARTIAL | Evidence / Readiness | P1 / 01E | PR-9A/B certification suites |
| PR-9C | Supplier intelligence continuation | Seller | Canonical supplier research/search and ProductOpportunity authorities; `/api/v1/intelligence/cross-marketplace/*` | `/intelligence/business-agent` continuation panel; `/intelligence/cross-marketplace` | Business Agent durable run/brief projection | IMPLEMENTED / LOCAL-VALIDATED | Research → Suppliers | P1 / 09C | 86-test PR-3/4.2/7/8/9A/9B matrix; Business Agent lineage assertions; Angular suite |
| PR-SOS-01.1 | Catalog certification: secure images, variants, economics, accessibility boundary | Seller | `/api/v1/catalog/*`, `/api/v1/media/*`, canonical economics/ProductOpportunity authorities | `/catalog`, `/catalog/:id` | CatalogService + ProductService + Media authority | IMPLEMENTED / CERTIFICATION PENDING | Sell / Catalog | P0 / SOS-01.1 | 6 persisted PostgreSQL integration tests; 62 Angular files / 223 tests; production build, lint, migration and security-boundary checks; post-change browser/axe evidence pending |
| PR-SOS-01.2 | Certification infrastructure recovery and final catalog browser closure | Seller | Existing catalog, media, product, draft, approval, and auth authorities | `/catalog`, `/catalog/:id`, `/products/new`, `/media/upload` | CDP browser harness + canonical APIs | IMPLEMENTED / CERTIFICATION PENDING | Sell / Catalog | P0 / SOS-01.2 | Fresh Alembic head, fixture lifecycle, 18 catalog/product + 12 media tests; authenticated CDP journey and responsive evidence; two-owner/axe blockers recorded |
| PR-SOS-01.3 | Owner isolation architecture decision and accessibility certification | Seller / system | `ck_users_single_owner`, authenticated owner dependencies, catalog/media authorities | Existing catalog/product/media routes | Canonical APIs + disposable installation probes | IMPLEMENTED / CERTIFICATION PENDING | Sell / Catalog / Security | P0 / SOS-01.3 | 22 focused auth/catalog/media tests; two isolated PostgreSQL installations; foreign brand/media/preview IDs return 404; axe/equivalent unavailable offline; same-DB two-owner N/A |
| PR-SOS-01.4 | Accessibility certification and final catalog release gate | Seller / system | Existing catalog, Product, MediaAsset, variant, listing-draft, readiness, HUMAN approval, and `ck_users_single_owner` authorities | `/catalog`, `/catalog/:id`, `/products/new`, `/products/:id`, `/products/:id/edit` | axe-core + CDP + canonical APIs | FULLY VALIDATED / LOCAL-ONLY | Sell / Catalog / Accessibility | P0 / SOS-01.4 | Zero axe violations across list/empty/detail/create/edit/media/variant/draft/readiness/HUMAN states; 18 PostgreSQL passes; 62 Angular files / 223 tests; keyboard, stale-media, private-preview, responsive, static, and migration checks |
| PR-SOS-02 | Amazon India account, catalog mapping, listing preparation, separate HUMAN review and single-use execution authorization | Seller | `/api/v1/marketplaces/amazon/*`, canonical `MarketplaceAccount`/`MarketplaceListing`/`GeneratedArtifact` authorities | `/marketplaces/amazon`, `/marketplaces/listings/:id/amazon` | `AmazonCommerceConnector` + `FakeAmazonSPAPITransport` + durable review/auth tables | FULLY VALIDATED / LOCAL FAKE-ONLY | Sell / Amazon | P0 / SOS-02 | PR-SOS-02.2: incomplete-listing blocker and back/forward/deep-link browser scenarios passed; 5 focused controls + 11 adjacent Amazon tests; 62 Angular files / 223 tests; axe 0 violations/incomplete on complete and blocked states; Ruff/Black/mypy/build/lint/compileall/diff-check passed; live SP-API intentionally excluded |
| PR-SOS-03 | Flipkart account, catalog mapping, listing preparation, server readiness, HUMAN review, single-use execution authorization, fake submission and reconciliation | Seller | `/api/v1/marketplaces/flipkart/*`, canonical `MarketplaceAccount`/`MarketplaceListing`/`GeneratedArtifact`/catalog/media authorities | `/marketplaces/flipkart`, `/marketplaces/listings/:id/flipkart` | `FlipkartCommerceConnector` + deterministic fake transport + shared marketplace review/auth tables | FULLY VALIDATED / LOCAL FAKE-ONLY | Sell / Flipkart | P0 / SOS-03 | PR-SOS-03.1: 26/26 authenticated browser scenarios; axe 0 violations/incomplete; responsive and keyboard traversal; fresh + predecessor PostgreSQL migration replay; 14 adjacent regressions + 3 focused tests; 62 Angular files / 223 tests; real Flipkart API/sandbox/publication intentionally excluded |
| PR-SOS-04 | Unified inventory, append-only stock ledger, channel-SKU mappings, atomic reservations, multi-channel order events, reconciliation, and overselling protection | Seller | `/api/v1/inventory/*`, `/api/v1/orders/*`, canonical Product/catalog/MarketplaceAccount authorities | `/marketplaces/inventory`, `/marketplaces/orders`, `UnifiedInventoryComponent`, `UnifiedOrdersComponent` | Owner-scoped inventory/order routers + fake-provider event boundary | FULLY VALIDATED / LOCAL FAKE-ONLY | Sell / Operations | P0 / SOS-04 | Fresh disposable Alembic chain at `20261020_0160`; 8 focused PostgreSQL tests + 14 adjacent PR-SOS-01–03 regressions; all 30 authenticated direct Chrome/CDP scenarios; axe-core 4.11 zero violations/incomplete; 320/360/390/768/1024/1440 responsive checks; keyboard traversal; Angular 62 files / 223 tests; no live channel writes |
| PR-SOS-05 | Unified sales facts, fee evidence, cost attribution, profitability, refunds, settlement reconciliation, alerts, durable calculation snapshots, and Business Agent read-only guidance | Seller | `/api/v1/financial/*`, canonical MarketplaceOrder/Fee/Refund/Settlement/Product authorities | `/marketplaces/financials`, `FinancialWorkspaceComponent` | Owner-scoped financial projection, immutable/idempotent event lineage, effective-dated UNKNOWN-aware cost evidence, durable snapshots; synthetic fixture boundary | IMPLEMENTED / LOCAL CERTIFICATION PENDING | Sell / Financials | P0 / SOS-05 | Fresh merged Alembic head `20261201_0144`; 4 focused financial tests + 8 PR-SOS-04 tests; canonical order/line projection; Angular pre-change baseline 223/223, post-template rerun 221/223 with 2 unrelated existing intelligence-test timeouts; build/lint; focused Ruff/Black/strict-mypy/compileall; dedicated authenticated browser/axe matrix remains pending; no live financial writes |
| GP | Guided commerce journey | Seller | `/api/v1/commerce-journeys/*` | Shared journey components | `CommerceJourneyService` | COMPLETE | Shell, dashboard, workflow pages | P0 / 01B | Journey projection and next-action navigation tests |
| GP | Evidence trust presentation | Seller | Canonical evidence classifications | Shared `EvidenceCardComponent`, `StatusBadgeComponent` | Typed inputs only | COMPLETE | Any evidence surface | P0 / 01A | Trust-label tests |
| GP | Loading/empty/error/blocked states | Seller | API response and error contracts | `state-components.ts` | Reusable standalone components | COMPLETE | All workflows | P0 / 01A | UX foundation tests |
| Core | Products, channels, inventory, orders | Seller | Product and marketplace routers | `/products`, `/marketplaces/*` | Product/marketplace services | PARTIAL | Sell | P1 / 01B/F | Route and marketplace regressions |
| Core | Content, media, campaigns, advertising | Seller | AI, media, campaigns, ads routers | `/ai/*`, `/media`, `/campaigns`, `/ads` | Domain services | PARTIAL | Create / Grow | P1 / 01F | Existing Angular suites |
| Core | Operations, approvals, audit, health | Operator / seller admin | `/api/v1/operations/*` | `/operations/*`, `/approvals`, `/execution-history` | `OperationsService` | COMPLETE | Advanced | P1 / 01A | Operations tests |
| Core | Provider adapters and workers | System | Provider/worker services | None required | Internal only | NOT_APPLICABLE | Advanced diagnostics only | P2 / 01F | Backend/security tests |
| Core | Owner isolation and HUMAN controls | Seller / system | Auth dependencies and canonical authorities | No frontend authority; visibility only | Interceptor + route guards | COMPLETE | Cross-cutting | P0 / 01A | Security and regression suites |

## PR-UX-01C coverage notes

- Supplier discovery and due-diligence now have context-safe, authenticated UX
  on top of the existing canonical authorities. The product opportunity and
  supplier IDs are resolved through owner-scoped API projections; a URL ID is
  never treated as proof of ownership or product membership.
- The UI renders provider mode, freshness, confidence, contradictions,
  verification gaps, unknown commercial values, and review boundaries returned
  by the API. It does not calculate risk or change trust labels.
- Local-fixture browser evidence is explicitly labelled `LOCAL_FIXTURE`; it is
  not live market evidence. Provider-dependent live readiness remains an
  operational prerequisite.

## PR-UX-01D coverage notes

- The sourcing economics workspace uses the journey-scoped decision-brief
  authority whenever a `journey_id` is present, so budget and goal context do
  not fall back to another owner goal.
- Landed-cost and unit-economics values are rendered from canonical immutable
  projections. Assumptions, partial calculations, warnings, unknowns, and
  `NOT_COMPARABLE` states remain visible; Angular does not calculate or rank
  suppliers.
- HUMAN decision controls use a stable journey/product/action idempotency key.
  Launch preparation is visibly disabled until the canonical brief is ready;
  research and reconsider actions remain available while blocked.
- PR-UX-01D is locally validated with a persisted disposable PostgreSQL
  fixture and authenticated Chrome checks at 360, 390, 768, 1024, and 1440
  CSS pixels. See [`pr-ux-01d-validation.md`](pr-ux-01d-validation.md).

## PR-UX-01E coverage notes

- The controlled supplier-engagement workspace is available at
  `/intelligence/supplier-engagement`. It projects the selected goal,
  ProductOpportunity, supplier, contact, HUMAN decision, engagement draft,
  approval state, authorization boundary, supplier responses, and procurement
  readiness from the existing canonical APIs.
- Draft preparation, approval, cancellation, response review, and history
  controls are HUMAN-labelled and owner-scoped. The certification route does
  not send RFQs, issue live authorizations, contact suppliers, or execute
  procurement. Provider-unavailable and deterministic-test restrictions are
  shown as explicit blockers.
- Local disposable fixtures are marked `DETERMINISTIC_TEST` and preserve
  unknown commercial values, raw response provenance, correlation, and
  extraction hashes. See [`pr-ux-01e-validation.md`](pr-ux-01e-validation.md).

## PR-SOS-01.4 coverage notes

- axe-core 4.11.0 was installed through the configured npm registry and run in
  an authenticated isolated Chrome session against disposable PostgreSQL
  state. Every required catalog state had zero axe violations; incomplete
  offscreen geometry records remain transparently documented in the report.
- Shared contrast tokens, skip-link focus restoration, breadcrumb labels,
  status-badge semantics, and product-editor landmarks were corrected without
  changing business or approval authorities.
- Keyboard, responsive, private-media, stale-version, HUMAN approval, and
  migration evidence is recorded in [`pr-sos-01-4-validation.md`](../seller-os/pr-sos-01-4-validation.md).

## Coverage rules

- A frontend link is only listed where the route exists in `app.routes.ts`.
- A status of `PARTIAL` means the workflow is reachable but still needs a
  dedicated UX slice, not that the backend is missing.
- The frontend never calculates commercial values or changes trust labels; it
  renders canonical API results and blockers.

## PR-UX-01F coverage notes

- The authenticated shell exposes one semantic `main` landmark per protected
  route. The dashboard page participates in the same landmark contract as
  routed workspaces, while the skip link still targets routed content.
- Sourcing economics repeatable lists use index-qualified keys so duplicate
  evidence codes, unknowns, limitations, and scenario labels do not emit
  Angular duplicate-key warnings at runtime.
- PR-UX-01F browser certification covers the supported dashboard, Business
  Agent, Product Opportunities, product detail, supplier intelligence, due
  diligence, sourcing economics, and Supplier Engagement routes with
  disposable persisted fixtures. See [`pr-ux-01f-validation.md`](pr-ux-01f-validation.md).

## PR-UX-01F status

The local/no-external stabilization scope is validated. Full automated axe,
screen-reader lab coverage, and live-provider certification remain separate
follow-up work and are not implied by this milestone.

## PR-9C coverage notes

- The Business Agent consumes the existing canonical `supplier.discovery` step
  output and projects only durable supplier-intelligence observations into the
  run result and decision brief. It does not recalculate confidence, risk,
  freshness, commercial values, or supplier ranking.
- The continuation link carries the canonical ProductOpportunity ID and opens
  the owner-scoped Cross-marketplace workspace. Supplier selection,
  verification, due diligence, commercial decisions, engagement, and external
  execution remain separate HUMAN-controlled authorities.
- `LOCAL_FIXTURE` and `LIVE_READ_ONLY` remain distinct. External writes are
  always reported as an empty list in this continuation projection. Missing
  provider data, contradictions, stale evidence, and unknown commercial values
  remain visible rather than being filled with inferred values.
- PR-9C was validated locally against disposable PostgreSQL state. No golden
  database, supplier contact, RFQ, procurement, payment, marketplace write, or
  live acquisition was performed.
- PR-UX-01B–F items remain backlog work and are not presented as complete.

## PR-SOS-01 coverage notes

- `/catalog` lists active owner-scoped Products and gives the seller one clear
  next action: open a catalog workspace. `/catalog/:id` shows canonical product
  identity, opportunity lineage, variants, supplier associations, channel
  drafts, readiness blockers, and HUMAN review state.
- Listing draft APIs never call a marketplace connector and persist no remote
  listing ID. The only terminal state is `APPROVED_FOR_FUTURE_SUBMISSION`; it
  does not authorize publication.
- ProductOpportunity conversion is selection-gated and replay-safe. Catalog
  provenance records the shortlist decision and preserves unknown commercial
  values rather than treating them as zero.
- Product images are selected from the owner-scoped secure MediaAsset library;
  the catalog stores only association metadata and never accepts remote image
  URLs or fetches arbitrary content. Economics are projected from canonical
  Product Opportunity context and remain explicitly unavailable when no
  sourcing calculation exists.

## PR-SOS-05.1 certification closure

The financial workspace is **FULLY VALIDATED (LOCAL / SYNTHETIC / NO LIVE
EXTERNAL MUTATIONS)**: 7 focused financial tests, 22 adjacent PR-SOS-01–04
regressions, 30 authenticated Chrome scenarios, and 12 axe scans with zero
violations/incomplete checks. See
[`../seller-os/pr-sos-05-1-validation.md`](../seller-os/pr-sos-05-1-validation.md).

| PR-SOS-06 | Business Agent Operational Intelligence & Action Center | Seller | `/api/v1/operations/action-center/*` over Catalog, Inventory, Orders, Financial authorities | `/operations/action-center`, dashboard/navigation Action Center link | Owner-scoped signal projection, deterministic priority, HUMAN lifecycle, briefing, notifications, conservative policy | FULLY VALIDATED / LOCAL-ONLY | Operations / Business Agent | P0 / SOS-06 | 4 focused PostgreSQL passes; 33 adjacent backend passes; 30/30 authenticated browser scenarios; 12 axe-core 4.11 scans with 0 violations/incomplete; Angular 62/223; build/lint/static/migration checks; no live external mutations |

## PR-SOS-06 coverage notes

- Operational signals preserve source authority, resource/version, evidence
  quality, freshness, confidence, explanation, recommended action, rule
  version, and stable owner-scoped fingerprints. The Action Center never
  mutates canonical Catalog, Inventory, Orders, Financial, Supplier, or
  marketplace records.
- HUMAN acknowledge, snooze, resolve, reopen, idempotency, notification
  read-state, emergency-stop, AI-impersonation denial, and external-mutation
  fail-closed behavior are certified against disposable PostgreSQL state.
- See [`../seller-os/pr-sos-06-validation.md`](../seller-os/pr-sos-06-validation.md)
  for the A–Z report and browser/axe evidence.

## PR-SOS-07 coverage notes

- Production readiness reuses the authenticated Operations Control Center and
  `/api/v1/system/*` health/release projections; no competing monitoring or
  approval authority was introduced.
- The one-seller/one-installation/one-database boundary and
  `ck_users_single_owner` are preserved. Production settings fail closed for
  loopback/default database endpoints, local filesystem media, missing backup
  destinations, and insecure public URLs.
- Backup checksum/path confinement, media recovery, maintenance mode,
  emergency-stop, structured correlation logs, provider default-deny switches,
  and existing HUMAN controls remain in force. See
  [`../seller-os/pr-sos-07-validation.md`](../seller-os/pr-sos-07-validation.md).

| PR-SOS-08 | Authorized Amazon India & Flipkart connectivity, read-only imports & reconciliation | Seller | `/api/v1/marketplaces/connectivity/*`, `/api/v1/marketplaces/accounts/{id}/imports*` | `/marketplaces/accounts` Connection Center | Capability classification, synthetic catalog/order/inventory/financial imports, durable checkpoints, idempotency, stale/reconciliation summary, external-mode deny | FULLY VALIDATED (LOCAL / SYNTHETIC / NO REAL PROVIDER CALLS) | Marketplace accounts / Business Agent warnings | P0 / SOS-08 | 35 browser assertions, 12 axe states, 45 adjacent PostgreSQL regressions, Angular suite/build/lint; real provider gates remain pending |

## PR-SOS-08 coverage notes

- The import ledger is an execution/evidence projection only; canonical
  `MarketplaceListing`, `MarketplaceOrder`, `MarketplaceInventory`,
  `MarketplaceSettlement`, Catalog, and Financial authorities remain the
  sources of truth. Replays reuse the same job and canonical remote identity.
- Account responses distinguish `AUTHORIZATION_REQUIRED`, `DEGRADED`,
  `EXPIRED`, and `UNVERIFIED`; synthetic validation never claims a real
  `CONNECTED` seller account. Credentials remain encrypted/write-only and are
  never returned to Angular.
- Provider contracts are labelled `UNVERIFIED` until official Amazon/Flipkart
  seller certification is separately completed. `LIVE_READ_ONLY` and all live
  writes are denied by default. See
  [`../seller-os/pr-sos-08-validation.md`](../seller-os/pr-sos-08-validation.md).

## PR-SOS-08.1 certification notes

Connection Center provider capability cards, explicit synthetic/external
transport labels, loading/refresh states, and accessible import labels are in
the frontend. Focused and adjacent PostgreSQL regressions plus the full
Angular suite pass. This historical pending note was superseded by the
PR-SOS-08.2 direct-CDP browser closure; no real-provider certification is
claimed. See [`../seller-os/pr-sos-08-1-validation.md`](../seller-os/pr-sos-08-1-validation.md).

## PR-SOS-08.2 certification notes

The reusable direct-CDP browser harness recovered authenticated certification
without weakening Windows ACLs or requiring a new dependency. The final run
passed 35/35 browser assertions, six responsive widths, keyboard traversal,
and all 12 axe states with zero violations. The PR-SOS-01 through PR-SOS-08
PostgreSQL matrix passed 45/45 on disposable state. The capability is now
**FULLY VALIDATED (LOCAL / SYNTHETIC MARKETPLACE CONNECTIVITY / NO REAL
PROVIDER CALLS)**. Real provider OAuth, transport, and marketplace writes are
still not certified. See
[`../seller-os/pr-sos-08-2-validation.md`](../seller-os/pr-sos-08-2-validation.md).

| PR-SOS-09 | First-seller launch preparation & deployment reference | Seller / Operations | Existing `/api/v1/system/*`, Catalog, Marketplace, Financial, Backup, Action Center authorities | `/operations/launch-readiness` plus canonical Catalog, Marketplace, Financial, Operations workspaces | Owner profile/readiness projection, deployment preflight, VPS reference topology, backup/recovery checklists, explicit HUMAN handoff | FULLY VALIDATED (LOCAL / PRODUCTION-LIKE FIRST-SELLER PREPARATION / NO LIVE DEPLOYMENT) | Operations / Action Center | P0 / SOS-09 | 39/39 warning-matrix assertions; 67/67 focused backend regressions; 227/227 Angular tests; authenticated nginx/CDP screenshots and network trace; axe 0 violations/incomplete; migration head; Ruff/Black/compileall/diff-check; no host/provider/marketplace writes |

## PR-SOS-09 coverage notes

### PR-SOS-09.1 certification update (2026-10-14)

Production-like API/worker/web/proxy/Postgres startup, encrypted backup and
separate restore, 16 PR-SOS-07/08/09 PostgreSQL regressions, and the witnessed
36/36 authenticated browser run are recorded in
[`../seller-os/pr-sos-09-1-validation.md`](../seller-os/pr-sos-09-1-validation.md).
The capability remains **IMPLEMENTED / LOCAL CERTIFICATION PENDING** while
warning-state browser coverage, the complete launch axe matrix, fresh-profile
CDP availability, and repository-wide strict mypy remain open.

- Launch readiness is a read-only projection. It does not persist a second
  onboarding, go-live, marketplace, financial, or approval authority.
- Production configuration rejects insecure URLs/cookies, loopback/default
  database roles, missing encryption/session/backup settings, and disposable
  filesystem storage. The safe configuration report is redacted.
- The reference Compose topology keeps PostgreSQL private, exposes only the
  reverse proxy, uses health checks/restart/resource controls, and keeps
  provider/external mutations deny-by-default. `deploy-reference.sh apply`
  requires an explicit HUMAN environment acknowledgement.
- No production deployment, external provider call, supplier contact, RFQ,
  procurement, payment, marketplace mutation, or golden-database change is
  performed by PR-SOS-09. See
[`../seller-os/pr-sos-09-validation.md`](../seller-os/pr-sos-09-validation.md).

### PR-SOS-09.2 certification update (2026-10-14)

The launch-readiness capability now includes canonical warning cards with
severity, evidence, and same-origin remediation links. Browser evidence passed
29/29 assertions, six responsive widths, keyboard/history/auth checks, and a
12-state axe scan with zero violations. Angular passed 227/227 and the
PR-SOS-07/08/09 PostgreSQL matrix passed 16/16. Classification remains
**IMPLEMENTED / LOCAL CERTIFICATION PENDING** until dedicated warning fixtures,
fresh-profile/proxy browser coverage, and Python quality-tool execution are
available. Full evidence is recorded in
[`../seller-os/pr-sos-09-2-validation.md`](../seller-os/pr-sos-09-2-validation.md).

### PR-SOS-09.3 certification update (2026-10-14)

PR-SOS-09.3 corrected the production-like edge topology and authenticated
bootstrap throttling. Local proxy certification passed 29/29 browser checks,
12 axe states with zero violations/incomplete results, six responsive widths,
keyboard/history/logout/deep-link checks, 227/227 Angular tests, focused
PostgreSQL regressions, and changed-file Ruff/Black/mypy checks. The status
remains **IMPLEMENTED / LOCAL CERTIFICATION PENDING** because independent
marker-protected warning fixtures for every readiness dimension and a fresh
Chromium profile were not available. External infrastructure and real
provider/business authorization remain outside this local capability.
See [`../seller-os/pr-sos-09-3-validation.md`](../seller-os/pr-sos-09-3-validation.md).

### PR-SOS-09 final warning-fixture closure (2026-10-14)

The independent marker-protected warning-dimension matrix is now complete.
Each canonical readiness warning has a deterministic fixture, browser-positive
assertion, legitimate negative-resolution assertion, screenshot, and proxy
network evidence. Mandatory external-mutation and HUMAN-signoff warnings stay
visible by design. The final local classification is **FULLY VALIDATED (LOCAL /
PRODUCTION-LIKE FIRST-SELLER PREPARATION / NO LIVE DEPLOYMENT)**. The only
remaining release gates are HUMAN-controlled production deployment, real
provider/marketplace authorization, TLS/DNS, secret-manager inputs, and
off-host backup. See [`../seller-os/pr-sos-09-validation.md`](../seller-os/pr-sos-09-validation.md).

### PC-first operational deployment preparation (2026-10-15)

| Capability | State | Evidence / limitation |
| --- | --- | --- |
| Windows PC local Compose profile | DISPOSABLE RUNTIME/BROWSER VALIDATED; BUSINESS ACTIVATION PENDING | 17/17 runtime, network, security, migration, and persistence checks; 25/25 authenticated Chrome checks; six axe scans with zero violations; five dashboard widths fit. Owner data DB was not started. |
| PC first-owner activation | PREPARED / HUMAN ACTIVATION REQUIRED | Unique generated configuration; one-owner constraint preserved; no synthetic records; exact typed phrase required; permanent owner DB intentionally not started. Activate only after the disposable encrypted backup/restore gate passes. |
| PC encrypted backup and restore | IMPLEMENTED / CERTIFICATION PENDING | Permanent-profile backup plus marker-protected disposable backup/restore rehearsal are implemented. The runner supports a configurable destination, validates writability, checks for paths inside host-addressable data volumes, and conservatively maps Docker Desktop storage to a physical disk or reports `UNVERIFIED`. Not executed in this shell: Docker, `age`, `age-keygen`, Python, and Node are unavailable; WSL and physical-disk inspection are denied. No scheduler task was registered. |
| External marketplace/provider operations | DENIED / NOT CONNECTED | Runtime network egress disabled; no Amazon/Flipkart accounts or real connectivity claimed; live mutations remain off. |

This PC profile is separate from and does not reopen PR-SOS-09. Retain
**PC-FIRST DEPLOYMENT — IMPLEMENTED / CERTIFICATION PENDING** until encrypted
backup and independent restore are validated on an approved separate disk.
Docker Desktop/Windows reboot recovery is also not yet witnessed.
