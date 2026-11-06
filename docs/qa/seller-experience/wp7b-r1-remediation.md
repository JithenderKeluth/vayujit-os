# WP7B-R1 — remediation and independent retesting

Date: 2026-11-05, Asia/Calcutta. Evidence timestamps are UTC and can show November 4.

This is the authorized R1 continuation, not a new milestone, launch approval, or restart of WP7B. Original WP7B reports and browser failures are preserved; see the eight-file hash audit in `tmp/qa-wp7br1/preserved-wp7b.json`. Gate A and Gate B are independent. WP7B remains **INCOMPLETE** while required manual accessibility evidence is missing.

## Demonstrated root causes

| Original failure | Root cause and evidence | Smallest correction |
| --- | --- | --- |
| B-GOALS Chrome 1440 | Native disclosure was bound to `!goals().length`. The initial empty signal opened it; the saved-goals response closed it, losing visibility and focus after seller interaction. This was an application race, not just a slow test. | Separate disclosure signal; decide the initial default after loading; remember seller interaction; synchronize native toggle and `aria-expanded`. |
| B-GOALS Chrome 390 | Same asynchronous binding boundary; not a separate mobile-only defect. | Same generic correction. |
| B-GOALS Edge 1440 | Same boundary. An occasional natural pass is not evidence that the race was absent. | Same generic correction; Enter/Space, validation, reload and delayed-response regressions. |
| B-DIALOG Chrome 1440 / Ads initial 500 | Parallel overview/anomaly GETs both selected an absent fingerprint and inserted it. PostgreSQL rejected the loser with `IntegrityError`, SQLSTATE `23505`, `uq_ad_performance_anomaly_fingerprint`. | Serialize detection on existing owner-scoped campaign row locks in stable ID order through commit; retain uniqueness; flush new rows before returning persisted IDs/defaults. |

Pre-fix proof:

- Angular delayed-goals regression: 14 passed, 1 failed; expected open=true, actual=false. `tmp/qa-wp7br1/pre-fix-unit-evidence.json` is a record of observed CLI output, not an invented JUnit file.
- Browser `cd102dd32f92bcc3`: login PASS, controlled delayed-goals regression FAIL. The actual API response was held, not fabricated; pending draft was open/focused, then closed/unfocused after release.
- Browser `67c081611ec1c006`: login/goal PASS, dialog FAIL. Fresh reproduction's losing endpoint was GET `/api/v1/ads/optimization/overview`, correlation `a288fb1f-99a2-4970-bb66-13a9c9a7ea0f`; anomalies returned 200. Both call the same detection operation. This is not a claim that a traceback from the original historical request survived. Reload returned 200 on both endpoints. Safe source locations at reproduction: `ads/optimization_router.py:71`, `ads/optimization.py:1581` and `:1131`.
- Exception metadata is retained in `tmp/qa-seller-browser/67c081611ec1c006/wp7br1-server-diagnostics.jsonl`; raw exceptions, SQL, parameters and credentials are not retained.

## Additional in-scope corrections

`metric_snapshot` previously manufactured zero numerators from missing observations, including zero budget utilization without known spend. Detection could therefore invent a delivery anomaly for a budget-only draft. Missing observations now remain missing; derived rates require their actual operands; explicit zero stays distinguishable. No fee/GST/economics formula was invented. Four persisted regressions cover unknown, known-zero, concurrent identity, reload and authorization/scope.

Actual native Chrome 400% review exposed an oversized Ads preview: intrinsic long JSON lines could widen the grid item and obscure the title. The dialog now has `min-width:0`, border-box sizing, `width:min(100%,700px)` and wrapping of long preview data. A separate responsive 320px assertion checks its real browser geometry and keyboard recovery. This is not a substitute for a completed post-fix native-zoom manual review.

Supplemental non-text measurements then exposed Marketplace's explicit gold focus outline: rgb(228,155,40) on white, 2.3286826338:1 against 3:1. The shared light-surface Marketplace rule now uses the existing `--vj-color-brand-strong` token, preserving the theme and the dark-navigation focus rule. No approval/workflow behavior changes. Browser checks now assert focus-measurement failures as well as text failures; an additional QA self-test protects this token/contrast boundary.

