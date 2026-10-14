# PR-UX-01F — Platform-Wide Frontend Stabilization, Accessibility, Performance & End-to-End Certification

**Validation date:** 2026-10-10  
**Mode:** local, authenticated, disposable PostgreSQL fixture, no external execution  
**Scope:** PR-UX-01F only. PR-9C and the next UX slices were not started.

## A–Z certification report

### A. Audit and authority boundary

The frontend was audited against the existing PR-0 through PR-9B route and authority map. The stabilization work reuses the existing authenticated API projections, Commerce Journey state, ProductOpportunity authority, supplier/economics authorities, HUMAN decision boundaries, and engagement/response authorities. No frontend calculation, trust-label mutation, approval bypass, or second business authority was introduced.

### B. Browser shell and navigation

The authenticated shell now has one semantic `main` landmark per protected route. The shell owns the skip link and routed content owns the page landmark; the dashboard was migrated to the same contract. Desktop sidebar and mobile navigation continue to use the shared Seller Navigation component, active-page semantics, and protected routing.

### C. Changed files in this slice

- `apps/web/src/app/app.component.html` — shared navigation component and non-nested routed content landmark.
- `apps/web/src/app/app.component.css` — `.app-main` layout selectors after removing the shell-level `main`.
- `apps/web/src/app/operations/dashboard.component.ts` — dashboard semantic `main` landmark.
- `apps/web/src/app/intelligence/sourcing-economics-workspace.component.ts` — index-qualified Angular tracking keys for repeated evidence/unknown/limitation/scenario/action collections, preventing duplicate-key runtime warnings.
- `docs/ux/seller-os-capability-matrix.md`, `docs/ux/seller-os-implementation-roadmap.md`, and `docs/ux/seller-os-journey-map.md` — PR-UX-01F coverage and status notes.

Other dirty files in the worktree are historical PR-UX/PR changes and were not reset or rewritten by this certification.

### D. Supported journey coverage

The authenticated route matrix covered Dashboard, Business Agent, Product Opportunities, Product Opportunity detail, Cross-marketplace Supplier Intelligence, Due Diligence, Sourcing Economics, and Supplier Engagement. Context links preserve goal, opportunity, supplier, journey, engagement, and response identifiers through the supported transitions.

### E. Dashboard and Business Agent

Dashboard and Business Agent render the canonical journey/next-action state, including blocked, review-required, empty, and provider-unavailable copy. The disposable Business Agent fixture intentionally had no plan/latest-run rows; its two expected `404` probes were rendered as the truthful empty/blocked state. No uncaught Angular error occurred.

### F. Product Opportunity surfaces

Product list and detail routes load owner-scoped canonical projections and keep evidence gaps and HUMAN selection boundaries visible. The route matrix confirmed a product detail heading and preserved product context on supplier, economics, and engagement links. No product or demand claim is invented by the frontend.

### G. Supplier discovery

Supplier discovery and comparison remain read-only projections of the canonical supplier authority. The browser fixture exposed the selected product and supplier IDs, sources, confidence, freshness, risk, contradictions, and review actions without contacting a supplier.

### H. Due diligence

Due Diligence rendered supplier/product context, evidence provenance, verification status, contradictions, unknown commercial values, stale/provider states, and HUMAN review boundaries. A foreign or stale context remains an error/blocker rather than a data selection mechanism.

### I. Sourcing economics

Economics renders canonical landed-cost, unit-economics, capital-fit, assumptions, warnings, unknowns, missing inputs, partial calculations, and `NOT_COMPARABLE` states. Repeated collections now use unique index-qualified keys; valid fixture routes produced no Angular NG0955 duplicate-key warnings.

### J. HUMAN and consequential-action boundaries

Selection, commercial decisions, engagement approval, response review, and procurement-readiness controls remain explicit HUMAN actions. The UI recommends next actions but does not silently select a product/supplier, send RFQs, contact suppliers, purchase, pay, or mutate a marketplace.

### K. Engagement and response handoff

The Supplier Engagement route loaded a persisted disposable engagement and response context, displayed draft/approval/authorization boundaries, immutable response evidence, unknowns, and procurement-readiness handoff. It remained local/no-send.

### L. Link, deep-link, and context integrity

Authenticated deep links loaded directly for product detail and supplier engagement. Query-string context was preserved for cross-marketplace, due diligence, and economics routes. No route treated a URL identifier as proof of ownership.

### M. Navigation history and refresh

CDP browser evidence: product detail → supplier engagement, Back returned to product detail, Forward returned to supplier engagement, and Reload preserved the engagement URL and heading. History length was 50 in the disposable browser profile.

### N. Logout and protected routes

Clicking Log out redirected to `/login` with the login heading and email control. Navigating to `/dashboard` after logout redirected back to `/login`; no protected content was exposed.

### O. Responsive evidence

The core route matrix was run at 320, 360, 390, 768, 1024, 1440, and 1920 CSS pixels. Every route had `mainCount: 1`, a correct `h1`, and no horizontal overflow. Reported `scrollWidth` was viewport minus the normal 15px scrollbar at several desktop widths, not content overflow.

