# WP7B-R3A — automation-first assessment

Assessed 2026-11-05T04:58:17.928Z. **GateA inherited PASS; GateB INCOMPLETE with one confirmed blocking contrast failure; overall WP7B INCOMPLETE.** No WCAG conformance or launch approval.

| Original review-group disposition | Count |
| --- | --- |
| Fully verified automatically (C-02 timeline text, C-08 financial headers) |2 |
| Confirmed failure (C-11 login focus) |1 |
| Partially verified, still NOT_VERIFIED |17 |
| No fresh execution, still NOT_VERIFIED |20 |
| Total |40 |

Thus machine outcomes:2VERIFIED_PASS,1VERIFIED_FAIL,37NOT_VERIFIED,0NOT_APPLICABLE. Thirteen speech groups are not automatically closed: existing reported login speech is retained without demanding repetition, while12 groups still have missing mandatory spoken components. Native12-group zoom and ambiguous visual requirements remain incomplete; do not turn every pending automatable assertion into human work.

Actual tests: primary28 (24PASS,4harness locatorFAIL); independent login-segment4PASS/0FAIL. After honest classification,28 passing scoped interaction/semantics records and4 retained harness failures, not a fabricated32PASS or whole-login PASS. Contrast285records:268textPASS/17NOT VERIFIED and one active-focusFAIL separately. Sixteen axe scans:0violation/10incomplete rule occurrences. Stable contrast follow-up112records/4contexts;84headers and4timeline targets close their exact text groups. Independent retained340contrast comparisons match with0mismatches. See [actual results](wp7b-r3a-automated-results.md) for screenshot-collision/render-stability limitations and exact commands.

Focused offline QA self-tests:14PASS/0FAIL/0skipped. Four new QA .mjs syntax checks PASS. Local evidence audit:22 earlier reports unchanged,9 trace ZIPs pass CRC,0 protected-secret or plaintext fixture-password matches. Known owned R3 launcher/runtime PIDs are absent. git diff --check PASS with existing LF/CRLF notices. No repository-wide Angular/backend regression or production build is claimed as freshly executed.

Existing authorization was valid at initial witness check; all browser work stopped before expiry. No new database was created or token extended. R3 automatically closed its owned browser/API/proxy and performed original guarded cleanup at expiry. Read-only independent QA-instance audit confirms exact database absent, signed DROPPED, unchanged application/build source and prior reports. No permanent/golden access, live provider, development-process control or Python source edit. Full historical suites were not rerun without need.

Six deliverables: [matrix](wp7b-r3a-automation-matrix.md), [results](wp7b-r3a-automated-results.md), [minimal human checklist](wp7b-r3a-human-minimal-checklist.md), [risks](wp7b-r3a-risk-update.md), this assessment and [gate](wp7b-r3a-gate.json). Prior reports are preserved; this addendum does not rewrite them. Evidence hashes and cleanup audit remain under tmp/qa-wp7br3a.

**Next owner decisions:** grant fresh marker-protected disposable QA lifecycle authorization before any further browser work. Separately authorize the proposed narrowly scoped auth focus-color correction if desired; no implementation authority is inferred. Then finish remaining automation and use the compact grouped checklist only for actual speech/irreducible perception. Do not restart backup, WP7C or WP8.
