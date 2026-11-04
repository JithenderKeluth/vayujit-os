# WP3 — Authenticated browser and regression evidence

Date: 2026-10-29.

**WP3 IMPLEMENTED / BOUNDED LOCAL JOURNEY VALIDATED — guarded cleanup recovery disclosed.**
Application certification remains **INCOMPLETE**. Manual-product full economics editing,
manual supplier association and genuine external operations are not certified.

## Accepted run and safety boundary

Final Chrome run: `0ebe4155420b6950`; actual production Angular bundle and
unmocked owner-authenticated application APIs, except the explicitly labelled
single decision-brief outage injection. Desktop 1440×900; mobile responsive
390×844, not a physical-device test. No real supplier or marketplace traffic.

- [Final 17-check report](../../../tmp/qa-seller-browser/0ebe4155420b6950/wp3-retest.json).
- [Desktop trace](../../../tmp/qa-seller-browser/0ebe4155420b6950/wp3-after-desktop/trace.zip).
- [Mobile trace](../../../tmp/qa-seller-browser/0ebe4155420b6950/mobile/trace.zip).
- [Mobile full-page screenshot](../../../tmp/qa-seller-browser/0ebe4155420b6950/mobile/001-mobile-economics-after-full.png).
- [Independent lifecycle/trace/secret audit](../../../tmp/qa-wp3-final-audit.json).
- [Machine-readable resolution](wp3-resolution.json).

Traces are local, Git-ignored synthetic QA artifacts and can contain synthetic
session material. Review/redact before sharing or uploading.

The dedicated approved PostgreSQL 17.10 instance is `vayujit-qa-postgres`,
loopback `127.0.0.1:55432`, role `vayujit_qa_admin`; instance ID
`389b97d2-a4cd-4d9b-972e-6bb2bf5785eb`. No connection secret is documented.
Only signed, token-marked `vayujit_qa<16-hex>_test` databases were used. The
harness verifies instance, container, endpoint, role, exact name, ownership, OID,
marker/creation token and lifecycle before deletion. Fresh migrations reached
`20261204_0147`; WP3 adds no migration and preserves `ck_users_single_owner`.

## Actual browser journey checks

These are grouped journey checks, not a claimed count of every individual
assertion or every application feature.

| # | Journey / assertion group | Result | Evidence |
| --- | --- | --- | --- |
| 1 | 013 primary Suppliers opens discovery, not sourcing decisions | PASS | [PNG](../../../tmp/qa-seller-browser/0ebe4155420b6950/wp3-after-desktop/001-suppliers-primary-navigation.png) |
| 2 | selected product to LOCAL_FIXTURE supplier with provenance | PASS | [PNG](../../../tmp/qa-seller-browser/0ebe4155420b6950/wp3-after-desktop/002-supplier-provenance.png) |
| 3 | 007 persisted HUMAN shortlist refreshes canonical counts without reload | PASS | [PNG](../../../tmp/qa-seller-browser/0ebe4155420b6950/wp3-after-desktop/003-shortlist-counts.png) |
| 4 | existing evidence assessment is discoverable and does not verify synthetic supplier | PASS | [PNG](../../../tmp/qa-seller-browser/0ebe4155420b6950/wp3-after-desktop/004-due-diligence-entry.png) |
| 5 | canonical financial arithmetic remains precise, assumed and incomplete (not net profit) | PASS | JSON / trace |
| 6 | supplier brief blocked until exact scoped economic inputs exist, with useful next action | PASS | [PNG](../../../tmp/qa-seller-browser/0ebe4155420b6950/wp3-after-desktop/006-saved-supplier-context-unknown-not-product-substitution.png) |
| 7 | 015/016 product-level summary, INR grouping, percentages, exact evidence retained | PASS | [PNG](../../../tmp/qa-seller-browser/0ebe4155420b6950/wp3-after-desktop/007-economic-summary.png) |
| 8 | original warning evidence remains keyboard discoverable, not parsed into financial facts | PASS | [PNG](../../../tmp/qa-seller-browser/0ebe4155420b6950/wp3-after-desktop/008-original-evidence-preserved.png) |
| 9 | 006 Catalog conversion and authoritative INR currency survives reload | PASS | [PNG](../../../tmp/qa-seller-browser/0ebe4155420b6950/wp3-after-desktop/009-catalog-currency-and-context.png) |
| 10 | canonical supplier to local pricing draft and seller-entered quotation, no dispatch | PASS | [PNG](../../../tmp/qa-seller-browser/0ebe4155420b6950/wp3-after-desktop/010-local-quote-scoped-and-unverified.png) |
| 11 | mobile persisted economics, readable summary, no document overflow, keyboard links | PASS | JSON / trace |
| 12 | mobile quotation deep link preserves exact saved draft and unverified quote | PASS | JSON / trace |
| 13 | invalid supplier context fails closed without another supplier or cost substitution | PASS | [PNG](../../../tmp/qa-seller-browser/0ebe4155420b6950/wp3-after-desktop/011-invalid-supplier-context.png) |
| 14 | manual Catalog product stays distinct from a researched opportunity | PASS | [PNG](../../../tmp/qa-seller-browser/0ebe4155420b6950/wp3-after-desktop/012-manual-product-lineage-gap.png) |
| 15 | backend read failure is explicit and recovery restores the same economic scope | PASS | [PNG](../../../tmp/qa-seller-browser/0ebe4155420b6950/wp3-after-desktop/014-economic-read-recovery.png) |
| 16 | explicit HUMAN keep-under-review persists; unknown/synthetic evidence cannot enable Proceed | PASS | [PNG](../../../tmp/qa-seller-browser/0ebe4155420b6950/wp3-after-desktop/015-human-review-decision-persisted.png) |
| 17 | no unexpected Angular console, page, network or provider errors | PASS | JSON / trace |

