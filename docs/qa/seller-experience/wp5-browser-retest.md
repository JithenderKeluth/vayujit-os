# WP5 — Browser replay and regression evidence

Date: 2026-10-30. **BOUNDED LOCAL DAILY-OPERATIONS VALIDATED**.
Application certification **INCOMPLETE**. [Root causes](wp5-remediation.md) /
[resolution ledger](wp5-resolution.json).

## Isolation and execution

Re-attested the approved WP0A instance: `vayujit-qa-postgres`, PostgreSQL 17.10,
loopback `127.0.0.1:55432`, non-superuser role `vayujit_qa_admin`; instance
`389b97d2-a4cd-4d9b-972e-6bb2bf5785eb`, container
`a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23`.
Only signed, marker/owner/OID-checked `vayujit_qa<16hex>_test` databases. Fresh
migrations reached existing head `20261204_0147`; no WP5 migration. Canonical UI
owner setup/auth and persisted APIs, no mocked auth, live providers or permanent DB.

Production Angular in installed Chrome and Edge, 1440×900 and 390×844. These are
responsive/headless desktop installations, not physical-device or independent
Firefox/WebKit certification. All fixtures are explicitly synthetic. A new QA-only
allowance permits just a credential-free `mock_publisher_v1` destination with exact
synthetic name/configuration; real connectors and execution remain denied. Two new
QA self-tests cover this boundary. Local sandbox accounts remain disabled/missing
credentials and never establish real connectivity.

Before run `69d80dd4ed546298`: actual Chrome desktop/mobile and Edge exploration;
before screenshots/traces/observations at `tmp/qa-seller-browser/<run>/`.
Accepted final browser **`80ca97a5e8d304d5`**: `wp5-retest.json` COMPLETE,
**21 PASS / 0 FAIL**, runtime CLEANED, child exit 0, signed cleanup/absence PASS.
Final evidence has **31 screenshots, four traces and eleven axe document scans**.
Keep authenticated traces private; review/redact before any sharing/publication.

## Actual final browser matrix

Evidence root: `tmp/qa-seller-browser/80ca97a5e8d304d5/`. Exact canonical fixture
UUIDs and assertions are in `wp5-retest.json`. Screenshot paths below use
`wp5-desktop/` unless another context is named; each context also has
`browser-evidence.json` and finalized `trace.zip`.

| # | Actually executed / independently asserted | Result |
| --- | --- | --- |
| 1 | New-owner Dashboard: zero local account/inventory record counts; empty Finance shows UNKNOWN and explicitly is not an accounting ledger. | PASS |
| 2 | Researched/manual synthetic identity without inventory plus a persisted mock publishing destination: configuration not connected channel. | PASS |
| 3 | Synthetic pending/cancelled orders, identical fake-event replay, exactly two records and two reserved units; explicit synthetic labels and visible SKU detail. | PASS |
| 4 | Order → exact Catalog Product → Back → product-filtered inventory; order deep link and reload preserve exact selection. Rounded stored unit/independent line-total warning visible. | PASS |
| 5 | Invalid order UUID yields explicit error and no substituted detail. | PASS |
| 6 | Exact order-list GET 503 seam: unavailable error, no successful empty-history claim; Retry restores persisted order. | PASS |
| 7 | Dashboard populated daily records, synthetic order count, missing financial inputs and source actions; not real revenue/verified connection. | PASS |
| 8 | Financial INR 200.25 sales / 20.05 fees, unknown costs/contribution, synthetic provenance, UTC scope and mutable-snapshot explanation. | PASS |
| 9 | New Finance filter GET 503 clears old figures, no false empty success; Retry and marketplace switch restore correct scope. | PASS |
| 10 | Future period excludes records, invalid period blocks figures, corrected date range restores evidence; reload retains current reporting scope. | PASS |
| 11 | Inspect signal source/evidence, duplicate pending acknowledgement creates one transition, reload preserves status, Open source retains exact product inventory scope. | PASS |
| 12 | Resolve notice locally, retrieve RESOLVED filter, rescan ongoing shortage → REOPENED; never claim source repaired. | PASS |
| 13 | Legitimate stock receipt makes old signal STALE, no active duplicate, stale acknowledgement rejected 409; historical evidence retained. | PASS |
| 14 | Exact scan POST 503 gives safe failure/no saved-success notice; retry works. | PASS |
| 15 | Explicit synthetic cost → -119.80 contribution, extra fee → -120.80; same working snapshot ID replaces metrics, one row, not immutable accounting history. | PASS |
| 16 | Business Agent operational links reach existing Action Center; no run/provider execution, no fake “action completed”; multiple relevant evidence states visible. | PASS |
| 17 | Chrome mobile menu keyboard Enter closes after successful navigation and main receives focus. | PASS |
| 18 | Mobile direct order link/reload, product handoff, provenance and current financial figures; no document overflow. | PASS |
| 19 | Installed Edge desktop and mobile independently render authenticated Dashboard, selected order and persisted Finance context. | PASS |
| 20 | Additional legitimate synthetic sale clears negative contribution; complete scan removes active warning and exposes STALE history. | PASS |
| 21 | Every context has zero unexpected console/page/failed/denied/server errors. | PASS |

