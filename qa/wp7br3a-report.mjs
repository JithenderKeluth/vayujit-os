// Read-only evidence reconciliation, with new documentation artifacts only.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
const base='docs/qa/seller-experience/',out='tmp/qa-wp7br3a/';
const read=async file=>JSON.parse(await fs.readFile(file,'utf8'));
const r2=await read(base+'wp7b-r2-gate.json'),r3=await read('tmp/qa-wp7br3/session-control.json');
const browser=await read(out+'browser-results.json'),login=await read(out+'login-retest.json'),extra=await read(out+'remaining-contrast.json'),focus=await read(out+'login-focus.json'),cleanup=await read(out+'cleanup-audit.json');
const now=new Date().toISOString();
const protectedReports={};
for(const name of await fs.readdir(base))if(/^wp7b(?:-|\.)/.test(name)&&!name.startsWith('wp7b-r3a-'))protectedReports[base+name]=crypto.createHash('sha256').update(await fs.readFile(base+name)).digest('hex');
await fs.writeFile(out+'preserved-report-hashes.json',JSON.stringify(protectedReports,null,2));
// Independent arithmetic, not imported from the rendering measurement implementation.
const lum=c=>c.slice(0,3).map(v=>v/255).map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4).reduce((a,v,i)=>a+v*[0.2126,0.7152,0.0722][i],0);
const ratio=(a,b)=>(Math.max(lum(a),lum(b))+0.05)/(Math.min(lum(a),lum(b))+0.05);
let comparisons=0,mismatches=0;const arithmeticSources=[];
for(const token of ['57e1c0c8d2d30df9','5bd3f03205fd40bd']){
 const file=`tmp/qa-seller-browser/${token}/wp7br1-browser.json`,bytes=await fs.readFile(file),v=JSON.parse(bytes);
 arithmeticSources.push({file,sha256:crypto.createHash('sha256').update(bytes).digest('hex')});
 for(const r of v.contrast)for(const m of [r,r.focus_indicator])if(Number.isFinite(m?.ratio)){
  comparisons++;if(Math.abs(ratio(m.effective_foreground,m.background)-m.ratio)>1e-10||(['PASS','FAIL'].includes(m.status)&&(ratio(m.effective_foreground,m.background)>=m.required)!==(m.status==='PASS')))mismatches++;
 }
}
assert.equal(comparisons,340);assert.equal(mismatches,0);
const arithmetic={timestamp:now,comparisons,mismatches,sources:arithmeticSources,scope:'Historical arithmetic/source-data verification only, not fresh rendered states'};
await fs.writeFile(out+'arithmetic.json',JSON.stringify(arithmetic,null,2));
const all=[...r2.screen_reader_checks,...r2.native_zoom_checks,...r2.contrast_review_groups];
const partial=new Set(['R2-SR-01','R2-SR-03','R2-SR-04','R2-SR-05','R2-SR-06','R2-SR-07','R2-SR-08','R2-SR-09','R2-C-01','R2-C-03','R2-C-04','R2-C-05','R2-C-06','R2-C-07','R2-C-12','R2-C-13','R2-C-14']);
const fully=new Set(['R2-C-02','R2-C-08']);
const details={
 'R2-SR-01':['Label/name, password type and show/hide pressed state; Tab/Shift+Tab between fields/toggle; capture focus and required-state applicability.','Existing reported login speech retained; do not repeat labels/toggle. Resolve remaining required-state applicability/build metadata; complete full keyboard-only login test separately.'],
 'R2-SR-02':['Skip-link destination, heading/landmark ordering, current navigation and actual keyboard sequence.','Listen once to navigation/headings/landmarks; no fresh observation obtained.'],
 'R2-SR-03':['Disclosure name/aria-expanded and native details state, Enter/Space, focus and draft persistence.','Hear only disclosure name/state before/after activation; keyboard segment automated in four contexts.'],
 'R2-SR-04':['Field names, required/help relationships, current invalid states and actual focus.','Hear goal label/help/required context; DOM alone is not speech.'],
 'R2-SR-05':['Legitimate invalid input, visible errors and their associations/invalid state, correction/focus recovery; no forced submission.','Already reported login errors/states retained. Remaining recovery and applicable goal-form feedback only; do not repeat verified login speech.'],
 'R2-SR-06':['Named imports group and individual accessible names/states; no import activation.','Hear group/control context once without executing import.'],
 'R2-SR-07':['Named editor group and panel buttons, local panel activation via keyboard.','Hear editor context and result of local panel change, not invented tab roles.'],
 'R2-SR-08':['Dialog accessible name, title focus entry and description relationships.','Hear actual dialog role/title/context once.'],
 'R2-SR-09':['Forward/reverse containment, Space Close, Escape, return focus and focused control identity.','Hear return-focus announcement; do not manually repeat already automated trap loops unless visually/audibly ambiguous.'],
 'R2-SR-10':['Live region semantics and actual state updates; supported bounded loading/error/recovery.','Hear relevant dynamic messages without forced focus; no mutation solely for speech.'],
 'R2-SR-11':['Review labels, prerequisite/disabled states and field associations without approval.','Hear HUMAN review prerequisites once; do not approve.'],
 'R2-SR-12':['Persisted synthetic goal/product/selection context and provenance labels, reload consistency.','Hear current research/selection/evidence context without discovery or selection.'],
 'R2-SR-13':['Actual table captions, th/scope/header relationships and list order.','Hear a representative caption/header/cell relationship with reader table navigation.'],
 'R2-C-01':['Expose exact Social textarea; solid-background/opacity/occlusion-aware text contrast.','Three of four text samples pass; Chrome390 remains NOT VERIFIED. Retry reliable rendered exposure before asking human.'],
 'R2-C-02':['Measure all exact .timeline strong targets, expose by scrolling and match screenshot/color state.','Four of four current targets PASS at 14.188746492925187:1; SC1.4.3, threshold4.5. No additional human judgment needed for this recorded solid-color text scope.'],
 'R2-C-03':['Measure Flipkart labels beyond old bound and index6 after stable rendering.','Remaining-measurement fixture currently renders seven labels, not prior eleven; absence of historical targets is not N/A. Mobile/exact legacy forms remain unclosed.'],
 'R2-C-04':['Measure remaining Flipkart buttons8/9, selected/focus state and essential indicators.','All eight remaining-button text samples PASS; focus/selected indicator coverage incomplete.'],
 'R2-C-05':['Measure Meesho buttons8/9 plus keyboard focus/selected indicator against true adjacent colors.','All ten buttons sampled in four contexts; text PASS does not establish inactive focus or all state indicators.'],
 'R2-C-06':['Expose exact mobile goal textarea/Meesho number input; text/focus/boundary measurements.','Goal help/textarea and Meesho forms partly measured; exact number input state and occluded samples remain.'],
 'R2-C-07':['Scroll both axes when necessary and measure actual captions after stable rendering.','Six desktop caption samples PASS; six mobile caption samples remain occluded/oversized and NOT VERIFIED. Retry automation before human interpretation.'],
 'R2-C-08':['Measure all21 financial headers per context, including thirteen beyond old bound.','84 of84 header text samples PASS across Chrome/Edge1440/390; SC1.4.3. No manual perception needed for this recorded solid-color text scope.'],
 'R2-C-09':['Measure actual Ads title/loading/error states; no artificial successful preview evidence.','Keyboard/semantics PASS is not fresh title/state contrast closure.'],
 'R2-C-10':['Use a legitimately eligible persisted Campaign reschedule state; measure actual textarea.','Existing draft checkpoint is ineligible. Needs authorized eligible fixture; no bypass or manufactured approval.'],
 'R2-C-11':['Keyboard-focus actual targets; measure active authored outlines against actual adjacent colors.','CONFIRMED FAIL: login password-toggle gold focus on white,2.374231440911746:1 versus3:1. Separate correction authorization required.'],
 'R2-C-12':['Identify which authored boundary/state is essential and measure relevant adjacent colors, not every decorative border.','Computed border data exists; essential-boundary applicability not fully adjudicated.'],
 'R2-C-13':['Capture aligned transition frames/computed values, hover/selected states; do not cancel transitions.','Settled-state sampling executed, not full180ms transition/hover adjudication.'],
 'R2-C-14':['Measure actual hit rectangles/spacing and justify only applicable inline/equivalent/UA/essential exceptions.','Login toggle height21.609375px observed; spacing/exception not adjudicated. Not automatically a target-size FAIL.'],
 'R2-C-15':['Reconcile original3169 stable observation keys by exact selector/state/cause/applicability.','Legacy record hashes/IDs retained; no complete cause-level closure or new unique-defect count claimed.'],
};
const groups=all.map(r=>{
 const d=details[r.id]||['Establish actual native browser zoom percentage using reliable native browser controls; measure CSS viewport/window, keyboard access, focus, clipping and reflow.','No native zoom executed during the remaining R3 lifetime. Responsive width is not zoom. Human visual confirmation only where objective evidence is insufficient.'];
 const status=fully.has(r.id)?'VERIFIED_PASS':r.id==='R2-C-11'?'VERIFIED_FAIL':'NOT_VERIFIED';
 const automated=browser.checks.filter(x=>x.review_id===r.id&&x.status==='VERIFIED_PASS');
 const refs=[r.acceptance_source,'docs/qa/seller-experience/wp7b-r2-gate.json'];
 if(automated.length)refs.push(out+'browser-results.json');if(r.id==='R2-SR-01')refs.push(out+'login-retest.json');
 if(/^R2-C-/.test(r.id))refs.push(out+'remaining-contrast.json',out+'browser-results.json');if(r.id==='R2-C-11')refs.push(out+'login-focus.json');
 return{...r,status,coverage:fully.has(r.id)?'FULL_RECORDED_GROUP':r.id==='R2-C-11'?'CONFIRMED_FAILURE':partial.has(r.id)?'PARTIAL':'NO_FRESH_EXECUTION',
  automatable_assertions:d[0],human_only_component:r.id.startsWith('R2-SR-')?r.id==='R2-SR-01'?'Provided historical login speech accepted; do not repeat without demonstrated evidence inadequacy':'Actual unverified speech only; do not repeat proven keyboard/semantics':'Only ambiguous perceptual/applicability portions after reliable measurement is exhausted',
  existing_evidence:r.id.startsWith('R2-SR-')?'R1 bounded keyboard/semantic evidence preserved; R2 speech NOT VERIFIED; supplied R3A human login summaries apply only to SR-01 and the reported part of SR-05':r.id.startsWith('R2-Z-')?'R1 native settings observed but complete post-fix interaction unverified; R2 no fresh native zoom':'R1 sampled rendered colors and R2 arithmetic/target reconciliation preserved; exact remaining target: '+(r.target||r.area),
  actual_result:d[1],required_for_closure:d[1],test_environment:{token:r3.session.token,origin:r3.session.origin,expired:true,fixture:'Existing R3 synthetic only',versions:browser.versions,viewport:[1440,390],native_zoom_verified:false},
  automated_assertion_records:automated,evidence:refs,assessment_timestamp:now};
});
assert.equal(groups.length,40);assert.equal(new Set(groups.map(r=>r.id)).size,40);
const observations={source:'User-supplied WP7B-R3A specification, section1; historical human reports, not new automated speech',exact_utterances_available:false,
 reports:['Login Email, Password and Show password correct names and roles on repeat','Show password state announced after both Space activations; focus remained','Empty login validation announced and visible; focus remained on submit','Email/password labels, invalid states and associated errors announced'],
 initial_unclear_observations:'Retained as historical unclear observations; verbatim initial utterances not supplied here; not invented or erased',
 limitation:'Reader/browser/build/time linkage not supplied for several utterances. Current captured build disables empty Sign in and does not demonstrate those individual validation-state associations. Preserve reported observations without attributing an unobserved current execution.'};
