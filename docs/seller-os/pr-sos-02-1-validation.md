# PR-SOS-02.1 — Amazon Local Certification Recovery & Controlled Integration Validation

## A–Z evidence report

**Final classification:** **PR-SOS-02 — IMPLEMENTED / LOCAL CERTIFICATION PENDING**

This closure certifies the deterministic local Amazon India integration only. It
does not certify Amazon seller OAuth, SP-API connectivity, Amazon sandbox
approval, production approval, listing publication, or any live marketplace
mutation.

### A. Authority audit

The validation reuses the canonical `MarketplaceAccount`,
`MarketplaceListing`, `GeneratedArtifact`, catalog product, media, variant,
price, inventory, audit, and worker authorities. Review and execution
authorization remain the separate durable HUMAN authorities introduced by
PR-SOS-02.

### B. Browser environment recovery

The supplied Computer Use helper remained unavailable with
`helper_unknown_error: apply deny-read ACLs`. Per the specification, it was not
repeated without a meaningful change. The existing project CDP harness was
used instead with an isolated Chrome profile, a disposable PostgreSQL database
(`vayujit_sos021_test`), Angular on `127.0.0.1:4200`, and the API on
`127.0.0.1:8004`.

The fixture owner, Amazon India account, approved artifact, listing, 600×600
PNG media asset, canonical variant, media mapping, and INR price were created
through supported local application authorities. No golden database was used.

### C. Browser journey matrix

| Scenario | Result | Evidence |
| --- | --- | --- |
| Login | PASS | Authenticated disposable seller session in isolated Chrome |
| Marketplace overview | PASS | `/marketplaces`, channel-health row and Open channel route |
| Amazon connection state | PASS | `/marketplaces/amazon`, configured/valid LOCAL_FAKE account |
| Catalog product mapping | PASS | Listing page showed product title, SKU, product type, variant, media, and price |
| Listing artifact review | PASS | Server readiness `Ready`, approved Artifact v1 |
| Exact title/SKU/product type/attributes | PASS | Listing editor and readiness rendered canonical values |
| Incomplete-listing blockers | NOT EXECUTED in browser | Ready fixture intentionally had no incomplete blockers; negative readiness remains backend-covered |
| HUMAN listing review | PASS | `Listing review: approved (Artifact v1)` |
| Review version/fingerprint | PASS | Durable review response and Artifact v1 were visible |
| One-time authorization | PASS | `Execution authorization: issued` with expiry |
| Expiry/revoke controls | PASS | Expiry rendered; revoke action returned `revoked` |
| Submit disabled without authorization | PASS | Initial DOM had submit disabled before review/authorization |
| Local fake submission | PASS | UI reported `Amazon listing submission recorded`; provider mode `LOCAL_FAKE` |
| Authorization consumed | PASS | UI rendered `consumed`; submit became disabled |
| Consumed replay | PASS | Authenticated browser replay returned HTTP 200 with `idempotent_reuse: true` |
| Stale listing content | PASS | Focused PostgreSQL regression returned HTTP 409 |
| Revoked authorization | PASS | Browser revoked state plus focused regression returned HTTP 409 |
| Expired authorization | PASS | Focused regression returned HTTP 409 |
| Emergency stop | PASS | Focused regression returned HTTP 503 and did not consume authorization |
| Live-mode disabled | PASS | Focused regression returned HTTP 409; no provider call was enabled |
| Status/error messaging | PASS | Safe submission, drift, and invalid-listing error states rendered without secrets |
| Refresh/deep link | PASS | Listing route survived reload and rehydrated server state |
| Back/forward | NOT EXECUTED | CDP history calls were attempted, but the Angular route transition did not provide a stable post-call target; no false pass is claimed |
| Logout | PASS | Authenticated shell returned to `/login` |
| Protected deep link after logout | PASS | Direct Amazon listing URL resolved to the login state |

The two explicitly unexecuted browser rows are not live-provider blockers, but
they are still required local browser evidence. The same state boundaries are
covered by deterministic API regressions; no browser pass is claimed for those
rows, so the full local release classification remains pending.

### D. Accessibility scans

`axe-core@4.11.0` was loaded from the existing approved frontend dependency.
After fixing the Amazon template, every scan reported **0 violations and 0
incomplete findings**:

| State / route | Viewports | Result |
| --- | --- | --- |
| Marketplace overview | 1440px | 0 violations, 0 incomplete |
| Amazon connection state | 1440px | 0 violations, 0 incomplete |
| Approved listing review | 1440px | 0 violations, 0 incomplete |
| Authorization issued | 1440px | 0 violations, 0 incomplete |
| Submission result / consumed authorization | 320/360/390/768/1024/1440px | 0 violations, 0 incomplete at every width |
| Revoked/blocked authorization | 1440px | 0 violations, 0 incomplete |
| Invalid-listing error state | 1440px | 0 violations, 0 incomplete |

