# PR-SOS-01.1 — Catalog Certification Closure

> Latest release-gate result: PR-SOS-01.4 is **FULLY VALIDATED (LOCAL / NO MARKETPLACE PUBLICATION)**. See [`pr-sos-01-4-validation.md`](pr-sos-01-4-validation.md) for the authenticated axe-core, keyboard, responsive, media-security, regression, and migration evidence. Marketplace publication and all external commercial writes remain disabled.

This historical report is retained for the original PR-SOS-01 pass. The
current PR-SOS-01.1 bounded certification report is
[`pr-sos-01-1-validation.md`](pr-sos-01-1-validation.md), and the latest
infrastructure/browser recovery report is
[`pr-sos-01-2-validation.md`](pr-sos-01-2-validation.md).

Validation date: 2026-10-11  
Environment: disposable PostgreSQL `vayujit_test`, `VAYUJIT_ENVIRONMENT=test`, authenticated local Angular workspace where available  
External execution: disabled; no marketplace, supplier, RFQ, procurement, payment, or golden-database write

## A. Roadmap and repository audit

The Seller OS roadmap and capability matrix were reconciled before implementation. The existing Product, ProductOpportunity, Supplier, HUMAN shortlist, audit, media, economics, and Commerce Journey authorities remain the sources of truth. PR-SOS-01 adds only the missing seller-catalog boundary and does not create a marketplace or a second journey state machine.

## B. Canonical authority mapping

| Concern | Reused authority |
| --- | --- |
| Seller product identity | `products.Product`, ProductService/Product router |
| Researched opportunity | `ProductOpportunity` and assessment/decision services |
| Explicit selection | canonical HUMAN shortlist decision |
| Supplier identity | canonical `Supplier` and supplier-intelligence services |
| Audit | existing `record_event` audit service |
| Seller authentication/owner scope | `current_user`, owner-scoped service queries |
| Marketplace publication | intentionally not called; no PR-SOS-01 authority |

## C. Changed files

Backend: `apps/api/vayujit_api/catalog/{models,schemas,service,router}.py`, migration `20261017_0157_catalog_product_images.py`, `apps/api/vayujit_api/core/test_database.py`, and `apps/api/tests/test_pr_sos_01_catalog.py`.

Frontend: shared catalog contracts, `catalog.service.ts`, and `catalog-workspace.component.{ts,css}`.

Documentation: `docs/ux/seller-os-implementation-roadmap.md`, `docs/ux/seller-os-capability-matrix.md`, and this report.

## D. Product master architecture

The new catalog lineage record is separate from `ProductOpportunity`, while the canonical seller Product remains the product identity. Lineage preserves opportunity, goal, assessment, selection decision, source kind, and provenance. Product variants, supplier associations, and channel drafts are separate owner-scoped records.

## E. Product creation

The existing authenticated Product creation route remains the manual creation authority. A disposable browser session created `Insulated Kids Lunch Box` under `Catalog Browser Brand`, category `Kids`, SKU `KIDS-BOX-001`, and INR 1299, then opened it in `/catalog/:id`. The catalog workspace does not silently convert research or publish anything.

## F. Opportunity conversion and lineage

`POST /api/v1/catalog/opportunities/{id}/convert` rejects conversion until a canonical HUMAN shortlist exists, then creates durable lineage (or links the already-canonical ProductOpportunity product). Replay is idempotent. Focused test: `test_catalog_conversion_requires_human_selection_and_is_replayable` passed.

Browser conversion was not re-run in this certification pass; the API authority and persisted regression are covered, but this is a remaining browser-evidence gap.

## G. Product editing and lifecycle

Existing Product edit/archive/restore authorities are reused. Catalog readiness blocks archived products. Catalog detail links directly to the canonical Product record and editor. Dedicated catalog lifecycle controls are not duplicated.

## H. Variants and SKU management

Variants now have an in-workspace add/edit/archive experience. Option JSON is parsed and validated, blank option keys/values are rejected, reordered duplicate combinations are rejected with a conflict, SKU/key uniqueness remains enforced by the existing service/database authority, and optimistic `version` checks reject stale writes. Archive is explicit and does not delete historical data.

