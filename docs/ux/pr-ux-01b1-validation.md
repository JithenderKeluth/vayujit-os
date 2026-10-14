# PR-UX-01B.1 — Populated Product Opportunity Journey & HUMAN Selection

## A–V certification report

**Run date:** 2026-10-10  
**Scope:** PR-UX-01B.1 only. No PR-UX-01C–F, PR-9C, supplier contact, RFQ, procurement, payment, marketplace write, commit, or push was performed.

### A. Canonical authority mapping

The validation used the existing authorities, without duplicating business logic:

`Business Agent goal/parser → plan/run → ProductOpportunity/research-results → product detail/intelligence → canonical comparison → HUMAN selection → Commerce Journey → cross-marketplace supplier handoff`.

Product opportunities were created through the supported API/ORM fixture mechanism in a disposable PostgreSQL database. No golden database was changed.

### B. Disposable fixture construction

Three persisted products were created for one authenticated owner and one Amazon India goal:

| Product | Category | Price | Opportunity |
|---|---|---:|---|
| Reusable Food Storage Set | Home & Kitchen / Food Storage | INR 599 | `88238f9e-3713-4da2-b3de-d17dec13c9ca` |
| Foldable Wardrobe Organizer | Home & Kitchen / Storage & Organization | INR 999 | `8e89a5f3-9f85-4043-9155-8c44ea5d885d` |
| Insulated Lunch Container | Home & Kitchen / Food Storage | INR 799 | `aae27e5e-f219-4542-bbbb-2c3557b4677e` |

The fixture used real application models and canonical API operations. It did not synthesize live external evidence; the UI correctly labels this disposable state as local/demo data with partial evidence.

### C. Authentication and owner scope

Authenticated login succeeded with the disposable owner. An unauthenticated research-results request returned HTTP 401. All populated data was owner-scoped. No authentication bypass was used.

### D. Populated opportunity list

The authenticated product-opportunities route rendered all three persisted opportunities, showed `3` products and `3` ready to compare, and exposed `View product research` and `Add to comparison` actions for each card. Empty, loading, and error states remained available through the existing route.

### E. Product detail

The detail route rendered product name, category/subcategory, marketplace, region, origin, provenance, evidence status, and the explicit next actions: `Select this product for supplier research`, `Continue research with VAYUJIT`, `Research market evidence`, and `Archive opportunity`.

### F. Evidence and trust presentation

The detail view preserves observed/derived/unknown distinctions and does not invent sales, demand, rank, conversion, supplier, or commercial values. Unknown commercial dimensions remain visibly unknown. The page states the local/demo boundary and evidence gaps.

`Load authoritative assessment` was exercised successfully. It rendered score `48.143/100`, `MODERATE`, confidence/risk `MODERATE`, readiness `PARTIALLY_READY`, and eligibility `PARTIALLY_SCORABLE`; no launch verdict or unsupported recommendation was shown.

### G. Opportunity comparison

Two cards were added to comparison and `Compare selected products` produced the canonical evidence-backed trade-off matrix. The UI explicitly states that comparison explains trade-offs and does not choose a winner. Canonical ranking returned `NOT_COMPARABLE` with the truthful reason that scores were not scorable under one model/profile because required supplier/economics evidence was unknown. No winner was fabricated.

### H. HUMAN selection

`Select this product for supplier research` produced the visible `Selected by you · HUMAN` state and the `Find suppliers` continuation. The canonical selection decision was replayed twice with the same idempotency key and returned the same decision identity, proving idempotency.

### I. Journey transition

The goal context was confirmed through the existing HUMAN confirmation control. The journey advanced from `1 of 8` to `2 of 8`; category `Home & Kitchen`, marketplace `AMAZON_IN`, capital/currency, and candidate count were visible as journey facts. Compare became complete and Source became the next available stage; later stages stayed blocked or review-gated as appropriate.

### J. Supplier-discovery handoff

The normal `Find suppliers` continuation opened the cross-marketplace route with the selected product context preserved: `Reusable Food Storage Set`, `AMAZON_IN`, `Home & Kitchen`, `Food Storage`, region `IN`. The page stated that context came from Product Research and is authoritative. It displayed `LIVE_READ_ONLY`, no supplier contact/external write, and `NOT_STARTED` supplier state with zero discovery requests. No supplier was fabricated or contacted.

### K. Owner isolation

No-cookie access was rejected with HTTP 401. A random owner-scoped opportunity returned HTTP 404, and an invalid comparison request returned HTTP 422. These checks confirm the route does not disclose another owner’s entities and preserves canonical validation errors.

