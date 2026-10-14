# PR-SOS-03.1 - Flipkart local certification recovery

**Date:** 2026-10-11  
**Classification:** **PR-SOS-03 - FULLY VALIDATED (LOCAL / FAKE FLIPKART TRANSPORT / NO LIVE MARKETPLACE MUTATIONS)**

This is the evidence-backed local closure report for PR-SOS-03.1. It covers the
historical migration repair, the authenticated 26-scenario Chrome journey,
axe-core, keyboard and responsive checks, backend regressions, and static
quality gates. No real Flipkart or Amazon credentials, provider calls, listing
publication, supplier action, RFQ, procurement, payment, golden-database
change, commit, or push was performed.

## A-Z certification report

### A. Objective and scope

PR-SOS-03.1 closed the two local blockers carried by PR-SOS-03: migration-from-
zero recovery and authenticated Flipkart browser certification. Existing
canonical catalog, marketplace account/listing, readiness, HUMAN review,
execution authorization, connector, worker, audit, and idempotency authorities
were reused. PR-SOS-04 was not started.

### B. Historical migration root cause

The original failure is reproducible in revision `20260728_0005_ai_content_generation`
when Alembic renders offline SQL. The seed used `op.bulk_insert` with Python
dict values for PostgreSQL JSONB columns. Under the installed Alembic/
SQLAlchemy versions, literal compilation raises:

`sqlalchemy.exc.CompileError: No literal value renderer is available for literal value "{...}" with datatype JSONB`.

This is an Alembic offline literal-rendering problem, not an invalid JSON cast
or a schema dependency problem. The migration was repaired with an explicit
SQL insert using a JSON string and PostgreSQL `::jsonb`, preserving historical
revision, seed semantics, ordering, and schema.

### C. Migration repair and safety

The repair is limited to `20260728_0005_ai_content_generation.py`; already-
migrated databases are unaffected because Alembic does not rerun an applied
revision. No production table was dropped, truncated, stamped, or bypassed.
The Flipkart control migration remains `20261019_0159_marketplace_listing_controls`.

### D. Fresh migration replay

On disposable PostgreSQL database `vayujit_pr_sos031_final`, online
`alembic upgrade head` replayed from an empty database to
`20261019_0159 (head)` successfully. The same database was used for the
browser fixture after migration.

### E. Earlier-revision upgrade replay

On disposable database `vayujit_pr_sos031_upgrade1011`,
`alembic upgrade 20261010_0151` completed, followed by `alembic upgrade head`.
`alembic current` reported `20261019_0159 (head)`.

### F. Offline SQL limitation

`alembic upgrade head --sql` now passes repaired 0005 but stops at the
pre-existing `20260728_0007_workflow_orchestration` JSONB bulk seed with the
same offline literal-rendering class of error. Online fresh and upgrade replays
pass; this unrelated historical offline-only issue is documented and was not
changed as unrelated feature work.

### G. Browser harness and isolation

An isolated Chrome/CDP profile, disposable PostgreSQL database, API on port
8013, Angular app on port 4200, deterministic fake Flipkart provider, and a
persisted authenticated fixture were used. Authentication and owner-scoped
routes remained enabled; no authorization bypass or live-provider switch was
used.

### H. Authenticated browser scenarios 1-8

**PASS:** login; marketplace overview; disconnected Flipkart state; fake
connection; product selection; listing draft creation/open; listing editing;
and initial readiness/review screen.

### I. Incomplete-listing blocker (scenario 9)

**PASS.** Server readiness returned `ready:false` with missing `variants`,
`media`, and `price`; HUMAN review returned HTTP 409. The UI exposed the actual
missing-information state and did not permit an authorization bypass.

### J. Correction and reassessment (scenario 10)

**PASS.** Persisting variants, media, and INR price returned HTTP 200; fresh
readiness returned `ready:true`; review returned HTTP 200 with exact context.

### K. Authorization lifecycle (scenarios 11-12)

**PASS.** Authorization creation returned HTTP 201 with `expires_at` and exact
artifact/fingerprint binding. Revoke returned HTTP 200 and subsequent submit
returned HTTP 409. Browser TTL metadata was checked; elapsed-time expiry is
covered by backend expiry regression.

### L. Valid submission and idempotent replay (scenarios 13-14)

**PASS.** A valid single-use authorization produced an accepted fake-provider
result and remote id `FK-LISTING-2a1007ac3183`. Replaying the same idempotency
contract returned HTTP 200 with `idempotent_reuse:true`; no second provider
execution was created.

### M. Reconciliation (scenario 15)

**PASS.** Reconciliation returned HTTP 200 and persisted `active` state with
the same remote id.

### N. Stale artifact rejection (scenario 16)

**PASS.** A changed listing/artifact context returned HTTP 409 and could not
reuse prior review or authorization.

### O. Provider rejection (scenario 17)

**PASS.** The fake provider returned a rejected SKU-conflict response. A
regression test and browser assertion prove a rejected response carrying a
remote id does not persist a remote listing claim or false success.

### P. Unknown provider outcome (scenarios 18 and 22)

**PASS.** The fake provider returned `unknown`/`PROCESSING`; reconciliation
returned HTTP 200 and the deterministic state converged to the active remote
projection. No blind replay was attempted.

### Q. Deep link and navigation (scenarios 19-23)

