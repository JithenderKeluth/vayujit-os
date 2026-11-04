# WP7 — Actual authenticated browser evidence

Installed browser versions: {"chrome":"155.0.8059.40","edge":"156.0.4314.50"}. Actual production Angular, full migrations to20261206_0149, signed disposable databases and normal UI authentication. Full inventory review Chrome1440×900/Edge390×844; critical pages additionally Chrome390, Edge1440 and Chrome768 tablet. These are desktop installations and responsive viewports, not physical devices or Firefox/WebKit.

| Suite | Token | Browser assertion groups PASS / FAIL | Browser exit | Original runtime cleanup | Evidence |
| --- | --- | --- | --- | --- | --- |
| wp1 | d1dba7f1ef3fa603 | 13 / 0 | 0 | CLEANED | tmp/qa-seller-browser/d1dba7f1ef3fa603/wp1-final-browser.json |
| wp2 | 03496e6c4077a837 | 23 / 0 | 0 | CLEANED | tmp/qa-seller-browser/03496e6c4077a837/wp2-browser.json |
| surface | 4963364d9460948d | 5 / 1 | 1 | CLEANUP_BLOCKED | tmp/qa-seller-browser/4963364d9460948d/wp7-surface.json |
| wp3 | 3dde2db902ceff79 | 13 / 1 | 1 | CLEANUP_BLOCKED | tmp/qa-seller-browser/3dde2db902ceff79/wp3-retest.json |
| wp3 | 9cce2e3c4fc034f5 | 17 / 0 | 0 | CLEANUP_BLOCKED | tmp/qa-seller-browser/9cce2e3c4fc034f5/wp3-retest.json |
| wp3 | 623633c485ad56de | 17 / 0 | 0 | CLEANED | tmp/qa-seller-browser/623633c485ad56de/wp3-retest.json |
| wp4 | 223c79f17f3ffc99 | 19 / 0 | 0 | CLEANED | tmp/qa-seller-browser/223c79f17f3ffc99/wp4-retest.json |
| wp5 | c8e9f313baf2cbde | 21 / 0 | 0 | CLEANED | tmp/qa-seller-browser/c8e9f313baf2cbde/wp5-retest.json |
| wp6 | 21aca7c922ea66ca | 8 / 0 | 0 | CLEANED | tmp/qa-seller-browser/21aca7c922ea66ca/wp6-retest.json |
| wp6a | 9dd80511a03c2a47 | 9 / 0 | 0 | CLEANED | tmp/qa-seller-browser/9dd80511a03c2a47/wp6a-retest.json |
| wp6b | e842f9624ff5502b | 8 / 0 | 0 | CLEANED | tmp/qa-seller-browser/e842f9624ff5502b/wp6b-retest.json |
| layout | 990ae2dfcdeb2888 | 36 / 0 | 0 | CLEANED | tmp/qa-seller-browser/990ae2dfcdeb2888/wp7-layout-after.json |

## Captures and original failures

729 state captures; 47 retained context evidence files. These are not unique test cases. Full route/path/network/status/screenshot references live in each browser-evidence.json. Traces contain synthetic session data and must remain private pending review before sharing.

The broad review recorded six real mobile overflows and one investigator strict-locator failure (Application vs Advanced summary). The historical failed WP3 exact-copy expectation, interrupted/timeout cleanup records and before evidence remain retained. Corrections are tested independently; original failures are not rewritten as passes. Two focused before helpers initially reused context labels: their PNG names and dimension JSON survive, the later context trace is not counted as a separate preserved earlier trace; broad surface traces retain the original affected pages.

Focused layout retest: 36 checks, 36 PASS; six routes at390/768/1440 in Chrome and Edge, long persisted synthetic product labels, named table-region focus/ArrowRight. No Generate, Publish, worker retry or optimization execution was clicked.

## Exact Windows commands

```powershell
.\scripts\qa-postgres.ps1 -Action Status
npm.cmd run build --workspace @vayujit/web -- --configuration production
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7.ps1 -Action Inventory
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7.ps1 -Action Backend
# Run browser batches serially after backend cleanup (PowerShell array invocation):
.\scripts\test-seller-wp7.ps1 -Action Browser -Suites wp1,wp2,wp3,wp4,wp5,wp6,wp6a,wp6b,layout,surface
node qa/wp7-static.mjs
npm.cmd run qa:unit
.\apps\api\.venv\Scripts\python.exe -m unittest discover -s qa/unit -p 'test_*.py'
npm.cmd test --workspace @vayujit/web -- --watch=false
.\apps\api\.venv\Scripts\python.exe -m qa.wp7_final_audit
node qa/wp7-report.mjs
git -c safe.directory=C:/Users/jithe/Documents/vayujit-os diff --check
```
No arbitrary admin URL, golden database, new instance, generic Docker prune or forced session termination is permitted. Every run must attest the existing approved instance and verify exact signed cleanup.
