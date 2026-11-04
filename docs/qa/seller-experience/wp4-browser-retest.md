# WP4 — Authenticated browser and persisted regression evidence

Date: 2026-10-30. **BOUNDED LOCAL JOURNEY VALIDATED; application certification INCOMPLETE.**
See [root causes](wp4-remediation.md) and [structured results](wp4-resolution.json).

## Environment and isolation

Reused the explicitly approved WP0A instance, not an inferred connection string:
`vayujit-qa-postgres`, container
`a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23`,
instance `389b97d2-a4cd-4d9b-972e-6bb2bf5785eb`, PostgreSQL 17.10,
`127.0.0.1:55432`, role `vayujit_qa_admin` (not superuser).
Only harness-issued `vayujit_qa<16hex>_test` databases, signed lifecycle, marker,
ownership/OID and exact instance checks authorize creation/deletion. No unrelated,
golden or permanent business database was selected or initialized.

Fresh databases migrated to existing Alembic head `20261204_0147`. No WP4 migration.
Owner setup/sign-in uses actual UI/authentication, not mocked auth. Chrome uses
production Angular assets and persisted API data; viewport 1440×900 and 390×844.
Synthetic fixtures and placeholder imagery are labelled as such, not live evidence.
QA default-deny prevents real provider/marketplace execution. New allowances are
method- and route-specific local preparation, not connector/credential/publication
permissions. PC-first backup and unrelated Docker resources were not operated.

## Before and final run identities

| Purpose | Run | Result / artifacts |
| --- | --- | --- |
| Accepted before evidence | `5ba740c21fc2a356` | `wp4-before.json`, desktop/mobile PNGs and traces under `tmp/qa-seller-browser/<run>/` |
| Final authenticated browser | `1502d2e695aad5d7` | `wp4-retest.json` COMPLETE; 18 PASS / 0 FAIL; `session-final.json` CLEANED, child exit 0; marker/absence/signed-lifecycle cleanup PASS |
| Final WP1–WP4 backend | `9d2b488a433741e5` | JUnit 33 PASS / 0 failure/error/skip; cleanup PASS |
| Catalog + opening-stock adjacent | `0e8069592f854529` | JUnit 42 PASS / 0 failure/error/skip; cleanup PASS |
| Existing economics engine | `ff54176e26dd450e` | JUnit 5 PASS / 0 failure/error/skip; cleanup PASS |

Backend artifacts: `tmp/qa-wp4-backend/<run>/backend-results.xml` and `cleanup.json`.
Final before/after evidence is local, not a public trace upload. Browser snapshots
are 19 screenshots (excluding the private uploaded fixture PNG) and two finalized
traces in the final run. Screenshot indices are evidence labels, not test counts.

## Final browser matrix — all actions actually executed

Paths below are under `tmp/qa-seller-browser/1502d2e695aad5d7/`.
The machine report contains exact product, opportunity, goal, variant, media, stock,
cost-context and draft UUIDs. Manual product `ac9cf765-3ae7-4f91-b3ca-ba09b0d5fb4f`;
converted product `02502eb6-12c2-4bc6-942a-1313bc4d83e2`.

