// Additive registration: preserve all previous ledgers and approved recovery evidence.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import { ids, assertions } from './wp7a6-contract.mjs';
const root = 'docs/qa/seller-experience/';
const prior = JSON.parse(await fs.readFile(root + 'wp7a6-coverage-ledger.json', 'utf8'));
const decision = JSON.parse(await fs.readFile(root + 'wp7a-remaining-seven-decision.json', 'utf8'));
if (prior.entries.length !== 48 || prior.entries.filter(e => e.inherited_closed).length !== 41 || decision.entries.length !== 7) throw Error('ORIGINAL_SCOPE_REQUIRED');
const ledger = { package: 'WP7A-7', original_denominator: 48, inherited_closed: 41,
  targeted: 7, status: 'INCOMPLETE', ads_clarification: { approved: true,
    owner_reply: 'Approve this explicit scope clarification',
    original_acceptance: decision.entries.find(e => e.id === 'L-17').original_acceptance,
    scope: 'Offline application certification verifies authorization states represented by the current supported contract. Provider token expiry is not certified where no authoritative expiry state or contract exists. Live-provider expiry behavior remains unverified and must not be represented as passing.' },
  entries: prior.entries.map(e => ({ ...e, history_source: root + 'wp7a6-coverage-ledger.json',
    acceptance: decision.entries.find(d => d.id === e.id)?.original_acceptance || e.acceptance,
    original_closure: decision.entries.find(d => d.id === e.id)?.original_closure,
    wp7a7_target: ids.includes(e.id), required_assertions: assertions[e.id] || [],
    status: e.inherited_closed ? 'PASS' : 'PARTIAL', full_closure: e.inherited_closed,
    attempts: [], evidence: [], acceptance_review: {complete: e.inherited_closed} })) };
await fs.mkdir('tmp/qa-wp7a7', {recursive: true});
const historical = (await fs.readdir(root)).filter(n => /^wp7a[2-6]?-|^wp7-journey-coverage-matrix|^wp7a-remaining-seven/.test(n));
const files = [...historical.map(n => root+n), 'tmp/qa-wp7a6/recovery-0e63cd34fede26e1.json', 'tmp/qa-wp7a6-final-audit.json', 'tmp/qa-wp7a6/before-approved-recovery-20261104T015051Z/manifest.json'];
const baseline = {files: await Promise.all(files.map(async file => ({file, sha256:crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')})))};
for (const [file, value] of [['tmp/qa-wp7a7/baseline.json', baseline], [root+'wp7a7-coverage-ledger.json', ledger]]) {
  try { await fs.writeFile(file, JSON.stringify(value,null,2), {flag:'wx'}); }
  catch(e) { if(e.code !== 'EEXIST') throw e; }
}
console.log(JSON.stringify({original:48,inherited_closed:41,targeted:ids,ads_scope_approved:true,historical_files:files.length}));
