# WP7A — critical journey coverage closure

**Decision: INCOMPLETE. Full WP7 remains INCOMPLETE; no application or production certification.**

The executed subset is materially stronger; broad unexecuted states are not promoted into PASS. Original WP7/WP6A/WP6B evidence is hash-witnessed in `tmp/qa-wp7a/baseline.json`; the read-only audit checks all 12 original files remain unchanged. Existing parent finding `SE-WP7-COVERAGE-001` remains open for the remaining scope. New B-01–06, G-01–05, H-01–04 and L-01–05 IDs are addendum children, not IDs invented retroactively in WP7.

## Targeted matrix

| Existing ID | Previous | New scope status | Actual coverage | Remaining |
| --- | --- | --- | --- | --- |
| B | NOT_TESTED | PARTIAL / INCOMPLETE | B-01–06; real UI goal/plan/start, local synthetic partial results, classified provider failure, retry/replay, committed response loss, original goal navigation, truthful unavailable-category result. | Source-observation freshness/staleness under materially changed research inputs has not been exercised. B-05 proves goal/navigation identity, not this broader semantic gate. |
| G | NOT_TESTED | PASS — BOUNDED LOCAL SCOPE | G-01–05; actual positive/negative/zero/insufficient adjustments, response loss after commit, replay, stale version, double click, persisted ledger, sibling variant isolation, reload and unauthenticated denial. | No outstanding scenario in this bounded local matrix |
| H | NOT_TESTED | PASS — BOUNDED LOCAL SCOPE | H-01–04; Amazon/Flipkart credential-free accounts; missing/expired/invalid/revoked disabled UNVERIFIED states; UI error recovery; persisted session expiry/relogin; negative internal import requests rejected before dispatch. | No outstanding scenario in this bounded local matrix |
| L | NOT_TESTED | PARTIAL / INCOMPLETE | L-01–05; local queue and replay without worker output, pending-review caption validation/save/reload, draft row-version and stale-write rejection, read failure/retry, Ads wizard preparation and authoritative preview rejection, recovery catalog and 502 monitoring. | Failed-generation worker/job retry and approved immutable storyboard version cloning were not exercised in the browser. Ads saved/observed campaign recovery is not covered by an empty campaign plus taxonomy catalog; no campaign confirmation was admitted. |

## Test evidence

| Backend run | Tests | Pass | Fail | Skipped | Cleanup |
| --- | --- | --- | --- | --- | --- |
| 99d9f1ebc706414b | 51 | 50 | 1 | 0 | PASS |
| 094180dc7f304634 | 56 | 56 | 0 | 0 | PASS |
| 167ca6c77f8c4866 | 12 | 12 | 0 | 0 | PASS |

| Quality check | Status | Executed count |
| --- | --- | --- |
| node-qa | PASS | 78 |
| python-qa | PASS | 70 |
| angular | PASS | 382 |
| typescript-app | PASS | not a test count |
| typescript-spec | PASS | not a test count |
| eslint-web | PASS | not a test count |
| eslint-qa | PASS | not a test count |
| ruff | PASS | not a test count |
| black | PASS | not a test count |
| mypy-migration | PASS | not a test count |
| mypy-research | PASS | not a test count |
| compileall | PASS | not a test count |
| powershell-parser | PASS | not a test count |
| diff-check | PASS | not a test count |

Final four-context browser evidence: 36072ba383581557; 80 passed / 0 failed; 20 independently recorded groups per context, not a whole-application census. Production build was executed successfully (422.71 kB initial). See browser report for traces, screenshots and all attempts.

## Safety and architecture

Reattested dedicated `vayujit-qa-postgres`, PostgreSQL17.10, 127.0.0.1:55432, non-superuser `vayujit_qa_admin`, instance389b97d2-a4cd-4d9b-972e-6bb2bf5785eb, container a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23. Scope only `vayujit_qa<16-hex>_test`. Each creation/drop uses existing instance/role/token/OID/marker/signed lifecycle/active-session guards; read-only final audit independently confirms absence. No arbitrary URL inference, forced drop or new orphan-recovery permission. Original WP7 recovery retained.

Test-only `wp7a_fixture.py` requires exact owned database token plus authenticated owner and x-qa-token. Fault wrappers throw offline provider-unavailable errors through normal orchestration; synthetic account sentinels are never usable credentials or verified accounts. Session expiry changes only the exact test cookie hash record. No worker executes and no Video output is fabricated. Same-origin/egress guard and global external-write deny remain. `ck_users_single_owner` unchanged.

## Remaining work / stop boundary

- B: Source-observation freshness/staleness under materially changed research inputs has not been exercised. B-05 proves goal/navigation identity, not this broader semantic gate.
- L: Failed-generation worker/job retry and approved immutable storyboard version cloning were not exercised in the browser. Ads saved/observed campaign recovery is not covered by an empty campaign plus taxonomy catalog; no campaign confirmation was admitted.

These are NOT_EXECUTED/NOT_FULLY_DEMONSTRATED critical scenarios, not green tests or claims that real provider credentials are needed for every remaining local case. Further bounded offline test work is needed before a WP7A PASS; no new milestone was started. For any later WP7B/C review: complete remaining supported artifact/recovery and changed-input lineage cases, then whole-application manual accessibility and original release-risk dispositions. Historical Ads502 remains unreproduced/cause unclassified, not resolved by repeat200s.

## Historical quality debt

Original repository-wide strict mypy219 diagnostics and main.py Ruff I001 are retained, not silently fixed or counted as new passing checks. This run executes focused strict mypy on migration0150 with follow-imports=skip, not whole-repository typing certification. Web lint retains2 warnings. Such nullability/index/type debt can affect production paths not exercised here; runtime subset PASS does not dismiss it. No UNKNOWN monetary input is changed or coerced. Manual/conditional axe findings remain; no complete WCAG compliance claim. Backup/restore, real provider contracts, live registration and production activation remain separate and uncertified.

## Reproduce

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/qa-postgres.ps1 -Action Status
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a.ps1 -Action Backend
npm.cmd run build --workspace @vayujit/web -- --configuration production
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a.ps1 -Action Browser
# Optional diagnostic Chrome-only run: append -Focused
node qa/wp7a-checks.mjs
.\apps\api\.venv\Scripts\python.exe -m qa.wp7a_final_audit
node qa/wp7a-report.mjs
```

Focused strict mypy also passed for the changed research service with follow-imports=skip. A final local variable annotation/name correction was rerun through the focused persisted module; its cases overlap the full backend matrix and are not added as distinct tests.


Commands require the already approved protected local QA profile; never substitute production/golden credentials. Do not run this in parallel with PC-first backup certification. Stop after WP7A for review.
