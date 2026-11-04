# WP6 — Cross-application UX and quality remediation

Date: 2026-10-30. **WP6 IMPLEMENTED / SCOPED FIXES BROWSER-VALIDATED / QUALITY CLOSURE PENDING.**
Application certification remains **INCOMPLETE**. Do not start WP7.

## Baseline and actual corrections

Read the original findings/backlog/target experience, WP1–WP5 remediation, browser
reports and resolution ledgers, and prior accessibility evidence. Preserve their
original observations, intermediate failures and remaining capability gaps.
Fresh Chrome reproduction `c23dd3b07a3c442f` confirmed all three remaining original
findings before their contracts changed. Baseline PNGs and traces survive cleanup.

| Finding | Exact cause and seller impact | Small correction and verification |
| --- | --- | --- |
| SE-BROWSER-009, mobile video layout | Actual 851px document at 390px. Grid-item intrinsic widths, two narrow wizard columns and unbroken diagnostic strings forced content beyond the screen despite a table scroll wrapper. | Shrinkable host/panels/grid children, wrapping strings, one mobile wizard column; retain the full 760px table in a named keyboard-scrollable region. Chrome 360/390/768/1440, Edge 390/1440 and reload passed. No generation/provider operation executed. |
| SE-BROWSER-017, creative prerequisites | Shared selector deliberately queried active products but said “No products yet” when persisted draft products existed. Creating duplicates did not solve eligibility. | Say “No active products available”, explain draft/archived exclusion, link Catalog, name selectors and provide canonical read Retry. No eligibility/approval rule relaxed. SEO, Images and Video exercised desktop/mobile; the same Product becomes eligible only after its required description and normal UI activation. |
| SE-BROWSER-020, authenticated deep link | Guard discarded RouterState URL; successful form unconditionally navigated Dashboard. | Preserve a validated internal return URL, query and fragment through guard/setup/login; replace Login after successful sign-in. Reject external, protocol-relative, encoded slash/backslash, control, traversal, outlet and auth-loop paths. Owner/resource authorization remains backend-owned. Actual fresh Chrome and Edge desktop/mobile sign-in returned to the exact persisted Catalog product. |
| Shared mobile navigation contrast | Light navigation palette was embedded inside the mobile menu's white surface. | Reuse the existing dark sidebar palette, not a new design system. Expanded Advanced menu measured 12.37:1 in final replay; Enter/Escape/navigation focus passed. This is bounded palette verification, not all-theme WCAG certification. |
| Historical Autonomous overflow | Broad replay measured 468px at 390px, correlating with intrinsic control widths and rigid grid tracks. | Shrinkable grid children/inputs, wrapping and bounded minimum tracks. Final 360/390/1440 document-width checks pass without starting a mission or changing policy. |
| Catalog action spacing | Product record / Edit product lacked a shared gap. | Reuse existing actions class; both targets and original links preserved. Catalog screenshots/keyboard inspection retained. |
| Inventory zero-delta / mypy | Pydantic does not enforce extra Field(ne=0); isolated runtime reproduction accepted zero, and strict mypy rejected that keyword. | Explicit field validator rejects zero; existing signed integer bounds unchanged. Persisted API rejects zero with422 and leaves stock/version unchanged. Nine WP6 cases plus adjacent inventory tests pass; focused strict schema mypy is clean. |
| Initial bundle warning | Three Advertising workspaces were eagerly imported by root routes, loading their implementation for every seller page. | Lazy-load the same components, retaining paths and auth guards. Initial bundle 519.17 → **422.71 kB**, below unchanged500kB budget. Chrome/Edge Ads/optimization/marketing routes render; underlying service failures remain open, not hidden as build success. |

## Money: investigation, not an arbitrary schema change

The known unit-price mismatch is **data-model precision combined with rounding at
different stages**, not currency conversion and not merely a display formatter.
`FakeOrderLine` accepts Decimal100.125; ingestion computes two-unit total200.250;
`MarketplaceOrderItem.unit_price` and `total_price` persist Numeric(12,2), yielding
100.13 and200.25. Multiplying the rounded projection would yield200.26 and is wrong.
WP6 independently asserts the persisted values/reload/synthetic provenance. Existing
UI explicitly calls the unit projection rounded and warns not to reconstruct totals.
Recorded totals remain authoritative; no financial arithmetic, historical amounts,
currency conversion or persisted monetary semantics changed. The underlying source
precision/storage/correlation contract remains **OPEN/P2** and needs a reviewed policy
and migration evidence before a change. Do not claim sub-paise accounting certification.

Finance clearly says current mutable projection / not an accounting ledger, explains
scope and source freshness, and retains UNKNOWN profitability with missing costs.
Same-scope FinancialCalculationSnapshot recalculation overwrites metrics/lineage;
recorded source events do not make that projection immutable accounting history.
QA-P3-GAP-001 remains open. No accounting ledger or generic execution engine added.

## New/confirmed service blockers: deliberately not certified

Actual authenticated production-build browser reads failed on Video/Social and Ads.
Read-only signed/OID/marker-verified inspection of final disposable database found:

