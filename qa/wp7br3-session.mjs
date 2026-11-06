// R3 verification only. Existing R1 runtime/policy is an implementation engine,
// NOT authorization: authority is the new exact R3 specification below.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawn, spawnSync } from 'node:child_process';
import { chromium, expect } from '@playwright/test';
import { start, capture, finish } from './seller-browser-explore.mjs';
import { sourceFingerprint } from './wp7a7-source.mjs';
import { wp3Owner, wp3Product } from './wp3-fixtures.mjs';
import { wp5Operations } from './wp5-fixtures.mjs';
import { prepareReviews } from './wp7br1-review-fixtures.mjs';
import { prepareReadOnlyRecommendation } from './wp7b-domain-fixture.mjs';

const root = path.resolve('tmp/qa-wp7br3');
await fs.mkdir(root, { recursive: true });
const reportPath = path.join(root, 'session-control.json');
try { await fs.access(reportPath); throw Error('R3_EXISTING_RECORD_REVIEW_REQUIRED'); }
catch (e) { if (e.code !== 'ENOENT') throw e; }
if (!process.env.QA_DATABASE_ADMIN_URL || !process.env.QA_POSTGRES_INSTANCE_MANIFEST)
  throw Error('R3_SIGNED_QA_REQUIRED');
const spec = 'C:/Users/jithe/.codex/attachments/814004cb-1834-4490-ab39-3820aa5bdb9f/Pasted text.txt';
const specBytes = await fs.readFile(spec);
if (!specBytes.toString('utf8').includes('APPROVED') || !specBytes.toString('utf8').includes('WP7B-R3'))
  throw Error('EXACT_R3_AUTHORITY_REQUIRED');
const before = await sourceFingerprint();
const prior = {};
for (const entry of await fs.readdir('docs/qa/seller-experience')) {
  if (/^wp7b(?:-r[12])?-/.test(entry)) {
    const file = 'docs/qa/seller-experience/' + entry;
    prior[file] = crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex');
  }
}
// Read-only attestation also records existing listeners, never their arguments/env.
const preflightCode = String.raw`
import json, subprocess
from qa.postgres_instance import QaInstance
i=QaInstance(); i.verify_server()
ps="Get-NetTCPConnection -State Listen | Where-Object {$_.LocalPort -in @(4200,8000)} | ForEach-Object {$p=Get-Process -Id $_.OwningProcess; [pscustomobject]@{port=$_.LocalPort;address=$_.LocalAddress;pid=$p.Id;start=$p.StartTime.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress"
r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',ps],capture_output=True,text=True,timeout=30,check=True)
containers=[]
for cid in i.docker('ps','-aq','--no-trunc').splitlines():
 c=json.loads(i.docker('inspect',cid))[0]
 containers.append({'id':c['Id'],'name':c['Name'],'image':c['Image'],'status':c['State']['Status'],'started':c['State']['StartedAt'],'finished':c['State']['FinishedAt'],'mounts':[{k:m.get(k) for k in ('Type','Name','Destination','RW')} for m in c['Mounts']],'networks':list(c['NetworkSettings']['Networks'])})
print(json.dumps({'container_id':i.manifest['container_id'],'instance_id':i.manifest['instance_id'],'endpoint':'127.0.0.1:55432','role':'vayujit_qa_admin','signed_guard_verified':True,'development_listeners':json.loads(r.stdout or '[]'),'containers':containers}))
`;
const pre = spawnSync(process.env.QA_PYTHON, ['-c', preflightCode], { windowsHide: true, encoding: 'utf8', timeout: 60000 });
if (pre.status !== 0) throw Error('R3_PREFLIGHT_DENIED');
const record = { package: 'WP7B-R3', status: 'STARTING', created_at: new Date().toISOString(),
  authority_sha256: crypto.createHash('sha256').update(specBytes).digest('hex'),
  scope: 'Fresh R3-owned synthetic databases only; no normal-app interruption or source changes',
  preflight: JSON.parse(pre.stdout.trim()), source_before: before, preserved_reports: prior,
  raw_output_persisted: false, human_observations: [], manual_groups_passed: 0,
  compatibility_engine: 'WP7BR1 runtime/startup and WP7A7 fixture policy reused; no old approval consumed' };
