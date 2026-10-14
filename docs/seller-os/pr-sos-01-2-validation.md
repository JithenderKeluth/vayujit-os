# PR-SOS-01.2 — Certification Infrastructure Recovery & Final Catalog Closure

Validation date: 2026-10-11  
Mode: local/disposable only; no marketplace publication or supplier contact.  
Final result: **PR-SOS-01 — IMPLEMENTED / CERTIFICATION PENDING**

## A. Scope and blockers

This run recovered the browser and migration certification infrastructure and
reran the catalog closure gates. The catalog journey is usable and persisted
on a fresh database. Certification is withheld because the canonical identity
model intentionally enforces one owner (`ck_users_single_owner`), so the
required two-owner browser/API isolation matrix cannot be executed, and no
local `axe-core`/equivalent engine is installed. Neither blocker was hidden or
worked around by weakening production authorities.

## B. Browser tooling investigation

The managed Computer Use helper was not retried after its documented Windows
ACL failure (`apply deny-read ACLs`). No Playwright package or `axe-core`
package is present in the repository/node_modules. Existing project CDP
harnesses were inspected and reused.

## C. Browser recovery implementation

A disposable Chrome profile (`tmp/ux-browser/chrome-prsos012`) was launched
with CDP on port 9223. A disposable Angular server on 4202 and API on 8002
were pointed at the validation database only; a browser-only CORS origin was
used. The temporary frontend API URL was restored to the repository default
(8000) before completion. The session used a synthetic owner, not seller
credentials. The helper scripts used were the existing CDP action/fill tools
plus temporary local CDP upload/keyboard helpers.

## D. Fresh PostgreSQL setup

Database: `vayujit_sos012_test` (marker-protected, disposable). It was created
with `scripts/prepare-test-database.ps1 -Purpose migration` and was never
used as the long-lived drifted `vayujit_test` database. `vayujit_golden_test`
was not opened or changed.

## E. Migration integrity

Canonical Alembic base→head completed successfully. Final check:
`20261017_0157 (head)`. Verified catalog/media tables and constraints include
`ck_catalog_product_image_position`, `ck_catalog_product_image_version`,
`uq_catalog_product_image_media`, and
`fk_supplier_portfolio_current_assessment`.

## F. Fixture dependency regression

Command: `pytest --no-cov -q apps/api/tests/test_certification_fixture_stability.py -k migrated_supplier_assessment_dependencies_survive_repeated_reset`.

Result: **1 passed, 20 deselected, 2 warnings** (74.96 s). The previous
fixture teardown failure was not reproduced on the fresh migrated database.

## G. Authenticated test owners

Owner 1 was created through `/setup` in the browser and authenticated as
`prsos012.owner1@example.com`. A second independent owner could not be
created through the canonical API because the production schema enforces the
single-owner invariant (`users.singleton_key` and `ck_users_single_owner`).
Creating a second row by dropping/altering that constraint would invalidate
the authority under test, so the cross-owner matrix is **BLOCKED**, not
fabricated.

## H. Catalog product journey

**PASS (browser):** authenticated setup/session, brand creation, `/catalog`,
`/products/new`, product creation, product detail, `/catalog/:id` workspace,
refresh, and persisted product values. Product used synthetic labels:
`PR SOS 012 Brand` / `Kids Silicone Snack Cup` / SKU
`PRSOS012-SCUP-001` / category `Kids / Feeding`.

## I. Variant editing

**PASS (backend):** focused catalog suite covers variant validation and
optimistic ownership rules. **PASS (browser):** a canonical variant was added
(`blue-small`, `PRSOS012-SCUP-BLUE-S`). Browser edit, archive, and duplicate
combination UI actions were **NOT EXECUTED** in this bounded run; they remain
covered by the backend authority and focused regression suite.

## J. MediaAsset association

**PASS (browser):** a local PNG was uploaded through `/media/upload`, reached
`ready`, and was attached to the product with alt text and primary-image
selection through the catalog workspace. The association remained owner and
product scoped. No remote URL was supplied.

## K. Private preview security

**PASS (backend):** MediaAsset integration/security coverage passed and the
catalog workspace rendered the authenticated asset metadata/preview state.
The required second-owner direct preview denial is **BLOCKED** with the
two-owner matrix (see G/Q); no guessed or unrestricted asset URL was tested.

## L. Economics integration

**PASS:** the catalog workspace displayed canonical economics as unavailable
because the synthetic manual product had no ProductOpportunity economics
lineage. No local calculation or UNKNOWN-to-zero coercion occurred.

## M. Business Agent guidance

**PASS (browser):** the workspace displayed the HUMAN-review guidance and
linked to the canonical Business Agent. It did not invent research claims or
commercial recommendations.

## N. Listing draft lifecycle

**PASS (browser):** Amazon India draft was created, seller-authored fields were
entered and saved, readiness blockers changed from missing required fields to
`human_review_required`, and the draft persisted as
`needs_review`/approved-for-future-submission. No remote listing was created.

## O. HUMAN approval

**PASS (browser):** `Approve as HUMAN` moved the draft to
`approved_for_future_submission` and readiness to `READY_FOR_FUTURE_SUBMISSION`.
The UI continued to state that future submission remains HUMAN-controlled and
external publication is disabled.

## P. Optimistic versioning

**PASS (backend):** focused catalog tests passed stale optimistic update
assertions. Browser stale-update replay was **NOT EXECUTED**.

## Q. Cross-owner isolation

**BLOCKED:** list/detail/update/variant/draft/approval/media-preview/opportunity
direct-ID checks requiring two independently authenticated owners could not be
run because the canonical one-owner invariant rejects a second owner. Existing
owner-scoped query dependencies remain unchanged.

## R. Deep links and history

