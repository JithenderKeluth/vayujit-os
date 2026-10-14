# PR-SOS-03 — Flipkart Seller Integration, Catalog Mapping & Controlled Listing Operations

**Date:** 2026-10-11  
**Classification:** **PR-SOS-03 - FULLY VALIDATED (LOCAL / FAKE FLIPKART TRANSPORT / NO LIVE MARKETPLACE MUTATIONS)**

This report records the bounded implementation and validation completed in the
local repository. The fake provider is deterministic and network-free. No real
Flipkart credential, API request, listing publication, supplier action, RFQ,
procurement, payment, golden-database change, commit, or push was performed.

## A–Z certification report

### A. Roadmap reconciliation

The repository already contained a substantial Flipkart adapter, router, worker,
projection, route, and workspace. The missing PR-SOS-03 boundary was the
server-authoritative HUMAN review and separate single-use execution
authorization between readiness and `/submit`. The roadmap and capability
matrix now identify PR-SOS-03 as fully validated locally; real Flipkart API
certification remains a separate external milestone.

### B. Existing authority reuse

Flipkart continues to use `MarketplaceAccount`, `MarketplaceListing`, `Product`,
`GeneratedArtifact`, `MarketplaceVariant`, `MarketplaceMediaMapping`,
`MarketplacePrice`, audit events, idempotency, connector, and worker authorities.
No second catalog or marketplace product master was introduced.

### C. Changed files

- `apps/api/vayujit_api/commerce/models.py` — shared marketplace-scoped review
  and execution-authorization models.
- `apps/api/vayujit_api/commerce/flipkart_router.py` — review, latest-review,
  authorization issue/latest/revoke, fingerprint-bound submit, emergency-stop
  and live-mode guards; draft pricing is persisted locally before submission.
- `apps/api/alembic/versions/20261019_0159_marketplace_listing_controls.py` —
  additive migration for the shared controls.
- `apps/web/src/app/marketplaces/flipkart-workspace.component.ts` — explicit
  Review exact listing → Authorize local execution → Confirm and submit flow,
  status and revoke controls.
- `apps/api/tests/test_pr_sos_03_flipkart_controls.py` — persisted PostgreSQL
  HUMAN review, idempotent authorization, replay, and stale-context regressions.
- `docs/seller-os/pr-sos-03-validation.md`, roadmap, capability matrix, and
  `docs/commerce/flipkart-marketplace.md`.

### D. Flipkart API contract verification

Official current Flipkart seller API requirements, authentication, permissions,
hosts, rate limits, and production/sandbox behavior were **not verified** in
this local milestone. The connector therefore remains conservative and fake-
transport only; no real-provider certification is claimed.

### E. Seller connection

Existing account create/validate/revalidate/enable/disable/credential replace
and removal routes remain owner-scoped. The focused account lifecycle passed.
Credential values are accepted only through write-only server routes and are not
returned to Angular, diagnostics, or audit metadata.

### F. Credential security

No credentials were used. Existing encryption and redaction boundaries remain in
place. No provider payload or secret is exposed by the new review/auth routes.

### G. Marketplace data model

The new generic `MarketplaceListingReview` and
`MarketplaceListingExecutionAuthorization` tables bind marketplace, owner,
account, listing, artifact/version, payload fingerprint, review actor, expiry,
status, and result. Foreign keys and unique idempotency constraints are additive.

### H. Catalog mapping

Flipkart draft creation still requires an owner-scoped active Product, Brand, and
approved GeneratedArtifact. Variant and media endpoints preserve product/listing
ownership and reject invalid associations.

### I. Listing preparation

Existing title, SKU, category, attributes, variants, ordered media, and INR
pricing routes remain in use. Draft pricing is a local persisted preparation
step and never calls the provider before controlled submission.

### J. Readiness validation

Server readiness continues to block disabled/unvalidated accounts, missing
credentials, inactive products, missing approved artifacts, category/SKU,
variants, media, and price. HUMAN review cannot be created while any blocker
remains.

### K. HUMAN review

`POST /listings/{id}/review` requires authenticated confirmation and stores an
immutable payload snapshot/fingerprint. Repeating the exact review is
idempotent. The review is bound to the current artifact version and listing
context; changes produce a new fingerprint and stale authorization rejection.

### L. Execution authorization

`POST /execution-authorizations` requires the exact approved review. Authorization
is single-use, expiring, revocable, owner/account/listing/marketplace bound, and
idempotent by key. Submission requires its UUID and exact payload fingerprint.

### M. Submission adapter

