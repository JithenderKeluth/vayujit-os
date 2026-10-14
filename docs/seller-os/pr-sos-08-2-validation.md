# PR-SOS-08.2 - Browser Harness Recovery and Final Local Marketplace Certification

## Scope and result

This report closes the local, synthetic marketplace-connectivity certification
for Amazon India and Flipkart. It does not certify seller OAuth, official
provider contracts, live read-only transport, sandbox access, or any external
marketplace write. The single-owner architecture and `vayujit_golden_test`
were not changed.

## A - Canonical authority audit

The existing `MarketplaceAccount`, provider capability contract, Catalog,
MarketplaceListing, MarketplaceOrder, MarketplaceInventory,
MarketplaceSettlement, Financial, Action Center, and `MarketplaceImportJob`
authorities were reused. The import job remains an execution/evidence ledger;
it is not a second catalog, order, inventory, or financial source of truth.

## B - Browser runner recovery

The repository CUA surface could not initialize on Windows with
`helper_unknown_error: apply deny-read ACLs`. No ACL weakening or elevation
bypass was attempted. A minimal reusable direct-CDP runner was added at
`scripts/pr-sos-08-2-browser.mjs`; it uses Node's built-in WebSocket/fetch,
the existing checked-in `axe-core` 4.11.0 bundle, screenshots, network capture,
explicit origins, and non-zero exit codes. The successful run used Chrome
154.0.8037.98 (Chrome DevTools Protocol 1.3) on the existing isolated CDP
endpoint. No new dependency was required.

## C - Fresh process and origin consistency

The API ran from the working tree on `http://127.0.0.1:8004` and Angular on
`http://127.0.0.1:4304`, with the test-only `certification` build replacement
pointing at port 8004. The browser network capture observed API requests to
8004, proving the page was not using the stale port-8000 process. Production
`environment.ts` was not changed.

## D - Disposable database

The marker-protected PostgreSQL database `vayujit_prsos082_test` was upgraded
from the repository base to Alembic head `20261203_0146`. One owner and
synthetic Amazon/Flipkart accounts were created through supported APIs. The
golden database and drifted `vayujit_test` were not used.

## E - Authenticated browser scenarios

The final run (`tmp/pr-sos-08-2/browser-run13/summary.json`) recorded **35/35
browser assertions PASS, 0 FAIL**. This includes the 30 PR-SOS-08.1 scenario
families (authentication, Connection Center/capabilities, account setup,
synthetic evidence/imports, security/idempotency, navigation, refresh/history,
logout/protected routes) plus six responsive widths and keyboard traversal.
Every record contains expected behavior, observed text/state, screenshot path,
and captured network evidence.

| Evidence group | Result |
|---|---:|
| Authentication and account/capability states | 4/4 PASS |
| Amazon + Flipkart catalog/order/inventory/financial imports | 8/8 PASS |
| Idempotency replay and external-mode deny | 2/2 PASS |
| Marketplace/deep-link routes | 10/10 PASS |
| Refresh, back/forward, logout, protected route | 4/4 PASS |
| Responsive checks (320, 360, 390, 768, 1024, 1440px) | 6/6 PASS |
| Keyboard traversal/focus smoke | 1/1 PASS |

The browser observed idempotent replay statuses `202/202` with the same job
ID. `LIVE_READ_ONLY` returned `409` with the authorization-required body and
created no external job. Logout reached `/login`, and a protected deep link
redirected back to the guest route.

## F - Accessibility

`axe-core` 4.11.0 scanned all 12 authenticated states: dashboard, marketplace
overview, Connection Center, Amazon, Flipkart, listings, inventory, orders,
settlements, analytics, financials, and Action Center. Final result: **0
violations, 6 incomplete/manual-review findings, and 12/12 states scanned**.
The six incomplete results are retained as manual-review evidence; they are
not claimed as automated WCAG conformance.