## I. Product attributes

Canonical Product fields remain the source of truth. Channel draft attributes are separate JSONB content with typed request bounds. Unknown commercial values stay `null`/missing; they are never coerced to zero.

## J. Product assets

`catalog_product_images` associates a catalog product with an owner-scoped, ready `MediaAsset`; it does not copy bytes or expose arbitrary URLs. Associations support idempotent attach, alt text, position/order, one primary image, optimistic updates, and association-only removal. Preview URLs are the existing private media preview route. Missing, cross-owner, non-ready, or guessed media IDs are rejected; deleting an association does not delete the underlying asset. The workspace exposes a ready Media Library picker, alt text input, primary selection, private preview, alt-text edit, set-primary, and remove actions.

## K. Marketplace listing draft model

`catalog_listing_drafts` is owner/product/channel unique and stores channel content, bullets, category mapping, attributes, bounded image references, intended price/currency, compliance, missing fields, validation/readiness state, HUMAN review state, provenance, version, and idempotency key. The catalog workspace now exposes a bounded seller-authored editor for these fields and validates compliance JSON before saving. No remote listing ID exists.

## L. Amazon India draft preparation

The authenticated browser created an Amazon India draft. The UI showed `incomplete` and explicitly listed `images`, `intended_price`, `currency`, and `compliance_information`; readiness remained `BLOCKED`. After seller-authored disposable local fields were supplied through the authenticated API, the UI exposed `Approve as HUMAN`; clicking it produced `approved_for_future_submission`, not publication. Evidence: `tmp/ux-browser/sos01-ready-review-1440.png`.

## M. Flipkart draft preparation

The authenticated browser created a separate Flipkart draft. It remained independently `incomplete` with its own blockers. Evidence is captured in the same disposable catalog detail session and the browser log.

## N. Listing validation

Readiness checks cover title, description, category, SKU, images, intended price/currency, compliance, unverified claims, archived products, HUMAN approval, and channel separation. Local readiness is explicitly not marketplace certification. Missing-field and stale-version assertions passed in backend tests and were visible in browser state.

## O. AI-assisted content and evidence

PR-SOS-01 does not add a second AI content authority. Existing AI/Business Agent surfaces remain separate and any generated content remains subject to their existing HUMAN review boundaries. Catalog-specific AI suggestions are not implemented in this slice.

## P. Supplier association

`catalog_supplier_associations` is owner/product/supplier unique, retains opportunity/provenance, defaults to `review_required`, and adds `supplier_approval: NOT_IMPLIED`. Explicit `accepted` is rejected because supplier approval belongs to the canonical HUMAN supplier authority. Persisted association/idempotency/approval-boundary assertions passed.

## Q. Economics integration

`GET /api/v1/catalog/products/{product_id}/economics` delegates to the canonical opportunity economics projection. It reports `available`, assessment/opportunity IDs, projection, and a truthful reason. When lineage or evaluated evidence is absent, the UI shows an unavailable/blocked state and a link to the opportunity workspace; it never calculates margin, landed cost, or profitability locally and never treats `UNKNOWN` as zero.

## Q. Business Agent guidance

The catalog includes a clear Business Agent guidance panel linking to `/intelligence/business-agent`. It explains that research and consequential decisions remain in the canonical Business Agent/HUMAN workflow; it does not create a second AI authority or auto-approve a product.

## R. Commerce Journey integration

Catalog navigation preserves Product and opportunity context through canonical IDs and links to existing journey workspaces. No second Angular journey state machine was introduced. A full browser Opportunity → Catalog transition was not re-run in this pass and remains an evidence gap.

## S. HUMAN approval and versioning

Listing approval is explicit (`Approve as HUMAN`), blocked while fields are missing, and guarded by optimistic version checks. Any edit resets review to `not_reviewed`. Backend stale-version and approval tests passed; browser approval evidence is captured above.

## T. Owner isolation and security