Flipkart submission remains `FlipkartCommerceConnector` plus its deterministic
fake transport. The API rejects emergency-stop or live-mode execution, records
safe provider status, consumes the authorization, and returns no credentials or
raw provider payloads.

### N. Fake-provider scenarios

The existing adapter/worker suites cover deterministic categories, account
lifecycle, fake submission, reconciliation, imports, throttling and worker
boundaries. New tests cover missing authorization, HUMAN review, idempotent
authorization replay, consumed replay, and stale listing rejection.

### O. Failure and reconciliation

Provider statuses remain explicit (`accepted`, `succeeded`, `rejected`,
`unknown`, `throttled`) and reconciliation remains required for asynchronous or
ambiguous outcomes. No duplicate execution is permitted through an already
consumed authorization.

### P. Economics integration

No parallel profitability calculator was added. Existing normalized pricing,
settlement, fee, and profitability projections remain the authority; unknown
Flipkart fees are not fabricated.

### Q. Worker safety

Existing Flipkart worker and generic publishing safety tests passed. The new
authorization tables are not a bypass for generic workers; `/submit` performs
the same current authorization checks before the fake connector call.

### R. Owner isolation

All new queries include the authenticated owner, marketplace, account, and
listing. Cross-owner resource IDs therefore resolve as not found through the
existing owner dependency and listing lookup.

### S. Migrations

The additive migration `20261019_0159_marketplace_listing_controls` is the sole
new migration and `alembic heads` reports it as the single head. Focused tests
use disposable PostgreSQL reset state; `vayujit_golden_test` was not modified.
The historical 0005 JSONB literal-rendering defect was repaired without changing
its revision or semantics. Fresh online replay and upgrade from
`20261010_0151` both reach `20261019_0159 (head)`. Offline `--sql` now passes
0005 but remains blocked later by the pre-existing 0007 JSONB seed; this
offline-only limitation is documented in the PR-SOS-03.1 closure report.

### T. Angular workspace

The Flipkart workspace now exposes the approval boundary in order: Refresh
readiness, Review exact listing, Authorize local execution, Confirm and submit,
or Revoke authorization. The current review and authorization status are shown
next to the actions, with safe error messaging.

### U. Authenticated browser validation

The complete authenticated isolated Chrome/CDP journey was executed: **26/26
PASS, 0 FAIL, 0 BLOCKED, 0 NOT EXECUTED**. Detailed scenario evidence is in
`docs/seller-os/pr-sos-03-1-validation.md` and reproducible artifacts are under
`tmp/ux-browser/`.

### V. Axe, keyboard, and responsive checks

The authenticated post-fix axe scan returned zero violations and zero
incomplete findings (615 passes); the protected/login scan also returned zero
violations (65 passes). Responsive widths 320/360/390/768/1024/1440 and
Tab/Shift+Tab/skip-link/Escape evidence passed. The synthetic Enter/Space
helper was inconclusive and is documented as a follow-up limitation; no
complete WCAG compliance claim is made.

### W. Backend and frontend regressions

- Focused Flipkart + PR-SOS-03 PostgreSQL suite: **3 passed, 8 warnings**.
- PR-SOS-01 + PR-SOS-02 + PR-SOS-03 regression matrix: **14 passed, 30 warnings**.
- Existing Flipkart adapter/API/E2E/integration/worker subset: included in the
  14 passing tests.
- Angular suite: **62 test files, 223 tests passed**.
- Angular lint: passed with two pre-existing lifecycle warnings.
- Angular production build: passed; existing initial bundle budget warning
  (509.18 kB vs 500 kB) remains and was not suppressed.

### X. Static quality gates

Focused Ruff, strict mypy on changed commerce files, Black, Python compileall,
TypeScript compilation through Angular build, and `git diff --check` passed.
The migration head check passed. Repository-wide historical warnings are not
reclassified as PR-SOS-03 defects.

### Y. Golden database, external effects, and limitations

No real Flipkart/Amazon calls, credentials, listing publication, price or
inventory mutation, supplier contact, RFQ, procurement, payment, or marketplace
write occurred. `vayujit_golden_test` was not touched. Official Flipkart API
compatibility remains outside this local certification; authenticated browser
and axe evidence are closed by PR-SOS-03.1.

### Z. Final classification

**PR-SOS-03 - FULLY VALIDATED (LOCAL / FAKE FLIPKART TRANSPORT / NO LIVE MARKETPLACE MUTATIONS)**

Real Flipkart API contract/sandbox/publication certification remains outside
this local milestone. PR-SOS-04 was not started.