| Width | Result |
| ---: | --- |
| 320 | PASS — no overflow, main landmark, expected headings |
| 360 | PASS — no overflow, main landmark, expected headings |
| 390 | PASS — no overflow, main landmark, expected headings |
| 768 | PASS — no overflow, main landmark, expected headings |
| 1024 | PASS — no overflow, main landmark, expected headings |
| 1440 | PASS — full 8-route matrix, no overflow |
| 1920 | PASS — no overflow, main landmark, expected headings |

### P. Accessibility semantics

Automated browser checks found one main landmark per page, a working skip-link target (`#main-content`), headings on every checked route, labelled controls after label-aware inspection, and table captions/headers on economics tables. Shared navigation retains active-page semantics and visible focus styling.

### Q. Keyboard/assistive-technology limitation

The managed CUA helper could not initialize because Windows returned `helper_unknown_error: apply deny-read ACLs`. CDP route and semantic checks were therefore used. A hidden remote Chrome target did not produce reliable focus movement for synthetic Tab dispatch, so full manual keyboard traversal and screen-reader lab coverage are not claimed. No critical keyboard or semantic defect was observed; this is a follow-up verification limitation, not an external-provider failure. No axe-core dependency is installed, so an automated axe report is not claimed.

### R. API resilience and truthful states

The fixture exercised empty/no-plan, blocked/review, local fixture, unknown, and provider-dependent states. The expected Business Agent `404` probes were handled as UI state, not thrown as uncaught errors. Supplier, economics, and engagement surfaces retained source-backed status and did not coerce unknown values to zero.

### S. Runtime warnings and defects fixed

The material PR-UX-01F runtime defect was repeated Angular duplicate-key risk in economics evidence collections. Track expressions were made deterministic with index-qualified keys. The second material defect was nested shell/page landmarks; the shell is now a layout wrapper and routed pages provide the single main landmark.

### T. Performance and bundle

`npm.cmd run build` passed. Measured initial bundle: **507.99 kB raw / 125.07 kB transfer**. Angular reported the existing initial budget warning: the 500.00 kB budget is exceeded by 7.99 kB. Feature code remains lazy-loaded (for example Product Opportunities 108.63 kB, Sourcing Economics 101.47 kB, Intelligence 62.24 kB, Business Agent 51.82 kB). No new runtime crash was introduced.

### U. Automated frontend tests

`npm.cmd test -- --watch=false` passed: **61 test files, 220 tests, 0 failures** (final run after the landmark changes; 14.68s). The earlier run made while the browser-only API override was still set to port 8001 is not counted; the environment was restored to the normal port before the final run.

### V. Backend/regression validation

Focused canonical supplier/engagement/response/certification command passed: **58 passed, 50 warnings** in 679.21s. The warnings are FastAPI `on_event` deprecations. Existing adjacent PR-5B through PR-8C log evidence records **36 passed, 66 warnings**. Existing PR-9A/PR-9B certification evidence records **55 passed**. These are regressions, not new PR-UX-01F authorities.

### W. Static quality and migrations

Focused canonical backend checks passed on 15 source files: **Ruff 0, Black 0, strict mypy 0** (`Success: no issues found in 15 source files`). The disposable migration stability harness passed **1/1 run**, including the full upgrade/downgrade lifecycle through migration 0155. `git diff --check` passed. Angular lint passed with **0 errors, 2 historical lifecycle-interface warnings** in `catch-up-dialog.component.ts` and `reschedule-dialog.component.ts`.

### X. Security, ownership, and trust

Authenticated browser checks confirmed protected-route redirects after logout. Owner-scoped API projections and canonical HUMAN authorities remain the only source of product, supplier, economics, and engagement state. The fixture was disposable and marked deterministic/local; no golden database was modified.

### Y. External-write and remaining-gap confirmation

No supplier site was contacted, no RFQ/email was sent, no procurement/payment/marketplace write occurred, and no external provider was executed by this validation. Remaining non-blocking follow-up: reduce the initial bundle by 7.99 kB, remove the two historical lint warnings, add axe-core/real keyboard and screen-reader lab coverage, and certify live providers separately. A larger historical integration fixture teardown drift remains outside this PR-UX-01F slice and was not altered.

### Z. Final classification

**PR-UX-01F — FULLY VALIDATED (LOCAL / NO EXTERNAL EXECUTION)**

All supported local frontend workflows, route/context/history/logout checks, responsive browser checks, semantic accessibility checks, focused backend regressions, migration stability, static checks, build, lint, and diff validation passed. This classification does not claim live-provider execution, WCAG conformance certification by an assistive-technology lab, or any external supplier action.

## Evidence and reproducibility

- Normal frontend API configuration restored to `http://127.0.0.1:8000/api/v1`.
- Browser validation used a disposable PostgreSQL-backed fixture and a temporary Chrome CDP profile; temporary API/UI processes and profile were stopped after validation.
- No commit or push was performed.