const finding={id:'WP7B-R3A-LOGIN-FOCUS-001',review_id:'R2-C-11',status:'VERIFIED_FAIL',severity:'P2',blocks_manual_accessibility_closure:true,route:'/login',
 expected:'Authored active focus indicator at least3:1 against actual adjacent white background (SC1.4.11).',actual:'Solid3px RGB224,154,54 outline on white;2.374231440911746:1, required3.',
 evidence:out+'login-focus.json',screenshot:focus.rows[0].screenshot,actual_timestamp:focus.timestamp,browser:focus.browser,
 source:'apps/web/src/styles.css:99-107 global focus rule; auth password-toggle has no scoped accessible override. R1 repaired other scopes, not this login target.',
 reproduction:'Synthetic /login: Tab to Show password; observe authored focus ring. No login submission needed.',
 impact:'Low-vision keyboard users may not distinguish the active control reliably.',
 suggested_fix:'Separately authorize a scoped light-auth focus rule using existing brand-strong token; preserve dark navigation and business authorities. Retest actual rendered focus contrast in both browsers.',code_changed:false,
 criterion_reference:'https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html'};
const allMeasurements=[...browser.contrast,...extra.rows,...focus.rows];
const collisions=Object.values(browser.contrast.reduce((a,r)=>{if(r.screenshot)(a[r.screenshot]??=[]).push(r);return a;},{})).filter(r=>r.length>1);
const gate={package:'WP7B-R3A',assessed_at:now,gate_A:{status:'PASS',inherited_from:base+'wp7b-r1-gate.json',rerun:false},gate_B:'INCOMPLETE',blocking_verified_failures:[finding.id],overall_WP7B:'INCOMPLETE',
 tools:{node:'24.19.0',playwright:'1.64.1',axe_core:'4.11.0',browser_versions:browser.versions,version_measurement:'Installed package versions read during R3A; browser versions returned by launched browsers'},
 focused_static_tests:{passed:14,failed:0,skipped:0,scope:'Existing seven R1 contrast/startup plus seven R3 guard/report self-tests; no manual accessibility closure',node_syntax_checks:4,diff_check:'PASS'},
 local_evidence_audit:await read(out+'evidence-audit.json').catch(()=>null),
 counts:{total_groups:40,VERIFIED_PASS:2,VERIFIED_FAIL:1,NOT_VERIFIED:37,NOT_APPLICABLE:0,fully_verified_automatically:2,partially_verified:17,without_fresh_execution:20,mandatory_speech_groups_with_missing_observations:12},groups,
 observations,findings:[finding],tests:{primary_browser:{total:28,passed:24,failed:4,failures_classification:'Changing-name locator harness error, preserved'},independent_login_retest:{total:4,passed:4,failed:0,scope:'Email/password/toggle keyboard segment, not full valid-login submission'},
 contrast:{records:allMeasurements.length,text_pass:allMeasurements.filter(r=>r.status==='PASS').length,text_not_verified:allMeasurements.filter(r=>r.status==='NOT VERIFIED').length,focus_fail:1,record_counts_are_not_unique_tests:true},
 axe:{scans:browser.scans.length,violation_rule_occurrences:browser.scans.reduce((n,s)=>n+s.violations.length,0),incomplete_rule_occurrences:browser.scans.reduce((n,s)=>n+s.incomplete.length,0)},historical_arithmetic:arithmetic},
 evidence_limitations:{primary_measurement_screenshot_collision_paths:collisions.length,primary_rows_at_colliding_paths:collisions.reduce((n,r)=>n+r.length,0),collision_rows_not_used_to_close_groups:true,
 primary_financial_target_detachment:'Four contexts ended with unstable transient target. Stable-state follow-up retained112 measurements, zero thrown limitations, but7 explicit NOT VERIFIED color samples.',
 narrow_main_contexts:'1440/390 responsive desktop contexts; main inherited helper did not set touch/mobile UA for R3A label. Login retest explicitly set isMobile/hasTouch at390.',
 keyboard_goal_Enter_precondition:'Goal-field check uses Enter only to open disclosure after prior keyboard-focused check; not claimed as a full page Tab-order audit.',
 no_native_zoom_or_new_speech:true},
 environment:{existing_R3_only:true,authorization_expired_at:r3.expires_at,new_database_lifecycle_operations:0,no_new_session_created:true,cleanup,
 existing_development_process_management:false,application_source_changes:false,normal_process_preservation:'No R3A stop/restart or Python file edits; R3 reload risk retained, not retroactively closed'},
 carry_forward:r2.carry_forward,prior_report_hash_manifest:out+'preserved-report-hashes.json',
 next_action:'Fresh explicit disposable QA lifecycle authorization needed before any additional live QA; separately authorize proposed auth focus correction if desired. No repeated login speech checklist.',
 live_provider_certification:false,backup_certification:'PARKED',WP7C_started:false,WP8_started:false};
