// Explicit run selection only; never infer precedence from file modification time.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import { gate, contexts, assertions } from './wp7a7-contract.mjs';
const [browserToken, backendToken] = process.argv.slice(2);
if (![browserToken, backendToken].every(t => /^[a-f0-9]{16}$/.test(t || ''))) throw Error('EXACT_RUNS_REQUIRED');
const root='docs/qa/seller-experience/';
const read=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const ledger=await read(root+'wp7a7-coverage-ledger.json');
const browserRoot='tmp/qa-seller-browser/'+browserToken;
const browser=await read(browserRoot+'/wp7a7-browser.json');
const backendRoot='tmp/qa-wp7a7-backend/'+backendToken;
const runner=await read(backendRoot+'/runner.json');
const xml=await fs.readFile(backendRoot+'/backend-results.xml','utf8');
const suite=/<testsuite\s[^>]+>/.exec(xml)?.[0] || '';
const backend={token:backendToken,...Object.fromEntries(['tests','failures','errors','skipped'].map(k=>[k,Number(new RegExp(k+'="(\\d+)"').exec(suite)?.[1] ?? NaN)]))};
const hashes=await read(backendRoot+'/tested-source-sha256.json');
let sourceMatches=true;
for(const [file,hash] of Object.entries(hashes)) {
 const current=crypto.createHash('sha256').update(await fs.readFile(file.replaceAll('\\','/'))).digest('hex');
 if(current.toLowerCase()!==hash.toLowerCase()) sourceMatches=false;
}
backend.complete=runner.exit_code===0 && runner.source_unchanged===true && sourceMatches;
backend.current_source_matches=sourceMatches;
const quality=await read('tmp/qa-wp7a7/quality.json');
const audit=await read('tmp/qa-wp7a7-final-audit.json');
for(const e of ledger.entries.filter(e=>e.wp7a7_target)) {
 const latest=contexts.map(c=>e.attempts.findLast(a=>a.context===c));
 const assertionsPass=latest.every(a=>a?.token===browserToken && a.status==='PASS' && a.persisted_state_verified===true && assertions[e.id].every(k=>a.acceptance_assertions?.includes(k)));
 let artifacts=assertionsPass;
 for(const a of latest.filter(Boolean)) for(const file of [a.screenshot,a.trace]) {
  try { if(!file || !(await fs.stat(file)).size) artifacts=false; } catch { artifacts=false; }
 }
 e.acceptance_review={complete:assertionsPass && browser.source_unchanged===true, selected_run:browserToken, original_assertions_preserved:true};
 e.evidence_integrity=artifacts && browser.source_unchanged===true && audit.extended_secret_scan?.matches===0;
 e.full_closure=e.acceptance_review.complete && e.evidence_integrity;
 e.status=e.full_closure?'PASS':'PARTIAL';
}
const blockers=[];
if(browser.source_unchanged!==true) blockers.push('Final browser source was not unchanged');
if(browser.checks.length!==28 || browser.contexts.length!==4) blockers.push('Final selected browser matrix incomplete');
const result=gate({...ledger,audit,quality,backend,blockers});
result.browser_run=browserToken; result.backend=backend;
result.browser_counts=Object.fromEntries(['PASS','FAIL','PARTIAL','BLOCKED'].map(k=>[k,browser.checks.filter(c=>c.status===k).length]));
result.quality_checks=quality.checks;
result.audit='tmp/qa-wp7a7-final-audit.json';
ledger.status=result.status;
ledger.closed=result.closed; ledger.remaining=result.remaining;
await fs.writeFile(root+'wp7a7-coverage-ledger.json',JSON.stringify(ledger,null,2));
await fs.writeFile(root+'wp7a7-gate.json',JSON.stringify(result,null,2));
console.log(JSON.stringify({status:result.status,closed:result.closed,remaining:result.remaining,backend,browser:result.browser_counts,cleanup:result.cleanup,regressions:result.regressions}));
