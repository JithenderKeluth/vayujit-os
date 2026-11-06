# WP7B-R1 — residual risk update

Date: 2026-11-05, Asia/Calcutta. Original WP7B risk register remains unchanged. This addendum neither waives risk nor authorizes WP7C/WP8 or launch.

| Risk | R1 disposition | Remaining requirement |
| --- | --- | --- |
| WP7B-GOAL-KEYBOARD-001 | Application async disclosure race demonstrated and corrected; independent real-browser regressions recorded separately | Keep regression coverage; speech of state/errors still unverified |
| WP7B-ADS-500-001 | Reproduced shared overview/anomaly unique-insert race; owner-scoped row lock/flush fix and 4-way persisted concurrency test | Keep DB uniqueness and owner scope; no inference about historical 502 |
| WP7B-MODAL-001 | Earlier keyboard fix retained; additional long-data responsive-width defect found and fixed | Complete post-fix native zoom/screen-reader review |
| WP7B-AT-001 | Narrator actually audible according to owner; required semantic speech matrix not completed | Actual witnessed words/roles/states/errors/statuses; no DOM substitution |
| WP7B-CONTRAST-001 / VISUAL-001 | Native settings 100/200/400 observed; additional sampled rendered colors recorded | Not blanket PASS: incomplete targets, transition states, non-text/focus, target exceptions and full zoom interaction remain |
| R1-LIGHT-SURFACE-FOCUS-001 | RESOLVED for demonstrated samples: Marketplace 2.33:1 and goal 2.37:1 gold outlines corrected; final goal/Ads Close/Marketplace samples verify 8.56:1 | Unsampled/manual targets remain open; never count prior text-only PASS as focus PASS; dark navigation unchanged |
| SE-WP6-ADS-502-001 | OPEN, cause UNATTRIBUTED | New 500 cause and later 200s do not identify original upstream 502 |
| WP7B-PG-TIMESTAMP-001 | OPEN, read-only structural identity/mount/network observation kept separate | Historical Oct14→Nov3 StartedAt/FinishedAt change remains unattributed; no restart/recreate or timestamp repair |
| WP7B-APP-PAUSE-001 | R1 owner/executable/repository/CWD and exact process-tree proof, pause and restoration PASS; frontend, API health/liveness/readiness HTTP 200 | Historical failed-pause record preserved; fresh health checks, not process launch alone, establish R1 restoration |
| WP7B-TYPING-001 | Focused strict mypy now includes Ads optimization and R1 diagnostic/test files, not only router/service | Repository-wide typing is not certified; assess untested production paths individually |
| WP7B-LINT-BUNDLE-001 | Angular/full web lint and production build executed; prior campaign lifecycle warnings and initial bundle-size warning not suppressed | Performance/lifecycle debt remains, not proof of data corruption and not a blanket harmlessness waiver |
| WP7B-SCHEMA-001 | No production schema or migration changes | Historical 3 nullability mismatches; 105 unmatched index names (26 existing left-prefix paths, 79 without demonstrated equivalence) remain. Not 105 proved slow queries |
| WP7B-FIN-PRECISION-001 | Existing Decimal/paise/8-decimal and largest-remainder regression scope preserved; no invented fees/GST | Unknown operands remain unknown; no display-rounded basis replaces raw financial basis |
| WP7B-FIN-HISTORY-001 | OPEN supported-model limitation | Same-version projections are not immutable accounting, statutory reporting or bank/settlement/tax reconciliation |
| WP7B-PROVIDERS-001 / PROVENANCE-001 | Offline synthetic fixtures only; default-deny preserved | No live Ads/supplier/marketplace certification, no simulated evidence promoted to real |
| WP7B-BACKUP-001 | PARKED | Independent encrypted backup/restore/destination certification remains separate and unresolved |

## Certification provenance

WP7A's 48/48 denominator means 48 prioritized remaining entries, comprising 41 inherited + 7 targeted, not all 156 route leaves or all operations. Earlier 124 route-review caveats are not upgraded.

L-17 retained its original acceptance text and passed an **explicitly approved narrower offline interpretation**. Actual owner reply: “Approve this explicit scope clarification.” Provider token expiry remains UNVERIFIED where the current authoritative contract does not express it. This is not a missing-approval exception and is not unqualified live-expiry certification. Original WP7A-7 provenance hashes and WP7B baseline files remain subject to the read-only final audit.

PostgreSQL observations: same original container ID, image, mounts and networks are checked separately from runtime timestamps. Historical StartedAt `2026-10-14T18:42:33.165982847Z` versus observed `2026-11-03T02:21:59.943341832Z`; historical FinishedAt `2026-10-14T18:41:58.572576561Z` versus `2026-11-03T02:13:23.074630975Z`. No actor/reason or row-level preservation claim is inferred from current healthy metadata. No PostgreSQL restart was performed to reconcile this.

## Decisions still required

Complete the bounded actual-reader/native-zoom/manual-target review, retaining NOT VERIFIED for unavailable evidence. Then review Gate A and B independently. Do not start WP7C automatically. No additional database/process authority was assumed, and no cleanup recovery bypass was used.

Final R1 update: the 32-check independent replay verifies measured goal/Ads Close/Marketplace focus outlines at 8.5590892627:1 with no measured focus failures. The normal API/frontend were restored and all four HTTP health/responsiveness checks passed. Nine owned QA databases are absent, original evidence hashes are preserved, and no forced cleanup was needed. These close the scoped behavior/process blockers, not the remaining manual accessibility, provider, timestamp, financial-history or independent-backup risks. Gate A PASS, Gate B INCOMPLETE, overall WP7B INCOMPLETE.
