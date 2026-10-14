# PR-SOS-02 — Amazon India Seller Integration, Catalog Mapping & Controlled Listing Operations

## A–Z implementation and validation report

**Classification:** **PR-SOS-02 — FULLY VALIDATED (LOCAL / FAKE AMAZON TRANSPORT / NO LIVE MARKETPLACE MUTATIONS)**

This slice adds the missing controlled-listing boundary on top of the existing
owner-scoped Amazon adapter and seller catalog authorities. It does not claim
Amazon SP-API certification or publish a listing.

### A. Authority audit

The existing `MarketplaceAccount`, `MarketplaceListing`, `GeneratedArtifact`,
catalog, media, variant, price, inventory, audit, and worker authorities remain
canonical. No duplicate product, listing, economics, or approval authority was
introduced.

### B. Amazon India mapping

The existing adapter remains the source of truth for India (`A21TJRUUN4KGV`,
INR, `en-IN`, `eu-west-1`). Product types and attributes remain server-driven.

### C. Credential safety

Credentials continue to be encrypted and write-only. The local transport is
`FakeAmazonSPAPITransport`; no token, signed request, provider payload, or
secret is returned to the browser.

### D. Durable HUMAN controls

`amazon_listing_reviews` records HUMAN approval of the exact listing title,
SKU, product type, attributes, and approved Artifact version. A separate
`amazon_listing_execution_authorizations` row is single-use, owner-scoped,
expiry-bound, idempotent, revocable, and fingerprint-bound to that review.

### E. Execution boundary

`POST /api/v1/marketplaces/amazon/listings/{id}/submit` now requires an
authorization ID. It locks and consumes the authorization, rejects stale
listing/artifact context, returns a durable idempotent replay, and fails closed
when the emergency stop or live-mutation flag is enabled without a real
transport. Local success is explicitly labelled `LOCAL_FAKE`.

The durable Amazon publishing worker also fails closed for generic publish jobs
because those jobs do not carry a consumable HUMAN authorization identity.
This prevents a scheduler path from bypassing the HTTP approval boundary.

### F. Frontend journey

The Amazon workspace now exposes the sequence: preview readiness → approve the
exact listing payload → issue one-time execution authorization → submit. The
UI shows review/authorization status, expiry, revoke, disabled prerequisites,
and the local-only provider boundary.

### G. Database migration

Migration `20261018_0158_pr_sos_02_controls.py` creates both owner-scoped
tables with foreign keys, status checks, indexes, and idempotency uniqueness.
Fresh migration validation completed on disposable database
`vayujit_migration_test` through Alembic head.

### H. Focused backend tests

The focused unit suite passed **11 tests** (`test_amazon.py`,
`test_amazon_e2e.py`, `test_amazon_workers.py`). The new PostgreSQL control
suite passed **2 tests**: HUMAN review/authorization/idempotent replay and
stale-context rejection. The existing Amazon API and integration wrappers also
passed their previously focused lifecycle checks (1 test each).

### I. Security cases covered

Owner-scoped listing lookup, owner-scoped review/auth lookup, missing approval,
missing authorization, revoked/expired/consumed status handling, stale
fingerprint rejection, emergency-stop fail-closed behavior, and live-mode
unconfigured fail-closed behavior are implemented. No cross-owner data is
returned by these routes.

### J. Idempotency and concurrency

Review payloads are unique by owner/listing/fingerprint. Execution authorizations
are unique by owner/listing/operation/idempotency key and are locked during
submit. A consumed authorization returns the stored safe result instead of
calling the provider again.

### K. Mock-provider scenarios

Existing deterministic fake coverage remains in place for success,
idempotency, processing, throttling, rejection, ambiguity, reconciliation,
media, variants, pricing, inventory, orders, returns, fees, settlements, and
drift. No scenario represents live Amazon.

### L. Angular validation

Angular suite: **62 files / 223 tests passed**. Production build completed.
Lint completed with **0 errors and 2 pre-existing lifecycle warnings** in
unrelated campaign dialogs. The build retains the pre-existing 500 kB initial
bundle warning (actual 509.18 kB).

### M. Accessibility and responsive UX

The new controls use native buttons, disabled prerequisite states, live status
text, and keyboard-operable actions. Existing PR-SOS-01.4 axe/browser evidence
remains valid for the shared catalog shell. A fresh PR-SOS-02 authenticated
axe pass was not run in this bounded local change; automated WCAG compliance is
not inferred from unit tests.

### N. Network and safety

No live Amazon request, supplier contact, RFQ, purchase, payment, or marketplace
write was performed. The implementation continues to use the deterministic
local fake transport and existing emergency-stop/live-mutation flags.

### O. Observability and audit

Review issued, execution authorization issued/revoked, and authorization
consumed events are written through the existing audit authority. Safe result
metadata excludes credentials and raw provider payloads.

### P. Static checks

Focused Ruff and Black checks passed for all changed Python files. Python
compileall passed. Angular lint/build passed as described above.

