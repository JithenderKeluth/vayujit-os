// Network-free CSS regression only. NOT the authenticated/persisted application.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {chromium,expect} from '@playwright/test';
import {measureTargets} from './wp7br1-contrast.mjs';
const root='tmp/qa-wp7br5/style-browser',globalCss=await fs.readFile('apps/web/src/styles.css','utf8'),current=await fs.readFile('apps/web/src/app/campaigns/campaigns.css','utf8');
const pre=JSON.parse(await fs.readFile('tmp/qa-wp7br5/preflight.json','utf8'));
const old=current.replace(/  --vj-focus: var\(--vj-color-brand-strong\);\r?\n/,'');
if(crypto.createHash('sha256').update(old).digest('hex')!==pre.original_campaign_css_sha256)throw Error('R5_EXACT_PREFIX_STYLE_REQUIRED');
await fs.mkdir(root,{recursive:true});
const report={package:'WP7B-R5',scope:'Network-free component-style browser regression; not canonical app/fixture/route certification',database_operations:0,external_calls:0,started_at:new Date().toISOString(),versions:{},checks:[],measurements:[]};
const previous=await fs.readFile(root+'/results.json','utf8').then(JSON.parse).catch(()=>null);
if(previous)await fs.writeFile(root+'/history-'+previous.started_at.replace(/[^a-z0-9]/gi,'')+'.json',JSON.stringify(previous,null,2));
const revision='run-'+Date.now();
report.initial_run_limitation='Earlier narrow CSS fixture omitted viewport meta; mobile screenshot width did not prove CSS viewport width. Earlier ratios remain scoped color observations, not responsive proof. History and original images retained; this run asserts actual innerWidth.';
for(const channel of ['chrome','msedge']){
 const browser=await chromium.launch({channel,headless:true});report.versions[channel]=browser.version();
 try{for(const width of [1440,390]){
  const context=await browser.newContext({viewport:{width,height:900},isMobile:width===390,hasTouch:width===390,serviceWorkers:'block'});
  await context.route('**/*',r=>r.abort());const page=await context.newPage();
  try{for(const [state,css]of [['before',old],['after',current]]){
   const directory=root+'/'+revision+'/'+channel+'-'+width+'-'+state;await fs.mkdir(directory,{recursive:true});
   await page.setContent('<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>R5 CSS regression only</title></head><body><main class="page"><h1>Component-style regression only</h1><section class="reschedule-panel" aria-labelledby="title"><h2 id="title">Reschedule Activity</h2><label>Reason <textarea rows="3" maxlength="500"></textarea></label><button type="button">Preview change</button></section></main></body></html>');
   await page.addStyleTag({content:globalCss+'\n'+css});await page.keyboard.press('Tab');await expect(page.locator('textarea')).toBeFocused();
   const rows=await measureTargets({page,directory},['.reschedule-panel textarea'],state);const row=rows[0];
   const screenshot=directory+'/full-focus.png';await page.screenshot({path:screenshot});
   const actual=row.focus_indicator.ratio,ok=state==='before'?actual<3:actual>=3;
   expect(ok).toBe(true);expect(row.rendered.outline.width).toBe('3px');
   const viewport=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));expect(viewport.width).toBe(width);
   report.measurements.push({...row,state,channel,width,actual_css_viewport:viewport,browser_version:browser.version(),full_focus_screenshot:screenshot,timestamp:new Date().toISOString()});
   report.checks.push({state,channel,width,status:'VERIFIED_PASS',actual_ratio:actual,expected:state==='before'?'Reconstructed exact prior CSS reproduces <3:1':'Current source CSS produces >=3:1',not_application_certification:true});
  }}finally{await context.close();}
 }}finally{await browser.close();}
}
report.completed_at=new Date().toISOString();await fs.writeFile(root+'/results.json',JSON.stringify(report,null,2));console.log(JSON.stringify({passed:report.checks.length,scope:report.scope,ratios:report.checks.map(c=>({state:c.state,channel:c.channel,width:c.width,ratio:c.actual_ratio}))}));
