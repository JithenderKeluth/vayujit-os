# WP7A-2 — Real browser evidence

Final evidence: tmp/qa-seller-browser/2903a4e2ff3d08df/wp7a2-browser.json. Versions: {"chrome":"156.0.8078.76","msedge":"156.0.4314.50"}. Each context has browser-evidence.json (route/status/console/failed-request metadata), screenshots and trace.zip. Actual Chrome/Edge binaries, not a substituted browser engine.

| Scenario | Existing matrix / addendum ID | Contexts passed | Result |
| --- | --- | --- | --- |
| A — Changed-input research freshness | B / B-07 | 4/4 | PASS |
| B — Failed creative-job retry | L / L-06 | 4/4 | PASS |
| C — Approved storyboard cloning | L / L-07 | 4/4 | PASS |
| D — Persisted Ads recovery | L / L-08 | 4/4 | PASS |

| Context | Checks | Trace and screenshots |
| --- | --- | --- |
| wp7a2-chrome-1440 | 4/4 PASS | tmp/qa-seller-browser/2903a4e2ff3d08df/wp7a2-chrome-1440/trace.zip; PNGs and browser-evidence.json in the same directory |
| wp7a2-chrome-390 | 4/4 PASS | tmp/qa-seller-browser/2903a4e2ff3d08df/wp7a2-chrome-390/trace.zip; PNGs and browser-evidence.json in the same directory |
| wp7a2-msedge-1440 | 4/4 PASS | tmp/qa-seller-browser/2903a4e2ff3d08df/wp7a2-msedge-1440/trace.zip; PNGs and browser-evidence.json in the same directory |
| wp7a2-msedge-390 | 4/4 PASS | tmp/qa-seller-browser/2903a4e2ff3d08df/wp7a2-msedge-390/trace.zip; PNGs and browser-evidence.json in the same directory |

A creates a revised goal through UI, delays the old response across navigation, replays research requests, reloads and checks historical reference-only selection boundaries. B queues, observes failure, focuses and presses Enter for retry, repeats concurrent requests, reloads queued/failed states and proves no output. C approves with keyboard Enter, edits/clones, repeats clone requests concurrently, uses Tab/Shift+Tab and Space-save for draft edits, reloads both versions and checks immutable source authority. D navigates accounts → wizard → server preview → explicit confirmation → campaigns → recovery; reloads and authenticates a fresh application process against the same persisted state, repeats recovery and observes a second failure. Synthetic provenance and UNKNOWN remain explicit. Keyboard assertions are bounded checks, not an application-wide manual accessibility claim.

Axe scans=24; violations=0; incomplete rules=14. Full rule IDs, targets, HTML and failure summaries are preserved in each browser-evidence.json and the main report scans. Incomplete checks are not suppressed or reported as WCAG success.

## Failure history (not added to final unique counts)

| Token | Recorded status | PASS | FAIL |
| --- | --- | --- | --- |
| 081819f0cfccd47e | INCOMPLETE | 3 | 1 |
| 2903a4e2ff3d08df | PASS | 16 | 0 |
| 2afea66f51527a0a | INCOMPLETE | 15 | 1 |
| 67abc9a3296a0694 | INCOMPLETE | 1 | 3 |
| 6b6c73e48c2d76eb | INCOMPLETE | 12 | 4 |
| 6cac925c2188b486 | INCOMPLETE | 3 | 1 |
| 82449c619a644e3b | INCOMPLETE | 0 | 4 |
| d127abe23d5d2f3a | PASS | 4 | 0 |
| e9e1a76dd2edc3bb | INCOMPLETE | 3 | 1 |
| eb0da709784a6fe9 | RUNNING | 0 | 0 |

Early runs include harness selector assumptions, serving a pre-rebuild Angular distribution, unbounded old-response wait (owned browser stopped; guarded cleanup retained), nested reconstruction timeout, and parsing app telemetry as one JSON document. Diagnostic details are sanitized; outcomes remain. A mid-development full run cannot certify final harness source. The accepted final run is the explicit token above. Header-bearing error logs were mechanically redacted; raw copies were not retained. Trace assets contain only disposable synthetic sessions, never permanent marketplace credentials.

Historical Ads502: UNREPRODUCED / CAUSE UNCLASSIFIED, not resolved. No502 cause is invented. Parent execution manifests under tmp/qa-wp7a2 record runtime exits and cleanup, including interrupted attempts.

## Incomplete accessibility checks — still open

All14 incomplete rule instances are color-contrast checks. Desktop Video states include textareas; mobile states additionally include research callout and horizontally constrained Video table cells/statuses. Exact HTML/targets are in the scan JSON. These nodes are not removed from scope, and incomplete is not PASS. Manual scrolling/focus/contrast review remains required.

| Context | State | Rule | Affected node count |
| --- | --- | --- | --- |
| wp7a2-chrome-1440 | B-failed-local-job | color-contrast | 1 |
| wp7a2-chrome-1440 | B-second-failure-persisted | color-contrast | 1 |
| wp7a2-chrome-1440 | C-immutable-original-draft-clone | color-contrast | 3 |
| wp7a2-chrome-390 | A-stale-context-reference-only | color-contrast | 1 |
| wp7a2-chrome-390 | B-failed-local-job | color-contrast | 5 |
| wp7a2-chrome-390 | B-second-failure-persisted | color-contrast | 11 |
| wp7a2-chrome-390 | C-immutable-original-draft-clone | color-contrast | 13 |
| wp7a2-msedge-1440 | B-failed-local-job | color-contrast | 1 |
| wp7a2-msedge-1440 | B-second-failure-persisted | color-contrast | 1 |
| wp7a2-msedge-1440 | C-immutable-original-draft-clone | color-contrast | 3 |
| wp7a2-msedge-390 | A-stale-context-reference-only | color-contrast | 1 |
| wp7a2-msedge-390 | B-failed-local-job | color-contrast | 9 |
| wp7a2-msedge-390 | B-second-failure-persisted | color-contrast | 21 |
| wp7a2-msedge-390 | C-immutable-original-draft-clone | color-contrast | 23 |