The desktop quotation path clicked the actual supplier-detail “Prepare local requirements and record quotes” CTA; its product and supplier query context were asserted before writing any record.
The mobile quote check restored the exact draft and quote via a new authenticated
browser context. Supplier economic inputs survived a document reload. The invalid
supplier check blocked saving without substituting another supplier. The outage
check used the actual journey-scoped brief route, then removed interception and
recovered against the real persisted API. HUMAN keep-under-review persisted;
Proceed remained unavailable for synthetic/incomplete evidence. No RFQ was
approved or dispatched.

## Independent arithmetic and presentation

All amounts below are explicitly hypothetical QA inputs, not quotations, official
marketplace fees or GST advice:

- 500 units × INR100.125 + INR2,500 freight = INR52,562.50 known acquisition total;
  exact landed unit cost 105.12500000.
- Hypothetical 10% selling-price cost on INR250 plus INR50/order ÷500 =
  25.10000000 selling cost/unit.
- Exact modeled total/unit 130.22500000; contribution/unit 119.77500000;
  margin ratio 0.47910000, displayed 47.91%.
- Capital INR3,00,000; required INR52,562.50; modeled headroom INR2,47,437.50.
- Taxes/GST, returns, advertising, storage and overhead remain UNKNOWN/excluded.
  This is modeled contribution, not verified net profit or authorization to buy.

Tests compare canonical values against these independently calculated constants.
UI formatting rounds display only and retains exact decimals/provenance. The
FX-label regression is additionally unit/source-contract tested; there is no
claim of live or FX-specific browser/provider certification.

## Accessibility and visual evidence

Four full-document axe scans: zero violations. Desktop expanded readiness and
desktop/mobile quote screens: zero incomplete rules. The mobile economics scan
retains one **color-contrast incomplete** rule covering 37 horizontally obscured
financial-table elements. Every original selector was individually scrolled into
view and rescanned with the established axe contrast rule: **37 actual passes,
zero violations, zero incomplete results**. Each targeted result includes a
passing rule count; nothing was hidden, removed or rule-suppressed to obtain it.

[Exposed-table screenshot](../../../tmp/qa-seller-browser/0ebe4155420b6950/mobile/002-exposed-financial-table-contrast.png)
and JSON preserve selectors, results and the original incomplete scan. This does
not turn the original full-document scan into a zero-incomplete result or certify
all WCAG criteria. Keyboard focus/Enter disclosure and section links were exercised;
full assistive-technology, screen-reader and exhaustive Tab/Shift+Tab review remain
manual work, not an invented PASS.

The same WP3 baseline measured 12,080px desktop /29,885px mobile; final fixture
measured **7,149px /10,840px**. Mobile document width390px at a390px viewport;
tables retain deliberate keyboard-accessible horizontal scrolling. A shorter page
is evidence of the scoped hierarchy change, not proof of universal usability.

## Actual test and quality results

| Check | Actual result |
| --- | --- |
| Persisted WP3/WP1/WP2 PostgreSQL | 23 passed: 7 +8 +8; 0 failed |
| Adjacent P5B/P5C/P6A/P6C/due diligence | 14 passed; 0 failed |
| Complete Angular suite | 319 passed in76 files; 0 failed |
| Node QA self-tests | 55 passed; 0 failed |
| Python QA self-tests | 54 passed; 0 failed |
| Authenticated browser grouped checks | 17 passed; 0 failed |
| Production build / TypeScript | PASS; existing518.25kB vs500kB initial bundle warning |
| Changed-file ESLint, Ruff, Black, compileall, PowerShell parser | PASS; no rule suppression |
| Strict mypy: economics projection | PASS |
| Strict mypy: legacy sourcing service | 29 errors; untouched HEAD shadow run also29, same historical untyped functions/call categories |
| git diff --check | PASS; Git also emits existing LF/CRLF notices |

[Final23-test JUnit](../../../tmp/qa-wp3-backend/017310dc9bfe4e65/backend-results.xml)
and [final14-test adjacent JUnit](../../../tmp/qa-wp3-backend/a2ff14300c664ae6/backend-results.xml)
are retained. Earlier19/22-test executions are intermediate evidence, not added
again to the final37-test count. Existing FastAPI lifespan/deprecation and duplicate
OpenAPI operation-ID warnings remain separate from assertions.

