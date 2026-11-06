// Native zoom is performed by the Windows UI operator, NEVER by CSS/CDP scaling.
// This bridge only navigates approved local fixture pages and records rendered evidence.
import fs from 'node:fs/promises';import path from 'node:path';
import {expect} from '@playwright/test';
import {start,axe,capture} from './seller-browser-explore.mjs';
export async function nativeReview(browser,s,f,authenticatedContext,runs){
 const run=await start(browser,s,null,'wp7br1-native-chrome');runs.push(run);
 const storage=await authenticatedContext.storageState();await run.context.addCookies(storage.cookies);
 const p=run.page;await p.goto(s.origin+'/intelligence/business-agent');await expect(p.locator('h1')).toBeVisible();
 const cdp=await run.context.newCDPSession(p);const {windowId}=await cdp.send('Browser.getWindowForTarget');
 await cdp.send('Browser.setWindowBounds',{windowId,bounds:{windowState:'normal'}});
 await cdp.send('Browser.setWindowBounds',{windowId,bounds:{left:80,top:50,width:1000,height:650}});
 const title=()=>p.evaluate(token=>document.title='WP7BR1 MANUAL '+token,s.token);await title();
 const record={status:'RUNNING',native_zoom_set_by_bridge:false,screen_reader:'Human observations recorded separately; DOM does not establish speech',captures:[],commands:[],errors:[]};
 const routes={goals:'/intelligence/business-agent',accounts:'/marketplaces/accounts',meesho:'/marketplaces/listings/'+f.meesho.id+'/meesho',ads:'/ads/recommendations',social:f.reviews?'/social/posts/'+f.reviews.social.id:null,login:'/login'};
 await fs.writeFile(path.join(s.folder,'r1-native-ready.json'),JSON.stringify({token:s.token,title:'WP7BR1 MANUAL '+s.token,origin:s.origin,window_id:windowId,synthetic:true,route_keys:Object.keys(routes)},null,2));
 const handled=new Set(),began=Date.now();let finished=false;
 while(Date.now()-began<900000 && !finished){
  const requests=await fs.readFile(path.join(s.folder,'r1-manual-requests.json'),'utf8').then(JSON.parse).catch(()=>[]);
  for(const request of requests){
   if(!Number.isInteger(request.id) || handled.has(request.id))continue;handled.add(request.id);
   try{
    if(request.action==='done'){finished=true;break;}
    if(request.action==='navigate'){
     if(!routes[request.route])throw Error('ALLOWLISTED_LOCAL_ROUTE_REQUIRED');
     if(request.route==='login')await run.context.clearCookies();else await run.context.addCookies(storage.cookies);
     await p.goto(s.origin+routes[request.route]);await expect(p.locator('h1')).toBeVisible();await title();
    }else if(request.action==='open-ads'){
     const button=p.getByRole('button',{name:'Preview',exact:true}).first();await expect(button).toBeVisible();
     for(let i=0;i<180 && !await button.evaluate(e=>e===document.activeElement);i++)await p.keyboard.press('Tab');
     await expect(button).toBeFocused();await p.keyboard.press('Enter');await expect(p.getByRole('dialog',{name:'Preview optimization',exact:true})).toBeVisible();
    }else if(request.action!=='capture')throw Error('ALLOWLISTED_MANUAL_ACTION_REQUIRED');
    const label='native-'+request.id+'-'+String(request.observed_zoom||'state').replace(/[^a-z0-9-]/gi,'');
    const shot=await capture(run,label,true),scan=await axe(run,label);
    const metrics=await p.evaluate(()=>({inner_width:innerWidth,inner_height:innerHeight,device_pixel_ratio:devicePixelRatio,visual_viewport_scale:visualViewport?.scale,document_width:document.documentElement.scrollWidth,active_tag:document.activeElement?.tagName,route:location.pathname}));
    record.captures.push({id:request.id,observed_zoom:request.observed_zoom||null,zoom_label_is_operator_observation:true,screenshot:shot.screenshot,metrics,axe:scan});
    record.commands.push({id:request.id,status:'EXECUTED',action:request.action,route:request.route||null});
   }catch{record.errors.push({id:request.id,safe_code:'MANUAL_ACTION_NOT_ESTABLISHED'});}
   await fs.writeFile(path.join(s.folder,'r1-manual-evidence.json'),JSON.stringify(record,null,2));
  }
  if(!finished)await p.waitForTimeout(500);
 }
 record.status=finished?'COMPLETED':'BOUNDED_SESSION_EXPIRED';
 await fs.writeFile(path.join(s.folder,'r1-manual-evidence.json'),JSON.stringify(record,null,2));return record;
}
