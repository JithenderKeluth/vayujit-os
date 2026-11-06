// Offline reconciliation only. Never launches a browser or database lifecycle.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
const base='docs/qa/seller-experience/',out='tmp/qa-wp7br4/';
const read=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const prior=await read(base+'wp7b-r3a-gate.json'),session=await read(out+'session-control.json');
if(session.package!=='WP7B-R4'||session.session.token!=='208c03c2118d62af')throw Error('R4_EVIDENCE_IDENTITY_REQUIRED');
const names=['browser','followup','auth-states','fields'];
const runs=await Promise.all(names.map(n=>read(out+n+'/results.json')));
for(const r of runs)if(r.token!==session.session.token)throw Error('R4_RUN_TOKEN_MISMATCH');
const measurements=runs.flatMap(r=>r.measurements),checks=runs.flatMap(r=>r.checks),scans=runs.flatMap(r=>r.scans||[]),fragments=runs.flatMap(r=>r.fragments||[]);
const cleanup=await read(out+'final-cleanup-audit.json').catch(()=>({status:'PENDING_ACTIVE_SESSION',independent_absence:false}));
const finalValidation=await read(out+'final-validation.json').catch(()=>null);
const human=await read(out+'human-observations.json');
const passed=new Set([1,2,3,4,5,6,7,8,10].map(n=>'R2-C-'+String(n).padStart(2,'0')));
const evidence=names.map(n=>out+n+'/results.json');
const missing={
 'R2-C-09':'Normal dialog heading and focus verified. Relevant loading/error state contrast is not fully established.',
 'R2-C-12':'Rendered control boundaries captured; essential-boundary/state applicability remains unadjudicated.',
 'R2-C-13':'Real requestAnimationFrame computed transition frames captured without disabling animation; transient low ratios require criterion and visual adjudication. No settled-state PASS is substituted.',
 'R2-C-14':'Target rectangles captured. Spacing, inline/label hit areas and legitimate exceptions not fully adjudicated.',
 'R2-C-15':'Legacy3169 occurrence keys preserved; full cause/applicability reconciliation not complete.'};
