// Documentation-only composition. No app, database, browser or network use.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {title,subtitle,date,sections} from '../source/compact-guide.mjs';
const root='docs/product-handbook';
const out=root+'/compact';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const inventory=JSON.parse(await fs.readFile(root+'/source/ui-inventory.json','utf8'));
const shots=JSON.parse(await fs.readFile(root+'/inventory/screenshot-register.json','utf8'));
await fs.mkdir(out,{recursive:true});
const retained=[root+'/VAYUJIT_OS_Complete_Product_Handbook_Reference_Draft_0_9_1.docx',root+'/source/book.json',root+'/source/handbook.md'];
const originalHashes=Object.fromEntries(await Promise.all(retained.map(async p=>[p,sha(await fs.readFile(p))])));
const baselinePath=out+'/retained-baseline.json';
try{await fs.writeFile(baselinePath,JSON.stringify(originalHashes,null,2)+'\n',{flag:'wx'});}catch(error){if(error.code!=='EEXIST')throw error;}
const retainedBaseline=JSON.parse(await fs.readFile(baselinePath,'utf8'));
if(JSON.stringify(retainedBaseline)!==JSON.stringify(originalHashes))throw Error('DETAILED_HANDBOOK_CHANGED');
const sourceReferences=new Set(inventory.pages.map(p=>p.page_id));
const pages=[{kind:'cover',title,subtitle,date}];
for(let offset=0;offset<sections.length;offset+=24)pages.push({kind:'contents',title:offset?'Continue through the guide':'Find the task you need',entries:sections.slice(offset,offset+24).map((s,i)=>({number:offset+i+1,title:s.title,anchor:'task_'+(offset+i+1)}))});
const checks=[];let words=0;let screenshotNumber=0;
for(const [i,s] of sections.entries()){
 if(!s.pages.every(id=>sourceReferences.has(id)))throw Error('INVALID_SOURCE_PAGE_REFERENCE');
 const wordCount=[s.where,s.intro,...s.steps,s.check,s.next].join(' ').split(/\s+/).length;
 words+=wordCount;
 if(wordCount>420)throw Error('TASK_PAGE_OVER_BUDGET:'+String(i+1));
 pages.push({kind:'task',number:i+1,anchor:'task_'+(i+1),...s,word_count:wordCount});
 if(s.shot){
  const shot=shots.find(x=>x.figure===s.shot);if(!shot)throw Error('MISSING_REVIEWED_SCREENSHOT');
  const bytes=await fs.readFile(shot.path);if(sha(bytes)!==shot.sha256)throw Error('SCREENSHOT_CHANGED');
  screenshotNumber++;
  const caption='Screenshot '+screenshotNumber+'. '+shot.caption.replace(/^Figure \d+\. /,'');
  pages.push({kind:'screenshot',number:i+1,title:s.title,path:shot.path,width:shot.pixel_width,height:shot.pixel_height,sha256:shot.sha256,caption,alt:caption,landscape:true});
 }
 checks.push({section:i+1,word_count:wordCount,source_pages:s.pages,screenshot:s.shot??null});
}
if(pages.length>90)throw Error('DESIGNED_PAGE_BUDGET_EXCEEDED');
const book={title,subtitle,date,pages,sections:sections.length,screenshots:pages.filter(p=>p.kind==='screenshot').length,body_words:words,designed_page_count:pages.length,maximum_requested_pages:110,actual_rendered_page_count:null,render_status:'NOT VERIFIED',source_handbook_edition:'0.9.1',retained_sha256:originalHashes,checks};
await fs.writeFile(out+'/source.json',JSON.stringify(book,null,2)+'\n');
let md='# '+title+'\n\n'+subtitle+'\n\nUpdated '+date+'\n\n';
for(const [i,s]of sections.entries()){
 md+='## '+(i+1)+' '+s.title+'\n\nWhere: '+s.where+'\n\n'+s.intro+'\n\n'+s.steps.map((v,j)=>(j+1)+'. '+v).join('\n')+'\n\nCheck: '+s.check+'\n\nNext: '+s.next+'\n\n';
 if(s.shot){const shot=shots.find(x=>x.figure===s.shot);md+='!['+shot.caption+'](../screenshots/'+shot.file+')\n\n'+shot.caption+'\n\n';}
}
await fs.writeFile(out+'/handbook.md',md);
console.log(JSON.stringify({sections:book.sections,body_words:words,screenshots:book.screenshots,designed_pages:pages.length,actual_pages:'NOT VERIFIED'},null,2));