| # | Actual action and deterministic witness | Result | Main evidence |
| --- | --- | --- | --- |
| 1 | Explicit HUMAN selection → Catalog conversion; replay returns same Product and preserves goal/opportunity/selection lineage. | PASS | `wp4-after-desktop/001-converted-catalog-lineage-full.png` |
| 2 | UI manual Product creation/edit/reopen; INR, metadata quantity not stock, no fabricated research identity. | PASS | `002-manual-catalog-unknown-costs.png` |
| 3 | Submit invalid variant JSON; product and h1 remain, inline error and entered input survive. | PASS | `003-inline-mutation-error-context-retained.png` |
| 4 | Add/edit stable variant title, SKU, price/currency; repeated pending click/reload does not duplicate identity. | PASS | `004-variant-sku-and-price-persisted.png` |
| 5 | Empty picker → private local upload → same product with ready option; explicit Add image; owner preview works, anonymous request 401. | PASS | `005-private-media-upload-return.png` |
| 6 | Variant opening route carries exact product/SKU; review requires HUMAN checkbox. Duplicate confirm records one inventory item and one HUMAN movement; reload stable. | PASS | `006-opening-stock-human-review.png`, `007-stock-reload-verified.png` |
| 7 | Catalog → product-filtered inventory includes variant ledger, not just master SKU. | PASS | `008-variant-stock-ledger.png` |
| 8 | Save manual assumed acquisition cost through canonical engine; exact API subtotal 12 × 100.125 = 1201.50; excluded costs UNKNOWN. | PASS | `009-manual-cost-assumed-unknown.png`, action/network ledger |
| 9 | Changed assumptions create distinct saved context; identical retry reuses. Select original history, reload exact `cost_context_id` and amounts. | PASS | same trace + `wp4-retest.json` |
| 10 | Missing/stale cost context shows explicit failure/unknown state, no fallback to another product estimate. | PASS | desktop trace + action ledger |
| 11 | Incomplete Amazon draft blocks local approval. Correct fields → HUMAN local review only. Later edit invalidates review; no remote listing. | PASS | `010-local-draft-edit-invalidates-review.png` |
| 12 | Product Channels exact product, Amazon/Flipkart missing accounts, intended draft price not sales, no duplicate Amazon alias; content destinations separate. | PASS | `011-marketplace-not-connected-no-false-sales-full.png` |
| 13 | Converted product has own variant, selected explicitly synthetic private image and incomplete local Flipkart draft; explicit zero stock remains zero/available-to-promise zero. | PASS | `012-converted-zero-stock-not-inferred.png` |
| 14 | Inject exact Catalog GET 503; initial read error/h1 visible; remove injection and Retry recovers same product. | PASS | action ledger, `catalog-recovered` axe state |
| 15 | Authenticated mobile direct Catalog cost link preserves product, saved cost, image and variant; document does not overflow viewport. | PASS | `mobile/001-mobile-catalog-costs-media-and-variant-full.png` |
| 16 | Keyboard focus/Enter opens stock route/review; confirm remains disabled without HUMAN checkbox; edit/cancel adds no movement. | PASS | `mobile/002-mobile-stock-review-cancelled.png` |
| 17 | Mobile Catalog → Product Channels → Back → Forward → refresh retains product/current local draft and exact return link; no page overflow. | PASS | `mobile/003-mobile-marketplace-history-full.png` |
| 18 | Unexpected console errors, page errors, failed/denied requests and server errors are zero in both final contexts. | PASS | `wp4-retest.json` signals and each `browser-evidence.json` |

Rows with a basename only use `wp4-after-desktop/`. Both contexts finalized
`trace.zip`. The only allowed server-error injection is the exact synthetic Catalog
GET 503; no arbitrary server/console failure is ignored. Direct API reads supplement
UI persistence assertions; they do not replace browser actions.

## Accessibility and visual review

Actual axe-core document scans, no rule suppression or removed difficult nodes:

| State | Violations | Incomplete rules | Incomplete node occurrences |
| --- | ---: | ---: | ---: |
| inline-catalog-error | 0 | 1 | 1 |
| marketplace-preparation-desktop | 0 | 0 | 0 |
| catalog-recovered | 0 | 1 | 3 |
| mobile-catalog | 0 | 1 | 3 |
| mobile-opening-review | 0 | 0 | 0 |
| mobile-marketplace-preparation | 0 | 0 | 0 |

Rule: `color-contrast`, impact serious, reason `elmPartiallyObscured` (background
could not be determined), not an established ratio failure. Targets:
`textarea[name="estimate-reason"]` (three state occurrences),
`textarea[maxlength="20000"]` and `textarea[spellcheck="false"]` (two each).
All seven were individually scrolled into view and rescanned; **all seven remain
incomplete**, none converted into a passing rule. Exact node HTML/targets/reason
are retained in `wp4-retest.json` → `axe_exposed` and the context evidence JSON.
These require manual review; do not report zero incomplete or full WCAG PASS.

The original Catalog mutation-error h1 violation is no longer present in the
tested state. Mobile bounded keyboard Enter/review/cancel and no-overflow checks
passed, not a full keyboard/screen-reader/zoom/forced-colors/physical-device audit.
Visual review of actual desktop/mobile screenshots confirms identity, unknown-cost
copy, missing-account copy, local-only controls and private image rendering. It
also retains low-priority SE-WP4-UX-001: adjacent Product record/Edit product links
need spacing; long Catalog hierarchy remains a recommendation.

## Regression and quality results