const save = () => fs.writeFile(reportPath, JSON.stringify(record, null, 2));
await save();
// Required dedicated role+manifest is independently checked again inside fixture_server.
const runtime = spawn(process.execPath, ['qa/seller-browser-session.mjs'], {
  env: { ...process.env, QA_PHASE: '2', QA_MIGRATE: '1', QA_BROWSER_PHASE: 'WP7A7',
    QA_WORK_PACKAGE: 'WP7BR1', QA_DATABASE_DROP_TIMEOUT_MS: '90000' },
  stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true,
});
record.runtime_pid = runtime.pid;
await save();
let s, buffer = '', exited = false, browser, run;
runtime.stdout.on('data', d => {
  buffer += d;
  const lines = buffer.split(/\r?\n/); buffer = lines.pop();
  for (const line of lines) { try { const v = JSON.parse(line); if (v.status === 'READY' && v.synthetic) s = v; } catch {} }
});
runtime.stderr.on('data', () => {}); // Never persist subprocess output.
runtime.on('error', () => { exited = true; });
const done = new Promise(resolve => runtime.on('exit', code => { exited = true; resolve(code); }));
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
try {
  for (let n = 0; n < 900 && !s && !exited; n++) await delay(400);
  if (!s) throw Error('R3_RUNTIME_NOT_READY');
  if (!/^vayujit_qa[a-f0-9]{16}_test$/.test(s.database_scope) || s.database_scope !== `vayujit_qa${s.token}_test`)
    throw Error('R3_DATABASE_SCOPE_DENIED');
  record.session = s;
  const witness = await fetch(s.origin + '/__qa/witness').then(r => r.json());
  if (!witness.disposable || witness.token !== s.token) throw Error('R3_WITNESS_DENIED');
  await fs.writeFile(path.join(s.folder, 'wp7br3-run.json'), JSON.stringify({ package: 'WP7B-R3', token: s.token, synthetic: true, authority_sha256: record.authority_sha256 }));
  browser = await chromium.launch({ channel: 'chrome', headless: false, args: ['--window-position=80,50','--window-size=1300,900'] });
  record.browser = { name: 'Chrome', version: browser.version(), pid_scope: 'Owned Playwright browser only' };
  // Existing default-deny browser policy and trace implementation, no business session.
  run = await start(browser, s, null, 'wp7br1-r3-manual');
  // Fixture authentication must not persist password-bearing network requests.
  await run.context.tracing.stop();
  const p = run.page; p.setDefaultTimeout(15000);
  // Canonical synthetic authentication. No password/storageState in any report.
  const owner = await p.request.post(s.origin + '/api/v1/auth/setup-owner', { data: {
    full_name: '[QA SYNTHETIC] R3 Owner', email: wp3Owner.email,
    password: wp3Owner.password, password_confirmation: wp3Owner.password,
  }});
  if (owner.status() !== 201) throw Error('R3_CANONICAL_OWNER_FAILED');
  await p.goto(s.origin + '/intelligence/business-agent');
  await expect(p.locator('h1')).toBeVisible();
  const f = await wp3Product(p, s.origin), { api, brand, op, assessment } = f;
  await api('post', 'brands/' + brand.id + '/activate', {});
  f.ops = await wp5Operations(api, brand);
  const generation = await api('post', 'ai/generations', {product_id:f.ops.product.id, provider_key:'deterministic_mock_v1', additional_instructions:'[QA SYNTHETIC] WP7A4 R3 accessibility only'});
  f.artifact = await api('get', 'ai/artifacts/' + generation.artifact_id);
  await api('post', 'ai/artifacts/' + f.artifact.id + '/approve', {});
  const account = await api('post','marketplaces/accounts',{marketplace:'meesho',environment:'sandbox',display_name:'[QA SYNTHETIC] WP7A4 R3',seller_account_id:'qa3-r3-meesho',credentials:{}});
  f.meesho = await api('post','marketplaces/meesho/listings',{account_id:account.id,brand_id:brand.id,product_id:f.ops.product.id,artifact_id:f.artifact.id,title:'[QA SYNTHETIC] QA7 R3',category:'Kids',marketplace_sku:'QA7-R3',idempotency_key:'wp7b-r3-meesho'});
  const adAccount = await api('post','ads/accounts',{provider:'meta',environment:'local',display_name:'[QA SYNTHETIC] WP7A2 R3',external_account_id:'qa-wp7a2-r3',credentials:{token:'QA-SYNTHETIC-NOT-A-REAL-CREDENTIAL'}});
  await api('post',`ads/accounts/${adAccount.id}/validate`,{}); await api('post',`ads/accounts/${adAccount.id}/enable`,{});
  // Reused domain helper checks this exact synthetic prefix and local/unpublished authority.
  const campaign = {provider:'meta',account_id:adAccount.id,product_id:f.ops.product.id,name:'[QA SYNTHETIC] WP7A2 WP7B R3',objective:'awareness',budget:{daily_amount:'100',currency:'INR'},idempotency_key:'wp7b-r3-ad'};
  const preview = await api('post','ads/campaigns/preview',campaign);
  f.adCampaign = (await api('post','ads/campaigns/confirm',{campaign,preview_fingerprint:preview.fingerprint,confirm:true,idempotency_key:'wp7b-r3-ad-confirm'})).campaign;
  f.recommendation = prepareReadOnlyRecommendation(s.token,f.adCampaign.id);
  f.reviews = await prepareReviews(run,s,f);
  record.fixture_ids = { goal:f.goal.id, opportunity:op.id, assessment:assessment.id, product:f.ops.product.id, meesho:f.meesho.id, flipkart:f.reviews.flip.id, social:f.reviews.social.id, campaign:f.reviews.campaign.id };
  record.routes = { login:'/login', goals:'/intelligence/business-agent', accounts:'/marketplaces/accounts',
    meesho:`/marketplaces/listings/${f.meesho.id}/meesho`, ads:'/ads/recommendations',
    social:`/social/posts/${f.reviews.social.id}`, flipkart:`/marketplaces/listings/${f.reviews.flip.id}/flipkart`,
    finance:'/marketplaces/financials', opportunity:`/intelligence/product-opportunities/${op.id}` };
  // Retain cookie in process memory only for later permitted route restoration.
  const storage = await run.context.storageState();
  await run.context.clearCookies();
  await run.context.tracing.start({screenshots:true,snapshots:true,sources:false});
  await p.goto(s.origin + '/login'); await expect(p.locator('#email')).toBeVisible();
  await p.evaluate(token => document.title = 'WP7BR3 SYNTHETIC ' + token, s.token);
  record.checkpoint_screenshot = (await capture(run,'R2-SR-01-awaiting-human')).screenshot;
  record.status = 'AWAITING_HUMAN_OBSERVATION';
  record.checkpoint = 'R2-SR-01: empty sign-in controls; actual Narrator utterances required';
  record.ready_at = new Date().toISOString();
  record.expires_at = new Date(Date.now() + 30*60*1000).toISOString();
  record.command_path = path.join(root,'manual-requests.json');
  await save();
  console.log(JSON.stringify({status:record.status, token:s.token, origin:s.origin, expires_at:record.expires_at}));
  const handled = new Set();
  while (Date.now() < Date.parse(record.expires_at) && !exited && browser.isConnected()) {
    const commands = await fs.readFile(record.command_path,'utf8').then(JSON.parse).catch(()=>[]);
    let stop = false;
    for (const c of commands) {
      if (!Number.isInteger(c.id) || handled.has(c.id)) continue; handled.add(c.id);
      if (c.action === 'done') { stop = true; break; }
      if (c.action === 'navigate' && Object.hasOwn(record.routes,c.route)) {
        await run.context.clearCookies();
        if (c.route !== 'login') await run.context.addCookies(storage.cookies);
        await p.goto(s.origin + record.routes[c.route]);
        await expect(p.locator('h1')).toBeVisible();
        await p.evaluate(token => document.title='WP7BR3 SYNTHETIC '+token,s.token);
      } else if (c.action !== 'capture') throw Error('R3_MANUAL_ACTION_DENIED');
      record.last_capture = (await capture(run,'r3-manual-'+c.id)).screenshot;
      record.last_capture_at = new Date().toISOString(); await save();
    }
    if (stop) break;
    await delay(500);
  }
} catch (error) {
  record.status = 'BLOCKED';
  record.safe_failure = /^R3_[A-Z_]+$/.test(error.message) ? error.message : 'R3_SESSION_PREPARATION_FAILED';
  if (/^WP3_FIXTURE_[0-9]{3}_[a-z-]+$/.test(error.message)) record.fixture_failure_code = error.message;
  // Safe class + repository source location only, never raw message/stack/arguments.
  record.failure_type = ['Error','TypeError','TimeoutError'].includes(error.name) ? error.name : 'Unclassified';
  record.failure_line = error.stack?.match(/wp7br3-session\.mjs:(\d+)/)?.[1] || null;
} finally {
  if (run) { try { record.trace = await finish(run); } catch { record.browser_cleanup = 'EVIDENCE_CLOSE_FAILED'; } }
  if (browser) await browser.close().catch(()=>{record.browser_cleanup='OWNED_BROWSER_CLOSE_FAILED';});
  if (s) await fs.writeFile(path.join(s.folder,'stop.request'),'WP7B-R3 bounded session complete');
  else runtime.stdin.end();
  record.runtime_exit = await done;
  if (s) record.cleanup = await fs.readFile(path.join(s.folder,'session-final.json'),'utf8').then(JSON.parse).catch(()=>null);
  record.session_ended_at = new Date().toISOString();
  const after = await sourceFingerprint();
  record.existing_source_unchanged = Object.keys(before).every(k=>before[k]===after[k]);
  record.original_reports_unchanged = true;
  for(const [file,hash] of Object.entries(prior)) if(crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')!==hash) record.original_reports_unchanged=false;
  if(record.status==='AWAITING_HUMAN_OBSERVATION') record.status='SESSION_ENDED_MANUAL_VERIFICATION_INCOMPLETE';
  await save();
  console.log(JSON.stringify({status:record.status, cleanup:record.cleanup?.status, raw_output_persisted:false}));
}