const groups=prior.groups.map(old=>{
 const g=structuredClone(old),isSpeech=g.id.startsWith('R2-SR-'),zoom=g.id.startsWith('R2-Z-');
 g.prior_evidence={report:base+'wp7b-r3a-gate.json',status:old.status,coverage:old.coverage,result:old.actual_result};
 g.status=passed.has(g.id)?'VERIFIED_PASS':g.id==='R2-C-11'?'VERIFIED_FAIL':'NOT_VERIFIED';
 g.coverage=g.status==='VERIFIED_PASS'?'FULL_RECORDED_GROUP':g.status==='VERIFIED_FAIL'?'CONFIRMED_FAILURE':zoom||g.id==='R2-C-15'?'NO_FRESH_EXECUTION':'PARTIAL';
 g.automated_assertion_records=checks.filter(c=>c.review_id===g.id);
 g.r4_measurement_records=measurements.filter(m=>m.review_id===g.id).length;
 g.r4_fragment_records=fragments.filter(m=>m.review_id===g.id).length;
 g.evidence=[...(old.evidence||[]),...evidence];
 g.test_environment={token:session.session.token,origin:session.session.origin,synthetic:true,versions:runs[0].versions,native_zoom_verified:false};
 g.actual_speech=null;g.actual_reader_version=null;g.assessment_timestamp=new Date().toISOString();
 g.required_for_closure=passed.has(g.id)?'No remaining assertion for this recorded contrast scope; no whole-screen or WCAG conformance claim.':isSpeech?'Actual remaining spoken behavior required. Existing login observations retained, not repeated; availability reply is not speech evidence.':zoom?'Actual native100/200/400% evidence required; responsive viewport is not native zoom.':g.id==='R2-C-11'?'Login subfinding resolved. Separately authorize localized Campaign focus-color correction and retest; no such fix made in R4.':missing[g.id];
 g.actual_result=passed.has(g.id)?'Fresh rendered measurements pass for original recorded targets; label/caption text exposure uses separately documented Range method where enclosing boxes did not fit.':g.id==='R2-C-11'?'Auth focus40PASS at8.559089262681107:1; Campaign focus4FAIL at2.374231440911746:1, threshold3.':isSpeech?'Automated semantics/keyboard evidence retained; no new actual utterance supplied.':zoom?'No reliable native zoom percentage captured; Narrator Home app-control approval/geometry prevented safe native path.':missing[g.id];
 g.reason=g.actual_result;g.fresh_evidence=evidence;return g;
});
const finding={id:'WP7B-R4-CAMPAIGN-FOCUS-001',review_id:'R2-C-11',status:'VERIFIED_FAIL',priority:'P2',blocking_gate_B:true,route:session.routes.campaign,selector:'.reschedule-panel textarea',criterion:'1.4.11',expected:'Authored active focus >=3:1 against adjacent verified backdrop',actual:'RGB224,154,54 on opaque white;2.374231440911746:1 in all four browser/viewport contexts. Text14.798385782792908:1 passes C-10.',reproduction:['Open marked synthetic Campaign with eligible missed local mock activity','Open Reschedule without confirming','Tab to reason textarea','Measure active3px authored outline against white'],impact:'Low-vision keyboard users may not distinguish focus.',suggested_fix:'Separately authorized local Campaign focus token override; preserve global/dark navigation.',fixed:false,evidence:out+'followup/results.json'};
const counts=Object.fromEntries(['VERIFIED_PASS','VERIFIED_FAIL','NOT_VERIFIED','NOT_APPLICABLE'].map(s=>[s,groups.filter(g=>g.status===s).length]));
const hash=async p=>crypto.createHash('sha256').update(await fs.readFile(p)).digest('hex');
const manifest=await read(out+'preflight.json');
const gate={package:'WP7B-R4',assessed_at:new Date().toISOString(),gate_A:{status:'PASS',inherited_from:base+'wp7b-r1-gate.json',rerun:false},R4_A:'VERIFIED_PASS',gate_B:'FAIL',overall_WP7B:'INCOMPLETE',counts:{total_groups:40,...counts,partially_verified:groups.filter(g=>g.coverage==='PARTIAL').length,without_fresh_execution:groups.filter(g=>g.coverage==='NO_FRESH_EXECUTION').length,remaining_speech_groups:12},groups,findings:[finding],login:{before:2.374231440911746,after:8.559089262681107,required:3,active_focus_samples:40,scope:'Auth-local one-line --vj-focus override only;3px width/3px offset retained; no authentication change'},tests:{browser_checks:{passed:checks.filter(c=>c.status==='VERIFIED_PASS').length,failed:checks.filter(c=>c.status==='VERIFIED_FAIL').length,primary_context_limitations:4,not_whole_matrix_pass:true},measurements:{element_records:measurements.length,fragment_records:fragments.length,not_unique_tests:true,focus_failures:measurements.filter(m=>m.focus_indicator?.status==='FAIL').length},axe:{scans:scans.length,violation_rule_occurrences:scans.reduce((n,s)=>n+s.violations.length,0),incomplete_rule_occurrences:scans.reduce((n,s)=>n+s.incomplete.length,0)},angular_auth:{passed:22,failed:0,files:4,full_442_suite_rerun:false},node_focused:{passed:14,failed:0,skipped:0},production_build:'PASS',eslint:'PASS',typescript_app:'PASS',typescript_spec:'PASS',prettier:'PASS after new-spec-only formatting',quality_history:out+'quality.json'},human,environment:{token:session.session.token,origin:session.session.origin,expires_at:session.expires_at,ended_at:session.ended_at||null,cleanup,preflight:out+'preflight.json',midrun_preservation:out+'process-preservation-midrun.json',normal_process_management:false,no_python_source_edit:true,raw_output_persisted:false},evidence_sources:evidence.map((p,i)=>({path:p,sha256:null,command:'node qa/wp7br4-'+(['browser','followup','auth-states','fields'][i])+'.mjs'})),source_hashes:{auth:await hash('apps/web/src/app/auth/auth-page.component.ts'),global_styles:await hash('apps/web/src/styles.css')},carry_forward:prior.carry_forward,historical_risk_disposition:'Unchanged; see wp7b-r4-risk-update.md',prior_evidence_hash_manifest:out+'preflight.json',live_provider_certification:false,backup_certification:'PARKED',WP7C_started:false,WP8_started:false};
for(const e of gate.evidence_sources)e.sha256=await hash(e.path);
gate.final_offline_validation=finalValidation;
gate.changed_files={production:['apps/web/src/app/auth/auth-page.component.ts'],angular_tests:['apps/web/src/app/auth/auth-focus-r4.spec.ts'],qa:['qa/wp7br4-preflight.mjs','qa/wp7br4-fixtures.mjs','qa/wp7br4-session.mjs','qa/wp7br4-quality.mjs','qa/wp7br4-browser.mjs','qa/wp7br4-followup.mjs','qa/wp7br4-auth-states.mjs','qa/wp7br4-text-fragments.mjs','qa/wp7br4-fields.mjs','qa/wp7br4-watch-cleanup.mjs','qa/wp7br4-report.mjs','qa/wp7br4-final-validation.mjs','qa/unit/wp7br4.test.mjs','scripts/test-seller-wp7br4.ps1'],documentation:['focus-remediation','isolated-session','accessibility-matrix','automated-results','human-review-guide','risk-update','assessment','gate'].map(n=>base+'wp7b-r4-'+n+(n==='gate'?'.json':'.md'))};
gate.environment.normal_frontend_at_preflight='Absent; no frontend was stopped or restarted';
gate.environment.final_owned_process_check=await read(out+'final-process-check.json').catch(()=>null);
gate.environment.reader_cleanup='Narrator Home app-control approval timed out; human exit may be required. No shared ShellHost process terminated.';
await fs.writeFile(base+'wp7b-r4-gate.json',JSON.stringify(gate,null,2)+'\n');
const write=(name,body)=>fs.writeFile(base+'wp7b-r4-'+name+'.md',body+'\n');
await write('focus-remediation',`# WP7B-R4 — login focus remediation

R4-A VERIFIED_PASS. Original R3A password-toggle focus RGB224,154,54 on opaque white measured2.374231440911746:1, below3 under SC1.4.11. Text was not the failure. Root cause: global authored focus color with no auth-local override (styles.css99–107).

Only production change: apps/web/src/app/auth/auth-page.component.ts, .auth { --vj-focus: var(--vj-color-brand-strong); }. Global token and3px solid outline/3px offset unchanged. Removing precisely this line reproduces preflight source hash; global stylesheet hash unchanged. No auth/API/validation/layout contract changes.

Chrome156.0.8078.76 and Edge156.0.4314.58 at1440/390 widths:40 active auth focus samples PASS, RGB7,84,98 on white,8.559089262681107:1. Email, Password, toggle and enabled Submit; hover/wrong-password401/disabled-submit behavior exercised. Disabled Submit is not keyboard-focusable, not fabricated as an active focus state. Full keyboard UI login passed in four contexts; Space toggle and focus restoration passed. Full viewport focus PNGs and clipping geometry accompany samples, e.g. tmp/qa-wp7br4/browser/wp7br1-r4-chrome-390/focus-64.png. Evidence: ${evidence.join(', ')}.

Angular auth22PASS (four files; includes two new regressions). Focused18 and later22 are overlapping scopes, not40 unique cases. Node14PASS. Production build/ESLint/TS app/spec/Prettier PASS. Initial formatting failure/new-test regex failure retained; corrected and rerun, no assertions weakened. Full historical442 suite not rerun.
`);
await write('isolated-session',`# WP7B-R4 — isolated session

Fresh R4 authority SHA256 ${session.authority_sha256}. Exact approved container a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23; instance389b97d2-a4cd-4d9b-972e-6bb2bf5785eb,127.0.0.1:55432, role vayujit_qa_admin. Signed lifecycle/owner/marker/token guards verified before creation. Database vayujit_qa208c03c2118d62af_test, token208c03c2118d62af. No business/golden target or FORCE fallback.

Separate QA Node/runtime29756 and wrapper40800, unused loopback origin ${session.session.origin}; production build proxy and exact-token runtime witness. Ready ${session.ready_at}, expires ${session.expires_at}; never extended for speech. Fixture IDs/routes/process evidence: tmp/qa-wp7br4/session-control.json and tmp/qa-seller-browser/208c03c2118d62af. Canonical synthetic owner, product, economics, local content/marketplace fixtures; eligible Campaign uses existing signed guarded synthetic interruption intent with worker_executed=false. No real authorization, remote execution, provider call or raw production row copy.

Preflight: normal frontend absent; two Python-only uvicorn reload trees enumerated, no custom includes. No Python source edited; one auth TS line safe from existing Python watcher. Midrun seven original process identities and original Docker metadata unchanged. Original unrelated containers not controlled.

Cleanup status: **${cleanup.status}**. Final independent read-only verification: tmp/qa-wp7br4/final-cleanup-audit.json. Owned session expires and invokes existing signed non-FORCE cleanup; watcher only verifies absence/signed DROPPED and process/container preservation, never creates/drops/restarts. Pending cleanup is not PASS. Narrator was started for requested human review; Home app-control approval timed out. Human may need to exit Narrator; no broad shared ShellHost/process kill is authorized.
`);
await write('accessibility-matrix',`# WP7B-R4 — authoritative40-group reconciliation

Original IDs, acceptance_source, expected requirements and criteria preserved from R3A. PASS is only the recorded target scope, not whole screen/WCAG. PARTIAL is coverage annotation, never a gate verdict. Prior login observations retained, not requested again. Exact automated expected/actual/browser/version/time/route/evidence/command records reside in the gate and source receipts.

| ID | Area / criterion | Original evidence | R4 evidence and result | Human-only / remaining blocker | Status / coverage |
| --- | --- | --- | --- | --- | --- |
${groups.map(g=>`| ${g.id} | ${g.area}; ${Array.isArray(g.criteria)?g.criteria.join(', '):g.criteria} | R3A ${g.prior_evidence.status}/${g.prior_evidence.coverage}; unchanged acceptance_source in gate | ${g.actual_result} ${g.automated_assertion_records.length} interaction assertions; ${g.r4_measurement_records} element/${g.r4_fragment_records} fragment records | ${g.required_for_closure} | ${g.status} / ${g.coverage} |`).join('\n')}

Counts:9VERIFIED_PASS,1VERIFIED_FAIL,30NOT_VERIFIED,0NOT_APPLICABLE.17partial and13without fresh execution. C10 text passes; Campaign focus fails C11 separately. No inaccessible fixture or missing observation classified N/A.
`);
await write('automated-results',`# WP7B-R4 — executed results

Node24.19.0; Playwright1.64.1; axe4.11.0; Chrome156.0.8078.76/Edge156.0.4314.58. All fresh browser evidence token208c03c2118d62af, synthetic loopback only. UTC timestamps, expected/actual, source selectors, snapshots/PNG/trace references in each result JSON.

| Command | Actual result |
| --- | --- |
| node qa/wp7br4-browser.mjs |32 scoped checksPASS; four subsequent harness assumptions about Flipkart named group stopped those contexts, retained, not app defects |
| node qa/wp7br4-followup.mjs |28PASS; actual Flipkart grouped-button contract used; all editor panels, tables, Campaign/Ads covered |
| node qa/wp7br4-auth-states.mjs |4PASS; genuine401, recovered canonical login,16focus measurements |
| node qa/wp7br4-fields.mjs |4PASS; exact numeric input,56actual text fragments |
| npm.cmd run test --workspace @vayujit/web -- --include=src/app/auth/*.spec.ts |22PASS/0FAIL,4files |
| node --test qa/unit/wp7br4.test.mjs qa/unit/wp7br1-contrast.test.mjs qa/unit/wp7br1-startup.test.mjs |14PASS/0FAIL/0skip after correcting QA-only literal matcher |
| npm.cmd run build --workspace @vayujit/web |PASS; initial422.81kB/estimated109.48kB transfer |

Totals68passing scoped interaction assertions, not68whole-accessibility gates.1124element records plus56word fragments; occurrences, not unique tests. Four separate Campaign focus measurements FAIL. Forty axe scans:0violation rule occurrences,28incomplete rule occurrences. Incomplete/obscured nodes are not PASS; no rule suppression or DOM exclusion. No WCAG conformance claim.

Original large enclosing label/caption boxes retained NOT_VERIFIED. New text-fragment method keeps original targets and measures every actual static text word via Range, safe scrolling and occlusion hit tests, solid ancestor-chain contrast; input values measured separately.56PASS supplies scoped text evidence, not whole-box geometry. Text/geometry uncertainty is not silently deleted. Main1440/390 runs responsive desktop, not touch emulation; auth-state and field390 runs explicitly mobile/touch. None proves native100/200/400zoom.

Real rAF transition samples captured, not disabled animations. Low intermediate computed ratios are not declared settled-state PASS or a fully adjudicated defect. Essential boundaries, target exceptions, legacy3169 reconciliation remain open.

ESLint scoped auth files, TS app/spec noEmit, Prettier after test-only formatting and diff check PASS. Initial quality history remains tmp/qa-wp7br4/quality.json. No Python source/migration change, so no unrelated Python full suite claimed. R1 historical52/32, Angular442, Node138, Python163, backend36 preserved, not freshly rerun. Exact check receipts/syntax/security audit see final-validation.json when available.

Browser commands require a newly approved active guarded session, matching receipt and exact-token witness. Current session is bounded; do not run browser commands against retired URLs. Offline report: node qa/wp7br4-report.mjs. Launch command used: powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7br4.ps1 (no persistent policy change).
`);
await write('risk-update',`# WP7B-R4 — risks and provenance

Login focus defect resolved. **${finding.id},P2,VERIFIED_FAIL**, Campaign reason textarea active outline2.374231440911746:1 vs3 in four contexts. C10 text passes14.798385782792908:1; low-vision keyboard focus is separate C11 failure. Reproduce via synthetic eligible Campaign, open Reschedule, Tab to reason, do not confirm. Source global styles.css99–107 plus missing Campaign-local override. Evidence followup/results.json and referenced PNG/traces. Smallest proposed fix: separately authorize local Campaign focus token; no unrelated fix made.

Reader readiness reply is not actual utterance. Narrator launched, updates informational card closed without settings changes; Home app approval timed out and browser input geometry failed. No bypass. Actual new speech unavailable; all12remaining speech groups NOT_VERIFIED. Native zoom percentages unproven; all12Zgroups NOT_VERIFIED. Human guide is protocol, not executed speech. No repeated already-reported login speech request.

Carry forward unchanged: WP7A48prioritized entries, not every156route/operation. L17 offline narrowing had explicit owner approval; provider expiry remains UNVERIFIED. Historical Ads502 attribution unresolved (not the separately fixed R1anomaly500). PostgreSQL timestamp attribution unresolved; no inferred DB loss/restart actor. Financial Decimal/paise/allocation scope is not immutable accounting/tax/bank/settlement reconciliation. Historical schema three nullability mismatches and105unmatched index names(26left-prefix,79not proven equivalent) do not establish105slow queries. Historical lint/bundle debt retained, not blanket harmless. Real providers UNVERIFIED. PC-first encrypted independent backup/restore PARKED. R3 unintended Python WatchFiles reload history preserved; R4 preflight/midrun/final process checks do not rewrite it.

Legacy3169 occurrence keys (2774manual-required/395historical violations), hash a1806a88e138c032772d1c6abd5c24bcecd1bfe7eb4c6c5fa6720fb7aaee0a5a, remain occurrence evidence, not current unique defects. Transition frames/boundary/target exceptions need adjudication; no suppressed nodes/rules. No WP7C/WP8, live-provider, business DB, backup, branch/commit/push.
`);
await write('assessment',`# WP7B-R4 — assessment

**R4-A VERIFIED_PASS. Gate A inherited PASS. Gate B FAIL. Overall WP7B INCOMPLETE.** No full WCAG, launch or live-provider certification.

Login authored focus corrected locally from2.374231440911746:1 to8.559089262681107:1 against white (threshold3),40authfocus samples. Only production source change is one auth-local CSS token. No auth logic/global theme changes.

40original groups:9fully verified recorded contrast scopes;1verified failure(C11Campaignfocus);17partial;13without fresh execution. Machine outcomes9PASS/1FAIL/30NOT_VERIFIED/0N/A. Existing login speech retained;12remaining human speech groups,12native zoom groups, C09/C12–15 residual checks not fully closed. User readiness is not actual speech evidence; no invented transcript.

Executed68scoped browser interaction checksPASS with four retained primary harness context limitations covered by follow-up where applicable;1124element+56fragment records include4Campaign focusFAIL.40axe scans0violation/28incomplete rule occurrences. Angular auth22PASS, Node focused14PASS, production build/scoped ESLint/TS/Prettier PASS. Full historical suites inherited, not falsely counted as rerun. Initial failed formatting/matcher checks preserved then corrected.

Cleanup: **${cleanup.status}**; independent audit receipt tmp/qa-wp7br4/final-cleanup-audit.json. Session expiry ${session.expires_at}; no extension pending speech. Original API/container comparison in final receipt; pending is notPASS. ReaderHome approval limitation preserved; owner may exit Narrator manually. No business/golden access, live actions, unrelated Docker operations, branches/commits/pushes. Backup parked.

Eight deliverables: focus-remediation, isolated-session, accessibility-matrix, automated-results, human-review-guide, risk-update, assessment and gate JSON. Prior reports unchanged. Next bounded decision: authorize Campaign-only focus remediation separately, then remaining manual/native/contrast applicability verification under fresh explicit synthetic session approval if expired. Do not begin WP7C/WP8. Stop for review.
`);
if(session.ended_at){
 const guide=base+'wp7b-r4-human-review-guide.md';
 let text=await fs.readFile(guide,'utf8');
 if(!text.includes('SESSION CLOSED —'))text=text.replace(/^(# .*)\n/,'$1\n\n**SESSION CLOSED — historical URLs below are evidence only. Do not use them or substitute the normal business app. Fresh explicit isolated-session authorization is required for further review. Narrator may be exited manually.**\n');
 await fs.writeFile(guide,text);
}
console.log(JSON.stringify({groups:groups.length,counts,checks:checks.length,axe_scans:scans.length,cleanup:cleanup.status}));