The goal textarea also inherited the global gold outline: rgb(224,154,54) on white, 2.3742314409:1. A scoped rule now applies the same strong brand token to the goal form/disclosure and light Ads workspace, including the preview Close control. The dark shell/navigation is unchanged. Goal and explicit focused-Close contrast assertions prevent text-only PASS from hiding focus failures.

## Changes and architecture impact

Production changes:

- `apps/web/src/app/intelligence/business-agent-workspace.component.ts` — disclosure state only; no change to goal, plan, selection, approval or persistence authority.
- `apps/web/src/app/intelligence/business-agent-workspace.css` — goal form/disclosure light-surface focus color only.
- `apps/api/vayujit_api/ads/optimization.py` — only metric snapshot and anomaly-detection behavior changed. Existing migration uniqueness and owner scope remain. Unrelated formatting was removed; formatter validation is scoped to changed functions.
- `apps/web/src/app/ads/ads-optimization.component.ts` — R1 dialog width/wrapping and scoped light-surface focus color. The earlier WP7B title focus, Tab containment, Space/Escape and return-focus fix is retained, not claimed as newly invented here.
- `apps/web/src/app/marketplaces/marketplaces.css` — only the light-surface focus-outline color, using the existing strong brand token.

Regression/infrastructure changes:

- Goal component spec: two regressions; `apps/api/tests/test_seller_wp7br1.py`: four persisted regressions.
- `qa/wp7b-browser.mjs`: original checks retained; delayed response/disclosure, responsive dialog and explicit contrast sampling added.
- `qa/wp7br1-contrast.mjs`, `qa/unit/wp7br1-contrast.test.mjs`: supplemental sRGB/alpha calculations, no assumed canvas background or blanket overlay/disabled exemption.
- `qa/wp7br1_diagnostics.py`, its Python self-tests, and guarded install in `qa/fixture_server.py`: allowlisted exception metadata only; R1 explicitly rejects a missing signed QA authority.
- `qa/wp7br1-native.mjs`, `qa/wp7br1-review-fixtures.mjs`: bounded isolated native review and canonical synthetic review fixtures; no publication/dispatch.
- `qa/wp7br1-startup.mjs`, its self-tests, `qa/seller-browser-session.mjs`: R1-only bounded cold-start budget. One attempt exceeded the prior readiness window; no identity/witness/cleanup guard was relaxed.
- `qa/wp7-run.mjs`, `qa/server.mjs`, `qa/seller-browser-explore.mjs`: R1 routing/evidence names and existing preview-only policy reused.
- `scripts/test-seller-wp7br1.ps1`, `scripts/wp7br1-app-window.ps1`, `qa/wp7br1-process-cwd.mjs`, package enum in `scripts/qa-wp7a6-app-window.ps1`: exact-owner/executable/repository/CWD preflight, scoped pause and restoration.
- `qa/wp7br1-preservation.mjs`, `scripts/wp7br1-final-audit.py`, `qa/wp7b-quality.mjs`, `qa/wp7br1-quality-supplement.mjs`: preservation/read-only absence audits and exact quality evidence.

No migration, ownership redesign, provider permission, business approval system or backup implementation changed. Existing unrelated dirty worktree changes were retained.

## Final decision

Gate A — application behavior: **PASS** for the demonstrated scoped defects. Original 52 focused assertions pass in `428ad971b5ba262d`; final 32 strengthened affected checks pass in `57e1c0c8d2d30df9`, including measured goal/Ads/Marketplace focus contrast at 8.5590892627:1. Backend 36, Angular 442, Node QA 138 and Python QA 163 pass. The final full quality receipt has all 15 checks PASS.

Gate B — manual accessibility: **INCOMPLETE**. Actual Narrator audibility is confirmed, but semantic spoken behavior, complete post-fix native zoom interaction, some exact contrast targets, Campaign reschedule fixture and other manual checks remain unverified. No DOM/axe substitution or full WCAG claim.

All nine owned QA databases are independently absent; 23 traces pass integrity checks; original WP7B/WP7A-7 evidence is preserved and protected-secret scan finds zero matches. Normal API/frontend health, liveness and readiness are verified after restoration. **WP7B remains INCOMPLETE.** Stop for user review; do not advance WP7C/WP8 or resume backup certification.

See [browser results](wp7b-r1-browser-retest.md), [manual evidence](wp7b-r1-manual-accessibility.md), [risk update](wp7b-r1-risk-update.md), and [machine-readable gate](wp7b-r1-gate.json).
