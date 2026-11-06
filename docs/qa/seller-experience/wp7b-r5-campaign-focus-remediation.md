# WP7B-R5 — Campaign focus remediation

## Root cause and exact correction

R4 confirmed .reschedule-panel textarea on the canonical /campaigns/:id route: authored3px solid gold outline rgb(224,154,54), offset3px, against opaque white,2.374231440911746:1 in Chrome156.0.8078.76/Edge156.0.4314.58 at1440/390. Text itself passed14.798385782792908:1. R4 evidence: tmp/qa-wp7br4/followup/results.json, unchanged. Global styles.css99–107 supplied the default; the Campaign panel lacked a local override.

Only production edit: apps/web/src/app/campaigns/campaigns.css, inside .reschedule-panel: --vj-focus: var(--vj-color-brand-strong);. No scheduling, preview, confirmation, persistence, API, auth, template, geometry or global/dark-navigation change. Hash after removing exactly this line matches preflight. Global/auth/Campaign TS/service hashes preserved. Existing inline labelled section is not a modal: no invented trap/dismissal requirement or new modal behavior.

SC1.4.11 applies to the authored active focus cue:3:1 against actual adjacent color. No additional AAA focus-area criterion was part of the original worklist. [W3C non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) distinguishes meaningful cues from decorative borders.

## Executed regression, with exact scope

Network-free real Chrome/Edge CSS regression8PASS: reconstructed exact prior stylesheet hash reproduces2.374231440911746:1; current production CSS yields8.559089262681107:1, RGB7,84,98 against verified opaque white in four browser/viewport contexts. Existing3px outline retained. This controlled component-style surface is NOT the authenticated application or persisted journey. Full focus PNGs, raw colors, timestamps and versions: tmp/qa-wp7br5/style-browser/results.json. No database or external request used.

Affected Angular14PASS (overlapping full suite); full Angular447PASS/91files; focused Node23PASS/0FAIL/0skip. Production build PASS422.81kB/estimated109.51kB transfer, scoped TS/ESLint/Prettier PASS. One existing OnInit warning remains. Three new Angular tests cover local scope, actual inline semantics/label associations, invalid-preview/confirmation prerequisites.

Canonical authenticated Campaign browser retest: **24VERIFIED_PASS/0FAIL;28focus records, four browser/viewport contexts**. Real keyboard/error/reload/navigation and full focus geometry verified with zero confirmations where the recorded assertions pass. Exact source, screenshots/traces: tmp/qa-wp7br5/browser/results.json. Initial16PASS/8FAIL is retained: four edge-of-viewport exposure assumptions and four unsupported authored3px expectations for UA auto1px error focus. New run safely centers original targets after keyboard reachability, without changing focus/styles/animations; actual ancestor clipping still fails. Native UA error focus is recorded separately(19.028110547666497:1), not forced to authored3px.24authored samples are8.559089262681107:1. No application fix beyond the one scoped token. Initial images/results retained in original folders/history-*; overlapping runs not summed as48unique checks. A separate C12empty-input boundary failure was discovered; it does not reopen the repaired Campaign focus finding or represent a regression introduced by its one-line scope.

