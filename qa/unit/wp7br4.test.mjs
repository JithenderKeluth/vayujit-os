import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {contrastRatio} from '../wp7br1-contrast.mjs';
const pre=JSON.parse(await fs.readFile('tmp/qa-wp7br4/preflight.json','utf8'));
const auth=await fs.readFile('apps/web/src/app/auth/auth-page.component.ts','utf8');
const global=await fs.readFile('apps/web/src/styles.css','utf8');
test('R4 production change is exactly one local focus-token declaration',()=>{
 const before=auth.replace(/        --vj-focus: var\(--vj-color-brand-strong\);\r?\n/,'');
 assert.equal(crypto.createHash('sha256').update(before).digest('hex'),pre.original_auth_sha256);
});
test('R4 does not change the global token or dark navigation theme',()=>{
 assert.equal(crypto.createHash('sha256').update(global).digest('hex'),pre.original_global_styles_sha256);
 assert.match(global,/--vj-focus: #e09a36/);
});
test('existing strong brand token clears3:1 while old gold does not',()=>{
 assert.ok(contrastRatio([7,84,98],[255,255,255])>=3);
 assert.ok(contrastRatio([224,154,54],[255,255,255])<3);
});
test('R4 retains global focus width and offset',()=>{
 assert.match(global,/outline: 3px solid var\(--vj-focus\)/);
 assert.match(global,/outline-offset: 3px/);
});
test('R4 watcher classifier does not mistake diagnostic source for uvicorn module execution',()=>{
 const module=/(?:^|\s)-m\s+uvicorn\s+/;
 assert.ok(module.test('python.exe -m uvicorn vayujit_api.main:app --reload'));
 assert.equal(module.test('python.exe -c "roots match uvicorn.*--reload; inspect --reload-include"'),false);
});
test('R4 session authority is fresh and cleanup is bounded/owned without FORCE',async()=>{
 const code=await fs.readFile('qa/wp7br4-session.mjs','utf8');
 assert.match(code,/authority_sha256/);assert.match(code,/60\*60\*1000/);
 assert.match(code,/R4_DATABASE_SCOPE_DENIED/);assert.match(code,/fs\.writeFile\(s\.folder\+'\/stop\.request'/);
 assert.doesNotMatch(code,/WITH \(FORCE\)|Stop-Process|taskkill/);
});
test('text-fragment measurements retain uncertain/missing original text rather than declaring PASS',async()=>{
 const code=await fs.readFile('qa/wp7br4-text-fragments.mjs','utf8');
 assert.match(code,/Text identity changed/);assert.match(code,/No direct label\/caption text fragment found/);
 assert.match(code,/resolveContrast\(measured\)/);
});
