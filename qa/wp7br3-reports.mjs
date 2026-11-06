// Evidence-only snapshot. Never invent speech, zoom, rendered contrast or cleanup.
import fs from 'node:fs/promises';
const base='docs/qa/seller-experience/';
const prior=JSON.parse(await fs.readFile(base+'wp7b-r2-gate.json','utf8'));
const s=JSON.parse(await fs.readFile('tmp/qa-wp7br3/session-control.json','utf8'));
const timestamp=new Date().toISOString();
const rows=[...prior.screen_reader_checks,...prior.native_zoom_checks,...prior.contrast_review_groups].map(r=>({
  ...r, status:'NOT_VERIFIED',actual_result:null,observation_timestamp:null,human_observer:null,
  browser:s.browser||null,screen_reader_used:null,evidence_reference:'docs/qa/seller-experience/wp7b-r2-gate.json#'+r.id,
  test_method:r.id.includes('-SR-')?'Actual human-reported Narrator utterances':r.id.includes('-Z-')?'Native browser zoom and human visual/keyboard observation':'Actual exposed rendered-state color/applicability measurement',
  remaining_blocker:s.status==='AWAITING_HUMAN_OBSERVATION'?'Awaiting human-assisted session; this group not yet executed':s.safe_failure||s.status,
}));
if(rows.length!==40 || new Set(rows.map(r=>r.id)).size!==40)throw Error('EXACT_40_GROUPS_REQUIRED');
const gate={package:'WP7B-R3',snapshot_at:timestamp,date:'2026-11-05',timezone:'Asia/Calcutta',
  status:s.status,overall_wp7b:'INCOMPLETE',gate_A:{status:'PASS',inherited:true,evidence:base+'wp7b-r1-gate.json'},
  gate_B:'INCOMPLETE',counts:{VERIFIED_PASS:0,VERIFIED_FAIL:0,NOT_VERIFIED:40,NOT_APPLICABLE:0},
  groups:rows,session_receipt:'tmp/qa-wp7br3/session-control.json',
  authority:{source:'Latest R3 specification attachment',sha256:s.authority_sha256,development_interruption:false,application_code_changes:false},
  environment:{preflight:s.preflight,session:s.session||null,browser:s.browser||null,expires_at:s.expires_at||null},
  cleanup:{status:s.cleanup?.status||'PENDING_ACTIVE_BOUNDED_SESSION',independent_absence_verified:false},
  tests:{offline_node_pass:14,offline_node_fail:0,powershell_parser_errors:0,fresh_manual_groups:0,full_regression_suites_rerun:false},
  carry_forward:prior.carry_forward,risks_preserved:true,application_certification:'INCOMPLETE',
  restrictions:{permanent_golden_database_access:false,live_provider_calls:false,backup:'PARKED',WP7C:false,WP8:false,commits:false,pushes:false},
};
await fs.writeFile(base+'wp7b-r3-gate.json',JSON.stringify(gate,null,2)+'\n');
const url=s.session?.origin||'NOT AVAILABLE — session not ready';
const routes=Object.entries(s.routes||{}).map(([k,r])=>`| ${k} | ${url}${r} |`).join('\n');
const table=rows.map(r=>`| ${r.id} | ${r.area} | ${Array.isArray(r.criteria)?r.criteria.join(', '):r.criteria} | NOT VERIFIED | No fresh human/manual observation |`).join('\n');
await fs.writeFile(base+'wp7b-r3-session-setup.md',`# WP7B-R3 — isolated synthetic session setup

Snapshot: ${timestamp}. Status: **${s.status}**. This is a session checkpoint, not final certification.

## Isolation

Fresh R3 authorization only. The existing signed guard attested container \`${s.preflight.container_id}\`, instance \`${s.preflight.instance_id}\`, endpoint \`127.0.0.1:55432\`, role \`vayujit_qa_admin\`. Naming: \`vayujit_qa<16-hex>_test\`. Exact owner/marker/token/OID and signed lifecycle remain authoritative. No FORCE fallback, business/golden target or alternative instance is authorized.

QA URL: **${url}**. Database: \`${s.session?.database_scope||'not yet reported'}\`. Token: \`${s.session?.token||'not yet reported'}\`. Runtime PID: ${s.runtime_pid||'not yet reported'}.

Normal API/frontend listener identities were captured before startup in the session receipt. No stop, restart, connection substitution, normal configuration change, Docker restart or port takeover was performed. The QA runtime allocates unused loopback ports and serves the existing production Angular build; the fixture server disables .env loading and denies outbound sockets/providers. The R1 runtime/policy is reused as an engine, not as old authorization; all new ownership receipts say R3.

## Fixtures and authentication

Existing canonical API/domain fixture mechanisms prepare an explicitly synthetic owner, goal/opportunity, catalog/inventory/financial scenarios, mock content artifact, sandbox Marketplace drafts, local unpublished Ads campaign/read-only recommendation, Social draft and future draft review checkpoint. These do not certify live evidence or provider authorization. The draft Campaign checkpoint is not a legitimately eligible reschedule fixture; C-10 remains unverified. No worker/publishing process is launched.

Passwords and storageState are not written to reports. The password-bearing setup occurs outside retained tracing. An empty sign-in page is provided for label/role speech; no login details need to be entered for the first check. Later authenticated navigation restores the synthetic cookie in process memory only.

## Routes

| Surface | Exact isolated route |
| --- | --- |
${routes}

## Bound and cleanup

Session expiry: **${s.expires_at||'not yet ready'}**. Only R3-owned browser/API/proxy processes may be closed. The launcher closes the owned browser, signals the existing runtime stop marker, and waits for signed marker-protected non-FORCE cleanup. Current cleanup: **${gate.cleanup.status}**. Independent post-cleanup database absence has **not yet been verified**. Do not read an active-session receipt as final cleanup PASS.

Launch command (only when no active R3 record/session exists):

\`\`\`powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7br3.ps1
\`\`\`

The launcher deliberately refuses to overwrite an existing control receipt. Do not delete that receipt or bypass guards to restart. Review the previous session and cleanup first.
`);
await fs.writeFile(base+'wp7b-r3-human-test-guide.md',`# WP7B-R3 — human-assisted accessibility guide

Snapshot: ${timestamp}. Use only **${url}** in the window titled **WP7BR3 SYNTHETIC ${s.session?.token||'(not ready)'}**. Do not use ports 4200/8000 or real credentials. Current browser: ${s.browser?.name||'not ready'} ${s.browser?.version||''}. The automated verifier cannot hear Narrator. Please start the installed Windows Narrator yourself if needed; do not install software or change security/privacy settings.

## First checkpoint — R2-SR-01 only

1. Restore the exact QA window above and check its address ends in /login. All fields must be empty.
2. With Narrator running, click the visible Email label/input, then press Tab to Password. Do not type a password. Tab onward to Show password; use Space once if available, then return it to hidden.
3. Report the actual words spoken at Email, Password and Show password before/after toggling. Expected: meaningful labels, editable/secure field information, and meaningful show/hide state. Exact wording may differ. Do not report any password or personal information.
4. Tell us your browser version, Narrator version if known, reader language/verbosity if changed, and whether anything was silent or confusing. “Narrator audible” alone is not semantic evidence.

**Stop here and reply with what you actually heard. Do not execute the remaining sessions yet.** If the URL/window is uncertain, the session expired or there is no speech, say so; that is NOT VERIFIED, not automatic application failure.

## Remaining grouped sessions — execute one instructed test at a time

| Session | Stable IDs | Actions and required evidence |
| --- | --- | --- |
| Navigation and goals | SR-02–05, SR-10 | Skip link/headings; disclosure Enter/Space and spoken state; focus goal fields/help; existing invalid-input recovery without creating a valid goal; actual status speech. |
| Research and review | SR-11–13 | Read persisted synthetic context, review prerequisites and table/header relationships. No selection, discovery, approval or external execution. |
| Marketplace editors | SR-06–07 | Focus import controls without invoking them; traverse named Meesho editor group/buttons and local panels without saving or publishing. |
| Ads | SR-08–09 | Read-only Preview only; hear title/role, Tab/Shift+Tab containment, Space Close/Escape, returned focus speech. Never confirm execution. |
| Native zoom | Z-01–12 | Four original critical surfaces at actual Chrome 100/200/400%; show percentage, record full-window screenshot, CSS viewport/DPR, reflow, keyboard/focus, forms/errors/dialogs. No CSS scaling or viewport-only substitute. |
| Contrast | C-01–15 | Exact retained targets and actual states; expose by scrolling/focus, record foreground/adjacent background, alpha/overlays, ratio and correct criterion, aligned screenshot. Unknown stays unknown. |

IDs above use the unchanged R2- prefix in the gate/checklist. Full acceptance requirements and original criteria: [R2 checklist](wp7b-r2-manual-checklist.md), copied unchanged per group into [R3 gate](wp7b-r3-gate.json). No group is waived or merged.

Observation format: ID; route; action; actual utterance/visual observation or measured colors; browser/reader; witness/date; screenshot reference; PASS/FAIL/NOT VERIFIED with reason. Never copy expected speech into actual evidence. Screenshots must show only the synthetic QA surface; avoid other windows, credentials, cookies and real business data.

At native 400%, use an approximately 1280 CSS-pixel content starting width to assess 320 CSS-pixel reflow; outer physical window size is not the same measurement. Reset to native100% afterward. Applicable contrast: normal text4.5:1, qualifying large text3:1, essential authored UI/state indicators3:1 against actual adjacent colors. Use unrounded ratios and documented exceptions; do not exempt all disabled-looking or small controls. New demonstrated defects require separate implementation authority.
`);
await fs.writeFile(base+'wp7b-r3-accessibility-evidence.md',`# WP7B-R3 — forty-group reconciliation

Snapshot: ${timestamp}. All forty original review IDs and acceptance sources remain in the machine gate. No semantic speech, native zoom or fresh manual contrast result has yet been obtained. Setup screenshots/keyboard/DOM/axe do not substitute for human observations. Historical sampled PASS evidence remains valid for its exact scope; NOT VERIFIED rows represent the unclosed remainder, not reopened R1 defects.

| ID | Workflow | Criterion | Result | Actual evidence |
| --- | --- | --- | --- | --- |
${table}

Shared execution metadata: human observer none; actual speech null; reader used not yet confirmed; manual observation timestamp null. Browser session details and setup screenshot, when ready, are in tmp/qa-wp7br3/session-control.json. No observation is silently inferred from it. Individual actions, actual results, witness, timestamps and evidence must be appended before changing any verdict.
`);
await fs.writeFile(base+'wp7b-r3-risk-update.md',`# WP7B-R3 — risk checkpoint

Snapshot: ${timestamp}. No new application-owned accessibility defect has yet been demonstrated. All40 manual groups remain NOT VERIFIED, not FAIL. No application changes authorized or made. If a defect is demonstrated, capture exact reviewID/state/reproduction/expected/actual/impact, then request a separate minimal correction authorization.

Preserved risks: WP7A48 prioritized local entries are not every route/operation; L-17 has the explicitly approved narrower offline scope and real expiry remains UNVERIFIED. R1 GateA PASS is inherited. Historical Ads502 remains unattributed (not closed by the distinct R1 anomaly500 repair). Historical PostgreSQL timestamp attribution remains unresolved. Financial projection/precision is not immutable accounting or statutory/bank/settlement/tax reconciliation. Historical typing/lint/schema/index and bundle risks remain. Live-provider certification is unsupported. PC-first independent encrypted backup/restore remains PARKED.

The forty groups retain the legacy index/cause/applicability review and its original stable references;3169 occurrence keys are not3169 unique current defects. Existing N/A sub-reviews for static text's own focus ring do not exempt their labels/text/associated controls. The draft Campaign checkpoint is ineligible for rescheduling; absence is not an exemption.

Remaining controls: human speech required, actual native zoom proof and visual confirmation required, no production target, no normal process interruption, no unrelated Docker change, no live calls, no FORCE cleanup. Current session cleanup is ${gate.cleanup.status}; final independent absence remains required. No WP7C/WP8/backup/launch authorization is granted.
`);
await fs.writeFile(base+'wp7b-r3-assessment.md',`# WP7B-R3 — assessment checkpoint

Snapshot: ${timestamp}. **GateA: inherited PASS. GateB: INCOMPLETE. Overall WP7B: INCOMPLETE.** This is not final certification or a WCAG conformance claim.

Session status: **${s.status}**. First required human checkpoint: R2-SR-01 empty sign-in labels. Human observations obtained:0. Forty review groups:0 VERIFIED PASS,0 VERIFIED FAIL,40 NOT VERIFIED,0 NOT APPLICABLE. Native zoom and remaining manual contrast have not been executed. No new mandatory checks or waived acceptance criteria.

Actual focused offline QA checks:14passed,0failed; Node syntax PASS; one PowerShell file parser0errors. These are launcher/safety and reused arithmetic/startup regressions, not actual manual accessibility evidence. Initial restricted-shell Node lookup failed; elevated existing Node execution succeeded. Initial direct PowerShell invocation was blocked by process execution policy; documented process-local invocation succeeded without system policy changes.

Signed QA instance preflight passed. A fresh task-owned migrated runtime and synthetic fixture setup status is recorded in the receipt; do not infer readiness from process creation alone. Existing normal development processes were not stopped or restarted. No application source, permanent/golden database, production .env, unrelated Docker resource, live provider, backup, branch, commit or push changed by R3.

Cleanup current status:${gate.cleanup.status}; independent absence NOT YET VERIFIED. The active bounded session is intentionally paused awaiting the first listener observation; automatic expiry triggers guarded cleanup. Final R3 certification and cleanup review must follow after the human-assisted session or failure/expiry.

Deliverables: [setup](wp7b-r3-session-setup.md), [human guide](wp7b-r3-human-test-guide.md), [40-group evidence](wp7b-r3-accessibility-evidence.md), [risks](wp7b-r3-risk-update.md), [gate](wp7b-r3-gate.json). Stop at the human checkpoint; no WP7C/WP8.
`);
console.log(JSON.stringify({reports:6,groups:rows.length,status:s.status,manual_pass:0}));
