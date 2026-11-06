// R5-only read-only attestation. Reuse the reviewed R4 instance/process inspector.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {inspect} from './wp7br4-preflight.mjs';
export const root='tmp/qa-wp7br5';
export const authority='C:/Users/jithe/.codex/attachments/f2ee7bed-6739-41de-8f8d-145ee14218bd/Pasted text.txt';
export {inspect};
export const sha=async file=>crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex');
// Docker container/network/mount inventories are sets, not ordered contracts.
// Preserve every measured field, especially identity and lifecycle timestamps.
export const canonicalContainers=rows=>rows.map(c=>({...c,networks:c.networks.slice().sort(),mounts:c.mounts.slice().sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)))})).sort((a,b)=>a.id.localeCompare(b.id));
if(process.argv.includes('--record-prelaunch-r5')){
 const target=root+'/prelaunch.json';
 try{await fs.access(target);throw Error('R5_PRELAUNCH_ALREADY_RECORDED');}catch(e){if(e.code!=='ENOENT')throw e;}
 const previous=JSON.parse(await fs.readFile(root+'/preflight.json','utf8')),data=inspect();
 if(data.instance_id!==previous.instance_id||data.container_id!==previous.container_id||!data.signed_authority_valid)throw Error('R5_PRELAUNCH_IDENTITY_CHANGED');
 if(data.processes.frontend_watchers.length||data.processes.custom_reload_includes)throw Error('BLOCKED_PROCESS_INTERRUPTION_NOT_AUTHORIZED');
 for(const [file,expected]of Object.entries(previous.preserved_sources))if(await sha(file)!==expected)throw Error('R5_SOURCE_CHANGED_SINCE_FOCUSED_TESTS');
 const css=await fs.readFile('apps/web/src/app/campaigns/campaigns.css','utf8');
 if(crypto.createHash('sha256').update(css.replace(/  --vj-focus: var\(--vj-color-brand-strong\);\r?\n/,'')).digest('hex')!==previous.original_campaign_css_sha256)throw Error('R5_FOCUS_SCOPE_CHANGED');
 data.package='WP7B-R5';data.at=new Date().toISOString();data.authority_sha256=await sha(authority);
 if(data.authority_sha256!==previous.authority_sha256)throw Error('R5_AUTHORITY_CHANGED');
 await fs.writeFile(target,JSON.stringify(data,null,2));
 console.log(JSON.stringify({status:'PASS',at:data.at,api_processes:data.processes.api_processes.length,frontend_watchers:0}));
}
// Package-specific argument avoids the retained R4 module's CLI entry guard.
if(process.argv.includes('--record-r5')){
 await fs.mkdir(root,{recursive:true});
 const target=root+'/preflight.json';
 try{await fs.access(target);throw Error('R5_PREFLIGHT_ALREADY_RECORDED');}catch(e){if(e.code!=='ENOENT')throw e;}
 const data=inspect();
 if(data.processes.frontend_watchers.length||data.processes.custom_reload_includes||data.processes.listeners.some(r=>r.LocalPort===4200))throw Error('BLOCKED_PROCESS_INTERRUPTION_NOT_AUTHORIZED');
 if(data.instance_id!=='389b97d2-a4cd-4d9b-972e-6bb2bf5785eb'||data.endpoint!=='127.0.0.1:55432'||data.role!=='vayujit_qa_admin'||!data.signed_authority_valid)throw Error('R5_EXACT_AUTHORIZED_INSTANCE_REQUIRED');
 data.package='WP7B-R5';data.at=new Date().toISOString();data.authority_sha256=await sha(authority);
 data.original_campaign_css_sha256=await sha('apps/web/src/app/campaigns/campaigns.css');
 data.preserved_sources={};
 for(const file of ['apps/web/src/styles.css','apps/web/src/app/auth/auth-page.component.ts','apps/web/src/app/campaigns/reschedule-dialog.component.ts','apps/web/src/app/campaigns/campaign-detail.component.ts','apps/web/src/app/campaigns/campaign.service.ts'])data.preserved_sources[file]=await sha(file);
 data.preserved_reports={};
 for(const name of await fs.readdir('docs/qa/seller-experience'))if(/^wp7b-/.test(name)&&!name.startsWith('wp7b-r5-')){const p='docs/qa/seller-experience/'+name;data.preserved_reports[p]=await sha(p);}
 await fs.writeFile(target,JSON.stringify(data,null,2));
 console.log(JSON.stringify({status:'PASS',instance_id:data.instance_id,api_processes:data.processes.api_processes.length,frontend_watchers:0,preserved_reports:Object.keys(data.preserved_reports).length}));
}
