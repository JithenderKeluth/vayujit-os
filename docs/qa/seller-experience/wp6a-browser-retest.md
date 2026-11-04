# WP6A — Real Chrome/Edge browser retest

2026-10-30. **9 grouped checks PASS,0 failed** in accepted final replay
`a373ab59c1c0c318`, fresh migration head149. Actual production Angular build,
real UI owner setup/sign-in, persisted synthetic fixtures, installed Chrome and
Edge channels at1440×900 and390×844. Both are Chromium; not Firefox/WebKit,
physical-device, full accessibility or real-provider certification.

## Before/after history

| Run | Result / retained evidence |
| --- | --- |
| `b7004c64985747de`, old head147 | Fresh authenticated reproduction: Video, Social, Ads and optimization all visibly unavailable; readonly schema inventory confirms legacy names/missing fields. `wp6a-before.json`, PNGs and trace retained. |
| `eb682f109ceff301`, head149 | First2 groups passed; harness expected capitalized `Disabled` but canonical UI uses `disabled`. Assertion capitalization corrected, production status unchanged. Post-repair42-table inventory retained. |
| `a373ab59c1c0c318`, head149 | Final **9/9 PASS**,27 axe scans,52 PNGs,4 traces. All same identities persist across reload and independent browser logins. |

Roots: `tmp/qa-seller-browser/<token>/`; final `wp6a-retest.json`, each context's
`browser-evidence.json`, screenshots and `trace.zip`; `session-final.json` records
normal cleanup. Traces contain synthetic session material: retain privately and
review/redact before sharing. No raw container logs were retained.

## Actual assertion groups

| # | Seller action / authoritative observation | Result |
| --- | --- | --- |
| 1 | Empty Video/Social/Ads/optimization routes load without prior SQL failures; actual campaign/generation APIs return empty200, not swallowed errors. | PASS |
| 2 | Canonical local storyboard fixture → Video Open editor → edit on-screen text → keyboard Enter Save → reload/reopen same saved scene. State stays draft; Queue Video disabled for absent prerequisites. | PASS |
| 3 | Actual Add account form: missing name blocked without POST; credential-free local synthetic account saved201, disabled/unverified and reload-stable. Dismiss Enable confirmation: no enable action. | PASS |
| 4 | Unvalidated account is not eligible in campaign wizard; unchecked HUMAN confirmation keeps final Confirm & queue disabled. No campaign created. | PASS |
| 5 | Exact controlled generations503 and Ads overview503 show unavailable state; Retry/Refresh restores actual canonical data. No fake successful provider output. | PASS |
| 6 | Chrome mobile login reopens same storyboard and account after reload; named history table takes keyboard focus and horizontal scroll. | PASS |
| 7 | Edge1440 independently signs in and reviews Video, Social, Ads overview/accounts/campaigns/optimization/marketing/settings; saved scene and reload checked. | PASS |
| 8 | Edge390 repeats those routes, persistence and provider-limitation guidance; document fits viewport. | PASS |
| 9 | Every context has0 unexpected console/page/server/guard/failed-request signals; final campaigns/generations remain empty. Only exact two injected503s and anonymous session401 probes are allowed. | PASS |

Creation of the storyboard fixture uses the existing canonical API because the
screen supports editing, not an invented creation control. Account editing also
has persisted API coverage, not a claim of completed browser account-edit flow.
No actual approve/queue/validate/enable/external-provider call was performed.

Example images inspected: final `wp6a-desktop/006-local-account-disabled-provenance.png`
shows LOCAL SYNTHETIC, disabled account and unknown validation; final
`mobile/001-mobile-persisted-storyboard.png` shows the focus outline on the bounded
scrollable history table. This horizontal table content is retained, not hidden.

## Accessibility: actual engine results and limits

Unmodified axe document scans: **27 scans,0 violations;16 incomplete rule
occurrences /29 node occurrences**. No rule exclusions or threshold changes.

| Incomplete rule | Occurrences / nodes | Exact remaining review |
| --- | ---: | --- |
| aria-prohibited-attr | 6 /6 | `.quick-actions` div aria-label needs semantic-role/manual review. |
| color-contrast | 7 /20 | Partially obscured Caption text and editor textareas, cells and empty headers; not measured PASS. |
| th-has-data-cells | 3 /3 | Conditional empty tables need manual populated-state review. |

Incomplete serious-impact rules are not silently promoted to passes. Engine
violations0 is not complete WCAG compliance or full keyboard certification.
Bounded keyboard save and table focus/scroll ran; full screen-reader, every
dialog/focus-return, zoom/themes/forced-colors and generation-populated UI remain
unexecuted. Prior WP6 manual review debt remains open. No broad UX redesign.

## Windows browser reproduction

```powershell
npm.cmd run build --workspace @vayujit/web -- --configuration production
# Terminal 1: wait for READY; leave running.
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp6a.ps1 -Action Browser
# Terminal 2: substitute the NEW READY token, never a cleaned historical token.
.\apps\api\.venv\Scripts\python.exe -m qa.wp6a_schema_probe <READY_TOKEN>
node qa/wp6a-browser-retest.mjs tmp/qa-seller-browser/<READY_TOKEN>/session.json
# Replay requests shutdown; wait for Terminal 1 CLEANED.
.\apps\api\.venv\Scripts\python.exe -m qa.wp6a_final_audit
```

Original Ads comparison502 was not reproduced, but its cause remains unknown.
No broad clean-health/application certification is inferred from this bounded
replay. Permanent/golden DBs untouched; backup parked; stop before WP7.
