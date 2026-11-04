# Seller Experience WP4 — Catalog, Inventory and Marketplace Readiness

Date: 2026-10-30. Work began 2026-10-29. Status: **WP4 IMPLEMENTED /
BOUNDED LOCAL JOURNEY VALIDATED / ACCESSIBILITY MANUAL REVIEW REMAINS**.
Application certification remains **INCOMPLETE**. Stop after WP4.

## Outcome and evidence policy

The supported Catalog-to-marketplace **preparation** journey now works in an
authenticated Chrome desktop/mobile replay against migrated, persisted disposable
PostgreSQL data. This is not marketplace connection, acceptance or publication
certification. Original failures, intermediate failed retests and unrelated dirty
worktree changes are preserved. No production `.env`, dependency, ownership model
or database migration was added for WP4.

Read together with [browser retest](wp4-browser-retest.md), [machine-readable
resolution](wp4-resolution.json), [original findings](browser-findings.json),
[backlog](prioritized-completion-backlog.md) and [coverage](browser-journey-coverage.md).
Local synthetic traces can contain authenticated session material; keep them
private and review/redact before sharing. No credentials are copied into these reports.

## Browser-first reproduction and root causes

Accepted before run: `5ba740c21fc2a356`,
`tmp/qa-seller-browser/5ba740c21fc2a356/wp4-before.json`; desktop/mobile screenshots
and finalized traces are retained alongside it. Both manual and converted products
were inspected before production corrections. Earlier fixture-script failures are
not counted as successful before coverage.

| Finding / newly verified issue | Root cause and bounded correction | Final disposition |
| --- | --- | --- |
| SE-BROWSER-010: Catalog mutation error replaces workspace | A shared error branch replaced already loaded detail after a recoverable mutation error. Retain product, form values and h1; show an inline result. Initial-load failure still fails closed and offers Retry. | RESOLVED_LOCAL_BROWSER_WP4 |
| SE-BROWSER-018: empty private image picker is a dead end | No point-of-need link to the existing upload authority. Add exact product return context, refresh/read-error feedback and explicit attachment. Async option loading required the Angular select value accessor; a ready uploaded image is selected but never auto-attached. | RESOLVED_LOCAL_BROWSER_WP4 |
| SE-BROWSER-019: master quantity confused with ledger stock | Entry/detail labels did not distinguish metadata from canonical inventory. Clarify this distinction and link exact product/variant to existing review and HUMAN-confirmed opening stock, then the product-filtered ledger. Do not copy metadata into stock. | RESOLVED_LOCAL_BROWSER_WP4 |
| SE-WP4-VARIANT-001: edits omit stable key | Existing backend `VariantUpdate` requires `variant_key`; the old UI sent version/title/archive without it. Preserve the persisted key and version; edit SKU/title/price/currency through the existing service. Pending guards prevent repeated local actions. | RESOLVED; browser, Angular and persisted API regressions |
| SE-WP4-MANUAL-COST-001: manual product has no meaningful economics next step | The product-level economics projection needs opportunity lineage, but the existing generic economic context/input/snapshot/calculation engine supports owned Product IDs. Add a small manual-product estimate editor using that engine, not a second calculator or fake research/supplier identity. | RESOLVED for explicit assumed acquisition subtotal only; full profitability is not established |
| SE-WP4-COST-REPLAY-001: conflicting quote-input replay / concurrent duplicates | Existing quote-input reuse did not compare material payload. Validate replay equality and product scope; transaction advisory locks serialize same-key input and context snapshot creation. Identical retry reuses, changed payload with same key conflicts. | RESOLVED; persisted positive/negative/concurrent tests |
| SE-WP4-DECIMAL-001: JSON numeric projection loses exact high-precision amounts | Legacy numeric JSON can pass SQL Decimal through a binary Number. Add backward-compatible `exact_amounts` decimal strings on calculation detail. Manual estimate UI displays these exact canonical amounts; absent exact amounts remain UNKNOWN. | RESOLVED; subcent/high-value persisted regression |
| SE-WP4-CHANNEL-001: content destinations, price and sales semantics mixed | Product Channels combined SEO destinations and marketplace aliases, and attributed channel-wide settlement totals/fees to one product, including use as price. Separate content destinations, normalize `amazon_in` to Amazon, show exact seller account/draft/remote evidence independently, use draft intended price only. Product sales/fees/profit remain UNKNOWN absent appropriate evidence. | RESOLVED for tested local preparation states |
| SE-WP4-CONTEXT-001: route/async handoff can lose product or variant | Subscribe to parameter changes, reset scoped state and reject late reads. Validate variant belongs to product, retain explicit stock scope, include variant inventory in the product filter, reject stale/invalid cost context without substitution. Destroyed estimate components cannot navigate back on late completion. | RESOLVED within tested bounded navigation and regression scope |

