# WP7A-5 browser evidence

| Original ID | A4 | Latest scenario | Acceptance | Remaining / disposition |
|---|---|---|---|---|
| R-184826c3 | PARTIAL | PASS | CLOSED | VERIFIED_LOCAL_SUPPORTED_ACCEPTANCE |
| R-794214d7 | PARTIAL | PASS | CLOSED | VERIFIED_LOCAL_SUPPORTED_ACCEPTANCE |
| R-3feda36d | PARTIAL | PASS | PARTIAL | Video draft with exact thumbnail/metadata is targeted; separate image-only draft and stale review permutations remain incomplete. |
| R-55e822d5 | PARTIAL | PARTIAL | PARTIAL | Configured-only overview checked; connected/revoked/expired account projections not fully exercised. |
| R-551d2f8c | PARTIAL | PARTIAL | PARTIAL | Exact draft/reload checked; full prerequisite correction and missing/expired/revoked/stale HUMAN authorization permutations unexecuted. |
| R-db243c36 | PARTIAL | PARTIAL | PARTIAL | Exact draft/reload checked; supported manual preparation/readiness/review permutations incomplete. No invented Meesho OAuth or dispatch. |
| R-d6a495d5 | PARTIAL | PARTIAL | PARTIAL | Exact draft/reload checked; full readiness and HUMAN authorization permutations incomplete. Authorization/readiness guard requires separate focused reproduction. |
| L-10 | PARTIAL | PASS | CLOSED | VERIFIED_LOCAL_SUPPORTED_ACCEPTANCE |
| L-12 | PARTIAL | PASS | CLOSED | VERIFIED_LOCAL_SUPPORTED_ACCEPTANCE |
| L-13 | PARTIAL | PASS | CLOSED | VERIFIED_LOCAL_SUPPORTED_ACCEPTANCE |
| L-15 | PARTIAL | PASS | CLOSED | VERIFIED_LOCAL_SUPPORTED_ACCEPTANCE |
| L-16 | PARTIAL | PARTIAL | PARTIAL | Exact binding and disabled-destination recovery tested; artifact-version replacement and dependency ordering still require browser evidence. |
| L-17 | PARTIAL | PARTIAL | PARTIAL | Local fake account/wizard checked; content/image creative and missing/expired/disabled authorization permutations remain unexecuted. |
| L-21 | PARTIAL | PASS | CLOSED | VERIFIED_LOCAL_SUPPORTED_ACCEPTANCE |
| L-22 | PARTIAL | PASS | CLOSED | VERIFIED_LOCAL_SUPPORTED_ACCEPTANCE |
| L-23 | PARTIAL | PASS | CLOSED | VERIFIED_LOCAL_SUPPORTED_ACCEPTANCE |

## Retained executions

| Run | Selected IDs | Checks | PASS | FAIL | PARTIAL | BLOCKED | Owned ORM snapshots |
|---|---|---|---|---|---|---|---|
| e8503d7f8b268bee | 16 | 64 | 2 | 18 | 16 | 28 | 4 |
| 11e7601f51503966 | 16 | 64 | 7 | 23 | 28 | 6 | 4 |
| d900aab45e95a807 | 16 | 64 | 26 | 16 | 20 | 2 | 4 |
| 9df2ae6fcb28919a | 7 | 28 | 12 | 12 | 4 | 0 | 4 |
| 311404b15e065329 | 5 | 20 | 12 | 8 | 0 | 0 | 4 |
| af9a5afd358cdc31 | 3 | 12 | 12 | 0 | 0 | 0 | 4 |

Each run is under `tmp/qa-seller-browser/<token>/`: `wp7a5-browser.json`, four context directories, viewport/full-page PNGs, state JSON and trace.zip. Per-entry exact references and chronological failures/retests are retained in the coverage ledger. EXECUTED means attempted, not assertions passed.

Installed Chrome/Edge were used, at 1440×900 and 390×900. Every fixture is disposable and synthetic. Canonical APIs prepare fixtures; real UI interactions and reload assertions are recorded separately. No live provider certification or external execution is inferred.

## Accessibility

Latest scans: 64; violation-rule occurrences: 0; incomplete-rule occurrences: 20. Automated axe and focus/Tab/Shift+Tab checks do not certify complete WCAG compliance; incomplete nodes and full screen-reader/keyboard workflows remain manual review.

## Reproduction

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a5.ps1 -Action Browser
# Optional exact-ID replay: set $env:QA_WP7A5_IDS to comma-separated original IDs.
# Four contexts remain mandatory; -Focused is debugging only, not certification.
```