Selected screenshot references:

- `004-order-read-outage-not-empty.png` and subsequent daily-status/Finance captures
  (use `browser-evidence.json` for final numeric indices).
- `mobile/001-mobile-navigation-focus.png`.
- `mobile/002-mobile-order-product-context-full.png`.
- `mobile/003-mobile-finance-current-projection-full.png`.
- `wp5-edge-desktop/001-edge-persisted-finance-full.png` and corresponding Edge mobile.
- Full-page synthetic order, stale signal and financial-warning resolution captures
  have descriptive filenames; no index range is falsely counted as independent tests.

Three **exact** injected outages are expected: GET `/api/v1/orders`, GET
`/api/v1/financial/summary`, POST `/api/v1/operations/action-center/scan`, each 503.
No generic error suppression. Earlier “no saved run” 404 was corrected through the
owned nullable-read contract, not waived or hidden by a synthetic run.

## Accessibility and manual evidence

Eleven final document axe scans, all **0 violations / 0 incomplete**:

- Chrome desktop: empty Finance, populated Orders, Dashboard, partial Finance,
  recovered Action Center, qualified synthetic contribution.
- Chrome mobile: Action Center, Orders, Finance.
- Edge desktop/mobile: persisted Finance.

No rules suppressed, no difficult nodes removed. No contrast node needed an exposed
rescan in this final run (`axe_exposed` is empty). Keyboard focus/Enter/navigation
and browser Back/Forward/reload were bounded checks, not every keyboard action.
Manual visual spot review inspected actual desktop Dashboard/Action Center and
mobile order/Finance screenshots for readable dark-on-light text, callouts and link
visibility. This is **not a measured all-pairs contrast or screen-reader/zoom/
forced-colors audit**. Historical global Advanced-link findings and WP4 incomplete
textarea targets remain outside these scans; no blanket WCAG compliance claim.
Not every error variation, policy control or returned-order screen received a
separate browser/axe pass. Return/lifecycle correctness also has persisted API coverage.

## Actual final regressions and quality

| Execution | Actual result / artifact |
| --- | --- |
| Final WP5 + WP4 persisted API | **21 passed**, 0 failure/error/skip; 11 WP5 + 10 WP4; `tmp/qa-wp5-backend/127e6a50e69b46d8/backend-results.xml` |
| Adjacent orders / financial / Action Center / Phase 3B | **35 passed**, 0 failure/error/skip: 8 + 7 + 4 + 16; run `2a9a69a084d9400e` |
| Distinct backend cases above | **56 PASS**, not sum of intermediate reruns |
| Angular full suite | **352 PASS, 80 files** |
| Node QA / Python QA self-tests | **59 / 54 PASS** |
| Focused ESLint; app/spec tsc | PASS |
| Focused Ruff, Black, compileall; PowerShell parser; diff check | PASS |
| Strict mypy five changed backend contracts | One historical schema Field(ne=0) overload error; unchanged HEAD shadow same error; no check weakened |
| Production build | PASS; 519.17 kB initial versus 500 kB warning budget |
| Final runtime and accepted backend cleanup | Normal PASS / exit 0 |
| Independent final audit | 14/14 signed DROPPED and absent; original Docker resources preserved; 20 trace CRCs PASS |

