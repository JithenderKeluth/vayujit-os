# PR-UX-01C certification report

Date: 2026-10-10

Scope: Supplier discovery, source-backed supplier detail, evidence trust
presentation, and due-diligence review UX. This slice uses existing canonical
backend authorities and does not add a supplier, approval, or procurement
authority.

## A. Roadmap audit and reconciliation

The supplier route, supplier research projection, canonical supplier detail,
shortlist boundary, and due-diligence APIs already existed. The gaps were in
context-preserving navigation, lifecycle messaging, credentialed verification
requests, stale supplier deep links, and zoneless rendering after async
due-diligence loads. Those gaps were fixed in the bounded UX-01C files listed
in section C. Commercial economics, controlled engagement, and marketplace
mutations remain outside this slice.

## B. Canonical authority mapping

The Angular layer calls the existing `CrossMarketplaceService` and the
supplier due-diligence routes. The API remains authoritative for owner scope,
product/supplier membership, evidence provenance, confidence, freshness,
contradictions, risk, verification status, HUMAN review, and external-write
controls. No duplicate state store or business rule was introduced.

## C. Changed files

- `apps/web/src/app/intelligence/cross-marketplace-supplier.component.ts`
- `apps/web/src/app/intelligence/cross-marketplace-supplier.component.spec.ts`
- `apps/web/src/app/intelligence/supplier-due-diligence.component.ts`
- `apps/web/src/app/intelligence/supplier-due-diligence.component.spec.ts`
- `docs/ux/seller-os-capability-matrix.md`
- `docs/ux/seller-os-journey-map.md`
- `docs/ux/seller-os-information-architecture.md`
- `docs/ux/seller-os-component-architecture.md`
- `docs/ux/seller-os-implementation-roadmap.md`
- this report

The repository was already dirty from earlier PR work; unrelated changes were
preserved and not reset.

## D. Supplier workspace architecture

`CrossMarketplaceSupplierComponent` remains a route-level orchestration
component. It renders shared breadcrumbs, journey context, supplier journey
navigation, provider state, candidate rows, source-backed detail cards,
comparison availability, and reports/history. `SupplierDueDiligenceComponent`
renders the verification context and review actions using the existing API.
Neither component calculates a supplier score or changes a trust label.

## E. Selected opportunity context

The supplier route accepts `opportunity_id`; the canonical research-results
projection supplies the selected product context. The fixture validation used
opportunity `9c66f7f9-8c36-463c-8eb2-ffa2dec10dc6`, product **Kids Reusable
Water Bottle**, category **Kids**, subcategory **Children's drinkware**, market
`AMAZON_IN`, region `IN`. The page states that supplier contact, RFQs,
purchasing, and payments are disabled.

## F. Discovery experience

Discovery is explicitly bounded to the selected product. The page shows the
provider mode (`LOCAL_FIXTURE` or `LIVE_READ_ONLY`), research status, researched
count, candidate count, and a truthful next action. A local fixture is never
labelled as live market evidence.

## G. Candidate list

The disposable fixture projected one canonical, product-relevant supplier:
**Bright Kids Manufacturing**. The candidate row exposed source count,
confidence, risk, freshness, and an Inspect supplier action. With one candidate,
comparison stays disabled and the page explains that more suppliers are needed;
there is no fabricated winner.

## H. Supplier detail

Selecting a row updates the URL with `supplier_id`, keeps the opportunity ID,
renders the detail region, and moves keyboard focus to it. A requested supplier
is accepted only if it is present in the canonical product-scoped list; stale,
foreign, or unavailable IDs render an actionable error and do not select data.

## I. Product relevance

The fixture supplier was attached to the selected Kids product and the browser
detail showed the product-match evidence. The list and detail are therefore
product-scoped rather than a global supplier directory.

## J. Provenance

The detail projection retained the canonical source, source type
`manufacturer_website`, provider mode `LOCAL_FIXTURE`, evidence lineage,
freshness, and confidence. Unknown commercial fields remain unknown. No raw
provider payload or secret was exposed.

## K. Claims and verification

The detail surface distinguishes observed facts, source metadata, commercial
fields, verification/certification fields, capabilities/facilities, risk and
contradictions, and confidence explanation. The fixture supplier was **needs
review**, not verified; the UI does not convert a source into a readiness claim.

## L. Due diligence