Source entry points: `catalog-workspace.component.ts`, `catalog.service.ts`,
`catalog-cost-estimate.component.ts`, `catalog-cost-estimate.service.ts`,
`media-upload.component.ts`, `opening-stock.component.ts`,
`unified-inventory.component.ts`, `product-channel-view.component.ts`,
`economic_service.py` and `economic_router.py` (exact paths in the resolution JSON).

## Manual-Catalog economics disposition

Supported chain: owned Product → existing economic context → explicit **ASSUMED**
acquisition input and reason → immutable input snapshot → existing calculation.
No supplier, quote evidence, ProductOpportunity or HUMAN selection is manufactured.
Currency defaults to INR and remains explicit; quantity/unit are explicit. Empty
cost is UNKNOWN; entered zero is a deliberate assumption, not a missing-value fallback.

Content-derived keys make an identical retry reuse the saved scenario. Changed
material inputs create a different scenario; the old one remains selectable and
reloadable by `cost_context_id`. Historical results are labelled historical, not
verified/current supplier terms. Invalid or stale context does not silently load
another estimate. Arithmetic is unchanged and remains backend-authoritative.

The browser independently checked 12 × INR 100.125 = INR 1,201.50. The API regression
also checked 12 × 9999999999.00000001 = 119999999988.00000012 without losing decimal
lineage. Freight, fees, GST/tax, returns, advertising and overhead stay UNKNOWN
unless legitimately supplied elsewhere. This subtotal is **not** net profit,
margin, full landed cost, live commercial readiness or permission to proceed.

Linked opportunity products retain the existing product economics/Business Agent
authority and research return route. Manual supplier association, automatic quote
import and full manual-product profitability remain unsupported here; the page
explains the missing lineage rather than creating it. SE-HANDOFF-004 is therefore
partially addressed, not blanket-closed.

## Stock, media and marketplace safety

- Private images use the existing local upload/media authority and authenticated
  preview. A UUID-only product return parameter is accepted; arbitrary return URLs
  are not. Upload is separate from explicit Catalog attachment. Anonymous preview
  was rejected with 401 in the browser replay.
- Variant opening stock verifies exact product/variant ownership and identity.
  An incompatible pending review or invalid variant does not silently become
  parent-product stock. Review and physical-count HUMAN confirmation are required.
  Double click produced one item and one HUMAN stock movement, not two. Cancel/edit
  review produced no new movement. Explicit zero stock stayed zero/out of stock.
- Product master quantity remains metadata. Installation-wide inventory summaries
  are labelled separately from a product-filtered list that includes variants.
- Amazon/Flipkart local drafts reuse canonical readiness and HUMAN review. An
  incomplete draft cannot be approved. Correcting legitimate fields enables only
  local review; a subsequent draft edit invalidates that review. No remote listing
  was created. Existing Meesho preparation is preserved, not newly certified.
- Product Channels shows destination, recorded seller account, raw connection/
  validation state, local draft/HUMAN review and remote listing evidence separately.
  A configured destination is not a connected/authorized marketplace. No real
  connection-pending/verified-provider transition was simulated as certification.

## Files changed in WP4

Production:

