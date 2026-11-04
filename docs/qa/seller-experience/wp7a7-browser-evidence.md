# WP7A-7 authenticated browser evidence

Installed Chrome and Edge are the required engines, at 1440 and 390 pixels.
Each run uses a fresh signed, marker-protected disposable PostgreSQL database,
authenticated synthetic owner, normal application APIs and an outbound-denying
QA proxy. No real provider credentials or provider success are certified.

## Preserved corrective attempts

| Run | Scope | Actual result | Cleanup |
|---|---|---|---|
| `8d71a76efa0d9458` | Seven entries, Chrome desktop | 1 PASS, 5 FAIL, 1 BLOCKED; retained original application/harness failures | CLEANED |
| `e32e94ac4b959e03` | Campaign and Ads, Chrome desktop | 1 BLOCKED, 1 FAIL; exposed legacy-generation contract mismatch and prospective creative readiness failure | CLEANED |
| `16847537e0cbbf86` | Seven entries, Chrome desktop | Five Social/Marketplace checks passed, Campaign selector failed, Ads interrupted by a duplicate dialog handler. No complete trace; not closure evidence. | CLEANED |
| `200b3c9d7f006d13` | Campaign and Ads, Chrome desktop | Two failures: unsupported synthetic failed-state reschedule affordance; wrong snapshot table name after Ads recovery. Trace retained. | CLEANED |
| `664ca90686da7f00` | All seven entries, Chrome/Edge 1440/390 | 23 PASS, 2 FAIL, 3 BLOCKED; unchanged source. Meesho loading race and duplicate Campaign fixture name retained for corrective retest. | CLEANED |

Two earlier setup/interceptor attempts, `363c6f3dfec66d93` and
`1b830f2d7181d8c2`, completed zero scenarios and are not counted as executed tests.
Their cleanup evidence remains retained.

Artifacts live under `tmp/qa-seller-browser/<run>/<context>/`; each completed
context contains screenshots, per-step JSON, signals and `trace.zip`.
Package execution records are in `tmp/qa-wp7a7/execution-<run>.json`.

## Evidence interpretation

Browser runner exit zero means all selected checks were attempted; it does not
mean the assertions passed. Only the strict ledger/gate may close an entry.
Old failures are not overwritten or closed from adjacent backend tests.

Persisted state snapshots expose owned identifiers, canonical amounts, versions,
review/authorization fingerprints, schedule/job references and publication state;
they do not expose credentials or private content bodies. UNKNOWN/live-unverified
states remain explicit. Image identity uses approved immutable Output/Media
identity and integrity metadata, not an invented source-version counter.

Automated axe results and basic focus/Tab/Shift+Tab/HUMAN-checkbox checks are
bounded browser evidence, not a claim of complete WCAG compliance. Historical
manual accessibility gaps remain open.

## Final execution

Run **`daf1450bc1179b3d`**: **28 PASS, 0 FAIL, 0 BLOCKED, 0 PARTIAL**.
Source and production build hashes unchanged from start to finish. Installed
Chrome `156.0.8078.76`, Edge `156.0.4314.58`. Four authenticated contexts,
1440/390 × Chrome/Edge; all seven original IDs passed in every context.
Disposable session status CLEANED; the independent audit confirms this database
and all 18 earlier task-owned databases absent with signed DROPPED records.

Final per-step results, assertion keys and persisted snapshot:
`tmp/qa-seller-browser/daf1450bc1179b3d/wp7a7-browser.json`.
Exact tested source:
`tmp/qa-seller-browser/daf1450bc1179b3d/wp7a7-tested-source.json`.

Each context directory is named `wp7a7-<engine>-<width>`. These screenshot names
exist in each directory (full-page alternatives have `-full.png`):

| ID | Screenshot | Journey endpoints |
|---|---|---|
| R-3feda36d | `002-R-3feda36d-PASS.png` | `/social/posts/:id`, exact review, failed PATCH/retry, HUMAN approval/reload |
| R-55e822d5 | `003-R-55e822d5-PASS.png` | `/marketplaces/overview` → `/marketplaces` → accounts; represented credential states |
| R-551d2f8c | `005-R-551d2f8c-PASS.png` | `/marketplaces/listings/:id/flipkart`, price/readiness/review/authorization |
| R-db243c36 | `007-R-db243c36-PASS.png` | `/marketplaces/listings/:id/meesho`, local pricing/manual boundary/reload |
| R-d6a495d5 | `009-R-d6a495d5-PASS.png` | Amazon workspace create → `/marketplaces/listings/:id/amazon`; actual local editor and authorization |
| L-16 | `011-L-16-PASS.png` | Artifact approval → Campaign handoff → dependency editor → reschedule preview/confirm → reload |
| L-17 | `013-L-17-PASS.png` | Ads wizard/image review → exact campaign detail → controlled fake failure → recovery |

All four traces are `trace.zip` in the corresponding context directories. For
example, inspect locally without contacting a provider:

```powershell
npx.cmd playwright show-trace "tmp/qa-seller-browser/daf1450bc1179b3d/wp7a7-chrome-1440/trace.zip"
```

## Actual accessibility results and manual-review limits

**40 axe scans**, 10 per context: seven final states plus Social exact-image
review, Campaign reschedule review and Ads image readiness. **Zero reported
violations**. **22 incomplete rule/context occurrences**, covering **76 repeated
node occurrences**, remain manual-review items, not PASS results.

| State/rule | Context occurrences | Actual affected selector | Remaining manual verification |
|---|---:|---|---|
| Social image review / `color-contrast` | 4 | `textarea` | Expose/focus/scroll and visually verify text, selection and focus contrast |
| Marketplace overview/accounts / `aria-prohibited-attr` | 4 | `tr:nth-child(n) > td:nth-child(7) > .marketplace-actions[aria-label="Read-only imports"]` | Inspect intended grouping semantics and accessible-name exposure with assistive technology |
| Flipkart final state / `color-contrast` | 2 | `form` | Expose the complete form and inspect painting/contrast; not inferred from other viewports |
| Meesho final state / `aria-prohibited-attr` | 4 | `.inner-tabs` | Verify navigation/group role and name semantics manually |
| Meesho final state / `color-contrast` | 2 | `form` | Expose complete form and inspect contrast |
| Campaign reschedule review / `color-contrast` | 4 | `textarea` | Focus/scroll and verify text and focus contrast |
| Social approved timeline / `color-contrast` | 2 | `.timeline:nth-child(2..5) > strong` | Expose timeline content and verify contrast manually |

These exact results are retained in each context's `browser-evidence.json` under
`axe[].incomplete`; HTML/target details and screenshots are available there.
No axe rule was disabled and no difficult node was removed from scan scope.
Historical manual accessibility gaps are not silently closed by this local
functional gate. This is not full WCAG or screen-reader certification.

Basic focus, Tab/Shift+Tab and explicit HUMAN-checkbox Space behavior were
exercised. No claim is made that every control, keyboard interaction or screen
reader journey has been exhaustively validated.
