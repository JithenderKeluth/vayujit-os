# WP7B-R3A — actual automated execution

Date2026-11-05 Asia/Calcutta; artifact timestamps UTC. Playwright1.64.1, axe-core4.11.0, Node24.19.0. Existing R3 session was valid at start, then expired at10:18:54AM IST. No extension/new database was used. Browser scripts refuse expired control records and exact-token witness mismatch; default-deny local transport/egress retained.

| Execution | Actual result | Interpretation |
| --- | --- | --- |
| Primary Chrome/Edge1440/390 |24PASS /4FAIL /28 | Four changing-name login locator failures, not four application defects |
| Independent corrected login segment |4PASS /0FAIL | Forward/reverse field order; both Space states and focus retained. No complete valid UI login claim |
| Contrast records |285 |268textPASS /17NOT VERIFIED; occurrence counts, not unique tests |
| Focus confirmation |1VERIFIED FAIL |2.374231440911746:1 vs3; screenshot/actual colors retained |
| Stable follow-up |112records /4contexts |105textPASS /7NOT VERIFIED; no thrown target-instability errors |
| axe |16scans,0violation rule occurrences,10incomplete | Not WCAG conformance |
| Retained arithmetic |340comparisons /0mismatch | Independent recalculation and source-file hashes; not fresh rendering |

The primary run selected a button by the old name Show password, then expected that same name after it changed to Hide password. The retest uses the actual button across both states and records aria-pressed/focus. All four retest contexts pass. Initial failures remain in browser-results.json. The retest starts by focusing Email programmatically, then uses actual Tab/Shift+Tab/Space; it is not an entire keyboard-only login flow. The primary trace separately retains initial Tab seeking.

Four primary finance attempts encountered detached async-render targets. Follow-up waited for actual network settling and measured each visible target independently without disabling transitions or removing nodes. It recovered84header and12caption records; six mobile captions remain objectively NOT VERIFIED. Social textarea Chrome390 remains NOT VERIFIED. Flipkart currently rendered seven matching labels, so old labels8–10 were not silently treated as passed or inapplicable.

Primary sampler invocations reused40 screenshot paths for80 records across selector loops. Those images cannot prove each earlier target/state and are not used for full-group closure. Stable follow-up uses unique state names; C-02/C-08 closure uses only that clean evidence. Text/color values are retained with the limitation. Main390 contexts are responsive narrow desktop contexts, not touch/mobile emulation; the independent login retest explicitly uses mobile/touch flags. No native zoom was run or inferred from width/DPR.

Reproduction commands (require an already valid, separately authorized isolated R3 session; **do not run now against the expired origin**):

```powershell
node qa/wp7br3a-browser.mjs
node qa/wp7br3a-login.mjs
node qa/wp7br3a-remaining.mjs
node qa/wp7br3a-report.mjs
```

These scripts do not create/extend a database, change approvals, execute imports or perform provider actions. The report command is offline; the other three require a fresh valid existing-session receipt and exact witness. Login-focus.json was produced by the retained inline procedure: existing-token witness; new owned Chrome context; GET/login; Tab to button[aria-pressed]; existing measureTargets; owned context close. Password-bearing API login requests were outside retained tracing. No private credentials, raw stderr or business customer data are printed.

Offline quality history: the initial report generator completed successfully. A later documentation-metadata edit introduced an unescaped backtick in a template, causing one syntax failure before report generation; the QA-only template was corrected and syntax/generation rerun successfully. No runtime or application behavior changed. Four QA JavaScript syntax checks and 14 focused self-tests pass; the failed command is not relabelled as PASS.

Focus-evidence limitation: the element PNG crops the outer outline. Its active-focus computed style, actual opaque adjacent-background chain and source CSS establish the measured non-text contrast failure; the crop alone is not visual proof of the ring or full focus conformance. No blanket manual visual PASS is inferred.

Screenshot/trace references are per assertion in browser-results.json/login-retest.json/remaining-contrast.json/login-focus.json, under tmp/qa-wp7br3a. R1 results52/32, Angular442, Node138, Python163, backend36 are inherited, not fresh R3A executions. No unrelated full regression suite or application build was rerun; there are no application source changes.