**PASS.** Authenticated deep link loaded with correct listing/account context.
Browser Back, Forward, and Refresh preserved route and persisted state. A
second CDP target opened the same deep link without cross-context leakage.

### R. Logout and protected routes (scenarios 24-25)

**PASS.** Logout returned HTTP 204; the protected listing route redirected to
`/login`; no private listing data was exposed after logout.

### S. External-write safety (scenario 26)

**PASS.** Only the injected deterministic fake transport was reachable. No
Flipkart/Amazon network call, supplier contact, RFQ, procurement, payment, or
marketplace mutation occurred.

### T. Scenario ledger

| # | Scenario | Result | Evidence |
|---:|---|---|---|
| 1 | Login | PASS | Authenticated session established |
| 2 | Marketplace overview | PASS | Flipkart route loaded |
| 3 | Disconnected state | PASS | Account state shown |
| 4 | Fake-provider connection | PASS | Connection persisted |
| 5 | Select catalog product | PASS | Owner-scoped product selected |
| 6 | Create/open listing draft | PASS | Draft route loaded |
| 7 | Edit supported attributes | PASS | Server update succeeded |
| 8 | Initial readiness/review screen | PASS | Readiness UI loaded |
| 9 | Genuine incomplete blocker | PASS | `ready:false`; review 409 |
| 10 | Correct and reassess | PASS | Updates 200; readiness true; review 200 |
| 11 | Authorization expiry metadata | PASS | Auth 201 with `expires_at` |
| 12 | Revocation | PASS | Revoke 200; submit 409 |
| 13 | Valid single-use submission | PASS | Accepted fake result |
| 14 | Consumed idempotent replay | PASS | 200; `idempotent_reuse:true` |
| 15 | Reconciliation | PASS | Active remote projection |
| 16 | Stale artifact | PASS | 409 |
| 17 | Provider rejection | PASS | Rejected SKU conflict; no claim persisted |
| 18 | Unknown provider outcome | PASS | Unknown/PROCESSING recorded |
| 19 | Authenticated deep link | PASS | Exact listing/account route |
| 20 | Browser Back | PASS | Route/context retained |
| 21 | Browser Forward | PASS | Route/context retained |
| 22 | Refresh | PASS | Persisted state retained |
| 23 | Same deep link in new target | PASS | `Target.createTarget` succeeded |
| 24 | Logout | PASS | HTTP 204 |
| 25 | Protected route | PASS | Redirected to `/login` |
| 26 | No live mutation | PASS | Fake transport only |

**Totals:** 26 PASS, 0 FAIL, 0 BLOCKED, 0 NOT EXECUTED.

Browser artifacts: `tmp/ux-browser/prsos031-flow2-final.log` and
`tmp/ux-browser/prsos031-browser-results-full.json`.

### U. Accessibility

`axe-core` 4.11.0 scans on protected/login and authenticated listing screens
reported **0 violations**, **0 incomplete findings**, and 65/615 passing rules
respectively. The authenticated scan includes connected, review,
authorization, rejection, unknown, and reconciliation projections. A serious
incomplete `aria-prohibited-attr` finding on the inner tab container was fixed
with `role="tablist"`, `role="tab"`, and `aria-selected`; the post-fix scan is
clean. This is automated evidence, not a complete WCAG-conformance claim.

### V. Keyboard and responsive checks

Tab and Shift+Tab traversal passed with visible focus, and the skip link focused
`main-content`. Escape kept the route stable and focus restoration was
verified. Widths 320, 360, 390, 768, 1024, and 1440 px passed without
page-level horizontal overflow or clipped primary actions. The CDP synthetic
Enter/Space interaction helper did not observe section changes even though the
controls are native buttons; this harness assertion is inconclusive and is
retained as a follow-up browser-evidence limitation rather than claimed as a
pass.

### W. Backend regression results

- Focused PR-SOS-03 suite: **3 passed, 8 warnings**.
- PR-SOS-01 catalog + PR-SOS-02 Amazon + PR-SOS-03 Flipkart matrix:
  **14 passed, 30 warnings, 0 failures**.
- The new regression covers provider rejection with a conflicting remote id;
  the persisted listing remains unclaimed.

### X. Frontend and static quality results

- Angular: **62 files, 223 tests passed**.
- Angular lint: passed; two existing lifecycle-interface warnings remain.
- Angular production build/type checking: passed; existing initial bundle budget
  warning remains (509.18 kB versus 500 kB) and was not suppressed.
- Ruff, Black `--check`, focused strict mypy, Python compileall, and
  `git diff --check`: passed.

### Y. Security, ownership, and immutable evidence

Owner/account/marketplace/listing/artifact/fingerprint binding, HUMAN-only
review, expiring/revocable single-use authorization, replay idempotency,
emergency-stop, live-mode deny, audit provenance, and protected-route behavior
remain enforced. `ck_users_single_owner` and the one-owner-per-installation
architecture were preserved. The golden database was not modified.

### Z. Final classification and external boundary

**PR-SOS-03 - FULLY VALIDATED (LOCAL / FAKE FLIPKART TRANSPORT / NO LIVE MARKETPLACE MUTATIONS)**

This classification covers local deterministic certification only. It does not
certify real Flipkart seller authorization, API connectivity, sandbox behavior,
production listing acceptance, or live publication. The offline-only failure in
later historical migration 0007 and the inconclusive synthetic Enter/Space CDP
assertion remain explicitly documented; neither blocked the required online
migration or 26-scenario local journey.