The first 320px scan exposed missing labels for variant/media table inputs,
missing keyboard access on a horizontally scrollable drift table, and the
shared shell's missing main landmark. Those were corrected and all scans were
rerun successfully.

### E. Keyboard and responsive checks

Native buttons and inputs remain keyboard-operable. Table regions now have
`role="region"`, `tabindex="0"`, and accessible names; dynamic variant/media
inputs have explicit accessible labels; the shell uses a real `<main>` landmark.
The skip link and native form controls remain available for Tab, Shift+Tab,
Enter, and Space interaction. No page-level horizontal overflow was observed
at 320, 360, 390, 768, 1024, or 1440px. Horizontal scrolling is confined to
the intentionally scrollable data tables.

### F. Backend control regressions

The focused PostgreSQL suite `test_pr_sos_02_amazon_controls.py` passed **4
tests** with **10 expected deprecation warnings**:

- HUMAN review → single-use authorization → local submission → idempotent replay;
- stale listing payload rejection;
- UUID-safe drift JSONB serialization;
- expired, revoked, emergency-stop, and live-mutation-disabled rejection.

Adjacent adapter/E2E/worker suites passed **11 tests** with **2 expected
FastAPI lifecycle warnings**.

### G. Drift defect fixed

The browser discovered a real 500 from `GET .../drift`: a UUID-valued
`media_id` was being inserted into JSONB. The smallest fix converts only that
serialized identifier to `str(row.media_id)`. A focused regression now proves a
drift response with mapped media returns HTTP 200 and a JSON string identifier.

### H. Frontend quality gates

- Angular: **62 test files / 223 tests passed**.
- Production build: passed; existing initial bundle warning remains at
  509.18 kB against a 500 kB budget.
- Angular lint: 0 errors, 2 pre-existing unrelated lifecycle warnings in
  campaign dialogs.
- axe: zero violations/incomplete findings in the scans above.

### I. Infrastructure and database

The marker-protected migration lifecycle passed from base to head, including
`20261018_0158_pr_sos_02_controls.py`, the review/authorization tables,
foreign keys, status checks, and idempotency uniqueness constraints. The
disposable migration database was removed afterward. The golden database was
not modified.

### J. Static checks

Focused Ruff, Black, strict mypy for `amazon_router.py`, Python compileall, and
`git diff --check` passed. The only visible lint/build notices are the
pre-existing warnings stated above.

### K. Local provider boundary

All browser and API mutation evidence used `FakeAmazonSPAPITransport` and
`execution_mode=LOCAL_FAKE`. Credentials are write-only/encrypted and were not
returned to the browser. The emergency-stop and live-mutation flags fail closed.

### L. Live provider limitation

Real seller OAuth/LWA, signed SP-API requests, Amazon sandbox certification,
production credentials, live listing publication, and remote reconciliation
remain intentionally unvalidated and require separate operator authorization.

### M. Network and external-write confirmation

No Amazon network call, supplier contact, RFQ, procurement, purchase, payment,
marketplace publication, or other unauthorized external write occurred.

### N. Changed files

- `apps/api/vayujit_api/commerce/amazon_router.py` — UUID-safe drift JSON;
- `apps/api/tests/test_pr_sos_02_amazon_controls.py` — drift and negative
  authorization regressions;
- `apps/web/src/app/app.component.html` — shared main landmark;
- `apps/web/src/app/marketplaces/amazon-workspace.component.ts` — input labels,
  seller autocomplete, focusable table regions, and valid main-image markup;
- `apps/web/src/environments/environment.ts` — restored to the normal local API
  port after isolated browser validation;
- this report, the prior PR-SOS-02 report, roadmap, and capability matrix.

### O. Remaining evidence gaps

The two browser interactions marked NOT EXECUTED (incomplete-readiness browser
state and stable back/forward route assertion) should be added to a future
browser harness pass if a stronger route-history driver is required. They do
not alter canonical data or security boundaries. Official Amazon SP-API
certification remains a separate external milestone.

### P. Git and golden-database safety

No commit or push was performed. The pre-existing broad worktree changes were
preserved. No golden database modification was performed.

### Q. Final decision

The local, authenticated, fake-provider Amazon integration and its accessibility
scans are implemented and substantially validated. The release classification
is intentionally **IMPLEMENTED / LOCAL CERTIFICATION PENDING** because the
incomplete-readiness browser state and a stable browser back/forward assertion
remain unexecuted. Rerun those two browser checks with the CDP harness to close
the local gate. This report must not be interpreted as authorization for any
live Amazon operation.
