# VAYUJIT OS — PR-SOS-01.3 Owner Isolation Architecture Decision & Accessibility Certification

Validation date: 2026-10-11  
Scope: local, disposable PostgreSQL and authenticated application checks only.  
Golden database, marketplace publication, supplier contact, RFQ, procurement,
payment, commit, and push were not performed.

## A. Final result

**PR-SOS-01 — IMPLEMENTED / CERTIFICATION PENDING**

The owner architecture is resolved as one owner per installation/database and
the applicable authorization, catalog, media, migration, frontend, and static
checks pass. Automated accessibility certification remains pending because no
axe-core or established equivalent is installed locally and no package was
downloaded outside the approved offline boundary. Same-database two-owner
tests are **NOT APPLICABLE TO CURRENT ARCHITECTURE**.

## B. Ownership architecture decision

The production model is one local owner per installation/database. Evidence:

- `identity.models.User` declares `singleton_key` as unique and applies
  `CheckConstraint("singleton_key = 1", name="ck_users_single_owner")`.
- Migration `20260727_0002_local_owner_auth.py` creates the same check and
  uniqueness constraint.
- `/api/v1/auth/setup-owner` creates the first owner and maps any integrity
  collision to HTTP 409 (`Owner setup is already complete.`).
- All catalog, media, product, brand, supplier, and approval queries still
  include the authenticated owner ID; owner-scoped code is defense in depth,
  not evidence of shared-database multi-tenancy.

No tenant-membership migration or shared-database owner contract is present.
The constraint was retained; no production schema or authority was changed.

## C. Same-database two-owner applicability

Two-owner tests in one database are **NOT APPLICABLE TO CURRENT ARCHITECTURE**.
Dropping the constraint in a test would validate a topology the product does
not support and would weaken the authority under review. Future multi-owner
support requires a separately reviewed tenant design and is outside PR-SOS-01.3.

## D. Disposable database and migration proof

Fresh marker-protected databases:

- `vayujit_sos013_test`
- `vayujit_sos013b_test`

Both migrated base → `20261017_0157 (head)` using Alembic. The golden database
`vayujit_golden_test` was not opened or modified.

## E. Authentication and setup boundaries

`test_auth_integration.py` passed all 4 tests: unauthenticated `/me`, setup,
duplicate setup/hashed password storage, generic throttling, expired sessions,
disabled-owner rejection, and logout/login session behavior.

## F. Catalog authorization

`test_pr_sos_01_catalog.py` passed all 6 tests. Coverage includes HUMAN
selection-gated conversion, owner-scoped supplier association, guessed IDs,
variant validation, stale optimistic replay, canonical economics unknown state,
and owner-scoped product-image association.

## G. Media authorization and security

`test_media_integration.py` plus `test_ai_image_security.py` passed in the
focused run. Coverage includes unauthenticated media reads, MIME/content and
filename rejection, duplicate-safe upload, authenticated private preview,
archive/restore, maintenance kill-switch, and owner-bound lookup.

## H. Installation isolation probe

Installation A created owner `install-a@example.com`, brand ID
`aa03a573-ea9a-4e9a-a3f1-8d74e2d9ad88`, and private MediaAsset ID
`89ea34e8-f4e2-4ba7-aae4-958bc6f661dd` through canonical APIs. Installation B
created its independent owner `install-b@example.com`; reads of A's brand and
media (including `/preview`) returned HTTP 404. No cross-installation data was
observed.

## I. Forged and mismatched identifiers

Catalog tests reject random product, draft, variant, media, and opportunity
IDs with safe 404/409 responses. The repository single-owner harness also
confirmed second setup returns 409 and forged brand/product/media/content IDs
do not disclose records until it reached an unrelated pre-existing video
schema failure (see T).

## J. Stale authorization/version safety

Catalog image and listing optimistic updates reject stale replays with HTTP
409. Session expiry, revocation, disabled-owner state, and logout reject stale
authentication. Browser stale replay was not repeated because the applicable
backend authority already passed and the isolated CDP session had been closed.

## K. Private media behavior

Authenticated owner preview passed with `Cache-Control: private` and
`X-Content-Type-Options: nosniff`. A foreign installation received 404 for
both metadata and preview. No unrestricted storage URL is returned.

