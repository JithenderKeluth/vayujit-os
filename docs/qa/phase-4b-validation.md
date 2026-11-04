# Phase 4B — initial stock entry implementation and independent validation

Final combined classification: **INITIAL STOCK ENTRY — VALIDATED (BOUNDED LOCAL SCOPE)**.
All eleven evidence gates in [the resolution record](phase-4b-resolution.json) passed.
Whole-application certification remains **INCOMPLETE**, regardless of this bounded
workflow's result. All business fixtures are synthetic and disposable.

## Final acceptance results

| Acceptance criterion | Actual result | Evidence |
| --- | --- | --- |
| Complete seller UI workflow | PASS | 16 desktop/mobile opening-stock scenarios |
| Correct persisted stock and reload | PASS | 36 opening API cases plus browser read-back/history |
| Auditable movement and audit | PASS | HUMAN opening ledger and atomic audit assertions |
| Duplicate/conflicting/concurrent submissions | PASS | Replay, three concurrent creator combinations and catalog FK-lock compatibility |
| Desktop/mobile accessibility and keyboard | PASS, bounded | 26 full axe scans with zero violations; 6 exposed-node checks passed; keyboard activation/focus passed |
| Existing regressions | PASS | Phase 4: 44 browser + 36 API; Phase 3: 18 + 36; Phase 2: 8 + 22; Phase 1: 8 browser; adjacent backend 45; Angular 267; QA self-tests 77 |
| Disposable cleanup | PASS | Final fixtures normal exit 0 and marker/absence proofs; independent check of all 27 task-specific database names, none remain; zero QA processes |

The active 129-record baseline now has **117 resolved and 12 open** records. Only
the initial-stock handoff and filtered-empty wording findings closed here. Eleven
older, already-resolved records were reintroduced by historical report writers;
their complete records and prior resolution decisions are preserved separately in
[historical record reconciliation](phase-4b-historical-records.json), not misreported
as new defects or new Phase 4B closures. Original evidence remains unchanged.
Older report generators retain historical review text and sometimes label all
inherited records as "open"; those are not current recurrence counts. The Phase 4B
resolution ledger and active backlog are authoritative for the current 117/12
status. Original reports are preserved rather than rewritten to hide that debt.

The one remaining stock full-scan incomplete is a short numeric table cell that
axe cannot classify; it is retained for manual review. The six separately exposed
help/caption/header checks passed without incomplete results. Neither this nor the
older manual-accessibility finding is labelled full WCAG compliance.

Remaining work is outside this bounded feature: historical financial reconstruction,
generic operational decision lifecycle, eight UX recommendations, the historical
accounts HTTP 502 suspect, and manual accessibility. No unrelated finding was
silently closed. See [the complete ledger](phase-4b-resolution.md).

## Seller workflow

Open **Inventory → Add opening stock**. Choose an owned physical product and, if
applicable, its variant. Review its existing canonical stock; enter the counted
whole quantity, internal SKU, location, unit and alert threshold. Select **Review
opening stock**, check the explicit local-count confirmation, then **Confirm
opening stock**. Success is displayed only after the item and HUMAN opening
movement have been reread and matched to the review. Return to Inventory to use
**View ledger**, or **Adjust stock** for later receipts/corrections.

Opening stock never overwrites an existing SKU/location. Separate locations or
variants must represent separately counted physical units, not another count of
the same units. Product master quantity is a different existing model and is not
silently synchronized. No marketplace stock publication occurs.

## Contract audit and smallest necessary changes

The API already created an inventory item, HUMAN opening movement and
`inventory.opening_balance_created` audit event atomically. It did not safely
compare replay intent, serialize competing creations, trim before lookup, or
reject nonphysical/archived products. The UI exposed no creation operation.

The bounded backend change retains the same endpoint, schemas, ownership and
ledger, with no migration. It serializes the short creation transaction on the
existing owner row using PostgreSQL **FOR NO KEY UPDATE**; saves immutable normalized intent in existing movement
provenance; rejects changed intent under a reused key; and preserves exact replay
even after a later adjustment. Historic ambiguous keys fail closed. Existing
SKU/location uniqueness, Product/variant ownership and stock invariants remain.

