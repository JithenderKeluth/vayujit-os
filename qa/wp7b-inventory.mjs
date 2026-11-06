// Historical observations, not new manual passes. No database or process control.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
export const normalizeRoute = value => String(value || '/UNKNOWN').split('?')[0].replace(/[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}/gi, ':id');
export function observationKey(o) {
  return JSON.stringify([normalizeRoute(o.route),o.component,o.rule,o.target,o.browser,o.viewport,o.cause]);
}
export const stableId = key => 'WP7B-A11Y-'+crypto.createHash('sha256').update(key).digest('hex').slice(0,12).toUpperCase();
const root='docs/qa/seller-experience/';
export async function inventory() {
  const observations=new Map(), inputs=[], errors=[];
  function add(scan,file,label) {
    const browser=/edge|msedge/i.test(label)?'Edge':/chrome/i.test(label)?'Chrome':'UNRECORDED';
    const viewport=scan.viewport?.width?String(scan.viewport.width):/1440/.test(label)?'1440':/768/.test(label)?'768':/390/.test(label)?'390':/mobile/.test(label)?'UNRECORDED_MOBILE':'UNRECORDED';
    for(const kind of ['violations','incomplete']) for(const rule of scan[kind] || []) for(const node of rule.nodes || []) {
      const route=normalizeRoute(scan.route),component=route.split('/').filter(Boolean).slice(0,2).join('/') || 'shell';
      const o={route,component,rule:rule.id,target:JSON.stringify(node.target || []),browser,viewport,cause:'NOT_YET_ATTRIBUTED'};
      const key=observationKey(o),row=observations.get(key) || {id:stableId(key),...o,classification:'Manual verification required',occurrences:[],historical_violation:false,historical_incomplete:false,current_status:'NOT RETESTED IN WP7B'};
      row.historical_violation ||= kind==='violations';row.historical_incomplete ||= kind==='incomplete';
      if(row.historical_violation) row.classification='Confirmed violation (historical scan; current status unverified)';
      row.occurrences.push({file,state:scan.state,kind,impact:rule.impact || null});observations.set(key,row);
    }
  }
  const folders=await fs.readdir('tmp/qa-seller-browser',{withFileTypes:true});
  for(const folder of folders.filter(d=>d.isDirectory() && /^[a-f0-9]{16}$/.test(d.name))) {
    const base='tmp/qa-seller-browser/'+folder.name;
    for(const context of await fs.readdir(base,{withFileTypes:true})) {
      if(!context.isDirectory()) continue;
      const file=base+'/'+context.name+'/browser-evidence.json';
      let data;
      try {data=JSON.parse(await fs.readFile(file,'utf8'));} catch(e) {if(e.code!=='ENOENT') errors.push({file,code:'UNREADABLE_EVIDENCE'});continue;}
      if(!Array.isArray(data.axe)) continue;
      inputs.push(file);
      for(const scan of data.axe) add(scan,file,context.name);
    }
  }
  for(const name of (await fs.readdir('docs/qa')).filter(n=>/accessibility.*\.json$/.test(n))) {
    const file='docs/qa/'+name;
    const data=JSON.parse(await fs.readFile(file,'utf8'));
    inputs.push(file);
    for(const scan of [...(data.scans || []),...(data.document_scans || [])]) add(scan,file,scan.project || 'UNRECORDED');
  }
  const agent='tmp/qa-agent';
  for(const d of await fs.readdir(agent,{withFileTypes:true}).catch(()=>[])) {
    if(!d.isDirectory() || !/^[a-f0-9]{16}$/.test(d.name)) continue;
    const base=agent+'/'+d.name+'/evidence';
    for(const context of await fs.readdir(base,{withFileTypes:true}).catch(()=>[])) {
      if(!context.isDirectory())continue;
      for(const name of (await fs.readdir(base+'/'+context.name)).filter(n=>/axe|accessibility/i.test(n) && n.endsWith('.json'))) {
        const file=base+'/'+context.name+'/'+name;
        try{const scan=JSON.parse(await fs.readFile(file,'utf8'));if(Array.isArray(scan.violations) && Array.isArray(scan.incomplete)){inputs.push(file);add(scan,file,context.name);}}catch{errors.push({file,code:'UNREADABLE_EVIDENCE'});}
      }
    }
  }
  const result={package:'WP7B',generated_at:new Date().toISOString(),scope:'Retained browser evidence; repeated scans are not unique defects',deduplication:['route (UUID normalized)','route-component bucket','rule','DOM target','recorded/inferred browser','viewport label','cause (unattributed pending review)'],limitations:['Historical labels do not always record exact viewport or engine; no dimensions are invented.','Component buckets are route-based, not confirmed source-component attribution.','A historical violation is not proof the current application still violates.','Different selectors may share a cause; these are observation keys, not a unique-defect count.'],files:inputs,errors,observation_keys:observations.size,entries:[...observations.values()].sort((a,b)=>a.id.localeCompare(b.id))};
  await fs.mkdir('tmp/qa-wp7b',{recursive:true});
  await fs.writeFile('tmp/qa-wp7b/accessibility-observations.json',JSON.stringify(result,null,2));
  return result;
}
if(process.argv[1] && path.resolve(process.argv[1])===path.resolve('qa/wp7b-inventory.mjs')) {
 const r=await inventory(); console.log(JSON.stringify({files:r.files.length,observation_keys:r.observation_keys,unreadable:r.errors.length,not_unique_defect_count:true}));
}
