# WP7A-6 browser evidence

Final frozen-build token: `befaa935c05fac4a`. Installed Chrome 156.0.8078.76; Edge 156.0.4314.58; each 1440×900 and touch/mobile 390×900. 28 entry/context attempts: {"PASS":0,"PARTIAL":28,"FAIL":0,"BLOCKED":0}. **PARTIAL is not PASS.** Actual owner onboarding/login and canonical API fixtures; actual UI image save/edit/preview/reload. Other entries do not have a complete negative/recovery matrix.

[Browser JSON](../../../tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-browser.json) records exact routes, database snapshots, network statuses and axe. [Final session](../../../tmp/qa-seller-browser/befaa935c05fac4a/session-final.json) records this run's cleanup. Earlier attempts and all traces remain retained; initial fixture/selector/payload errors are harness failures, not app defects. Intermediate matrix 12005da551e0e91e is diagnostic, not release evidence (a rebuild overlapped its tail).

Axe: 28 scans, 0 violations, 14 incomplete rule occurrences. Tab/Shift+Tab focus return was checked on the first visible control for each entry, **not** a full keyboard workflow audit. No complete WCAG claim.

### R-3feda36d — PARTIAL

Image-only creation, exact media/content/product, preview/edit stale fingerprint and reload verified; HUMAN review and concurrent-action matrix remain incomplete. No publication.

- wp7a6-chrome-1440: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-1440/001-R-3feda36d-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-1440/trace.zip); persisted invariant: true.
- wp7a6-chrome-390: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-390/001-R-3feda36d-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-390/trace.zip); persisted invariant: true.
- wp7a6-msedge-1440: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-1440/001-R-3feda36d-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-1440/trace.zip); persisted invariant: true.
- wp7a6-msedge-390: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-390/001-R-3feda36d-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-390/trace.zip); persisted invariant: true.

Unverified acceptance assertions: duplicate_concurrent, failure_recovery, approval_no_publish, owner_isolation.

### R-55e822d5 — PARTIAL

Sandbox configuration persisted; real connection is NOT certified. Expired/revoked and exact account projections remain unverified.

- wp7a6-chrome-1440: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-1440/002-R-55e822d5-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-1440/trace.zip); persisted invariant: true.
- wp7a6-chrome-390: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-390/002-R-55e822d5-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-390/trace.zip); persisted invariant: true.
- wp7a6-msedge-1440: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-1440/002-R-55e822d5-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-1440/trace.zip); persisted invariant: true.
- wp7a6-msedge-390: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-390/002-R-55e822d5-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-390/trace.zip); persisted invariant: true.

Unverified acceptance assertions: missing_credentials, fake_validated_label, invalid_expired_revoked, account_mismatch, reload_recovery, default_deny.

### R-551d2f8c — PARTIAL

flipkart: persisted draft and missing-readiness/default-deny checked; readiness correction and complete authorization matrix not yet verified.

- wp7a6-chrome-1440: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-1440/003-R-551d2f8c-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-1440/trace.zip); persisted invariant: true.
- wp7a6-chrome-390: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-390/003-R-551d2f8c-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-390/trace.zip); persisted invariant: true.
- wp7a6-msedge-1440: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-1440/003-R-551d2f8c-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-1440/trace.zip); persisted invariant: true.
- wp7a6-msedge-390: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-390/003-R-551d2f8c-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-390/trace.zip); persisted invariant: true.

Unverified acceptance assertions: legitimate_resolution, human_review, authorization_states, exact_fingerprint, stale_mismatch, repeat_concurrent, reload_failure_recovery, no_submission, owner_isolation.

### R-db243c36 — PARTIAL

meesho: persisted draft and missing-readiness/default-deny checked; readiness correction and complete authorization matrix not yet verified.

- wp7a6-chrome-1440: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-1440/004-R-db243c36-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-1440/trace.zip); persisted invariant: true.
- wp7a6-chrome-390: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-390/004-R-db243c36-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-390/trace.zip); persisted invariant: true.
- wp7a6-msedge-1440: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-1440/004-R-db243c36-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-1440/trace.zip); persisted invariant: true.
- wp7a6-msedge-390: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-390/004-R-db243c36-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-390/trace.zip); persisted invariant: true.

Unverified acceptance assertions: manual_resolution, review_boundaries, unsupported_live_truthful, stale_duplicate, reload_failure_recovery, no_dispatch, owner_isolation.

### R-d6a495d5 — PARTIAL

amazon: persisted draft and missing-readiness/default-deny checked; readiness correction and complete authorization matrix not yet verified.

- wp7a6-chrome-1440: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-1440/005-R-d6a495d5-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-1440/trace.zip); persisted invariant: true.
- wp7a6-chrome-390: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-390/005-R-d6a495d5-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-390/trace.zip); persisted invariant: true.
- wp7a6-msedge-1440: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-1440/005-R-d6a495d5-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-1440/trace.zip); persisted invariant: true.
- wp7a6-msedge-390: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-390/005-R-d6a495d5-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-390/trace.zip); persisted invariant: true.

Unverified acceptance assertions: legitimate_resolution, authorization_states, exact_fingerprint, stale_mismatch, repeat_concurrent, reload_failure_recovery, no_submission, owner_isolation.

### L-16 — PARTIAL

Exact draft/activity persisted and reloaded; dependency/artifact-version stale fingerprint matrix remains unverified.

- wp7a6-chrome-1440: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-1440/006-L-16-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-1440/trace.zip); persisted invariant: true.
- wp7a6-chrome-390: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-390/006-L-16-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-390/trace.zip); persisted invariant: true.
- wp7a6-msedge-1440: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-1440/006-L-16-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-1440/trace.zip); persisted invariant: true.
- wp7a6-msedge-390: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-390/006-L-16-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-390/trace.zip); persisted invariant: true.

Unverified acceptance assertions: artifact_versions, dependency_graph, changed_preview_stale, fingerprint_confirmation, concurrent_replay, interrupted_recovery, no_release.

### L-17 — PARTIAL

Local fake account/wizard exercised without submission; complete creative/authorization matrix remains unverified. Historical 502 not classified as resolved.

- wp7a6-chrome-1440: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-1440/007-L-17-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-1440/trace.zip); persisted invariant: false.
- wp7a6-chrome-390: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-390/007-L-17-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-chrome-390/trace.zip); persisted invariant: false.
- wp7a6-msedge-1440: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-1440/007-L-17-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-1440/trace.zip); persisted invariant: false.
- wp7a6-msedge-390: PARTIAL; [screenshot](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-390/007-L-17-PARTIAL.png); [trace](C:/Users/jithe/Documents/vayujit-os/tmp/qa-seller-browser/befaa935c05fac4a/wp7a6-msedge-390/trace.zip); persisted invariant: false.

Unverified acceptance assertions: creative_content_image, exact_versions, missing_invalid_prerequisites, authorization_states, preview_fingerprint, human_confirm, stale_concurrent, failure_recovery_latest, reload_owned, no_spend.

## Commands

`powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a6.ps1 -Action Browser`

Only run against the attested dedicated QA instance. Exact approved cleanup is now independently verified; inspect signed lifecycle state before any future QA run. Never target 5432 or a permanent/golden database.
