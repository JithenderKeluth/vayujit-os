# WP6B — Actual browser/API regression evidence

2026-10-30. Application certification **INCOMPLETE**. Final machine-readable
decision/results: `wp6b-quality-gate.json`; stop before WP7 execution.

## Actual runtime and journeys

Existing attested QA instance only: loopback127.0.0.1:55432, dedicated
`vayujit_qa_admin`, signed `vayujit_qa<16hex>_test` lifecycle, owner/OID/creation
marker and exact container identity. Actual production Angular served by the
existing local QA reverse proxy; no production credentials or real providers.
Installed Chrome/Edge1440×900 and390×844; not independent Firefox/WebKit coverage.

Final main run **`e62facf73615c750`:8 grouped checks PASS**, normal cleanup/exit0:

1. Empty Video, Ads, optimization and Finance load with truthful missing/unknown
   states after real full migrations to head149, not metadata-only creation.
2. Canonical synthetic order/fee evidence and UNKNOWN costs →known total cost10.05;
   Finance sales200.25, fee20.05 →profit170.15. Same-scope recalculation identity,
   reload and synthetic provenance asserted. Orders show the rounded-unit warning.
3. Actual Ads optimization navigation repeated8 times;32 explicitly recorded
   authenticated API reads (comparison/overview/optimization/anomalies) return200;
   additional natural browser reads are retained in network evidence. Refresh
   preserves state. **No502 reproduced**, not proof the old observation is resolved.
4. Exact controlled Ads overview503 →visible unavailable →Refresh →canonical
   success. No campaign or video generation created, no approval/execution.
5–7. Chrome390, Edge1440 and Edge390 independently sign in, review six affected
   routes, preserve persisted financial values/reload, inspect caption/scene/table
   nodes, exercise keyboard/menu and200% text resizing.
8. No unexpected console/page/server/failed-request/guard signals. Only the exact
   injected503 and anonymous session401 probes are allowlisted; campaigns and
   generations remain empty. No provider authorization was fabricated.

Social follow-up **`dca65d7d5070a63b`:4 groups PASS**, normal cleanup/exit0.
The initial empty-state group repeats; three contexts expose the original Social
headers/accessibility tree and original Video empty cell with keyboard scrolling.
This is additional manual evidence, not four new complete seller workflows.

Main28 and follow-up10 axe scans have0 violations;12/19 and11/13 incomplete
rule/node occurrences remain retained.39 actual focused manual measurements pass
for normal-state contrast/unobscured centres. Full limitations and original-target
traceability: [accessibility review](wp6b-accessibility-review.md).

## Intermediate runs retained, not silently closed

| Token | Actual result |
| --- | --- |
| `02ecb813fd29f146` | Initial four-route baseline passed; caption measurement collection0 because the harness queried before route readiness. Not claimed as manual coverage. |
| `f08380eda97e982d` | Baseline passed; both original caption controls actually measured14.80:1. Original duplicated DOM retained in screenshots. |
| `27c1bacc93a57a37` | Four groups passed; harness requested nonexistent Visual guidance label. Corrected to actual Narration; no production rename to satisfy test. Cleanup interruption retained, guarded recovery verified. |
| `9962918f1d9709f7` | Four groups passed plus four manual measurements; harness sought button inside link-based Quick actions. Corrected to actual link role. Cleanup interruption retained, guarded recovery verified. |
| `e62facf73615c750` | Final complete main replay,8 groups; normal signed cleanup, child exit0. |
| `dca65d7d5070a63b` | Accepted Social/Video-empty-cell manual follow-up,4 groups; normal signed cleanup, child exit0. |

Evidence lives in `tmp/qa-seller-browser/<token>/`; actual screenshot/trace paths
are in report/surface JSON. Screenshots inspected include mobile caption input
with focus/disabled Add track and original Social Status/Action headers. Keep
traces private: synthetic sessions are still authentication material.

## Backend / regression counting

`test_seller_wp6b.py`: final28 cases target financial rounding, missing/nonfinite
values, conserved allocation/invalid weights, FX/no-pair, small-unit/large-quantity,
negative/zero profit, undefined zero-net-sales margin, canonical persistence,
raw sub-paise source retention, zero allocation basis and v1 snapshot preservation.

Adjacent matrix49 =13 Video/Ads services +8 fresh/populated/guarded rollback
migrations +9 WP6 +11 WP5 +8 inventory/order regressions. No new migration or
numeric-scale change. Final exact counts and process/cleanup outcomes are in the
gate; a passing JUnit assertion count is not used to hide a nonzero cleanup exit.
Accepted final new suite `64b108e20bd44e44`:28 PASS, process exit0, normal guarded
cleanup. Accepted final adjacent `8118ef894b5f40f5`:49 PASS, process exit0, normal
guarded cleanup. Both record the bounded90s connection-local DROP setting. An
earlier49-case run `8b319ea2c843497c` also passed/cleaned; it is not added again.
Original25-case attempt had23 pass/2 failures: early NaN guard compared before
checking finiteness, plus harness expected nonexistent `products` response key
instead of canonical `rows`. Both corrected without weakening expected values.
Intermediate25/26/27-case passes remain historical, not summed into unique coverage.

Angular373/81 files, Node66, Python57 self-tests passed. Production build422.71kB
under unchanged500kB budget. Focused configured Ruff/Black, new monetary-helper
strict mypy, compileall, Video ESLint, app/spec TypeScript, JS/PowerShell parsers
and diff check are recorded in the gate. No repository-wide typing/lint claim;
FastAPI startup/operation-ID and historical debt remain separately classified.

## Reproduce on Windows

```powershell
.\scripts\qa-postgres.ps1 -Action Status
npm.cmd run build --workspace @vayujit/web -- --configuration production
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp6b.ps1 -Action Backend
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp6b.ps1 -Action Adjacent
# Terminal 1: wait for READY, keep open. Do not rebuild during replay.
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp6b.ps1 -Action Browser
# Terminal 2: substitute that NEW READY token only.
.\apps\api\.venv\Scripts\python.exe -m qa.wp6b_schema_review <READY_TOKEN>
node qa/wp6b-browser-retest.mjs tmp/qa-seller-browser/<READY_TOKEN>/session.json
# Wait for CLEANED. Start another fresh Browser runtime for the follow-up:
node qa/wp6b-browser-retest.mjs tmp/qa-seller-browser/<NEW_READY_TOKEN>/session.json --social
.\apps\api\.venv\Scripts\python.exe -m qa.wp6b_final_audit
# After all four accepted runs and cleanup are complete, regenerate the gate:
node qa/wp6b-report.mjs <MAIN_TOKEN> <SOCIAL_TOKEN> <BACKEND_TOKEN> <ADJACENT_TOKEN>
npm.cmd run qa:unit
.\apps\api\.venv\Scripts\python.exe -m unittest discover -s qa/unit -p 'test_*.py'
npm.cmd test --workspace @vayujit/web -- --watch=false
git -c safe.directory=C:/Users/jithe/Documents/vayujit-os diff --check
```

Do not substitute another database if attestation fails. Do not reuse historical
cleaned tokens. No golden/permanent data, unrelated Docker deletions, real provider
calls, marketplace writes, backup operations, branches, commits, pushes or WP7 work.
Final audit:15 signed databases absent;14 traces CRC PASS; five earlier guarded
interrupted-drop recoveries preserved; original Docker resources unchanged.
