import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {sections} from '../source/compact-guide.mjs';
const root='docs/product-handbook';
const book=JSON.parse(await fs.readFile(root+'/compact/source.json','utf8'));
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');

test('compact source covers 45 coherent tasks without exhaustive route catalogue',()=>{
 assert.equal(sections.length,45);assert.equal(book.body_words,5394);
 for(const section of sections)assert.ok(section.where&&section.intro&&section.steps.length>=3&&section.check&&section.next);
 assert.equal(new Set(sections.map(s=>s.title)).size,45);
});
test('explicit layout stays conservatively inside requested page budget',()=>{
 assert.equal(book.designed_page_count,67);assert.ok(book.designed_page_count<=110);
 assert.equal(book.actual_rendered_page_count,null);
 assert.equal(book.render_status,'NOT VERIFIED');
 assert.ok(book.checks.every(c=>c.word_count<=420));
});
test('all nineteen screenshots retain reviewed bytes and truthful provenance',async()=>{
 const shots=book.pages.filter(p=>p.kind==='screenshot');assert.equal(shots.length,19);
 for(const [i,shot]of shots.entries()){
  assert.equal(sha(await fs.readFile(shot.path)),shot.sha256);
  assert.ok(shot.caption.startsWith('Screenshot '+(i+1)+'. '));
  assert.match(shot.caption,/historical synthetic capture/i);assert.ok(shot.alt);
 }
});
test('contents links resolve to every task exactly once',()=>{
 const entries=book.pages.filter(p=>p.kind==='contents').flatMap(p=>p.entries);
 const tasks=book.pages.filter(p=>p.kind==='task');assert.equal(entries.length,45);
 assert.deepEqual(entries.map(e=>e.anchor),tasks.map(t=>t.anchor));
});
test('detailed handbook and its unified sources remain byte-identical',async()=>{
 for(const [path,digest]of Object.entries(book.retained_sha256))assert.equal(sha(await fs.readFile(path)),digest);
 const baseline=JSON.parse(await fs.readFile(root+'/compact/retained-baseline.json','utf8'));
 assert.deepEqual(book.retained_sha256,baseline);
});
test('source labels preserve optional reason and separate authorization',()=>{
 const reschedule=sections.find(s=>s.title==='Preview an activity reschedule');
 assert.match(reschedule.steps.join(' '),/Reason is optional, at most 500/);
 assert.match(reschedule.steps.join(' '),/Confirm reschedule is a separate action/);
 const text=JSON.stringify(sections);
 for(const phrase of ['not zero','not an immutable statutory ledger','backup certification remains parked','accessibility remains incomplete'])assert.ok(text.toLowerCase().includes(phrase.toLowerCase()));
 assert.ok(!/AGE-SECRET-KEY-1|postgres(?:ql)?:\/\/[^\s"]+:[^\s"]+@/.test(text));
});