Text is trimmed before validation/lookup. Quantity and threshold are strict
integers in the existing 0–2,000,000,000 range; booleans, strings, fractions,
negative and oversized values are not coerced. Unsupported actor/source fields
are rejected, not trusted as HUMAN attribution. The API's historic default-zero
quantity is retained for compatibility; the UI requires an explicit count.

The existing contract does **not** require supplier, acquisition cost, account,
listing, arbitrary approval reason or source text. Movement reason is canonically
**Opening balance**. No prerequisites or commercial values are fabricated.

The dedicated lazy Angular screen preserves the review/key in owner-scoped tab
storage before any write. A 20-second HTTP timeout does not silently retry or
claim failure means nothing was saved. An uncertain outcome can only replay the
identical reviewed intent after renewed confirmation; a definitive rejection
allows correction, including after reload. A committed request with failed
verification remains pending. Missing tab storage fails before submission.

The Inventory page adds a discoverable handoff, restores filter context, and
distinguishes a genuine initial empty state from filtered no-match and API error.
The only change to the original Phase 4 browser assertion is its expected
filtered-empty heading. Reversing that exact string restores the immutable
original byte hash; no test or axe rule was removed or relaxed.

## Executed tests and evidence

- Persisted PostgreSQL: **81 passed**, zero failed/skipped. Opening stock **36**;
  Phase 3A **17**; Phase 3B **16**; Action Center **4**; original inventory/orders
  **8**. JUnit: `tmp/qa-agent/df731018cff94996/backend-results.xml`; normal marker
  cleanup: `tmp/qa-agent/df731018cff94996/cleanup.json`.
- Full Angular: **267 passed in 71 files**, including 15 focused opening-stock
  component/transport assertions. QA self-tests: **49 Node + 28 Python = 77**.
  Exact commands, exit codes, source hashes and local logs are in
  [quality evidence](phase-4b-quality.json).
- The final desktop/mobile stock, original Phase 4 and Phase 3/2/1 results are
  consumed from their actual run reports, not inferred from unit-test success.
  See [stock browser results](phase-4b-report.md), [full regression](phase-4-report.md),
  [Phase 3](phase-3-report.md), [Phase 2](phase-2-report.md), and
  [Phase 1 retest](phase-1-retest-report.md).
- [Exact stock accessibility results](phase-4b-accessibility.json),
  [route/control captures](phase-4b-route-control-coverage.json), and
  [finding-by-finding decisions](phase-4b-resolution.md) are generated only from
  recorded executions. The stock report links local screenshots, traces when a
  failure occurred, API operations and console/network telemetry.

API scenarios cover explicit zero/positive/boundary counts; missing/null/invalid
UI quantities and invalid API values; whitespace; unsupported actor/source
fields; changed quantity/product/variant/SKU/location/unit/threshold under a key;
identical replay after an adjustment; same SKU/location with a different key;
separate locations; three concurrency combinations; physical/digital/service/
affiliate/archive eligibility; correct/archived/cross-product variants; unknown
IDs and anonymous denial. Tests also check audit persistence, original master
quantity and UNKNOWN acquisition cost rather than inventing costs or suppliers.

Browser scenarios exercise genuine empty/no-products, positive and zero counts,
validation and focus, cancellation, variant/custom SKU/location preservation,
review reload/reapproval, lost committed response and identical-key replay,
competing stock after review, product archival after review, API failure/recovery,
filter preservation, history/deep links/refresh, unknown IDs, logout and protected
routes. The two independent installations do not seed multiple owners into one
database. They do not constitute every possible cross-installation attack test.

## Accessibility and usability

Established axe-core scans use the unchanged full-document rules. Explicit
labels keep names stable when help, validation messages or product options change.
Status/error announcements, first-invalid focus, review/success focus and visible
keyboard focus are tested. Tab, Shift+Tab, Space, Enter and Escape are exercised;
the nonmodal review does not trap focus. Document-width assertions and full-page
screenshots cover 1440px desktop and 390px mobile Chrome emulation. This is not
physical-device, assistive-technology or complete WCAG certification.

