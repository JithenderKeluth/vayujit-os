# PR-SOS-08.1 — Marketplace Connectivity Browser, Accessibility & Regression Certification

## Scope and safety

This report certifies the local, synthetic marketplace-connectivity boundary only.
Amazon India and Flipkart accounts, OAuth consent, provider credentials, live
read-only transport, sandbox access, marketplace writes, supplier actions,
payments, and production deployment were not used. The one-owner architecture
and `vayujit_golden_test` database were preserved.

## A — Authority audit

`MarketplaceAccount`, the existing provider connectors, catalog/listing/order/
inventory/settlement authorities, financial projections, Action Center, and
single-owner identity remain canonical. `MarketplaceImportJob` is only a
durable import execution/evidence ledger; it does not become a second source
of truth.

## B — Fresh environment

The repository API was started from the working tree against the marker-protected
database `vayujit_prsos081b_test` on PostgreSQL at `127.0.0.1:5432`. The fresh
process listened on `127.0.0.1:8001` because an older repository Uvicorn process
continued to hold port 8000. `GET /health` returned 200 and
`GET /api/v1/marketplaces/connectivity/capabilities` returned Amazon and
Flipkart with `external_writes=false`. Alembic upgraded the disposable database
from empty schema to `20261203_0146 (head)`. No golden database was touched.

## C — UI closure changes

The Connection Center now displays the provider capability contract returned by
the API, clearly labels synthetic availability and denied live transport, shows
loading and refresh states, exposes accessible per-account import labels, and
keeps external-write messaging visible. Existing account, import, reconciliation,
and owner-scoped history authorities were reused.

Changed frontend files:

- `apps/web/src/app/marketplaces/marketplace.service.ts`
- `apps/web/src/app/marketplaces/marketplace-accounts.component.ts`
- `apps/web/src/app/marketplaces/marketplaces.css`
- `apps/web/src/app/marketplaces/marketplace-accounts.component.spec.ts`

## D — Focused backend evidence

The focused PR-SOS-08 suite passed **5/5** PostgreSQL-backed scenarios. It
covers explicit capabilities, all four synthetic operations, durable checkpoints
and provenance, idempotent replay, external-mode replay protection, owner/job
isolation, job detail, reconciliation, and completed-job cancellation.

## E — Adjacent regression matrix

The selected PR-SOS-01 through PR-SOS-08 PostgreSQL matrix passed **45/45**:
catalog, Amazon controls, Flipkart controls, inventory/orders, financials,
Action Center, readiness, and connectivity. The run produced 79 existing
deprecation warnings and no failures.

## F — Frontend quality

- Focused Connection Center test: **1/1 passed**.
- Full Angular suite: **63 test files, 224/224 tests passed**.
- Angular lint: **0 errors, 2 pre-existing warnings** in unrelated campaign
  dialog lifecycle declarations.
- Production build: passed; initial bundle 514.20 kB against a 500 kB warning
  budget (14.20 kB advisory overage, no build failure).
- Ruff: passed on changed PR-SOS-08 Python files and tests.
- Black: 4 files unchanged.
- Strict mypy: passed on the 4 focused Python files.
- `compileall`: passed.
- `git diff --check`: exit 0; only existing line-ending normalization warnings
  were reported.

## G — Accessibility and responsive gate

`axe-core` 4.11.0 is already present in the approved web dev dependencies.
Authenticated Chrome/CDP and axe scans were **not executed** in this run. The
computer-use harness failed during initialization with
`windows sandbox failed: helper_unknown_error: apply deny-read ACLs`, and the
normal frontend API origin (8000) was occupied by an older repository process;
the fresh current-code API was therefore intentionally kept on 8001 rather than
running a mismatched browser session. No automated WCAG claim is made.

The following 30 browser scenarios remain **NOT EXECUTED**: login, Connection
Center/disconnected states, synthetic account setup and imports, catalog/order/
inventory/financial evidence, idempotency, stale/rate-limited/partial states,
Action Center warning, denied external writes, refresh/history/deep link, and
logout protection. The required widths (320, 360, 390, 768, 1024, 1440px),
keyboard traversal, focus restoration, and axe states are also pending the
working browser harness.

### Browser scenario ledger

