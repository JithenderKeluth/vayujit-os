# WP7A-2 — Coverage closure

Bounded four-scenario result: **PASS**. **WP7A INCOMPLETE; application certification INCOMPLETE.**

## Authority and remaining scope

Read the WP7A reports/gate, original WP7 matrix/defect register and relevant WP6A/WP6B reports. The named follow-ups are B and L; prior bounded G/H evidence is retained. Seven original historical files have frozen SHA256s in tmp/qa-wp7a2/baseline.json. They are not overwritten. Original WP7 matrix L: other supported AI/image/content/campaign preparation and artifact-review actions remain unexecuted; route rendering is not functional certification. This task does not silently turn route review into action coverage or start WP7B/C/WP8.

| Scenario | Existing matrix / addendum ID | Contexts passed | Result |
| --- | --- | --- | --- |
| A — Changed-input research freshness | B / B-07 | 4/4 | PASS |
| B — Failed creative-job retry | L / L-06 | 4/4 | PASS |
| C — Approved storyboard cloning | L / L-07 | 4/4 | PASS |
| D — Persisted Ads recovery | L / L-08 | 4/4 | PASS |

## Actual execution

Final browser token: 2903a4e2ff3d08df; 16 PASS / 0 FAIL, Chrome and Edge at1440/390. Final backend token: 6097ae72026143d4; 84 PASS / 0 FAIL / 0 ERROR / 0 SKIP. These are not added to overlapping earlier runs as unique coverage.

| Check | Actual outcome |
| --- | --- |
| node-qa | PASS — 81 tests |
| python-qa | PASS — 80 tests |
| angular | PASS — 387 tests |
| typescript-app | PASS |
| typescript-spec | PASS |
| eslint-web | PASS / 2 warnings |
| eslint-qa | PASS |
| ruff | PASS |
| black | PASS |
| mypy-video/service.py | PASS |
| mypy-ads/router.py | FAIL |
| mypy-ads/service.py | PASS |
| compileall | PASS |
| powershell-parser | PASS |
| diff-check | PASS |
| production-build | PASS |

## Correctness boundaries

A uses the supported immutable-goal revision workflow, not a mutation of historical observations. Goals, runs, candidates, timestamps and provenance are retained. Independent QA SHA256s bind inspected input/profile snapshots; the plan hash describes the step graph and is NOT falsely represented as an input fingerprint. A historical category-mismatched product is reference-only; no selection control is available in the new goal. Commercial claims remain unverified/partial.

B drives the normal local queue and canonical worker into a real recorded provider failure. The owner uses the existing generation recovery API through the newly discoverable UI. Retries preserve job/attempt identity and historical evidence, clear only current error/scheduling fields and record one audit intention. The second attempt is correctly failed, not a fabricated success; no output or approval is created.

C obtains genuine owner approval in the browser, then edits the approved storyboard through the supported Save-to-draft-clone contract. Duplicate/concurrent edits reuse one clone intent. The approved original remains unchanged; the new draft has explicit source audit lineage and no inherited approval. The clone is edited and reopened. The backend still rejects an unapproved clone for governed generation.

D prepares and confirms a LOCAL SYNTHETIC campaign using a non-real credential marker. Exact previewed inputs/fingerprint are retained; material changes require a new preview/review. Canonical fake-connector workers record failures; repeated retries share one job, stale new intentions are409, a second observed failure gets a new recovery identity. A fresh Python application instance authenticates the persisted browser session through normal auth and Ads APIs in a read-only transaction. The owner's normal API/service is not stopped, no provider is enabled and no remote campaign is created.

## Safety and recovery

Approved instance389b97d2-a4cd-4d9b-972e-6bb2bf5785eb, container a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23, loopback127.0.0.1:55432, non-superuser vayujit_qa_admin, exact scope vayujit_qa<16-hex>_test. Canonical markers/tokens/role/OID/signed lifecycle and session guards remain. Two interrupted-run lifecycle files were found null-filled. `67abc9a3296a0694` was independently absent; its original signature could not be validated and its new record is explicitly an absence-only attestation. `325de41be0b7492f` was an interrupted-DROP tombstone, OID8996294, owned by the QA role. After separate explicit HUMAN approvals, the exact instance/name/OID was rechecked, damaged records quarantined, task processes/sessions excluded and non-FORCE DROP used. The inaccessible tombstone marker was NOT claimed as reread. This is a two-token exception, never an automatic deletion fallback. The OS-level cause of null-filled files is unknown.

Final read-only audit: DATABASES_ABSENT_ENVIRONMENT_BASELINE_DRIFT; 14 task databases independently absent; historical baseline unchanged=true; protected credential matches=0. Docker preservation and trace CRC details are in wp7a2-gate.json and tmp/qa-wp7a2-final-audit.json.

## Limitations and stop decision

Axe: 24 scans, 0 violation instances, 14 incomplete-rule instances requiring review. No full WCAG/manual assistive-technology certification. Strict mypy passes for Video and Ads services; the Ads router's pre-existing diagnostics remain, with a source-baseline comparison showing 0 added diagnostic messages. This is not repository-wide typing certification. Nullable/dynamic endpoint types remain a production risk outside the executed subset. Existing web warnings are retained. Historical Ads502 remains unreproduced/cause unclassified, not resolved by repeat200s. No real integration, production activation, backup certification, publishing or marketplace write is certified.

## Reproduce

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/qa-postgres.ps1 -Action Status
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a2.ps1 -Action Backend
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a2.ps1 -Action Browser
node qa/wp7a2-checks.mjs
.\apps\api\.venv\Scripts\python.exe -m qa.wp7a2_final_audit
node qa/wp7a2-report.mjs 2903a4e2ff3d08df 6097ae72026143d4
```

Requires the already approved protected QA profile, never business/golden credentials. One-time recovery commands are not normal startup/test instructions and must not be generalized. Stop after WP7A-2.

## Exact environment and static-check dispositions

The strict historical Docker preservation check remains **FAIL**: only the start/finish timestamps of /infrastructure-postgres-1 differ. All10 original container identities/images/mounts/networks remain structurally unchanged, and no original network or volume is missing or added. The restart cause is UNATTRIBUTED; this work does not restore/backdate the owner's container state to force PASS. Database absence is independently **PASS**. Overall environment audit is **DATABASES_ABSENT_ENVIRONMENT_BASELINE_DRIFT**.

The raw focused Ads-router strict-mypy CLI check retains 63 diagnostics. A separate same-source, nonincremental baseline comparison records 78 baseline versus 78 current messages and 0 additions. Different analysis entry points are not summed or called identical test counts. No diagnostic is suppressed; the baseline review is not a substitute for an all-green typing gate. Web lint retains2 existing warnings.