Any axe `incomplete` results remain manual-review requirements, not passes. The
prior `QA-P4A-A11Y-MANUAL-001` and its 85 historical incomplete occurrences are not
silently closed by a clean stock workflow. Unrelated UX recommendations, currency
defaults, long economics screens and other missing workflows remain open.

## Intermediate failures and cleanup honesty

The initial API harness referenced `audit_logs` instead of `audit_events` and
attempted archival with a status PATCH instead of the supported archive action.
Those fixture errors were corrected; the assertions were retained and strengthened.
The first browser pass exposed nested labels whose option/help text destabilized
field names. Explicit labels corrected the actual screen. A subsequent run exposed
the rejected-review/pending-storage issue, now covered by reload tests. A test-only
ESLint unsafe matcher assignment was replaced by a typed error outcome, without
suppressing the rule. Earlier failed reports are archived, not represented as PASS.

A further deterministic PostgreSQL test reproduced an owner-lock compatibility
defect in the first implementation: while opening creation held `FOR UPDATE` on
User and waited for a Product row, an audit-style `FOR KEY SHARE` check on User
timed out. Before-fix evidence is retained in
`tmp/qa-agent/b2aae66c87a14d04/backend-results.xml` (one failure, 35 deliberately
deselected cases in this diagnostic-only run). The final implementation uses
`FOR NO KEY UPDATE`, verified from SQLAlchemy's actual PostgreSQL compilation.
This still serializes opening creators but permits the foreign-key check, avoiding
that lock-order cycle. The full final matrix includes the same regression without
selection/deselection. SQL in this test takes read locks and sets a local timeout;
it does not seed or manufacture business records.

Exposed stock-node checks additionally found inline help wrapping beside a count
input and a centered wide-table caption whose text was outside the narrow viewport.
Stock form fields now use aligned grid cells with a separate help line; the
Inventory component left-aligns its own captions. Six targeted, scrolled contrast
checks supplement, never replace, the 26 full-document stock scans. A short numeric
cell that axe cannot classify remains explicitly manual review rather than being
altered to make the rule pass.

An intermediate original Phase 4 execution passed **44 browser + 36 API** checks
but timed out one desktop child at the existing 45-second cleanup boundary. Its
classification remained INCOMPLETE. Read-only process inspection found no remaining
QA child. The existing exact-token recovery tool verified that database already
absent; no sessions were terminated and no unrelated database was dropped. Proof:
`tmp/qa-agent/a917ff3341ae0ac4/recovery-cleanup.json`. The exact cause of the delayed
shutdown/report is not established; resource contention while the 80-case API run
was active is a possibility, not a confirmed diagnosis. A later serial execution
must independently pass normal cleanup; recovery is not substituted for it.

The intermediate stock execution in `c8986ac7881272e0` / `59c378d9fc810464`
also recorded child-exit timeouts although both marker/absence proofs were written.
It remained INCOMPLETE (and its new exposed-node assertions failed before the
layout correction). Those timeouts are retained, not relabelled normal exits.
The final stock run is executed without the concurrent backend batch and must
produce both normal child exits as well as database absence.

The final run did produce normal exit **0** for both contexts and both marker/
absence proofs. Its keyboard test waits for the confirmation button to become
enabled after Space before checking Tab/Shift+Tab order, eliminating an observed
render-timing race without dropping the focus assertions. Visual review also
removed empty red validation bars; real nonempty errors remain visible and tested.
Final desktop/mobile full-page screenshots were inspected. Independent cleanup
proof: [all task targets](phase-4b-cleanup-verification.json). The original Phase 4
read-only rerun preceded the final no-key-update and stock-specific layout polish;
all affected opening/backend scenarios were rerun afterward. No blanket claim of
rerunning every historical test against every intermediate edit is made.

## Quality warnings and limits

Focused Ruff, Black, strict mypy for the router/new regression/fixture, TypeScript,
frontend/QA lint, compileall and diff checks are recorded independently. Whole
schema strict mypy still reports the **pre-existing** unsupported `Field(ne=0, ...)`
argument in `InventoryAdjustmentRequest.delta` (`commerce/schemas.py:261`). It is
not the new opening-stock integer validation, and it is not suppressed or labelled
green. The existing UI prevents zero delta; complete API zero-delta semantics
remain a separate follow-up. Opening creation tests exercise strict integer bounds,
atomicity and replay without that adjustment-field assumption.

