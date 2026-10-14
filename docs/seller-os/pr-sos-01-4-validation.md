# PR-SOS-01.4 — Accessibility Certification & Final Catalog Release Gate

Validation date: 2026-10-11  
Scope: authenticated Seller Catalog, Product, MediaAsset, Variant, listing-draft, readiness, and HUMAN-review surfaces.  
Environment: disposable PostgreSQL `vayujit_sos014_test`, Alembic `20261017_0157 (head)`, isolated Chrome/CDP profile, Angular dev server on `127.0.0.1:4200`, API on `127.0.0.1:8003`.  
External execution: disabled. No supplier contact, RFQ/email, procurement, payment, marketplace publication, or golden-database write was performed.

## A–Z certification report

### A — Authority and architecture

The one-owner-per-installation architecture remains authoritative. `ck_users_single_owner` and `users_singleton_key_key` were preserved. Existing Product, catalog, MediaAsset, variant, listing-draft, economics, Business Agent, and HUMAN-approval authorities were reused; no parallel approval or catalog authority was introduced.

### B — Browser and database setup

The disposable database was created and migrated from empty state to Alembic head. The fixture was created through canonical owner setup, Product, MediaAsset upload, catalog image association, variant, and listing-draft APIs. The golden database was not opened or modified.

### C — Catalog list

Authenticated `/catalog` rendered the persisted owner-scoped product, filters, clear next action, and safe publication boundary. axe-core 4.11.0: **0 violations, 281 passing checks**.

### D — Empty state

The rendered no-match catalog state was exercised through the real search filter and gave an actionable empty state. axe-core: **0 violations, 251 passing checks**.

### E — Product creation

`/products/new` loaded the canonical brand context and labelled form controls. Submitting an empty form produced the required-name message without an API write. axe-core: **0 violations, 389 passing checks** (the two offscreen textarea checks are documented under K).

### F — Product editing

`/products/{id}/edit` loaded persisted product values and the corrected semantic `<main>` landmark. No product edit was committed during the accessibility run. axe-core: **0 violations, 395 passing checks**.

### G — Product details

`/products/{id}` preserved product identity, status, category, SKU, journey links, and canonical context. axe-core: **0 violations, 461 passing checks**.

### H — Image picker and preview

The catalog workspace displayed the owner-scoped ready Media Library picker and the attached primary image. The authenticated preview returned `200 image/png`; no arbitrary remote URL was accepted.

### I — Variants

The catalog workspace displayed the persisted variant editor and SKU/option context. Variant creation/edit/archive controls remained owner-scoped and optimistic-version protected. Focused catalog tests cover duplicate combinations, invalid options, stale updates, and owner boundaries.

### J — Listing drafts and HUMAN review

The Amazon India draft was completed through the canonical draft API, then the browser clicked **Approve as HUMAN**. The UI showed `approved_for_future_submission`; no remote listing ID or publication action was created. The approved state axe run had **0 violations and 607 passing checks** (offscreen geometry notes under K).

### K — Automated accessibility findings

`axe-core` was installed through the configured npm registry with a lockfile update (`axe-core@4.11.0`). Initial serious `color-contrast` findings (rule `color-contrast`, impact `serious`) affected the Active brand label, active brand name, and current breadcrumb (`#6b8288` on `#f3f7f6`, ratio 3.75:1). The token was changed to `#506b74`; the skip link received an explicit navigation landmark, duplicate breadcrumb labels were separated, status badges no longer use unsupported `aria-label` on a text-only span, and product editors now expose a main landmark. All scanned routes report **zero axe violations** (including zero critical/serious violations).

The remaining axe `incomplete` entries on catalog/editor are not violations: axe cannot determine background when offscreen textareas or a badge are partially obscured by the viewport during geometry analysis. Direct computed-style inspection showed textarea foreground `rgb(18,43,51)` on `rgb(255,255,255)` and no overlay at their real scroll position. These are retained as scanner limitations, not suppressed findings.

### L — Keyboard and focus

Authenticated CDP verification recorded 12 forward Tab targets and 4 reverse Shift+Tab targets, all visible with a 3px focus outline. Enter on the skip link moves focus to `#main-content`. Empty product submission surfaces the required-name error. The mobile menu has an Escape handler; a browser DOM Escape event closes the details element and prevents default. No modal/dialog or keyboard trap was present.

### M — Media security and stale versions

From the authenticated browser session, an image update with the current version returned `200`, replaying the same stale version returned `409`, and the private preview returned `200 image/png`. Existing API regressions additionally cover guessed IDs, cross-owner media, non-ready media, MIME/size/dimension validation, and association-only deletion.