The due-diligence route now accepts `supplier_id` and `opportunity_id`, filters
contexts to the selected supplier, and shows a selected-product context panel.
Review and waiver calls are credentialed and remain HUMAN actions. The fixture
context was `REVIEW_REQUIRED` with one MOQ missing evidence gap.

## M. Risk and contradictions

The browser detail displayed medium risk and the canonical risk/evidence blocks.
The frontend preserves contradictions and unresolved risks as returned; it does
not rank or silently suppress them.

## N. Missing and stale evidence

The UI preserves unknown price, MOQ, and lead-time values and explains that
freshness or verification gaps require review. Explicit status copy covers
no-candidate, provider unavailable, approval required, blocked, failed, stale,
running, and completed states.

## O. Comparison preview

The existing comparison entry point remains a trade-off view, not a winner
decision. With one supplier, the UI truthfully indicates that comparison is not
available yet. No commercial inference was added.

## P. HUMAN boundaries

The frontend only presents canonical shortlist, verification, waiver, and
approval boundaries. It cannot approve a supplier, send an RFQ, contact a
supplier, purchase, pay, or mutate a marketplace.

## Q. Business Agent integration

The supplier workspace is reachable from the selected ProductOpportunity and
retains the commerce-journey context. The next action remains a recommendation
to inspect evidence; it does not auto-select a supplier or advance SOURCE.

## R. Lifecycle states

Loading, empty, error, blocked, provider-unavailable, no-candidate,
approval-required, stale, and completed states are rendered with plain-language
messages. A missing supplier context links back to discovery rather than
silently showing another owner's record.

## S. Responsive validation

Authenticated Chrome CDP captures were produced for the supplier workspace at
360, 390, 768, 1024, and 1440 CSS pixels:

- `tmp/ux-browser/prux01c-cross-360.png` (360 x 900)
- `tmp/ux-browser/prux01c-cross-390.png` (390 x 900)
- `tmp/ux-browser/prux01c-cross-768.png` (768 x 900)
- `tmp/ux-browser/prux01c-cross-1024.png` (1024 x 900)
- `tmp/ux-browser/prux01c-cross-1440.png` (1440 x 900)

The due-diligence route was also captured at 360 x 900 in
`tmp/ux-browser/prux01c-dd-360.png`; its DOM check had no horizontal overflow.
The supplier workspace DOM checks reported no horizontal overflow and preserved
the selected product/supplier context at the tested widths.

## T. Accessibility

The selected detail region has a labelled heading, `tabindex=-1`, and receives
focus after selection. Research status uses `role=status` and `aria-live`,
buttons have action-specific labels, and existing shell skip-link, breadcrumb,
landmark, keyboard-focus, and active-link semantics remain in use.

## U. Authenticated journey

Chrome was authenticated with a disposable owner on the disposable fixture DB.
The validated path was sign-in -> selected product context -> supplier
discovery -> candidate -> detail -> due diligence. The API and browser both
showed the local fixture boundary; no unauthenticated data path was used.

## V. Owner and security validation

The canonical API continued to enforce owner isolation and context membership.
The supplier deep-link restore path first checks the scoped list and then uses
the canonical detail endpoint. Due-diligence requests use credentials. Existing
backend supplier and due-diligence integration regressions passed. The
browser-only second-owner switch was not performed because the browser helper
was unavailable; owner enforcement was validated through the existing backend
suite.

## W. Effects on protected data

No golden database path was present in the repository root, and no golden
database was modified. A disposable database `vayujit_ux01c_test` was migrated
and seeded through ORM/canonical reconciliation by
`tmp/ux-browser/create_prux01c_fixture.py`; no raw SQL was used to manufacture
the supplier state. No external network write or supplier contact occurred.
After validation, the disposable API process was stopped and only
`vayujit_ux01c_test` was dropped. PNG/log evidence was retained under
`tmp/ux-browser` for review. A read-only PostgreSQL check still listed
`vayujit_golden_test`; no production or golden data was touched.

## X. Tests and static checks

- Angular unit suite: **60 test files, 214 tests passed** (16.39s final run).
- Focused `tests/test_cross_marketplace_e2e.py`: **1 passed**, 2 warnings.
- Focused `tests/test_supplier_due_diligence_integration.py`: **1 passed**, 4 warnings.
- Focused `tests/test_pr4_supplier_journey.py`: **1 passed**, 4 warnings.
- Focused `tests/test_pr42_functional.py`: **1 passed**, 4 warnings (52.04s).
- Combined focused backend result: **4 passed**, no failures; warnings were
  existing FastAPI `on_event` deprecations.