The final browser has no unexpected Angular console errors, uncaught page errors,
failed requests or denied external requests. It retains exactly the expected
injected503 resource error and anonymous mobile login GET `/auth/me`401.
The QA helper checks endpoint/method/screen/count; an authenticated/protected-page
401 or TypeError still fails. No real server5xx result is accepted as ordinary success.

## Interim failures are retained

- `0039f102098b3111`: before-harness incorrectly expected a product-wide model in
  a supplier scope without a context; stopped and corrected, no cost substitution.
- `c664f26be17f72e7`: completed before replay; raw dictionary detector missed
  `source_references`, while saved body/screenshots establish the observation.
- `9d8c5ecc4b2aceb3`: test used a top-level decision counter instead of
  `integrity.decision_count`.
- `397c861ae788b9a8`: overly specific historical heading locator; replaced by the
  actual assess-existing-evidence action.
- `8d0cfff3b3f4abeb`: real quotation request422 revealed an empty Product UUID;
  the test's predicted404 was wrong. Its trace and blocked screenshot remain.
- `a4832f6e5540468d`: fault injection targeted only the product brief, while the
  actual route was the journey brief. Correct exact routes were then tested.
- Earlier16-check runs `4b299ec35a40faa7`, `fb33680f8063a983`,
  `eb7feec0e33e4d3c` retained Angular console errors from the genuinely missing
  empty-projection array. They are superseded, not treated as console-clean PASS.
- `a136e7fc5c888b0d`: the stricter gate caught the legitimate anonymous login401;
  the exception was narrowed to that exact GET/session/screen, with negative
  self-tests for protected pages. No authentication behavior was weakened.

## Cleanup and preservation

All **17** WP3 databases are signed DROPPED and independently absent. Four
interrupted guarded DROP operations needed exact-token `resume_drop` recovery:
`8d0cfff3b3f4abeb`, `4b299ec35a40faa7`, `a136e7fc5c888b0d`,
`cb7276e258ec05e7`. Recovery reverified instance/owner/OID/marker and used a
bounded60,000ms statement timeout. No FORCE, session termination, prefix deletion,
lifecycle reset, unrelated database or Docker deletion was used.

The final runtime completed normal automatic cleanup: **CLEANED, child exit0** in
[session-final.json](../../../tmp/qa-seller-browser/0ebe4155420b6950/session-final.json).
The four earlier interrupted runtimes retain their original failed records; for
example, [cb7276e258ec05e7](../../../tmp/qa-seller-browser/cb7276e258ec05e7/session-final.json)
remains CLEANUP_BLOCKED / child exit1 rather than being rewritten to a normal exit.
The independent audit proves eventual safe cleanup for those earlier runs too.
Their retained diagnostics show OperationalError at guarded DROP; exact initial
PostgreSQL error text is unavailable. Longer bounded recovery succeeded, but its
precise initial cause is not asserted as established.

Ten original containers and original networks/volumes remain preserved. Twenty
retained traces passed CRC. QA credential scan: zero matches in documentation,
evidence and scanned container logs; raw container logs were not persisted.
No golden/permanent database, production env, supplier or marketplace was used.

## Exact local Windows reproduction

Use the already approved dedicated QA instance. Do not infer authorization from
an arbitrary database URL, create another instance over an existing name, or run
these against the business database.

```powershell
npm.cmd run build --workspace @vayujit/web -- --configuration production
.\scripts\qa-postgres.ps1 -Action Status
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-seller-wp3.ps1 -Action Backend
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-seller-wp3.ps1 -Action Adjacent
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-seller-wp3.ps1 -Action Browser
```

The Browser command remains running and prints its fresh `session.json` path.
In a second PowerShell, from the repository root:

```powershell
node .\qa\wp3-browser-retest.mjs "<exact session.json path printed by that run>"
```

The browser script writes its owned stop marker. Wait for the runtime's cleanup
result. A stopped approved QA instance can be started with
`.\scripts\qa-postgres.ps1 -Action Start`; do not provision/reuse unrelated resources.

If and only if an owned run records signed DROPPING after interrupted cleanup,
the existing guarded recovery is:

```powershell
.\apps\api\.venv\Scripts\python.exe -c "from qa.postgres_instance import QaInstance; QaInstance().resume_drop('<exact owned 16-hex token>', timeout_ms=60000)"
.\apps\api\.venv\Scripts\python.exe -m qa.wp3_final_audit
```

Do not use a prefix, guessed token, FORCE deletion or manually edited lifecycle.
Offline/regression checks are `npm.cmd run qa:unit`,
`.\apps\api\.venv\Scripts\python.exe -m pytest qa/unit -q` and
`npm.cmd test --workspace @vayujit/web -- --watch=false`.

Stop after WP3. See [remaining limits](wp3-remediation.md#remaining-limits-and-decisions);
no next work package, backup activation or application certification is started.