### Q. Migration and database integrity

Fresh disposable PostgreSQL migration chain passed through `20261018_0158`.
The golden database was not modified. Existing integration reset fixtures now
include the new models through `Base.metadata`.

### R. Browser evidence

The existing isolated Chrome/CDP harness and PR-SOS-01.4 responsive evidence
were preserved. The earlier browser-control attempt could not start because the
CUA helper exited with `helper_unknown_error: apply deny-read ACLs`, and no
local Angular dev-server/CDP listeners were available on ports 4200/9224. That
historical limitation was closed by PR-SOS-02.2 using the isolated direct-CDP
fallback; see the final closure addendum below.

### S. Real SP-API certification

Not performed. Production certification still requires a separately approved
transport implementation, Amazon authorization/LWA configuration, provider
contract tests, and explicit operational approval.

### T. Changed files

- `apps/api/vayujit_api/commerce/models.py`
- `apps/api/vayujit_api/commerce/amazon_router.py`
- `apps/api/vayujit_api/commerce/amazon_worker.py`
- `apps/api/alembic/versions/20261018_0158_pr_sos_02_controls.py`
- `apps/api/tests/test_pr_sos_02_amazon_controls.py`
- `apps/web/src/app/marketplaces/amazon-workspace.component.ts`
- `apps/web/src/app/marketplaces/marketplaces.css`
- roadmap, capability matrix, and Amazon integration documentation

### U. Remaining blockers

1. Authenticated Chrome/CDP and axe evidence for the new Amazon workspace
   controls at 360/390/768/1024/1440px. The current environment blocker is the
   browser-helper ACL failure and unavailable 4200/9224 listeners described in R.
2. Official Amazon SP-API transport and live sandbox certification, which is
   intentionally outside this no-external-write task.
3. Two unrelated pre-existing Angular lint warnings and the existing bundle
   budget warning.

### V. HUMAN actions required for a later release

An operator must configure approved Amazon credentials and separately authorize
any live transport. This report does not request or store those credentials.

### W. Restrictions confirmed

No golden database modification, commit, push, supplier acquisition, RFQ,
procurement, payment, marketplace publication, or PR-SOS-03 work occurred.

### X. Final decision

The implementation and deterministic local validation are complete, but the
release gate remains **PR-SOS-02 — IMPLEMENTED / CERTIFICATION PENDING** until
the dedicated authenticated browser/axe evidence and a separately authorized
Amazon sandbox certification are available. The local provider is never
represented as real Amazon.

### PR-SOS-02.1 recovery addendum

The dedicated PR-SOS-02.1 browser recovery and accessibility run completed
the Amazon overview, connection, listing readiness, HUMAN review, one-time
authorization, local fake submission, consumed replay, revoke, refresh, logout,
and protected-route checks. Axe-core 4.11.0 reported zero violations and zero
incomplete findings across the required 320/360/390/768/1024/1440px views and
the overview, connection, review, authorization, submission, revoked, and error
states. The focused control suite then passed 4 tests, including drift UUID
serialization and negative authorization/kill-switch cases. The two rows that
were still unexecuted at this historical milestone were closed by PR-SOS-02.2.
See
[`pr-sos-02-1-validation.md`](pr-sos-02-1-validation.md) for the complete
evidence-backed closure report. Real Amazon OAuth, SP-API certification, and
live publication remain out of scope.

### PR-SOS-02.2 final closure addendum

PR-SOS-02.2 executed the two remaining local browser certification scenarios:
the genuine incomplete-listing blocker and stable browser history/deep-link
navigation. Both passed in authenticated isolated Chrome. The blocked listing
showed the exact server-derived missing artifact, variant, image, and price
requirements, kept HUMAN review/authorization/submission unavailable, and
re-evaluated readiness after a canonical media correction. The complete
listing retained its identifier, owner context, Ready status, approved review,
and one-time authorization across back/forward history restoration, refresh,
and a second authenticated deep-link tab. CDP runtime/console error capture
reported zero errors. Axe-core reported zero violations/incomplete findings
on the complete and blocked/correction states.

The bounded drift repair persists `remote_kept` on the listing and preserves
resolved field state on replay; the focused regression now covers this exact
readiness boundary. Final results were 5 focused controls tests passed, 11
adjacent Amazon adapter/E2E/worker tests passed, 62 Angular files / 223 tests
passed, focused Ruff/Black/strict mypy/compileall passed, production build and
lint passed (pre-existing bundle/lifecycle warnings only), and `git diff
--check` passed. See [`pr-sos-02-2-validation.md`](pr-sos-02-2-validation.md)
for the A–Z evidence ledger.

**PR-SOS-02 — FULLY VALIDATED (LOCAL / FAKE AMAZON TRANSPORT / NO LIVE
MARKETPLACE MUTATIONS).** Real Amazon OAuth, SP-API connectivity, sandbox
acceptance, and production publication remain outside this local certification.