- Angular lint: exit 0; two existing warnings for missing `OnInit` interfaces
  in unrelated campaign dialogs.
- Angular production build: exit 0; existing initial-bundle budget warning
  (507.67 kB, 7.67 kB over the 500 kB budget).
- Focused Ruff: pass on the existing supplier research and due-diligence
  authorities. Focused Black: pass (three files unchanged). Focused
  `compileall`: pass.
- Focused strict mypy: **11 existing errors** in the unmodified
  `due_diligence_service.py` and `due_diligence_router.py` (missing return
  annotations, `Any` returns, and one unused ignore). These are historical
  backend typing debt, not introduced by this frontend slice; no broad typing
  refactor was made.
- Disposable PostgreSQL migration and fixture lifecycle completed successfully
  against `vayujit_ux01c_test`; a read-only Alembic check reported
  `20261014_0155 (head)`.
- `git diff --check`: exit 0; only Git line-ending normalization warnings.

## Y. Limitations and next milestones

This is a local deterministic fixture validation, not a claim that a live
provider is available or that Bright Kids Manufacturing is a real market
supplier. Live provider readiness remains configuration-dependent. The due
diligence API currently exposes the supplier UUID rather than the friendly name
in its context projection; discovery detail provides the friendly name. A
future UX slice can improve that projection and add dedicated comparison and
commercial decision layouts without duplicating authority.

The managed computer-use helper could not initialize because its Windows ACL
helper returned `apply deny-read ACLs`; authenticated Chrome CDP was used as the
equivalent local browser harness. This is an environment limitation, not an
application failure.

The captured browser certification covered the authenticated supplier discovery
and detail path, selected-product deep link, stale-context guard, keyboard
focus, and responsive overflow. Full logout/back-forward replay, every
provider-unavailable branch, and five-width due-diligence screenshots were not
rerun after the helper failure; those are remaining browser-certification gaps,
not claims of unsupported functionality.

## Z. Final classification

Specification classification: **PR-UX-01C - IMPLEMENTED / CERTIFICATION PENDING**.

**PR-UX-01C — IMPLEMENTED / LOCALLY VALIDATED; LIVE PROVIDER CERTIFICATION
PENDING.** The supported authenticated supplier discovery, evidence, detail,
context-preserving navigation, and due-diligence review experience is
implemented and regression-tested. Full LIVE certification is intentionally
not claimed because this run used the permitted disposable `LOCAL_FIXTURE`
provider and no supplier acquisition or external write was authorized.

## PR-UX-01C.1 certification update

Date: 2026-10-10. This closure run used the authenticated disposable owner
`prux01c1@example.com` and the canonical fixture context:

- Opportunity: `9c66f7f9-8c36-463c-8eb2-ffa2dec10dc6`
- Product: **Kids Reusable Water Bottle** (`Kids` / `Children's drinkware`)
- Supplier: **Bright Kids Manufacturing**
  (`bd1be1e0-7c8a-4f84-9315-072031c8d408`)
- Due-diligence context:
  `24fe29cc-6e05-4524-9301-dcc2a9beccfe`

### A. Canonical context and authority audit

The browser journey remained scoped to the selected ProductOpportunity. The
supplier projection contained exactly one product-relevant candidate, retained
the opportunity ID, and displayed product-match evidence, source metadata,
freshness, confidence, risk, and unknown commercial fields. Due diligence
retained the opportunity and supplier IDs and showed the unresolved MOQ gap as
`REVIEW REQUIRED`; no supplier was auto-selected for procurement and no
commercial value was inferred.

### B. PR-UX-01C.1 defect and bounded fix

The first browser replay exposed a real history defect: supplier selection used
`replaceUrl`, so Back could not leave the supplier detail state, and the
component did not reconcile query-parameter changes after Back/Forward. The
smallest fix was to create a normal history entry and subscribe to the
canonical query-param stream. Removing `supplier_id` now clears the selected
detail; restoring it rehydrates only the scoped canonical supplier. A focused
Vitest regression covers the history navigation contract.

### C. Authenticated browser scenarios

The local Chrome CDP run covered:

1. Authenticated deep link to supplier discovery with `opportunity_id`.
2. Candidate -> supplier detail navigation with `supplier_id` added.
3. Supplier detail refresh with product, supplier, evidence, and URL context
   preserved.
4. Back: `supplier_id` removed and `#supplier-detail` absent.
5. Forward: `supplier_id` restored and `#supplier-detail` present.
6. Authenticated deep link and refresh to due diligence with both IDs.
7. Logout from due diligence; the session returned to `/login`.
8. Direct protected due-diligence deep link after logout redirected to `/login`
   without rendering supplier data.

The fixture intentionally contains one candidate, so supplier switching was
not fabricated; the single-candidate empty comparison state was verified.

### D. Responsive and accessibility evidence

Both supplier detail and due-diligence routes were captured at every required
CSS viewport. Each check reported `overflow=false` and preserved the expected
context:

| Viewport | Supplier detail | Due diligence | Captures |
| --- | --- | --- | --- |
| 360 | 360px, scrollWidth 345 | 360px, scrollWidth 345 | `tmp/ux-browser/prux01c1-cross-360.png`, `tmp/ux-browser/prux01c1-dd-360.png` |
| 390 | 390px, scrollWidth 375 | 390px, scrollWidth 375 | `tmp/ux-browser/prux01c1-cross-390.png`, `tmp/ux-browser/prux01c1-dd-390.png` |
| 768 | 768px, scrollWidth 753 | 768px, scrollWidth 753 | `tmp/ux-browser/prux01c1-cross-768.png`, `tmp/ux-browser/prux01c1-dd-768.png` |
| 1024 | 1024px, scrollWidth 1009 | 1024px, scrollWidth 1009 | `tmp/ux-browser/prux01c1-cross-1024.png`, `tmp/ux-browser/prux01c1-dd-1024.png` |
| 1440 | 1440px, scrollWidth 1425 | 1440px, scrollWidth 1425 | `tmp/ux-browser/prux01c-cross-1440.png`, `tmp/ux-browser/prux01c1-dd-1440.png` |

Supplier detail checks asserted the selected product, supplier, and observed
evidence text at all five widths. Due diligence checks asserted the selected
product context marker, supplier ID, `REVIEW REQUIRED` status, and missing-MOQ
gap at all five widths. The detail region remains keyboard-focusable with a
labelled heading; live research status continues to use an announced status
region and all consequential actions remain explicit buttons.

### E. Validation commands and results

- Angular: **60 test files, 215 tests passed**.
- Focused backend regressions on disposable `vayujit_test`: **4 passed**, 8
  existing FastAPI deprecation warnings.
- Angular lint: pass, 0 errors; two pre-existing campaign-dialog warnings.
- Angular production build: pass; existing 507.67 kB initial-bundle warning
  (7.67 kB over the 500 kB budget).
- Ruff: pass for supplier intelligence and focused regression files.
- Black: pass; 267 files unchanged.
- `compileall`: pass for `vayujit_api/intelligence`.
- `git diff --check`: pass; only line-ending normalization warnings.
- Strict mypy: 11 pre-existing errors remain in the unchanged due-diligence
  service/router (`no-untyped-def`, `no-any-return`, and one unused ignore).
  They are outside the frontend UX closure and were not weakened or hidden.

### F. Database, ownership, and safety

The browser fixture was created through the supported ORM/canonical fixture
helper in disposable PostgreSQL `vayujit_ux01c_test` and validated at Alembic
head `20261014_0155`; that database was dropped after capture. The focused
backend suite used the existing marked disposable `vayujit_test` and restored
it through the normal test reset path. A final read-only catalog check showed
`vayujit_golden_test` still present; it was never modified. No provider call,
supplier contact, RFQ, procurement, payment, or marketplace write occurred.

The managed computer-use helper remained unavailable because its Windows ACL
helper returned `apply deny-read ACLs`; authenticated Chrome CDP supplied the
equivalent local browser evidence. This is an environment limitation, not an
application failure.

### G. Final PR-UX-01C.1 classification

**PR-UX-01C.1 - FULLY VALIDATED (LOCAL FIXTURE / NO LIVE PROVIDER CLAIM).**

All supported PR-UX-01C.1 browser, context, navigation, responsive, logout,
protected-route, provenance, owner-boundary, and regression checks passed.
The remaining mypy findings and bundle-size warning are pre-existing tracked
technical debt; live-provider certification remains a separate milestone.