The in-scope findings fixed before the final run were malformed definition-list
groups, non-focusable horizontally scrollable tables, and duplicate main
landmarks on the dashboard. The affected templates now use valid `dt`/`dd`
groups, labelled keyboard-focusable table regions, and the application shell's
single main landmark.

## G - Security and owner isolation

Synthetic mode was the only provider mode exercised. Credentials remained
write-only/encrypted, account and import queries were owner-scoped, and the
external transport boundary stayed fail-closed. No OAuth, real provider call,
supplier action, procurement, payment, listing publication, or marketplace
mutation occurred.

## H - Regression and quality evidence

- Focused `test_pr_sos_08_connectivity.py`: **5 passed**.
- PR-SOS-01 through PR-SOS-08 PostgreSQL matrix: **45 passed** (79 existing
  deprecation warnings; no failures).
- Angular: **63 test files, 224 tests passed**.
- Angular lint: **0 errors, 2 pre-existing lifecycle warnings** in unrelated
  campaign dialogs.
- Production Angular build: passed; existing advisory initial-bundle budget
  warning (514.20 kB vs 500 kB) remains.
- Ruff: passed for the focused PR-SOS-08 Python files.
- Black: 4 focused files unchanged.
- `compileall`: passed for focused backend files.
- Alembic `current` and `upgrade head`: `20261203_0146 (head)`.
- `git diff --check`: exit 0 (line-ending normalization warnings only).
- Strict mypy remains blocked by one pre-existing unrelated Pydantic typing
  error at `commerce/schemas.py:259` (`Field(ne=0, ...)`); no PR-SOS-08.2
  typing error was introduced.

## I - Changed files in this milestone

- `scripts/pr-sos-08-2-browser.mjs` - reusable direct-CDP certification runner.
- `apps/web/angular.json` - test-only `certification` configuration.
- `apps/web/src/environments/environment.certification.ts` - isolated API
  origin replacement used only by the certification build.
- `apps/web/src/app/marketplaces/marketplace-accounts.component.ts` - valid
  definition lists, labelled/focusable import regions.
- `apps/web/src/app/marketplaces/flipkart-workspace.component.ts` and
  `marketplace-settlements.component.ts` - labelled/focusable table regions.
- `apps/web/src/app/marketplaces/marketplace-home.component.ts` - labelled
  operational table region.
- `apps/web/src/app/operations/dashboard.component.ts` - removes nested main
  landmark.
- `docs/seller-os/pr-sos-08-2-validation.md` and linked roadmap/matrix notes.

## J - Reproducibility

Run the disposable stack, then execute:

```powershell
$env:PRSOS_WEB_ORIGIN='http://127.0.0.1:4304'
$env:PRSOS_API_ORIGIN='http://127.0.0.1:8004'
$env:PRSOS_CDP_URL='http://127.0.0.1:9223'
$env:PRSOS_OUTPUT='tmp/pr-sos-08-2/browser-rerun'
node scripts/pr-sos-08-2-browser.mjs
```

No stale application process is required by the runner; the certification API
and Angular processes are started explicitly, and origins/output are explicit.
The current validation stack was intentionally left running because other
unrelated local processes existed and no process was terminated.

## K - Real-provider boundary and remaining gaps

Official Amazon/Flipkart OAuth, seller identity, provider contract approval,
real pagination/rate limits, webhooks, sandbox acceptance, and marketplace
publication remain separate HUMAN/deployment gates. The six axe incomplete
items require manual assistive-technology review if a full WCAG certification
is desired. The two lint warnings, bundle advisory, and unrelated strict-mypy
error remain outside this bounded milestone.

## Final classification

**PR-SOS-08 - FULLY VALIDATED (LOCAL / SYNTHETIC MARKETPLACE CONNECTIVITY /
NO REAL PROVIDER CALLS)**

This classification is local only. It must not be read as certification of
real Amazon or Flipkart connectivity or publication.