| # | Scenario | Expected | Observed | Result |
|---:|---|---|---|---|
| 1 | Login | Authenticated seller reaches the app | CDP harness did not initialize | NOT EXECUTED |
| 2 | Open Connection Center | Current route renders | CDP harness did not initialize | NOT EXECUTED |
| 3 | Disconnected Amazon | `AUTHORIZATION_REQUIRED` is clear | Browser state unavailable | NOT EXECUTED |
| 4 | Disconnected Flipkart | `AUTHORIZATION_REQUIRED` is clear | Browser state unavailable | NOT EXECUTED |
| 5 | Connection requirements | HUMAN/provider prerequisites are visible | Browser state unavailable | NOT EXECUTED |
| 6 | Synthetic labeling | Local fixture mode is explicit | Browser state unavailable | NOT EXECUTED |
| 7 | Configure synthetic Amazon | Account can be created locally | Browser state unavailable | NOT EXECUTED |
| 8 | Verify Amazon status | Synthetic/unverified status persists | Browser state unavailable | NOT EXECUTED |
| 9 | Configure synthetic Flipkart | Account can be created locally | Browser state unavailable | NOT EXECUTED |
| 10 | Provider capabilities | Amazon/Flipkart capability cards are visible | Browser state unavailable | NOT EXECUTED |
| 11 | Synthetic catalog import | Job completes with evidence | Browser state unavailable | NOT EXECUTED |
| 12 | Catalog evidence | Canonical listing evidence is visible | Browser state unavailable | NOT EXECUTED |
| 13 | Unmapped SKU | Missing mapping is surfaced | Browser state unavailable | NOT EXECUTED |
| 14 | Synthetic order import | Canonical order is projected | Browser state unavailable | NOT EXECUTED |
| 15 | Canonical order | Order remains owner-scoped | Browser state unavailable | NOT EXECUTED |
| 16 | Duplicate import | Same idempotency key replays one job | Browser state unavailable | NOT EXECUTED |
| 17 | Idempotency result | No duplicate canonical record appears | Browser state unavailable | NOT EXECUTED |
| 18 | Inventory discrepancy | Observation/reconciliation is reviewable | Browser state unavailable | NOT EXECUTED |
| 19 | Financial evidence | Provenance and unknowns are visible | Browser state unavailable | NOT EXECUTED |
| 20 | Settlement status | Settlement evidence is reviewable | Browser state unavailable | NOT EXECUTED |
| 21 | Expired authorization | Expired state is clearly blocked | Browser state unavailable | NOT EXECUTED |
| 22 | Missing permission | Permission state is not overstated | Browser state unavailable | NOT EXECUTED |
| 23 | Rate-limited import | Failure/retry guidance is visible | Browser state unavailable | NOT EXECUTED |
| 24 | Partial import | Partial evidence and recovery action are visible | Browser state unavailable | NOT EXECUTED |
| 25 | Import history/detail | Durable job metadata is inspectable | Browser state unavailable | NOT EXECUTED |
| 26 | Action Center warning | Failed/stale evidence creates HUMAN review signal | Browser state unavailable | NOT EXECUTED |
| 27 | External writes denied | Live modes fail closed | Browser state unavailable | NOT EXECUTED |
| 28 | Refresh/history | State survives refresh/back/forward | Browser state unavailable | NOT EXECUTED |
| 29 | Authenticated deep link | Owner/account context is preserved | Browser state unavailable | NOT EXECUTED |
| 30 | Logout/protected route | Logout redirects and protected route is denied | Browser state unavailable | NOT EXECUTED |

The API equivalents for scenarios 3, 6, 8, 10, 11, 14, 16, 17, 20, 25,
27, and owner isolation passed in the PostgreSQL regression suite; those API
results are not counted as browser passes.

### Axe result ledger

Connection overview, disconnected Amazon, disconnected Flipkart, synthetic
connected, import controls, in-progress, completed, failed, partial, history,
detail, and validation/error states: **NOT EXECUTED**. Violations: none
reported because no scan ran; incomplete results: all requested states remain
pending browser-harness recovery.

## H — Security boundaries

Synthetic imports are local deterministic fixtures only. `SANDBOX` and
`LIVE_READ_ONLY` fail closed with 409 and `X-VAYUJIT-External-Write: denied`;
live write is not exposed. Account credentials remain write-only, owner/account
queries are scoped, canonical inventory quantities are not overwritten, and
Action Center projections remain advisory/HUMAN-review signals.

## I — Real-provider boundary

Real Amazon/Flipkart connectivity is **NOT YET CERTIFIED**. A later activation
requires HUMAN-approved provider contracts, OAuth/scopes or approved secret
manager credentials, seller identity verification, transport allowlists,
rate/retry policy, and a separately authorized write milestone.

## J — Final classification

**PR-SOS-08 — IMPLEMENTED / LOCAL CERTIFICATION PENDING.**

The synthetic API, database, frontend tests, adjacent regressions, migration,
static checks, and build passed. Local browser/CDP and axe evidence is the only
remaining PR-SOS-08.1 certification blocker; no provider or marketplace action
was performed.