The existing bundle warning remains: initial output **517.89 kB**, above 500 kB
(previous Phase 4A 515.08 kB). The bounded shared transport timeout adds roughly
2.81 kB; this is not called a resolved performance issue. Two existing Angular
OnInit interface warnings and existing FastAPI operation-ID/deprecation warnings
remain. No repository-wide typing, migration or real-provider certification is
claimed. No migration was added; inventory/catalog/Product models are unchanged.

## Files and architecture impact

- Backend: `commerce/inventory_router.py`, `commerce/schemas.py`, and new
  `tests/test_qa_phase4b_opening_stock.py`.
- Frontend: `app.routes.ts`, `marketplaces/marketplace.service.ts`,
  `unified-inventory.component.ts`, new `opening-stock.component.ts`,
  `opening-stock.css`, `opening-stock.component.spec.ts`,
  `opening-stock.service.spec.ts`.
- QA: `qa/run.mjs`, `safety.mjs`, `fixture_server.py`, `playwright.config.mjs`,
  `archive-reports.mjs`, the single expected-message change in
  `tests/phase4.spec.mjs`, new `tests/phase4b.spec.mjs`, `unit/phase4b.test.mjs`,
  `phase4b-status.mjs`, `phase4b-quality.mjs`, `certify-phase4b.mjs`,
  `capture-phase4b-baseline.mjs`, and the `qa:phase4b` package command.
- Documentation/evidence: Phase 4B baseline/browser/quality/accessibility/control/
  resolution reports, stock-entry assessment, seller review, coverage matrix,
  active defect backlog, refreshed adjacent execution reports and report history.
  No unrelated dirty worktree files are claimed as this task's changes.

## Exact Windows reproduction

Use the existing dependencies, local PostgreSQL and Chrome from the repository
root. Supply a dedicated local test administrator capable of creating/dropping
only disposable QA state; never use a business database. No `.env` edit is needed.

```powershell
$env:QA_DATABASE_ADMIN_URL = 'postgresql+psycopg://LOCAL_QA_USER:URL_ENCODED_PASSWORD@127.0.0.1:5432/postgres'
npm.cmd run qa:phase4b
npm.cmd run qa:phase4
npm.cmd run qa:phase3 -- --preserve-inventory
npm.cmd run qa:phase2 -- --preserve-inventory
npm.cmd run qa:smoke -- --retest --preserve-inventory
node qa/phase4b-quality.mjs

$env:PYTHONPATH = 'apps/api;.'
$env:QA_ORIGIN = 'http://127.0.0.1:4200'
$env:QA_PHASE = '3'
$qaStockToken = [guid]::NewGuid().ToString('N').Substring(0,16)
& .\apps\api\.venv\Scripts\python.exe qa/fixture_server.py --port 0 --token $qaStockToken --output "tmp/qa-agent/$qaStockToken" --pytest test_qa_phase4b_opening_stock.py test_qa_phase3a_remediation.py test_qa_phase3b_remediation.py test_pr_sos_06_action_center.py test_pr_sos_04_inventory_orders.py
node qa/certify-phase4b.mjs "tmp/qa-agent/$qaStockToken"
git diff --check
Remove-Item Env:QA_DATABASE_ADMIN_URL
```

Do not rerun the one-time baseline capture or the old Phase 4A closure generator
against changed Phase 4B sources. The stock closure gate rejects stale source
hashes, duplicate/missing scenarios, failed/skipped tests, missing axe states or
abnormal cleanup. Only `QA-P3-GAP-003` and `QA-P4-UX-STOCK-EMPTY` are eligible for
closure here; all original evidence and unrelated findings are preserved.

## Safety

Only fresh marker-protected disposable PostgreSQL databases and synthetic records.
Stock-only fixtures use DISABLED provider mode, kill switches and outbound network
guards; adjacent tests use the established local fixture policy. No permanent or
golden database writes, credentials, live providers, marketplace calls/publication,
supplier contact, procurement, payment, new ownership model, branch, commit or push.
No Docker resources or PC-first backup/restore scripts/runtime were touched.
