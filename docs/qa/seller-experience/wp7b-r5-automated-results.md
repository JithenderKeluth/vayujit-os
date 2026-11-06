# WP7B-R5 — actual automated results

## Executed

| Command | Result / scope |
| --- | --- |
| npm.cmd run test --workspace @vayujit/web -- --include=src/app/campaigns/*.spec.ts --include=src/app/auth/auth-focus-r4.spec.ts |14PASS/0FAIL/4files; overlaps full suite |
| npm.cmd run test --workspace @vayujit/web |447PASS/0FAIL/91files |
| node --test qa/unit/wp7br5.test.mjs qa/unit/wp7br4.test.mjs qa/unit/wp7br1-contrast.test.mjs qa/unit/wp7br1-startup.test.mjs |23PASS/0FAIL/0skip;9newR5 +14retained focused regressions; earlier19/21PASS retained in receipt |
| node qa/wp7br5-style-browser.mjs |8PASS: four exact-prior-style reproductions and four current-style PASS; Chrome/Edge1440/390,390mobile/touch. **Not application/DB certification** |
| node qa/wp7br5-retained-review.mjs |3169stable IDs preserved;28target snapshots and8transition contexts independently reviewed;0group promotions |
| npm.cmd run build --workspace @vayujit/web |PASS422.81kB initial/estimated109.51kB transfer |
| TypeScript app/spec noEmit, scoped ESLint, Prettier |PASS; existing OnInit warning at reschedule-dialog.component.ts224 preserved |

R5 canonical authenticated browser: **24 recorded assertions; 24PASS/0FAIL**. Ads states: **16 assertions; inspect individual outcomes**. Fresh application axe scans: **13**, with all violation/incomplete rows retained. Historical R4 forty scans/zero violation/28incomplete occurrences inherited, not rerun. No speech or native100/200/400zoom PASS. Full CSS fixture viewport size is not native zoom. Commands: node qa/wp7br5-browser.mjs; node qa/wp7br5-ads-states.mjs (active exact-token R5 only).

Boundary assessment command: node qa/wp7br5-boundaries.mjs. 4rendered records, 4VERIFIED_FAIL. This is not four unique defects: one newly demonstrated pre-existing C12cause. Empty enabled/unfocused Email input has an authored1px #9bb9bd border on white with no placeholder/internal value/icon/shadow and identical white fill/outside. Actual border2.0857912059328765:1 vs3; images and CSS metadata in boundaries/results.json. No submissions or authentication changes. Its4additional axe scans retained separately; automated axe may not adjudicate this authored essential-boundary criterion. No additional production fix.

Current suite snapshots together contain17axe scans,0violation rule occurrences and9incomplete rule occurrences. Counts are latest-scope execution receipts, not whole-WCAG compliance or unique-defect totals. Earlier retest scans remain in history, not erased or relabelled as fresh passing coverage.

Ads original15PASS/1FAIL, second15PASS/1FAIL and current individual outcomes are retained under ads-states/history-* plus unique revision images. Failures are NOT VERIFIED exposure/alignment samples, not measured low-contrast failures. Full screenshot and earlier geometry are temporally inconsistent in affected rows; bounded sampler improvement retains original data and uses settled rectangles/current computed colors/full-image before-after geometry without disabling animation. No retries are relabelled as a single16PASS run. C09 is not promoted unless its sufficient-state predicate actually passes.

Style test evidence includes actual unrounded sRGB/solid ancestor backgrounds and full PNGs; no invented white canvas. Its prior version is reconstructed by removing precisely the authorized line and matching preflight SHA256. It is intentionally a static labelled component surface, not a substitute for real application APIs or persisted fixtures. Component-style ratio8.559089262681107:1 is valid for that controlled state only. Initial CSS fixture omitted viewport meta: narrow mobile screenshot dimensions did not establish CSS layout width. Initial results/images retained in style-browser/history-* and original folders, not used as responsive proof. Corrected fixture includes the normal viewport meta and asserts innerWidth1440/390; all8before/after checks independently pass again with unique revision image paths. Overlapping runs are not16unique tests.

Retained legacy SHA256 a1806a88e138c032772d1c6abd5c24bcecd1bfe7eb4c6c5fa6720fb7aaee0a5a matches. Real rAF data still has intermediate low computed contrast, but screenshots are not temporally aligned; no transient waiver/PASS or persistent defect asserted. Retained target sizes lack complete hit-region/exception adjudication. [W3C target-size guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) permits only justified exceptions, not blanket small-control exemptions.

Quality CLI evidence: tmp/qa-wp7br5/quality.json. Initial preflight generic--record import collision failed closed before any R5 lifecycle; corrected package-specific--record-r5 succeeded without overwriting old evidence. No weakening of authorities or assertions. Final syntax/report/security/diff audit is recorded separately in final-audit.json. One intermediate audit had19PASS/1Docker-comparisonFAIL; retained in audit-history-20261105T181707420Z.json. Fresh exact-field inspection found no differences. Cause of that earlier mismatch is not demonstrated because its actual snapshot was not retained; do not infer a restart or assign an actor. Current audit stores both snapshots and canonicalizes unordered network/mount/container inventories while preserving every metadata value. Two regressions prove order-insensitivity and sensitivity to actual timestamp changes. No Python, backend or migration source changed; no unrelated historical backend suite claimed.

Launch command used after current readiness: powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7br5.ps1 (process-local, no system policy change). No duplicate session or ordinary4200/8000 target permitted. Current launcherPID31620; wrapperNode37708; runtime41356; bounded read-only cleanup watcher28848. node qa/wp7br5-report.mjs is offline only.

