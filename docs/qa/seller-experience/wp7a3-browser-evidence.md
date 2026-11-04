# WP7A-3 — Real browser evidence

## Accepted bounded execution

Final run `95a8b3bab0282fa7`: **36 passed / 0 failed / 0 skipped**, nine asserted subjourneys in each of four authenticated contexts. Chrome `156.0.8078.76` and Edge `156.0.4314.50`, headless installed-browser channels, viewports1440×900 and390×900. This is real browser execution, not endpoint-only substitution or live-provider certification.

Root: `tmp/qa-seller-browser/95a8b3bab0282fa7/`. Each context (`wp7a3-chrome-1440`, `wp7a3-chrome-390`, `wp7a3-msedge-1440`, `wp7a3-msedge-390`) has `trace.zip`, `browser-evidence.json`, nine viewport PNGs, nine full-page PNGs and matching state JSON. Summary and actual ORM projections: `wp7a3-browser.json`; lifecycle: `session-final.json`, `cleanup.json`. The PostgreSQL database was migrated to Alembic head and subsequently removed by the signed lifecycle.

| Asserted subjourney | Seller action / canonical evidence actually verified | Contexts |
| --- | --- | --- |
| L-09 bounded | Empty-product generation disabled; select actual synthetic product; deterministic request201 creates a real artifact; keyboard Enter approves through existing HUMAN endpoint; approved UI/API/ORM state survives reload. | 4/4 |
| L-10 bounded | Queue202; identical payload reuses generation ID; canonical worker receives local injected provider failures to exhaustion; reload exposes failure; HUMAN retry targets all exact failed jobs; normal deterministic worker creates outputs; refresh/reload and persisted state agree. | 4/4 |
| L-11 complete bounded contract | Edit pending draft; PATCH200 returns different pending-review revision; URL follows returned identity; reload shows revised title; old source content unchanged; stale source version409; real PostgreSQL concurrent regression separately verifies one successful edit and one conflict. | 4/4 |
| L-12 bounded | Invalid file type rejected; real64×64 synthetic PNG uploaded201; actual media-detail redirect/reload; anonymous private preview401; deterministic image queue/worker; actual private output preview; explicit HUMAN approval200/reload; regeneration follows actual unapproved child with parent lineage; no runtime TypeError/page error. | 4/4 |
| L-13 bounded | Bulk text plan200; queue202; three channel outputs processed by canonical worker; history/detail refresh/reload and persisted operation agree. | 4/4 |
| L-14 bounded | Bulk image plan with cost reported unavailable; enqueue202; actual output/job/media identities; existing worker completion; saved operation query parameter; explicit status refresh and completed UI state after reload. | 4/4 |
| L-15 bounded | Existing SEO analyze201 for exact product; seller-visible findings and analysis history; canonical persisted analysis ID/product association. No marketplace demand or verified commercial claim inferred from scores. | 4/4 |
| L-16 bounded | Create owned synthetic Asia/Kolkata campaign201; add two checkpoints with explicit unique sequences; readiness200; dependency201 and reload persistence; empty campaign handoff does not fabricate completion. No release/scheduling/dispatch occurs. | 4/4 |
| L-17 bounded negative | Missing advertising account produces canonical preview422 and useful blocker; overview/comparison read200. This is NOT a positive creative/account authorization certification. | 4/4 |

Example screenshots: `wp7a3-chrome-390/004-L12-private-image-output-review-full.png`, `006-L14-bulk-image-persisted-full.png`, `008-L16-campaign-context-and-readiness-full.png`. Equivalent desktop/Edge images and traces are retained. Inspect a trace with:

```powershell
npx.cmd playwright show-trace tmp/qa-seller-browser/95a8b3bab0282fa7/wp7a3-msedge-390/trace.zip
```

Temporary QA session cookies/synthetic login interactions may occur in local traces; these are not production credentials and no artifact is automatically published.

## Accessibility and keyboard limits

All **36 axe scans**: **0 violations**, **18 incomplete rule occurrences**. No rules or thresholds were suppressed. These are not18 confirmed violations and not a WCAG certification. Exact nodes/HTML/failure summaries are retained in each context's `browser-evidence.json` (`axe` array) and the run summary.

Manual-review targets include `.ai-compare` (`aria-prohibited-attr`, serious/incomplete); textareas in artifact edit, Studio and bulk content (`color-contrast`, serious/incomplete); mobile image-review `code`; obscured bulk-table headers/cells and Review links on mobile. Screenshots and selector arrays identify exact nodes. Off-screen/obscured content was not silently removed from axe scope. These incomplete results remain open rather than being called PASS.

The exercised native-button Enter action and accessible-name interactions passed. Complete Tab/Shift+Tab/Space/Escape/focus-restoration and modal/state permutations across all creative routes were NOT executed in this package. Desktop/mobile viewport coverage does not imply touch-device or screen-reader certification.

## Before and intermediate evidence retained

| Token | Actual assertion result | Disposition |
| --- | --- | --- |
| dd8bd9e223bc4039 | 1 passed / 8 failed, Chrome desktop | Initial reproduction; mixture of application and harness failures, not eight proven production defects. |
| 227ddf5740a67cd5 | 6 passed / 3 failed, Chrome desktop | Retest exposed harness response-code/identity/timing issues. |
| 64b9ce5b5e48f61d | 36 assertions passed | Not accepted as complete: initial bulk-image reload assertion only proved API persistence; uncaught image decision TypeError was subsequently found in signals. |
| ac7c0435b6bdadc0 | 32 passed / 4 failed | Stronger campaign test reproduced duplicate sequence500; image decision crash retained in console evidence. |
| ee53c09717e8a0d1 | 32 passed / 4 failed | Application corrections present; dependency selectors were incorrectly exact-matched against wrapping labels that include options. Locator corrected, not application rules weakened. |
| 95a8b3bab0282fa7 | 36 passed / 0 failed | Final accepted bounded assertions, including actual dependency save/reload and runtime-error checks. |

Counts from repeated runs are not summed into unique coverage. No result here closes all of original family L. The new matrix/JSON explicitly retains48 open prioritized entries and124 inherited route-review caveats. Historical Ads502 remains unreproduced/unclassified; final signals do not establish its historical cause.

## Exact Windows commands

From the repository root, using the already approved dedicated QA instance:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a3.ps1 -Action Browser
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a3.ps1 -Action Backend
```

`-Focused` selects Chrome desktop for Browser, and the scoped AI/image tests for Backend. It is not a substitute for full four-context certification. The scripts attest the protected QA profile and never require copying credentials into production `.env`. Missing/invalid attestation must fail closed.