### N — Navigation and responsive checks

Authenticated catalog detail was measured at 360, 390, 768, 1024, and 1440 CSS px. Measured document widths were 345, 375, 753, 1009, and 1425 respectively against inner widths 360, 390, 768, 1024, and 1440; no horizontal overflow was introduced. Evidence screenshots are in `tmp/ux-browser/prsos014-detail-{360,390,768,1024,1440}.png` and `tmp/ux-browser/prsos014-catalog-list.png`.

### O — Owner isolation

The required topology is a single owner per installation. Focused catalog/media/auth tests passed owner-scoped lookups and guessed-ID denial; the prior two-installation probe returned `404` for foreign brand/media/preview IDs. No shared-database second-owner path was introduced.

### P — Product lifecycle and readiness

Readiness remained canonical and HUMAN-gated. Unknown economics and missing marketplace data were not converted to zero. The catalog UI renders blocked, unavailable, loading, empty, and approved-for-future-submission states without inventing commercial values.

### Q — Quality checks

- Angular: **62 test files / 223 tests passed**.
- Angular production build: passed; existing initial bundle warning is **509.18 kB vs 500 kB budget** (warning only, not hidden).
- Angular lint: passed, **0 errors / 2 pre-existing lifecycle warnings**.
- Focused catalog/media/product/auth PostgreSQL suite: **18 passed, 38 warnings**.
- Focused Ruff: passed.
- Focused Black: passed, **6 files unchanged**.
- Strict mypy on catalog/media/products: passed, **15 source files**.
- compileall: passed for catalog and focused tests.
- Alembic current/upgrade: `20261017_0157 (head)`; idempotent upgrade passed.
- `git diff --check`: passed.

### R — Regression boundary

The focused suite exercised catalog conversion/HUMAN selection, listing readiness and stale versions, variants, economics-unavailable behavior, private media and optimistic image updates, product lifecycle, and authentication. No production or golden schema was changed.

### S — Single-owner constraint

`ck_users_single_owner` remains present and enforced. The certification does not claim a same-database two-owner test because that topology is intentionally forbidden by the installation architecture.

### T — Video schema defect triage

The unrelated defect remains documented: ORM expects `video_generations.storyboard_version`, while the existing migration created `storyboardversion`. Catalog, media, product, listing-draft, and shared startup paths ran without requiring that table, so no video migration was modified to obtain a green catalog report. It remains outside PR-SOS-01.4 and should be repaired under a separately scoped video migration task.

### U — External-write safety

No supplier site, marketplace connector, email, RFQ, procurement, payment, or external write was invoked. API and UI boundaries continue to state preparation-only and HUMAN review requirements.

### V — Dependency and registry integrity

`axe-core@4.11.0` was installed using normal npm integrity/lockfile resolution from the configured registry. npm reported **10 existing dependency vulnerabilities (2 moderate, 5 high, 3 critical)**; no automatic audit fix was run because that would expand scope.

### W — Worktree and golden database

The worktree remains intentionally uncommitted and includes historical PR work. No commit or push was made. `vayujit_golden_test` was not modified; all persisted fixture activity used `vayujit_sos014_test`.

### X — Remaining limitations

Automated axe is not a substitute for a full manual WCAG/screen-reader audit. The two offscreen `incomplete` geometry records are retained for follow-up. The bundle-budget warning and unrelated video schema mismatch remain visible. No marketplace publication or live supplier certification is implied.

### Y — Changed files in this closure

- `apps/web/package.json`, `package-lock.json` — add locked `axe-core@4.11.0`.
- `apps/web/src/styles.css` — accessible muted-text token.
- `apps/web/src/app/app.component.html/.ts` — skip-navigation landmark, explicit focus restoration, Escape-close mobile menu, shared navigation usage.
- `apps/web/src/app/shared/breadcrumbs.component.ts` — configurable accessible breadcrumb labels.
- `apps/web/src/app/shared/status-badge.component.ts` — remove unsupported ARIA label from text-only status.
- `apps/web/src/app/products/product-form.component.ts` — semantic main landmark.
- `tmp/ux-browser/*` — disposable fixture/CDP evidence helpers only.

### Z — Final classification

**PR-SOS-01 — FULLY VALIDATED (LOCAL / NO MARKETPLACE PUBLICATION)**

All applicable catalog certification gates, including automated accessibility scans with zero critical/serious violations, authenticated keyboard checks, owner-scoped media/stale-version checks, responsive browser evidence, focused PostgreSQL regressions, Angular tests/build/lint, static checks, and migration validation passed. The classification is local-only and does not authorize marketplace publication, supplier contact, procurement, or any external write.