## L. Browser evidence

The PR-SOS-01.2 isolated Chrome/CDP evidence remains the available browser
baseline: authenticated catalog/product editor/workspace, upload/association,
variant creation, listing draft/HUMAN approval, deep links, refresh,
back/forward, logout/protected route, skip-link activation, and responsive
overflow at 320/360/390/768/1024/1440px. No second same-database owner was
required or fabricated for this architecture decision.

## M. Accessibility dependency audit

Repository, `node_modules`, and npm cache searches found no `axe-core`,
Playwright accessibility runner, pa11y, Lighthouse, or other established
engine. No network installation was attempted. A homemade DOM heuristic was
not treated as an accessibility scan.

## N. Automated accessibility result

**PENDING**. The catalog, product editor, variants, image picker, listing
draft, readiness, and HUMAN approval surfaces therefore have no axe/equivalent
result in this run. Existing semantic Angular tests and keyboard subset remain
useful but do not establish WCAG conformance.

## O. Keyboard and semantic checks

The existing CDP evidence verified Tab traversal and Enter activation of the
skip link, with focus moving to `#main-content`; semantic labels/status text
remain covered by Angular tests. Full assistive-technology, Shift+Tab,
dialog-focus, and every form-error path remain unverified.

## P. Angular tests

`npm.cmd run test --workspace @vayujit/web -- --watch=false`: **62 test files,
223 tests passed**.

## Q. TypeScript, lint, and build

- `npx tsc --noEmit -p apps/web/tsconfig.app.json`: passed.
- Angular lint: 0 errors, 2 pre-existing lifecycle warnings in campaign dialog
  components.
- Angular production build: passed; existing initial bundle warning remains
  (508.63 kB versus 500 kB budget).

## R. Python quality checks

Scoped strict mypy (`identity`, `catalog`, `media`): passed, 15 source files.
Ruff: passed. Black check: passed, 15 files unchanged. `compileall`: passed.
`git diff --check`: passed; only normal Windows LF/CRLF notices were emitted.

## S. Focused test totals

The focused PR-SOS-01.3 run produced **22 passed, 24 warnings** in 181.89s:
4 auth tests, 1 media integration test, 11 image-security cases, and 6
catalog tests. Warnings are existing FastAPI `on_event` deprecations.

## T. Adjacent regression limitation

`test_final_owner_isolation.py` started successfully and verified setup 409
plus forged brand/product/media/content/image IDs, then exposed a pre-existing
unrelated migration/schema mismatch: the ORM selects
`video_generations.storyboard_version`, while the migrated table contains
`storyboardversion`. This is outside PR-SOS-01.3 catalog/media scope; no broad
video refactor or migration rewrite was made.

## U. Security and external-write confirmation

No supplier or marketplace was contacted. No RFQ, email, purchase, payment,
procurement, listing publication, or external write occurred. No auth,
HUMAN-review, owner, media, or migration guard was weakened.

## V. Changed implementation surface

No production source, migration, or security-control change was necessary for
PR-SOS-01.3: the single-owner invariant and owner-scoped authorities already
match the intended architecture. This slice adds the architecture decision,
certification evidence, and roadmap/matrix updates only.

## W. Golden database and repository state

`vayujit_golden_test` is unchanged. No commit or push was made. Historical
worktree changes from prior slices were preserved.

## X. Remaining evidence gaps

1. Install an approved local axe/equivalent engine and scan all requested
   catalog surfaces.
2. Complete the remaining browser stale-version/media-auth transitions with a
   fresh isolated CDP session if desired.
3. Repair the unrelated `video_generations.storyboard_version` migration drift
   before claiming a full repository-wide owner-isolation pass.

## Y. Certification gate decision

Applicable owner architecture, auth, resource-ID, private-media,
stale-session/version, installation-isolation, migration, Angular, and static
checks passed. Same-database two-owner gates are N/A by architecture.
Automated accessibility is not executable in the current offline environment;
therefore the full PR-SOS-01 closure classification is intentionally withheld.

## Z. Final classification

**PR-SOS-01 — IMPLEMENTED / CERTIFICATION PENDING**

No PR-SOS-02 work was started.
