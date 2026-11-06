// R5 read-only actual-rendered C12 assessment. No app correction authorized here.
import fs from 'node:fs/promises';
import {chromium,expect} from '@playwright/test';
import {start,capture,axe,finish} from './seller-browser-explore.mjs';
import {parseColor,resolveContrast,contrastRatio} from './wp7br1-contrast.mjs';
const root='tmp/qa-wp7br5/boundaries',c=JSON.parse(await fs.readFile('tmp/qa-wp7br5/session-control.json','utf8')),s=c.session;
if(c.package!=='WP7B-R5'||c.status!=='READY_FOR_VERIFICATION'||Date.now()>Date.parse(c.expires_at)-30000)throw Error('ACTIVE_R5_REQUIRED');
const witness=await fetch(s.origin+'/__qa/witness').then(r=>r.json());if(witness.token!==s.token||!witness.disposable)throw Error('EXACT_R5_REQUIRED');
await fs.mkdir(root,{recursive:true});const report={package:'WP7B-R5',token:s.token,started_at:new Date().toISOString(),review_id:'R2-C-12',records:[],contexts:[],scans:[],versions:{},form_submissions:0,scope:'Unfocused empty authored text-input boundary; actual label is outside control; no input value/icon/focus cue substituted for baseline identification',criterion:'1.4.11',reference:'https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html#adjacent-colors'};
for(const channel of ['chrome','msedge']){
 const browser=await chromium.launch({channel,headless:true});report.versions[channel]=browser.version();
 try{for(const width of [1440,390]){
  const run=await start(browser,{...s,folder:root},{width,height:900},'wp7br1-'+channel+'-'+width),p=run.page,ctx={context:run.label,width,height:900};
  try{
   await p.goto(s.origin+'/login');const input=p.locator('#email');await expect(input).toBeVisible();await expect(input).toHaveValue('');expect(await input.evaluate(e=>e===document.activeElement)).toBe(false);
   await input.evaluate(e=>e.scrollIntoView({block:'center'}));
   const m=await input.evaluate(el=>{const r=el.getBoundingClientRect(),cs=getComputedStyle(el),ancestors=[];for(let a=el;a;a=a.parentElement){const s=getComputedStyle(a);ancestors.push({backgroundColor:s.backgroundColor,backgroundImage:s.backgroundImage,opacity:s.opacity});}return{value_empty:el.value==='',placeholder:el.getAttribute('placeholder'),type:el.type,disabled:el.disabled,focused:el===document.activeElement,color:cs.borderTopColor,fontSize:24,fontWeight:700,textShadow:cs.textShadow,visible:r.width>0&&r.height>0&&r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight,obscured:document.elementFromPoint(r.left+r.width/2,r.top+r.height/2)!==el,outline:cs.outline,border:{color:cs.borderTopColor,width:cs.borderTopWidth,style:cs.borderTopStyle},background:cs.backgroundColor,backgroundImage:cs.backgroundImage,boxShadow:cs.boxShadow,appearance:cs.appearance,ancestors,rect:{left:r.left,top:r.top,width:r.width,height:r.height},viewport:{width:innerWidth,height:innerHeight},labels:[...el.labels].map(l=>({text:l.textContent.trim(),contains_control:l.contains(el)}))};});
   const borderOutside=resolveContrast({...m,ancestors:m.ancestors.slice(1)}),borderInside=resolveContrast(m),inside=parseColor(m.background),outside=borderOutside.background;
   const fill=inside&&outside&&inside[3]===1?contrastRatio(inside,outside):null;
   const applicable=m.value_empty&&!m.placeholder&&!m.disabled&&!m.focused&&m.type==='email'&&m.border.style==='solid'&&m.backgroundImage==='none'&&m.boxShadow==='none'&&fill!==null&&fill<3&&borderOutside.ratio!==undefined&&borderInside.ratio!==undefined;
   const row={context:run.label,channel,browser_version:browser.version(),route:'/login',selector:'#email',timestamp:new Date().toISOString(),rendered:m,border_to_outside:borderOutside,border_to_inside:borderInside,fill_to_outside:fill,applicability:{established:applicable,reason:'Enabled empty authored email field has no internal value/placeholder/icon, opaque fill matches surrounding auth surface, border is the baseline identifying cue. External label does not replace identifying the blank input.'},status:applicable?(borderOutside.ratio>=3&&borderInside.ratio>=3?'VERIFIED_PASS':'VERIFIED_FAIL'):'NOT_VERIFIED'};
   row.evidence=(await capture(run,'empty-email-boundary')).screenshot;report.records.push(row);report.scans.push({context:run.label,...await axe(run,'empty-email-boundary')});
  }catch(e){ctx.limitation='R5_BOUNDARY_CONTEXT_INCOMPLETE';}
  finally{ctx.trace=await finish(run);report.contexts.push(ctx);await fs.writeFile(root+'/results.json',JSON.stringify(report,null,2));}
 }}finally{await browser.close();}
}
report.completed_at=new Date().toISOString();await fs.writeFile(root+'/results.json',JSON.stringify(report,null,2));console.log(JSON.stringify({records:report.records.length,pass:report.records.filter(r=>r.status==='VERIFIED_PASS').length,fail:report.records.filter(r=>r.status==='VERIFIED_FAIL').length,not_verified:report.records.filter(r=>r.status==='NOT_VERIFIED').length,ratios:report.records.map(r=>r.border_to_outside.ratio)}));