- `video_generations`: ORM requires `storyboard_version`, `style_version`; database
  has `storyboardversion`, `styleversion` instead. This confirms/extends the old
  video migration defect; it did not block shared auth/Catalog startup.
- `ad_campaigns`: missing ORM columns `correlation_id`, `failure_category`,
  `next_retry_at`, `retry_after_seconds`. `/ads/overview` selects this ORM entity.
- Additional Ads optimization/anomalies/comparison500s and one comparison502 were
  observed. The inspection proves schema drift, not that every Ads failure shares
  a fully established root cause.

These need a separately reviewed data-preserving migration repair, existing-data
upgrade/downgrade/rollback tests and supported read regressions. No metadata.create_all,
table recreation, fake success, empty-result masking or historical migration editing
was used. Retain **SE-WP6-VIDEO-001/HIGH/P1**, **SE-WP6-ADS-001/HIGH/P1** and the
unclassified Ads502 recovery observation. This prevents quality/application closure.

## Changes and architecture

Production Angular: `auth/auth-return-url.ts` (new), `auth.guards.ts`,
`auth-page.component.ts`; `shared/business-entity-selectors.component.ts`;
`ai/ai-video.component.ts`; `intelligence/autonomous-research.component.ts`;
`app.component.css`, `app.routes.ts`; `catalog/catalog-workspace.component.ts`.
Backend: only `commerce/schemas.py` (localized nonzero validator). No new migration,
dependency, business authority, financial formula, approval system or production env.

Tests: new `auth/auth-wp6.spec.ts`, shared selector spec additions, new
`apps/api/tests/test_seller_wp6.py` (9 cases). Existing full Angular suite preserved.
QA: `wp6-before.mjs`, `wp6-browser-retest.mjs`, `wp6_schema_probe.py`,
`wp6_final_audit.py`, `unit/wp6-safety.test.mjs`, Windows runner
`scripts/test-seller-wp6.ps1`; bounded changes to session/exploration helper,
fixture allowlist, safety/proxy and shared read-only WP4 audit package selector.
Four WP6 reports and original findings/backlog/coverage addenda updated.

WP6 alone adds an empty-payload local Product activation allowance in the QA proxy.
It does not authorize marketplace publication or relax backend product requirements;
initially missing description correctly returned409. Two safety self-tests cover
exact route/origin/method and payload denial; historical phases remain unchanged.
The existing dirty worktree, WP1–5 and parked backup work are preserved.

## Validation and disposition

**28 backend cases PASS** (9 WP6,11 WP5,8 inventory/orders); **370 Angular PASS**;
**61 Node /54 Python QA self-tests PASS**. Final production build, focused ESLint,
app/spec TypeScript, Ruff/Black/compileall, PowerShell5.1 parser and diff check pass.
Focused schema strict mypy passes; this does not close older sourcing/economic
router or repository-wide typing debt. Bundle budgets unchanged, warning resolved.

Actual broad replay:92 screen review visits /39 distinct planned routes;7 grouped
functional checks PASS, not92 complete workflows. Final focused replay:26 review
visits /8 checks PASS, including the last CSS change and populated listing textareas.
No unexpected page exceptions or network guard denials; **real observed service
errors remain**, so there is no clean-console/API-health certification.

Broad96 axe scans:0 violations,31 incomplete rule occurrences/45 nodes. Focused30
scans:0 violations,11 incomplete rule occurrences/21 nodes. Six exposed Catalog
textarea measurements are14.80:1 with unobscured centers and focus outlines. These
measurements do not waive axe incompletes or close the prior unexecuted error state.
Manual assistive technology/theme/zoom/conditional-state coverage remains open.

Final read-only audit: **6/6 signed databases DROPPED/absent**, original10 Docker
containers/networks/volumes preserved,23 retained traces CRC PASS, approved credential
matches0, no raw container logs persisted. One earlier interrupted drop was recovered
through existing exact-token guards; its failure remains recorded. Final accepted
backend/broad/focused runs cleaned normally with exit0. No FORCE/unrelated cleanup.

See [browser matrix](wp6-browser-retest.md), [ledger](wp6-resolution.json) and
[quality debt](wp6-quality-debt.md). No permanent/golden data, real provider/supplier
calls, external commercial actions, branch/commit/push or backup operations.
**Stop after WP6. Application certification INCOMPLETE; no WP7 started.**

## Subsequent WP6A disposition (2026-10-30)

The historical failures above remain preserved. [WP6A](wp6a-schema-remediation.md)
now corrects the Video/Ads column drift and storyboard scene NOT NULL defect with
two new data-preserving migrations. Fresh and populated upgrades, guarded rollback,
13 service cases,28 adjacent cases and9 real Chrome/Edge browser assertion groups
pass. Video Retry recovery is also corrected and independently retested. Full
application certification remains INCOMPLETE; the original isolated502 cause,
manual accessibility, monetary/history and broader schema/index debt remain open.
No permanent upgrade or provider execution was performed. Stop before WP7.