**PASS (browser):** direct catalog detail navigation, hard refresh, catalog
list navigation, back/forward route handling, logout, and protected-route
redirect to `/login` were observed. The authenticated detail page reconstructed
the persisted product after refresh.

## S. Responsive certification

**PASS (overflow check):** catalog detail/list workspace was measured at
320, 360, 390, 768, 1024, and 1440 CSS pixels. `scrollWidth` did not exceed
`innerWidth` at any width (320→320, 360→345, 390→375, 768→753,
1024→1009, 1440→1425). Screenshots were captured under `tmp/ux-browser/`.
Detailed visual/a11y review of every control at every width remains bounded by
the axe/second-owner limitations.

## T. Automated axe accessibility

**NOT EXECUTED/BLOCKED:** no local axe-core or established equivalent is
installed, and network download was intentionally not performed. No claim of
complete WCAG conformance is made. Semantic labels, explicit status text, and
the existing Angular test suite still pass.

## U. Keyboard accessibility

**PASS (validated subset):** CDP Tab traversal reached visible shell and
catalog controls; the skip link was activated with an actual Enter key event
and focus moved to `#main-content`. Detailed Shift+Tab, every form error,
variant archive, image controls, approval, dialog Escape, and focus-restoration
checks were **NOT EXECUTED**.

## V. Authenticated browser E2E matrix

| Scenario | Result | Evidence |
| --- | --- | --- |
| Setup/authenticated session | PASS | `/setup` → dashboard |
| Login after logout | NOT EXECUTED | Session setup was validated; no second login cycle |
| Open catalog | PASS | `/catalog` |
| Create product | PASS | `/products/new` |
| Edit product | NOT EXECUTED | Backend/API coverage only |
| Product details | PASS | `/products/:id` |
| Add variant | PASS | canonical variant persisted |
| Edit variant | NOT EXECUTED | Backend coverage only |
| Archive variant | NOT EXECUTED | Backend coverage only |
| Reject duplicate combination | NOT EXECUTED (browser) | Backend rule covered |
| Upload ready MediaAsset | PASS | `/media/upload` |
| Associate authorized image | PASS | `/catalog/:id` |
| Private preview | PASS (UI/API state) | ready asset rendered |
| Reorder/change primary/alt text | PASS (primary/alt) | association controls |
| Reject unauthorized asset | BLOCKED | needs owner 2 |
| Review economics | PASS | unavailable/UNKNOWN truthfully shown |
| Business Agent guidance | PASS | canonical link/message |
| Create listing draft | PASS | Amazon India draft |
| Edit/save listing draft | PASS | required fields persisted |
| Readiness blockers | PASS | explicit missing-field → review state |
| HUMAN approval | PASS | approved-for-future-submission |
| Optimistic version replay | NOT EXECUTED (browser) | backend assertions pass |
| Direct deep link | PASS | detail URL |
| Hard refresh | PASS | detail reconstructs |
| Back/forward | PASS | route transitions |
| Logout | PASS | returns `/login` |
| Protected route | PASS | redirects after logout |
| Two-owner isolation | BLOCKED | canonical single-owner constraint |

## W. Backend regression results

- Catalog: **6 passed, 14 warnings** (`test_pr_sos_01_catalog.py`, 88.78 s).
- Product lifecycle: **7 passed** (`test_products_integration.py`, included in
  combined run).
- Combined catalog/product/media: **18 passed, 28 warnings**.
- Media integration/security: **12 passed, 4 warnings**.
- Business Agent parser/orchestration/concurrency: **22 passed, 1 failed,
  28 warnings**. The one failure is the pre-existing PostgreSQL concurrency
  assertion that a later Business Agent step has dependency keys; it is not a
  PR-SOS-01.2 catalog regression and was not weakened.

## X. Angular/static/build quality gates

- Angular: **62 files / 223 tests passed**.
- TypeScript app check: passed.
- Angular lint: passed, **0 errors / 2 pre-existing warnings** in campaign
  dialogs.
- Production build: passed; existing initial bundle warning 508.63 kB vs
  500 kB budget was retained (not silenced by budget changes).
- Scoped mypy: passed (5 catalog source files).
- Scoped Ruff: passed.
- Scoped Black: passed after a formatting-only catalog service correction.
- Scoped compileall: passed.
- `git diff --check`: passed (only normal LF/CRLF warnings).

## Y. Golden database, external effects, and limitations

No golden database was modified. No supplier was contacted; no RFQ, email,
procurement, purchase, payment, marketplace mutation, or external write was
performed. The isolated API/web/Chrome processes were stopped after evidence
capture. The disposable database name is retained for auditability. Remaining
limitations are the canonical one-owner invariant, absent local axe engine,
and the unexecuted browser sub-scenarios listed above.

## Z. Final classification

The migration, fixture, focused backend, authenticated catalog journey,
responsive overflow, keyboard skip-link, HUMAN approval, and safety gates are
validated. Because the specification requires a two-owner security matrix and
automated accessibility scan, the evidence does not support the full closure
classification.

**PR-SOS-01 — IMPLEMENTED / CERTIFICATION PENDING**

No PR-SOS-02 work, commit, or push was started.

## PR-SOS-01.3 follow-up

PR-SOS-01.3 resolved the ownership architecture question: this product is
intentionally one owner per installation/database (`ck_users_single_owner`),
so same-database two-owner isolation scenarios are **NOT APPLICABLE TO CURRENT
ARCHITECTURE**, not an unresolved production defect. The follow-up passed the
focused auth/catalog/media suite on fresh disposable PostgreSQL installations
and separately demonstrated that brand and private MediaAsset IDs from one
installation return 404 in another. Automated axe/equivalent scanning remains
pending because no offline-safe engine is installed. See
[`pr-sos-01-3-validation.md`](pr-sos-01-3-validation.md).
