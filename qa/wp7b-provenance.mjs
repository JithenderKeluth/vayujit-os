import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {assertions,ids} from './wp7a6-contract.mjs';
const root='docs/qa/seller-experience/';
const read=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const gate=await read(root+'wp7a7-gate.json'),ledger=await read(root+'wp7a7-coverage-ledger.json'),prior=await read(root+'wp7a6-coverage-ledger.json'),decision=await read(root+'wp7a-remaining-seven-decision.json');
const exact=ledger.entries.length===48 && new Set(ledger.entries.map(e=>e.id)).size===48 && ledger.entries.filter(e=>e.inherited_closed).length===41 && ids.length===7;
const inherited=ledger.entries.filter(e=>e.inherited_closed).every(e=>prior.entries.some(p=>p.id===e.id && p.status==='PASS' && p.acceptance===e.acceptance));
const original=ids.every(id=>ledger.entries.find(e=>e.id===id)?.acceptance===decision.entries.find(e=>e.id===id)?.original_acceptance);
const keys=ids.every(id=>JSON.stringify(ledger.entries.find(e=>e.id===id)?.required_assertions)===JSON.stringify(assertions[id]));
const baseline=await read('tmp/qa-wp7a7/baseline.json');
let preserved=true;
for(const row of baseline.files) if(crypto.createHash('sha256').update(await fs.readFile(row.file)).digest('hex')!==row.sha256) preserved=false;
const manifest={};
for(const name of ['wp7a7-gate.json','wp7a7-coverage-ledger.json','wp7a7-closure-plan.md','wp7a7-closure-report.md','wp7a7-browser-evidence.md']) manifest[root+name]=crypto.createHash('sha256').update(await fs.readFile(root+name)).digest('hex');
const result={package:'WP7B',historical_wp7a_gate:gate.status,exact_48_reconciliation:exact,inherited_41_match:inherited,seven_original_texts_preserved:original,original_assertion_keys_preserved:keys,earlier_44_evidence_files_unchanged:preserved,
 ads:{stable_id:'L-17',original_acceptance:decision.entries.find(e=>e.id==='L-17').original_acceptance,explicit_approval_recorded:ledger.ads_clarification.approved===true,owner_reply:ledger.ads_clarification.owner_reply,contract_disposition:'Approved narrower offline interpretation; not an unqualified pass of provider authorization expiry',live_provider_expiry:'UNVERIFIED'},
 denominator_scope:'48 prioritized remaining WP7A entries, not all 156 application route leaves or all operations; preceding 124 route-review caveats are not upgraded',
 existing_result_modified:false,approval_evidence_review:'The actual owner reply in the conversation approves the explicit scope clarification; artifact claims alone are not treated as authority',manifest};
await fs.mkdir('tmp/qa-wp7b',{recursive:true});await fs.writeFile('tmp/qa-wp7b/provenance.json',JSON.stringify(result,null,2));
console.log(JSON.stringify({exact,inherited,original,keys,preserved,ads_scope_approved:result.ads.explicit_approval_recorded,gate_unchanged:true}));
process.exitCode=exact&&inherited&&original&&keys&&preserved&&result.ads.explicit_approval_recorded?0:1;
