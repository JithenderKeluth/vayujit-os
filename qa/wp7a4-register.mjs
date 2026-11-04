import fs from 'node:fs/promises';
import crypto from 'node:crypto';
const dir='docs/qa/seller-experience/';
const source=JSON.parse(await fs.readFile(dir+'wp7a3-required-coverage.json','utf8'));
const pending=source.entries.filter(e=>!e.full_closure);
const previous=JSON.parse(await fs.readFile(dir+'wp7a3-gate.json','utf8'));
if(pending.length!==48||new Set(pending.map(e=>e.id)).size!==48||pending.some(e=>!previous.open_entries.includes(e.id))) throw Error('WP7A4_SCOPE_RECONCILIATION_REQUIRED');
await fs.mkdir('tmp/qa-wp7a4',{recursive:true});
const names=['wp7-certification-report.md','wp7-journey-coverage-matrix.md','wp7-defect-register.md',
 'wp7-journey-coverage-matrix-wp7a-addendum.md','wp7-journey-coverage-matrix-wp7a2-addendum.md',
 'wp7-journey-coverage-matrix-wp7a3-addendum.md','wp7a3-required-coverage.json','wp7a3-gate.json','wp7a3-defect-resolution.md'];
const hashes=[];for(const name of names)hashes.push({file:dir+name,sha256:crypto.createHash('sha256').update(await fs.readFile(dir+name)).digest('hex')});
await fs.writeFile('tmp/qa-wp7a4/baseline.json',JSON.stringify({files:hashes},null,2),{flag:'wx'}).catch(e=>{if(e.code!=='EEXIST')throw e});
const group=e=> /publishing|workers|workflows|approvals/.test(e.route)?'publishing-runtime':/marketplaces/.test(e.route)?'marketplaces':/supplier|trends/.test(e.route)?'research':/campaign|ads|social/.test(e.route)?'campaigns-social-ads':/video/.test(e.route)?'video':/images|media/.test(e.route)?'images-media':/^L-/.test(e.id)||/ai\//.test(e.route)?'content-ai':'authentication-navigation';
const ledger={package:'WP7A-4',source:dir+'wp7a3-required-coverage.json',status:'RUNNING',required:48,
 counting:'Exactly the 48 original outstanding IDs. Partial evidence is not PASS; original L-11 is not retested or counted as a new closure.',
 entries:pending.map(e=>({...e,prior_status:e.status,status:e.status==='PARTIAL'?'PARTIAL':'NOT_TESTED',group:group(e),
  required_behavior:e.capability,missing_acceptance_evidence:e.remaining,browser_requirements:'Authenticated Chrome and Edge desktop/mobile actions, negative/recovery, reload, screenshot/trace; not rendering alone.',
  api_database_requirements:'Canonical owned IDs, persistence, replay/version/approval/provenance assertions where applicable; no invented evidence.',
  fixture_requirements:e.dependencies,risk:/publishing|marketplace|approval|ads|economic/.test(e.route)?'HIGH':'MEDIUM',
  execution_complexity:/publishing|portfolio|social|video/.test(e.route)?'HIGH':'MEDIUM',evidence:[],attempts:[],final_disposition:'PENDING_EXECUTION'})),
 checkpoint:{safe_resume:'Use only a new signed QA run; never reuse an absent database or delete another run. Retained observations are immutable attempts; repeat affected IDs only.',completed_ids:[],remaining_ids:pending.map(e=>e.id)}};
await fs.writeFile(dir+'wp7a4-coverage-ledger.json',JSON.stringify(ledger,null,2),{flag:'wx'}).catch(e=>{if(e.code!=='EEXIST')throw e});
console.log(JSON.stringify({required:pending.length,groups:[...new Set(ledger.entries.map(e=>e.group))],prior_partial:pending.filter(e=>e.status==='PARTIAL').length}));
