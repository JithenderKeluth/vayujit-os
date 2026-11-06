import {test} from 'node:test';import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {contrastRatio,resolveContrast,waitForTransitions} from '../wp7br1-contrast.mjs';
const base={visible:true,obscured:false,disabled:false,textShadow:'none',color:'rgb(0, 0, 0)',fontSize:16,fontWeight:400,ancestors:[{opacity:'1',backgroundImage:'none',backgroundColor:'rgb(255, 255, 255)'}]};
test('R1 contrast uses unrounded WCAG luminance and verified alpha compositing',()=>{assert.equal(contrastRatio([0,0,0,1],[255,255,255,1]),21);assert.equal(resolveContrast(base).ratio,21);assert.equal(resolveContrast({...base,color:'rgba(0, 0, 0, 0.5)'}).effective_foreground[0],127.5);});
test('R1 contrast does not fabricate a canvas or ignore a gradient/overlay',()=>{assert.equal(resolveContrast({...base,ancestors:[{...base.ancestors[0],backgroundColor:'rgba(0,0,0,0)'}]}).status,'NOT VERIFIED');assert.equal(resolveContrast({...base,obscured:true}).status,'NOT VERIFIED');assert.equal(resolveContrast({...base,ancestors:[{...base.ancestors[0],backgroundImage:'linear-gradient(red, blue)'}]}).status,'NOT VERIFIED');});
test('R1 contrast distinguishes inactive-control exemption from a real low contrast failure',()=>{assert.equal(resolveContrast({...base,disabled:true}).status,'NOT APPLICABLE');assert.equal(resolveContrast({...base,color:'rgb(220,220,220)'}).status,'FAIL');});
test('R1 observes transitions finishing without canceling them or accepting infinite animation',async()=>{
 let completed=false;const finished=new Promise(resolve=>setTimeout(()=>{completed=true;resolve();},10));
 const element={evaluate:fn=>fn({getAnimations:()=>[{finished,effect:{getComputedTiming:()=>({iterations:1})}}]})};
 assert.equal(await waitForTransitions(element),true);assert.equal(completed,true);
 assert.equal(await waitForTransitions({evaluate:fn=>fn({getAnimations:()=>[{effect:{getComputedTiming:()=>({iterations:Infinity})}}]})}),false);
});
test('Marketplace light-surface focus ring uses the existing accessible brand token',async()=>{
 const css=await fs.readFile('apps/web/src/app/marketplaces/marketplaces.css','utf8');
 assert.match(css,/outline: 3px solid var\(--vj-color-brand-strong\)/);
 for(const file of ['apps/web/src/app/intelligence/business-agent-workspace.css','apps/web/src/app/ads/ads-optimization.component.ts'])assert.match(await fs.readFile(file,'utf8'),/outline-color: var\(--vj-color-brand-strong\)/);
 assert.ok(contrastRatio([7,84,98,1],[255,255,255,1])>=3);
 assert.ok(contrastRatio([228,155,40,1],[255,255,255,1])<3);
});