| Check | Actual accepted result |
| --- | --- |
| WP4 new persisted API cases | 10 PASS |
| WP3 / WP2 / WP1 persisted API | 7 / 8 / 8 PASS |
| Existing Catalog / opening-stock cases | 6 / 36 PASS |
| Existing economics foundation / calculation | 2 / 3 PASS |
| Backend total above, no repeated reruns counted | **80 PASS, 0 FAIL, 0 SKIP** |
| Angular full suite | **339 PASS in 79 files** |
| Node QA self-tests | **57 PASS, 0 FAIL/SKIP** |
| Python QA self-tests | **54 PASS** |
| App/spec TypeScript; focused changed-TS ESLint | PASS |
| Focused Ruff / Black / compileall, five Python files | PASS |
| PowerShell 5.1 parser, WP4 wrapper | PASS |
| Strict mypy, economic_service.py | PASS |
| Strict mypy, shared economic_router.py | 42 historical missing-return annotations; baseline HEAD shadow with MYPYPATH has 43, no relaxed check |
| Production build | PASS; existing warning: initial 518.31 kB exceeds 500 kB by 18.31 kB |
| git diff --check | PASS; existing LF/CRLF notices are not whitespace failures |
| Read-only final lifecycle, trace and secret audit | PASS; 23 databases absent, 18 valid retained trace archives, original Docker resources preserved, zero approved credential matches |

Migration-backed fixture creation ran in each accepted backend/browser environment.
This is not a complete migration downgrade matrix or repository-wide lint/mypy
certification. Existing backend deprecation warnings and prior WP3 sourcing typing
debt are not hidden or asserted resolved. Production-critical implication: shared
untyped routes reduce static assurance, although focused runtime/serialization
tests passed; full static cleanliness remains outstanding. The bundle warning is
a performance-budget issue, not evidence of failed build or quantified load time.

## Failed attempts and cleanup recovery — retained, not counted as passes

Before/after fixture development exposed incorrect fixture assumptions: a commercial
readiness prerequisite without supplier evidence (409), legacy dynamic Angular input
names, two-decimal Product price versus eight-decimal economic amounts, asynchronous
navigation/option readiness and preservation of the existing Meesho destination.
Assertions were corrected only to actual canonical contracts; missing evidence was
not fabricated. Intermediate real UI defects (empty async media selection and alias/
content mixing) were fixed and the entire final journey rerun.

An added return annotation briefly made FastAPI validate an SQLAlchemy row as
`dict[str, object]`, producing a Pydantic serialization 500 in three API cases and
the browser. Explicit `response_model=None` preserves the preexisting raw projection;
only exact decimal strings are additive. The final 33-case API run and clean browser
retest verify that correction; those intermediate failures are not waived.

Some runs experienced delayed host/tool operations and DROP statement timeouts;
one Docker attestation failed. Original failure/child-exit reports remain intact.
Eleven signed DROPPING records required the existing exact-token `resume_drop`,
with bounded 60/90-second statement timeouts; one ACTIVE leftover was normally
guarded-dropped after attestation passed. No lifecycle record was manually edited,
no FORCE drop or unrelated session termination. Final accepted browser and backend
runs cleaned automatically with exit 0. Read-only `tmp/qa-wp4-final-audit.json`
independently verifies all 23 tokens DROPPED/absent and resource preservation.
Automatic cleanup under host stalls remains a harness reliability limitation.

## Exact Windows reproduction

From the repository root, using the existing approved QA instance (never substitute
another URL/instance):

```powershell
.\scripts\qa-postgres.ps1 -Action Status
npm.cmd run build --workspace @vayujit/web -- --configuration production
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-seller-wp4.ps1 -Action Backend
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-seller-wp4.ps1 -Action Adjacent
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-seller-wp4.ps1 -Action Engine
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-seller-wp4.ps1 -Action Browser
```

The Browser command stays running and prints a **fresh** session path. In a second
PowerShell from the same repository:

```powershell
node .\qa\wp4-browser-retest.mjs "<exact fresh session.json path>"
```

Wait for the runtime's normal cleanup confirmation, then:

```powershell
.\apps\api\.venv\Scripts\python.exe -m qa.wp4_final_audit
npm.cmd run qa:unit
.\apps\api\.venv\Scripts\python.exe -m unittest discover -s qa/unit -p 'test_*.py'
npm.cmd test --workspace @vayujit/web -- --watch=false
git -c safe.directory=C:/Users/jithe/Documents/vayujit-os diff --check
```

If the approved instance is stopped, use only `qa-postgres.ps1 -Action Start`.
Never infer authority from a different connection string. Do not rerun against an
old cleaned session. Interrupted cleanup requires inspecting the exact signed
lifecycle first; it is not permission to drop a guessed name or all prefix matches.

## Stop boundary

010/018/019 resolved locally. 009/012/017/020, suspected Advanced-link contrast,
seven WP4 manual accessibility checks and wider historical gaps stay open. No live
provider/marketplace certification, publication, payments, permanent database,
backup activation or next work package was performed. No application certification.
