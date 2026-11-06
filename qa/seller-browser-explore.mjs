// Evidence helpers for human-directed Playwright exploration; no application fixes.
import fs from 'node:fs/promises';
import path from 'node:path';
import { allowRequest } from './safety.mjs';
import { snapshotSurface } from './phase4-surface.mjs';

export async function start(browser, session, viewport, label) {
  const directory = path.join(session.folder, label);
  await fs.mkdir(directory, {recursive:true});
  const context = await browser.newContext({baseURL:session.origin,viewport, serviceWorkers:'block',
    isMobile:label === 'mobile' || /^wp7(?:a[4567]|br1|b)-(chrome|msedge)-390$/.test(label), hasTouch:label === 'mobile' || /^wp7(?:a[4567]|br1|b)-(chrome|msedge)-390$/.test(label)});
  const signals = {console_errors:[],page_errors:[],network:[],failed_requests:[],denied_requests:[]};
  await context.route('**/*', async route => {
    const r = route.request();
    if (!allowRequest(r.url(),r.method(),session.origin,/^wp7b(?:r1)?-/.test(label) && session.qa_phase==='WP7A7' ? 'WP7B' : ['WP6','WP6A','WP6B','WP7A','WP7A2', 'WP7A3', 'WP7A4', 'WP7A5', 'WP7A6', 'WP7A7'].includes(session.qa_phase) ? session.qa_phase : '4')) {
      signals.denied_requests.push({method:r.method(),path:new URL(r.url()).pathname});
      await route.abort('blockedbyclient');
    } else await route.continue();
  });
  await context.tracing.start({screenshots:true,snapshots:true,sources:false});
  const page = await context.newPage();
  page.on('console',m => {if(m.type()==='error') signals.console_errors.push(m.text().slice(0,500));});
  page.on('pageerror',e=>signals.page_errors.push(e.message.slice(0,500)));
  page.on('response',r=>{
    const u=new URL(r.url());
    if(u.pathname.startsWith('/api/') || r.status()>=400)
      signals.network.push({screen:new URL(page.url()).pathname,method:r.request().method(),path:u.pathname,status:r.status()});
  });
  page.on('requestfailed',r=>signals.failed_requests.push({method:r.method(),path:new URL(r.url()).pathname,code:r.failure()?.errorText}));
  return {page,context,session,directory,label,signals,surfaces:[],actions:[],axe:[]};
}

export async function capture(run, state, full=false) {
  const {page}=run;
  // Angular Router may commit its lazy component after a click promise resolves.
  await page.waitForTimeout(200);
  await page.waitForLoadState('networkidle',{timeout:4000}).catch(()=>{});
  const n=String(run.surfaces.length+1).padStart(3,'0');
  const key=n+'-'+state.replace(/[^a-z0-9-]/gi,'-');
  const data=await snapshotSurface(page,new URL(page.url()).pathname,state);
  data.body=await page.locator('body').innerText();
  data.browser=run.label;
  data.viewport=page.viewportSize();
  data.screenshot=key+'.png';
  data.elapsed_navigation_ms=run.navigationBegan ? Date.now()-run.navigationBegan : null;
  await page.screenshot({path:path.join(run.directory,key+'.png'),fullPage:false});
  if(full) await page.screenshot({path:path.join(run.directory,key+'-full.png'),fullPage:true});
  await fs.writeFile(path.join(run.directory,key+'.json'),JSON.stringify(data,null,2));
  run.surfaces.push(data);
  await persist(run);
  return {route:data.route,headings:data.headings,body:data.body.slice(-15000),
    controls:data.controls.filter(c=>c.visible),screenshot:path.join(run.directory,data.screenshot),
    layout:data.layout};
}

export async function visit(run, route, state) {
  run.navigationBegan=Date.now();
  await run.page.goto(run.session.origin+route,{waitUntil:'domcontentloaded',timeout:20000});
  return capture(run,state || route.replaceAll('/','-'));
}

export async function axe(run, state) {
  if(!await run.page.evaluate(()=>!!globalThis.axe))
    await run.page.addScriptTag({path:path.resolve('node_modules/axe-core/axe.min.js')});
  const result=await run.page.evaluate(async()=>{
    const r=await globalThis.axe.run(document);
    const map=v=>({id:v.id,impact:v.impact,help:v.help,nodes:v.nodes.map(n=>({target:n.target,html:n.html,failureSummary:n.failureSummary}))});
    return {route:location.pathname,violations:r.violations.map(map),incomplete:r.incomplete.map(map),passes:r.passes.length};
  });
  result.state=state;
  run.axe.push(result);
  await persist(run);
  return result;
}

export async function persist(run) {
  await fs.writeFile(path.join(run.directory,'browser-evidence.json'),JSON.stringify({label:run.label,
    surfaces:run.surfaces,actions:run.actions,axe:run.axe,signals:run.signals},null,2));
}

export async function finish(run) {
  await persist(run);
  await run.context.tracing.stop({path:path.join(run.directory,'trace.zip')});
  await run.context.close();
  return {screens:run.surfaces.length,trace:path.join(run.directory,'trace.zip')};
}