### L. Stale, duplicate, and replay behavior

The canonical HUMAN decision replay was idempotent. Invalid/random detail and ranking contexts were rejected rather than silently accepted. The disposable browser run retained one additional replayed selection while exercising the API directly; this is a fixture-run artifact only and does not alter application behavior or any golden data.

### M. Error and blocked-state behavior

The UI displayed explicit evidence-gap, `NOT_COMPARABLE`, unknown commercial, and no-supplier states. It did not present blocked stages as successful. API failure states remained actionable and owner-scoped.

### N. Responsive validation

Real authenticated Chrome validation was run at all required widths after the bounded intrinsic-width fix:

| Viewport | Document width | Horizontal overflow | Product content |
|---:|---:|---|---|
| 360 px | 345 px (scrollbar-adjusted) | No | Present |
| 390 px | 375 px (scrollbar-adjusted) | No | Present |
| 768 px | 753 px (scrollbar-adjusted) | No | Present |
| 1024 px | 1009 px (scrollbar-adjusted) | No | Present |
| 1440 px | 1425 px (scrollbar-adjusted) | No | Present |

The fix prevents grid/card min-content widths from forcing horizontal overflow on narrow screens.

### O. Accessibility smoke checks

At 360 px, keyboard focus reached `Compare selected products` with a visible focus indicator; a skip link was present; all buttons had accessible names; there were no unexpected alerts; the status region was present; and horizontal overflow was false.

### P. Browser evidence

Screenshots captured from the authenticated isolated Chrome session:

- `tmp/ux-browser/prux01b1-opportunities-1440.png`
- `tmp/ux-browser/prux01b1-detail-1440.png`
- `tmp/ux-browser/prux01b1-fixed-360.png`
- `tmp/ux-browser/prux01b1-fixed-390.png`
- `tmp/ux-browser/prux01b1-fixed-768.png`
- `tmp/ux-browser/prux01b1-fixed-1024.png`
- `tmp/ux-browser/prux01b1-fixed-1440.png`

The normal computer-use connector could not initialize because the Windows helper failed while applying its ACL; the equivalent isolated Chrome CDP harness was used instead, with normal authenticated HTTP APIs and browser rendering.

### Q. Angular tests

`npm run test --workspace @vayujit/web -- --run` completed with **60 test files passed, 213 tests passed**. Angular lint passed. Production build passed with the existing initial-bundle budget warning (507.67 kB against 500 kB); the product-opportunity lazy chunk was 108.63 kB.

### R. Backend regressions

The prior adjacent backend baseline was **15 passed, 20 deselected, 2 warnings**; commerce integration baseline was **2 passed, 6 warnings**. A fresh focused product-opportunity integration rerun was attempted against the disposable PostgreSQL database and reached fixture teardown, but 9 tests errored while the test reset tried to drop `intelligence_supplier_portfolio_assessment_versions` with dependent objects (`DependentObjectsStillExist`). This is a test-schema reset/fixture-ordering blocker, not a populated journey/browser failure. It must be resolved before claiming a clean backend certification.

### S. Static and technical checks

`git diff --check` passed. Web lint passed. Historical repository-wide Python Ruff (227 diagnostics), Black (13 files), and mypy (161 errors across 19 files) findings were not introduced or broadened by this bounded UX change. Full repository Prettier retains six historical failures.

### T. Changed files

Intentional source change in this turn:

- `apps/web/src/app/intelligence/product-opportunity-workspace.css` — adds `min-width: 0`, `overflow-wrap:anywhere`, and safe mobile grid sizing for candidate/trade-off cards.

Validation artifact:

- `docs/ux/pr-ux-01b1-validation.md` — this report.

The temporary fixture/CDP files are under `tmp/ux-browser` and are not application source. The API environment file was restored to its original port-8000 value.

### U. Limitations and remaining technical debt

The product data in this certification is intentionally disposable local fixture data; live external product acquisition was not authorized and was not performed. Supplier discovery was validated only to the read-only handoff boundary. The canonical comparison correctly remains `NOT_COMPARABLE` until sufficient evidence exists. Backend integration certification remains blocked by the existing PostgreSQL fixture teardown dependency-order error described in R. No golden database was modified.

### V. Final classification

**IMPLEMENTED / CERTIFICATION PENDING — populated product-opportunity journey, comparison, HUMAN selection, idempotent replay, responsive browser behavior, and supplier handoff validated; clean backend regression certification is blocked by the existing disposable test-schema teardown error.**

The application did not claim a false winner, supplier, or procurement readiness. No external write occurred.
