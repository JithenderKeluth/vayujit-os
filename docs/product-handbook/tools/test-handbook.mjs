import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {prompts,journeys} from '../source/editorial.mjs';
import {guidance,fieldOverrides,pageUpdates} from '../source/page-guidance.mjs';
const root='docs/product-handbook';
const data=JSON.parse(await fs.readFile(root+'/source/ui-inventory.json','utf8'));
const book=JSON.parse(await fs.readFile(root+'/source/book.json','utf8'));
const fields=JSON.parse(await fs.readFile(root+'/source/field-guides.json','utf8'));
const shots=JSON.parse(await fs.readFile(root+'/inventory/screenshot-register.json','utf8'));
test('source route census reconciles pages and redirects',()=>{assert.equal(data.routes.length,156);assert.equal(data.routes.filter(r=>r.kind==='PAGE').length,150);assert.equal(data.routes.filter(r=>r.kind==='REDIRECT').length,6);assert.ok(data.routes.filter(r=>r.kind==='PAGE').every(r=>data.pages.some(p=>p.routes.includes(r.route))));});
test('all 104 page families retain A through M references',()=>{assert.equal(Object.keys(guidance).length,104);for(const p of data.pages){const start=book.blocks.findIndex(b=>b.kind==='heading'&&b.text.startsWith(p.page_id+' '));assert.ok(start>=0);const tail=book.blocks.slice(start+1);const end=tail.findIndex(b=>b.kind==='heading'&&b.level<=2);const section=end<0?tail:tail.slice(0,end);const letters=section.filter(b=>b.kind==='heading'&&b.level===3).map(b=>b.text[0]);assert.deepEqual(letters,'ABCDEFGHIJKLM'.split(''));}});
test('all declared fields have stable unique reference records',()=>{assert.equal(fields.length,693);assert.equal(new Set(fields.map(f=>f.id)).size,693);assert.ok(fields.every(f=>['purpose','required','type','accepted','example','validation','effect','mistake'].every(k=>typeof f[k]==='string'&&f[k].length)));});
test('manually reviewed field overrides resolve source IDs',()=>{assert.equal(Object.keys(fieldOverrides).length,26);for(const id of Object.keys(fieldOverrides))assert.ok(fields.some(f=>f.id===id));});
test('prompt library has twenty four complete task records',()=>{assert.equal(prompts.length,24);assert.ok(prompts.every(p=>p.length===8&&p.every(v=>typeof v==='string'&&v.length>0)));});
test('six journeys retain prerequisites limitations and safe boundaries',()=>{assert.equal(journeys.length,6);assert.ok(journeys.every(j=>j.prerequisites&&j.limits&&j.next&&j.steps.length>=6&&j.pages.every(id=>guidance[id])));});
test('screenshots are genuine reviewed historical copies not live claims',async()=>{assert.equal(shots.length,19);for(const s of shots){assert.ok(s.synthetic&&s.historical&&s.reviewed_for_visible_secrets);assert.equal(crypto.createHash('sha256').update(await fs.readFile(s.path)).digest('hex'),s.sha256);assert.equal(crypto.createHash('sha256').update(await fs.readFile(s.source)).digest('hex'),s.sha256);}});
test('figures numbered in actual document order',()=>{assert.deepEqual(book.blocks.filter(b=>b.kind==='image').map(b=>b.figure),Array.from({length:19},(_,i)=>i+1));});
test('draft edition does not invent current UI or final certification',()=>{assert.equal(book.edition,'0.9.1');assert.equal(book.metrics.fresh_current_ui_pages,0);const text=JSON.stringify(book.blocks);assert.ok(text.includes('Gate B remains NOT PASSED'));assert.ok(text.includes('PC-first encrypted independent backup/restore remains PARKED'));assert.ok(text.includes('not an immutable accounting ledger'));});

test('R5 field clarification matches source and preserves confirmation boundary',async()=>{
 const source=await fs.readFile('apps/web/src/app/campaigns/reschedule-dialog.component.ts','utf8');
 assert.ok(source.includes("reason: ['', Validators.maxLength(500)]"));
 assert.ok(source.includes("timezone: ['UTC', [Validators.required, Validators.maxLength(100)]]"));
 assert.ok(source.includes('Asia/Kolkata'));
 assert.match(fieldOverrides['reschedule-dialog-F004'].required,/Optional/);
 assert.match(fieldOverrides['reschedule-dialog-F005'].required,/Conditional/);
 assert.match(pageUpdates.P032.L,/24 passing.*zero confirmations/);
 assert.match(pageUpdates.P032.H,/Do not click Confirm reschedule/);
 assert.deepEqual(Object.keys(pageUpdates),['P032']);
});

test('maintenance changelog preserves both editions',async()=>{
 const history=await fs.readFile(root+'/changes/handbook-changelog.md','utf8');
 assert.match(history,/edition 0\.9\.1/);assert.match(history,/edition 0\.9\n/);
 assert.ok(history.includes('Created current source route/field/action/section inventories.'));
});