Every catalog lookup includes authenticated owner scope; supplier and opportunity lineage are checked against the same owner. Database foreign keys and owner/product/channel uniqueness constrain records. No unrestricted external URL fetch, marketplace write, or supplier contact is reachable from these routes. Existing ProductService and supplier security regressions remain in the adjacent suite. Dedicated cross-owner catalog-IDOR tests and automated axe checks were not added in this slice and are tracked as blockers for a full certification claim.

## U. Responsive and accessibility

Semantic headings, labelled sections, buttons, links, and mobile single-column cards are present and the Angular build passes. Full Chrome width and overflow measurements were not re-certified after these changes, and automated axe/focus/keyboard certification was not run. The Computer Use helper failed during Windows ACL initialization (`apply deny-read ACLs`), while the available CDP target was not a safe authenticated disposable post-change session.

## V. Authenticated browser certification

Existing pre-change CDP evidence covers catalog navigation, detail, draft readiness, HUMAN review, logout/protected routes, and responsive widths. It is not used as post-change proof for image picker/preview, variant editing, economics, or Business Agent guidance. A new authenticated post-change run was not safely executable in this environment, so no browser write was attempted and no full browser certification is claimed.

## W. Backend regressions

- PR-SOS-01 focused PostgreSQL tests: **6 passed** (`test_pr_sos_01_catalog.py`, including image ownership/optimistic updates, variant option validation, and economics-unavailable behavior; 118.41 s).
- Existing Product integration regression: **7 passed**, 16 pre-existing warnings (77.39 s).
- No test modified `vayujit_golden_test`.

## X. Angular, static, build, and migration checks

- Angular: **62 test files / 223 tests passed**.
- Angular lint: passed; only previously existing campaign warnings remain.
- Shared TypeScript build: passed.
- Angular production build: passed; existing initial bundle warning 508.63 kB vs 500 kB budget remains (not hidden or raised).
- Focused Black: passed (6 files unchanged).
- Focused Ruff: passed.
- Focused strict mypy for `vayujit_api/catalog`: passed (5 source files).
- Focused compileall: passed.
- Migration lifecycle on disposable PostgreSQL: downgrade `20261016_0156 → 20261014_0155`, upgrade back to `20261016_0156 (head)`: passed.
- `git diff --check`: passed; Git only reports normal LF→CRLF warnings for existing Windows working-tree files.

## Y. Golden database, external effects, and remaining limitations

The golden database was not modified. No supplier was contacted, no RFQ/email/procurement/payment was sent, and no Amazon/Flipkart publication or remote listing ID was created. Remaining limitations are the post-change authenticated browser run, full responsive/accessibility evidence, and a dedicated two-owner browser/API matrix. Economics remains unavailable until canonical opportunity lineage/evidence is present.

## Z. Final classification

PR-SOS-01.1 supersedes the historical PR-SOS-01 wording below. The current bounded result is:

**PR-SOS-01.1 — IMPLEMENTED / CERTIFICATION PENDING**

Secure MediaAsset image associations, variant editor validation, canonical economics projection, Business Agent guidance, the additive migration, focused regressions, Angular suite, lint/build, and scoped static checks are complete and passing. Full production certification remains pending a safe authenticated post-change browser run, full responsive/accessibility evidence, and the remaining cross-owner/browser regression evidence.

**PR-SOS-01 — IMPLEMENTED / CERTIFICATION PENDING**

PR-SOS-01.3 records the intentional one-owner-per-installation architecture,
applicable resource-isolation evidence, and the remaining accessibility-engine
limitation. See [`pr-sos-01-3-validation.md`](pr-sos-01-3-validation.md).

The durable catalog authority, listing-preparation boundary, HUMAN review gate, owner-scoped APIs, migration, focused tests, Angular workspace, seller-authored draft editor, and authenticated responsive browser path are implemented and locally validated. Full classification **PR-SOS-01 — FULLY VALIDATED (LOCAL / NO MARKETPLACE PUBLICATION)** is intentionally withheld until the remaining image/variant UI, cross-owner, browser-transition, economics, asset, AI, and accessibility evidence gaps are closed.