- `apps/api/vayujit_api/intelligence/economic_service.py`
- `apps/api/vayujit_api/intelligence/economic_router.py`
- `apps/web/src/app/catalog/catalog-workspace.component.ts` and `.css`
- `apps/web/src/app/catalog/catalog.service.ts`
- `apps/web/src/app/catalog/catalog-cost-estimate.component.ts` (new)
- `apps/web/src/app/catalog/catalog-cost-estimate.service.ts` (new)
- `apps/web/src/app/media/media-upload.component.ts`
- `apps/web/src/app/products/product-form.component.ts`
- `apps/web/src/app/products/product-details.component.ts`
- `apps/web/src/app/marketplaces/opening-stock.component.ts`
- `apps/web/src/app/marketplaces/unified-inventory.component.ts`
- `apps/web/src/app/marketplaces/product-channel-view.component.ts`

Tests/harness:

- `apps/api/tests/test_seller_wp4.py` (new; 10 test cases)
- `apps/web/src/app/catalog/catalog-wp4.spec.ts` (new)
- `apps/web/src/app/catalog/catalog-cost-estimate.service.spec.ts` (new)
- `apps/web/src/app/catalog/catalog.service.spec.ts`
- `apps/web/src/app/catalog/catalog-economics-presentation.spec.ts`
- `apps/web/src/app/media/media-upload-context.spec.ts` (new)
- `apps/web/src/app/marketplaces/opening-stock.component.spec.ts`
- `qa/wp4-before.mjs`, `qa/wp4-browser-retest.mjs`,
  `qa/wp4_final_audit.py`, `qa/unit/wp4-safety.test.mjs` (new)
- `qa/fixture_server.py`, `qa/safety.mjs`, `scripts/test-seller-wp4.ps1` (new script)
- The three WP4 reports plus original findings, backlog and journey coverage updates.

Some files already contained WP1–WP3 edits. This list identifies WP4 semantic work,
not every dirty file in the repository. Existing unrelated backup changes were
not touched. No new migration, dependency installation, branch, commit or push.

## Results and remaining limits

Final accepted results: **80 backend cases, 339 Angular cases, 57 Node QA self-tests,
54 Python QA self-tests and 18 grouped authenticated browser checks passed**.
No failed/skipped case in the accepted backend/browser runs; intermediate failures
are retained and explained in the browser report. Focused ESLint, app/spec tsc,
Ruff, Black, compileall, PowerShell parsing, production build and diff whitespace
checks passed. Strict mypy passes the changed economics service. The shared legacy
economic router still has 42 missing-return-annotation diagnostics; untouched HEAD
shadow with correct module path has 43. The edited detail function is now annotated;
this is not a repository-wide typing pass. Prior WP3 sourcing typing debt remains
outside WP4. Existing initial bundle budget warning remains: 518.31 kB / 500 kB.

Six document axe scans: zero violations; seven **incomplete color-contrast node
occurrences** remain after individual scrolling/rescanning (textarea backgrounds
reported partially obscured). They are neither confirmed contrast failures nor
passes. Manual review, full keyboard/screen-reader, zoom/forced-colors and physical
device testing remain incomplete. No WCAG compliance claim.

Visual review also observed adjacent `Product record` / `Edit product` links with
insufficient spacing (SE-WP4-UX-001, LOW/P3). Both are individually accessible; keep
as a polish item, not a release-blocking correctness defect or silently resolved.
Long Catalog content remains a hierarchy/navigation recommendation.

Original findings **010/018/019** are now resolved locally. Original **009/012/017/020**
and suspected global Advanced navigation contrast remain open. Historical findings
and earlier resolutions are preserved. Whole-app coverage, live discovery,
marketplace OAuth/API contracts, provider connectivity, sandbox/production
publication, populated real financial events and full cross-owner security matrix
are not certified by WP4.

Final read-only audit independently verified **23/23 WP4 databases DROPPED and absent**,
18 retained trace archives with valid CRC, the original 10 Docker containers and
original networks/volumes preserved, zero approved credential matches in scanned
evidence, no raw container logs persisted. Eleven interrupted DROPPING lifecycles
required existing exact-token guarded recovery; one ACTIVE leftover required normal
guarded deletion after instance attestation recovered. These were not labelled
normal cleanup. Final accepted backend/browser runs cleaned normally with exit 0.
No FORCE/drop-prefix/session-termination workaround was used.

Stop here for review. PC-first backup remains parked; no activation or next package
is authorized by this result.