The schema typing diagnostic means intended nonzero-delta validation needs separate
runtime review; no complete global input-validation certification is inferred.
Other four changed routers pass strict typing in that grouped run. Repository-wide
typing/lint, historical source debt and performance/load are not certified here.
Existing FastAPI lifecycle/duplicate-operation warnings were not silenced.

## Preserved failed/intermediate executions

- `f02d10a22e99fe10`: partial before exploration; exact-label locator did not match
  the old label including option text. Corrected test locator, then complete baseline.
- `42f01424504e4ec1`: 6 failed / 13 passed; new order projection and fixture wrongly
  assumed a `MarketplaceOrder.currency` column. Currency actually lives in recorded
  totals metadata. Corrected nullable projection, not schema or invented INR.
- `06ca8b597e5849d7`: 6 failed / 29 passed, same order-currency regression in the
  concurrently started adjacent suite. Fully rerun after correction.
- `3085dc7d3faf43eb`: 19 passed; later extended by obsolete-condition and owned
  empty-state cases. `d2600a63e4ec4feb`: 20 passed, cleanup interrupted; not accepted
  as normal-cleanup final evidence.
- `2f6a8366eea8d82f`: idle runtime stopped before browser execution after the currency
  regression was found. No browser coverage claimed.
- `1ad90f86b79623cb`: 18 browser checks passed, financial negative-resolution failed.
  Corrected actual completed-scan retirement and reran.
- `ceb22a323dbbc102`: 19 checks passed, clean-console gate failed on no-run 404.
  Corrected empty-state read contract; original failed signal retained.
- `ffae3c6aa173617d`: runtime never READY; QA_SESSION_FAILED while a frontend rebuild
  was also running. Underlying startup exception was not retained; build overlap is
  context, not a proven root cause. No browser execution claimed.
- `c9793e585b637ee4`: 20 passed, normal cleanup. Final replay adds explicit Orders
  outage verification and rounded-unit disclosure; final token above is authoritative.
- Intermediate nullable closure typing errors and one old unit assertion expecting
  a one-argument plan read were corrected; original render/persistence assertions
  remain, final build and complete Angular rerun pass.

Seven interrupted drops are disclosed, not relabelled normal cleanup. A 90-second
recovery DROP was directly cancelled by PostgreSQL statement timeout during concurrent
work. After execution settled, the existing guarded exact-token recovery succeeded.
No privilege increase, FORCE, lifecycle edit or unrelated session termination.
`tmp/qa-wp5-final-audit.json` is the independent read-only proof. No raw container
logs persisted; approved credential scan has zero matches. Backup remains parked.

## Windows reproduction

From repository root with the existing approved QA instance and installed dependencies:

```powershell
.\scripts\qa-postgres.ps1 -Action Status
npm.cmd run build --workspace @vayujit/web -- --configuration production
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-seller-wp5.ps1 -Action Backend
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-seller-wp5.ps1 -Action Adjacent
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-seller-wp5.ps1 -Action Browser
```

Wait for READY and its fresh session path; do not rebuild production assets during
runtime startup. Keep that terminal open. In a second PowerShell:

```powershell
node .\qa\wp5-browser-retest.mjs "<exact fresh session.json path>"
```

The replay requests owned shutdown. Wait for normal cleanup, then:

```powershell
.\apps\api\.venv\Scripts\python.exe -m qa.wp5_final_audit
npm.cmd run qa:unit
.\apps\api\.venv\Scripts\python.exe -m unittest discover -s qa/unit -p 'test_*.py'
npm.cmd test --workspace @vayujit/web -- --watch=false
git -c safe.directory=C:/Users/jithe/Documents/vayujit-os diff --check
```

Never substitute an unrelated database URL or reuse a cleaned session. If approved
QA is stopped, only `qa-postgres.ps1 -Action Start` is relevant; do not remove/recreate
other containers. Inspect exact signed lifecycle before any interrupted-drop recovery.
Preserve the single-owner model and all external-write restrictions. Stop after WP5.
