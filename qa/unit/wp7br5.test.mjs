import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {contrastRatio} from '../wp7br1-contrast.mjs';
import {canonicalContainers} from '../wp7br5-preflight.mjs';
const pre=JSON.parse(await fs.readFile('tmp/qa-wp7br5/preflight.json','utf8'));
const css=await fs.readFile('apps/web/src/app/campaigns/campaigns.css','utf8');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
test('R5 production change is precisely one local reschedule focus declaration',()=>{
 const before=css.replace(/  --vj-focus: var\(--vj-color-brand-strong\);\r?\n/,'');
 assert.equal(hash(before),pre.original_campaign_css_sha256);
 assert.match(css,/\.reschedule-panel \{\s*--vj-focus: var\(--vj-color-brand-strong\);/);
});
test('R5 preserves authentication, global theme, scheduling and API source hashes',async()=>{
 for(const [file,expected]of Object.entries(pre.preserved_sources))assert.equal(hash(await fs.readFile(file)),expected,file);
});
test('old gold fails and existing brand-strong clears authored3:1 threshold',()=>{
 assert.ok(contrastRatio([224,154,54],[255,255,255])<3);
 assert.ok(contrastRatio([7,84,98],[255,255,255])>=3);
});
test('R5 does not replace global focus geometry or disable animations',async()=>{
 const global=await fs.readFile('apps/web/src/styles.css','utf8');
 assert.match(global,/outline: 3px solid var\(--vj-focus\)/);
 assert.match(global,/outline-offset: 3px/);
 assert.doesNotMatch(css,/animation:\s*none|transition:\s*none|outline:\s*(?:0|none)/);
});
test('R5 preflight has its own entry switch and exact approved instance guard',async()=>{
 const code=await fs.readFile('qa/wp7br5-preflight.mjs','utf8');
 assert.match(code,/--record-r5/);assert.doesNotMatch(code,/includes\('--record'\)/);
 assert.match(code,/R5_EXACT_AUTHORIZED_INSTANCE_REQUIRED/);
 assert.match(code,/BLOCKED_PROCESS_INTERRUPTION_NOT_AUTHORIZED/);
});
test('R5 session requires current listener readiness before launching any QA runtime',async()=>{
 const code=await fs.readFile('qa/wp7br5-session.mjs','utf8');
 assert.ok(code.indexOf('R5_CURRENT_HUMAN_READINESS_REQUIRED')<code.indexOf('const runtime=spawn('));
 assert.match(code,/authority_sha256/);assert.match(code,/R5_DATABASE_SCOPE_DENIED/);
 assert.match(code,/60\*60\*1000/);assert.match(code,/fs\.writeFile\(s\.folder\+'\/stop\.request'/);
 assert.doesNotMatch(code,/WITH \(FORCE\)|Stop-Process|taskkill/);
});
test('R5 style regression is explicitly not persisted application certification',async()=>{
 const code=await fs.readFile('qa/wp7br5-style-browser.mjs','utf8');
 assert.match(code,/database_operations:0/);assert.match(code,/NOT the authenticated\/persisted application/);
 assert.match(code,/context\.route\('\*\*\/\*',r=>r\.abort\(\)\)/);
 assert.match(code,/finally\{await browser\.close\(\);\}/);
});
test('preservation compares unordered inventories without mutating source evidence',()=>{
 const rows=[{id:'b',networks:['z','a'],mounts:[{Destination:'/b'},{Destination:'/a'}],started:'original'}];
 const reversed=[{...rows[0],networks:['a','z'],mounts:rows[0].mounts.slice().reverse()}];
 assert.deepEqual(canonicalContainers(rows),canonicalContainers(reversed));
 assert.deepEqual(rows[0].networks,['z','a']);
});
test('preservation still detects actual container lifecycle metadata changes',()=>{
 const rows=[{id:'a',networks:['n'],mounts:[],started:'original'}];
 assert.notDeepEqual(canonicalContainers(rows),canonicalContainers([{...rows[0],started:'changed'}]));
});
