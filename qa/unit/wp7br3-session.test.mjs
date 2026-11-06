import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const source = await fs.readFile('qa/wp7br3-session.mjs','utf8');
test('R3 session requires explicit new scope and protected QA manifest',()=>{
  assert.match(source,/814004cb-1834-4490-ab39-3820aa5bdb9f/);
  assert.match(source,/QA_POSTGRES_INSTANCE_MANIFEST/);
  assert.doesNotMatch(source,/qa-wp7br1\/owner-authorization/);
});
test('R3 reuses signed lifecycle and exact synthetic witness',()=>{
  assert.match(source,/i\.verify_server\(\)/);
  assert.match(source,/witness\.token !== s\.token/);
  assert.match(source,/s\.database_scope !== `vayujit_qa\$\{s\.token\}_test`/);
});
test('R3 has no development process management or FORCE cleanup',()=>{
  assert.doesNotMatch(source,/taskkill|Stop-Process|WITH \(FORCE\)|docker.*(?:stop|restart|rm)/i);
  assert.match(source,/runtime\.stdin\.end\(\)/);
});
test('R3 expires, closes owned browser, and invokes existing guarded cleanup',()=>{
  assert.match(source,/30\*60\*1000/);
  assert.match(source,/await browser\.close\(\)/);
  assert.match(source,/'stop.request'/);
  assert.match(source,/'session-final.json'/);
});
test('manual groups cannot be promoted from session preparation',()=>{
  assert.match(source,/manual_groups_passed: 0/);
  assert.match(source,/AWAITING_HUMAN_OBSERVATION/);
  assert.match(source,/human_observations: \[\]/);
});
test('password-bearing setup is outside retained trace; storage stays in memory',()=>{
  assert.ok(source.indexOf('await run.context.tracing.stop()') < source.indexOf("'/api/v1/auth/setup-owner'"));
  assert.doesNotMatch(source,/JSON\.stringify\(storage|writeFile\([^\n]*password/);
  assert.match(source,/Never persist subprocess output/);
});
test('all forty inherited review IDs are preserved as the checklist source',async()=>{
  const gate=JSON.parse(await fs.readFile('docs/qa/seller-experience/wp7b-r2-gate.json','utf8'));
  const rows=[...gate.screen_reader_checks,...gate.native_zoom_checks,...gate.contrast_review_groups];
  assert.equal(rows.length,40); assert.equal(new Set(rows.map(r=>r.id)).size,40);
  assert.equal(rows.filter(r=>r.status!=='NOT VERIFIED').length,0);
});