await fs.writeFile(base+'wp7b-r3a-gate.json',JSON.stringify(gate,null,2)+'\n');
const table=groups.map(g=>`| ${g.id} | ${g.area} | ${Array.isArray(g.criteria)?g.criteria.join(', '):g.criteria} | ${g.existing_evidence} | ${g.automatable_assertions} | ${g.human_only_component} | ${g.status} (${g.coverage}) | ${g.required_for_closure} |`).join('\n');
await fs.writeFile(base+'wp7b-r3a-automation-matrix.md',`# WP7B-R3A — 40-group automation traceability

Assessed ${now}. All original IDs/criteria retained. Two groups close by objective rendered-text evidence; one has a confirmed focus defect. Other groups remain NOT_VERIFIED even where automated sub-assertions pass. PARTIAL is a coverage annotation, not an invented gate verdict. Existing R1/R2 scope is preserved, not rerun or downgraded.

Environment for fresh rows: existing marked R3 token dd240c756c70f504, Chrome156.0.8078.76 / Edge156.0.4314.58,1440×900 and390×900. Session is now expired/cleaned. Exact per-assertion expected/actual/tool/version/route/timestamp/screenshot/trace/command references are retained in [gate](wp7b-r3a-gate.json) and tmp/qa-wp7br3a. Prior evidence per row is linked through unchanged acceptance_source and R2 gate references. No permanent/golden data or live provider.

| Review ID | Requirement/workflow | Criterion | Existing evidence | Automatable assertions | Human-only portion | Current status | Evidence/closure requirement |
| --- | --- | --- | --- | --- | --- | --- | --- |
${table}

Full-group PASS sources: R2-C-02 uses remaining-contrast.json filtered route_key=social/original_selector=.timeline strong (4PASS,14.188746492925187:1). R2-C-08 uses route_key=finance/original_selector=main th (84PASS,21headers×4contexts). Both have unique aligned screenshots and sufficient solid-color rendered evidence. Missing fixtures/unstable/occluded targets are never N/A. No full-group speech PASS is inferred from semantics or keyboard events.
`);
await fs.writeFile(base+'wp7b-r3a-automated-results.md',`# WP7B-R3A — actual automated execution

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

\`\`\`powershell
node qa/wp7br3a-browser.mjs
node qa/wp7br3a-login.mjs
node qa/wp7br3a-remaining.mjs
node qa/wp7br3a-report.mjs
\`\`\`

These scripts do not create/extend a database, change approvals, execute imports or perform provider actions. The report command is offline; the other three require a fresh valid existing-session receipt and exact witness. Login-focus.json was produced by the retained inline procedure: existing-token witness; new owned Chrome context; GET/login; Tab to button[aria-pressed]; existing measureTargets; owned context close. Password-bearing API login requests were outside retained tracing. No private credentials, raw stderr or business customer data are printed.

Screenshot/trace references are per assertion in browser-results.json/login-retest.json/remaining-contrast.json/login-focus.json, under tmp/qa-wp7br3a. R1 results52/32, Angular442, Node138, Python163, backend36 are inherited, not fresh R3A executions. No unrelated full regression suite or application build was rerun; there are no application source changes.
`);
await fs.writeFile(base+'wp7b-r3a-human-minimal-checklist.md',`# WP7B-R3A — minimal remaining human review

**Do not test now: the isolated session expired and its database is independently absent. No current QA URL exists.** Historical http://127.0.0.1:55226 is evidence only, not a valid test target. Fresh lifecycle authorization is required before creating another synthetic session. Never substitute the ordinary app or real credentials.

Keep the four user-reported login observations and initial unclear history. Do not repeat correct Email/Password/Show names, show/hide state speech or already reported validation/error announcements. Exact utterances not captured remain unspecified. Full keyboard-only login check5 was not completed; its automatable portions are not assigned as human labor.

After a newly approved session is ready, insert its exact origin/fixture links into this checklist. Run automation first for remaining field states, stable mobile exposure, financial captions, eligible Campaign fixture, contrast/focus/target applicability and native zoom where reliable. Only unresolved perception/actual speech then needs a person. No long one-message-per-control chat loop.

## Session1 — grouped Narrator observations

| IDs | Navigation/actions | Listen for only the unverified component |
| --- | --- | --- |
| SR-02–05,SR-10 | New QA /intelligence/business-agent; skip/main/headings; disclosure Enter/Space; focus goal/help; legitimate existing invalid/recovery state without saving valid goal | Navigation/context; expanded/collapsed; required/help; remaining correction/status feedback. Do not repeat previously reported login validation speech |
| SR-06–07 | New QA /marketplaces/accounts, then exact new Meesho draft link supplied by session | Import group/control context by focus only (no import), editor group/panel context |
| SR-08–09 | New QA /ads/recommendations; read-only Preview, then Close/Escape | Dialog title/role/context and returned-focus speech; automated trap tests need not be repeated manually |
| SR-11–13 | Exact new synthetic opportunity/review page and /marketplaces/financials | Approval prerequisites without approving, current goal/product/unknown/synthetic evidence and representative table caption/header/cell relationship |

12 speech groups retain missing mandatory components; this is not12 separate chat handoffs. For each grouped row reply **PASS / FAIL / UNCLEAR**, with optional actual words and any confusing/silent part. Record browser/reader versions, language/verbosity and date once for the whole session. DOM/axe is not speech. The supplied historic login summaries have no exact words for several actions; do not invent transcripts.

## Session2 — only irreducible visual review

First establish native100/200/400% using reliable browser-native evidence, not CSS scaling or viewport emulation. Where automation cannot prove percentage or judge content, ask the human once to show the browser Zoom menu and inspect Goals, Marketplace imports, Meesho and Ads dialog at those settings (Z-01–12). Capture full-window percentage, CSS viewport/window metrics, meaningful clipping/reflow, keyboard/focus and form/modal usability; starting content1280CSS pixels corresponds to320 at400%. Reset to100%. Never execute imports, approvals or publishing.

For C-01/C-07 mobile occlusion or C-12–15 ambiguous backgrounds/essential indicators/target exceptions, exhaust safe scrolling/focus/objective measurement first. Ask for human perception only for identified unresolved states, not all historical occurrence keys. No universal border3:1 or AAA focus requirement is introduced. Confirmed login focus contrast already fails objectively; no human vote is needed to establish its arithmetic.

This checklist is a protocol, not executed evidence. Do not use retired fixture UUIDs or assume future authorization from these instructions.
`);
await fs.writeFile(base+'wp7b-r3a-risk-update.md',`# WP7B-R3A — residual risks and new confirmed finding

**${finding.id}: VERIFIED FAIL, P2, R2-C-11, /login.** Tab to Show password on the synthetic login. Authored solid3px outline RGB224,154,54 on verified white measures2.374231440911746:1 (required3). Text itself passes; this is a focus-state contrast issue, not a keyboard trap. Low-vision users may not distinguish focus. Source: global focus rule styles.css99–107 and lack of scoped auth override. Existing R1 goal/Ads/Marketplace repairs remain valid and are not reopened. Actual measurements/screenshot: tmp/qa-wp7br3a/login-focus.json. [W3C non-text contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) supports the applicable threshold for authored active focus states. No AAA focus-area requirement is imposed.

Smallest proposed correction: separately authorize a scoped light-auth focus rule using the existing brand-strong color, preserving dark navigation. Then run actual focused-state measurements in Chrome/Edge. No source fix has been made or authorized by R3A.

Preserve R1 GateA PASS; no overall accessibility PASS. Human login observations are historical user reports from the new specification, not invented transcripts or fresh robot speech. Current source disables invalid Sign in and does not expose per-field error associations in the captured login snapshot; historical empty-submit/error announcements lack build/time linkage. Preserve both facts without declaring the human wrong or manufacturing a current successful validation test. This provenance/coverage gap needs a current legitimate contract test in a newly approved session, not repeated verified label speech.

Environmental boundary: existing R3 expired10:18:54AM IST; signed cleanup completed, independent absence PASS. No new lifecycle or development process management occurred. Avoided new Python files/edits that could trigger normal API WatchFiles; only QA .mjs/reports changed. R3's earlier unintended reload remains recorded, not retroactively waived by the owner's separate process changes. No permanent/golden row-level preservation claim for historical startup activity.

Other retained risks: WP7A48 prioritized local entries are not every route/operation; L-17 explicitly narrowed offline acceptance with actual owner approval, provider expiry UNVERIFIED. Historical Ads502 attribution and PostgreSQL timestamp attribution unresolved. Financial precision/projections are not immutable accounting or tax/bank/settlement reconciliation. Static/schema/index/bundle debt remains scoped. Live provider connectivity unsupported. Independent PC-first encrypted backup/restore remains PARKED. Legacy3169 keys are observation occurrences, not unique fresh defects; full cause/applicability reconciliation remains open. No WP7C/WP8/branches/commits/pushes.
`);
await fs.writeFile(base+'wp7b-r3a-assessment.md',`# WP7B-R3A — automation-first assessment

Assessed ${now}. **GateA inherited PASS; GateB INCOMPLETE with one confirmed blocking contrast failure; overall WP7B INCOMPLETE.** No WCAG conformance or launch approval.

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
`);
console.log(JSON.stringify({reports:6,groups:40,fully_automated:2,verified_failure:1,partial:17,unexecuted:20,historical_comparisons:comparisons,mismatches}));
