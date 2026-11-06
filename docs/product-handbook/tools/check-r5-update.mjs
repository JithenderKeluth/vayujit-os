// Documentation-only preservation evidence. Does not start the application.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
const root='docs/product-handbook';
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
const read=async file=>JSON.parse(await fs.readFile(root+'/'+file,'utf8'));
function sections(book){
 const result={};let chapter='',section='',blocks=[];
 const flush=()=>{if(blocks.length)result[chapter+'/'+section]=hash(JSON.stringify(blocks));blocks=[];};
 for(const block of book.blocks){
  if(block.kind==='heading'&&block.level===1){flush();chapter=block.text;section='';}
  if(block.kind==='heading'&&block.level===2){flush();section=block.text;}
  blocks.push(block);
 }
 flush();return result;
}
async function snapshot(updated=false){
 const book=await read('source/book.json');
 const shots=await read('inventory/screenshot-register.json');
 return {edition:book.edition,sections:sections(book),fields:Object.fromEntries((await read('source/field-guides.json')).map(f=>[f.id,hash(JSON.stringify(f))])),screenshots:Object.fromEntries(await Promise.all(shots.map(async s=>[s.path,hash(await fs.readFile(s.path))]))),inventory_sha256:hash(await fs.readFile(root+'/source/ui-inventory.json')),word_sha256:hash(await fs.readFile(root+(updated?'/VAYUJIT_OS_Complete_Product_Handbook_Reference_Draft_0_9_1.docx':'/VAYUJIT_OS_Complete_Product_Handbook_Reference_Draft.docx')))};
}
const baselinePath=root+'/quality/r5-update-baseline.json';
if(process.argv[2]==='baseline'){
 await fs.writeFile(baselinePath,JSON.stringify(await snapshot(),null,2)+'\n',{flag:'wx'});
 console.log('Preserved documentation baseline; no application or QA operations.');
}else if(process.argv[2]==='verify'){
 const before=JSON.parse(await fs.readFile(baselinePath,'utf8'));const after=await snapshot(true);
 const changed=(a,b)=>[...new Set([...Object.keys(a),...Object.keys(b)])].filter(k=>a[k]!==b[k]);
 const changedSections=changed(before.sections,after.sections);
 const changedFields=changed(before.fields,after.fields);
 const unexpectedSections=changedSections.filter(k=>!['Page by page reference/P032 Campaign detail','Shared controls and field reference/reschedule dialog','Edition evidence and maintenance/'].includes(k));
 const unexpectedFields=changedFields.filter(k=>!/^reschedule-dialog-F00[1-5]$/.test(k));
 const result={status:'PASS',target_package:'WP7B-R5',documentation_edition:after.edition,changed_sections:changedSections,changed_fields:changedFields,unexpected_sections:unexpectedSections,unexpected_fields:unexpectedFields,screenshots_replaced:changed(before.screenshots,after.screenshots),screenshots_preserved:Object.keys(after.screenshots).length,inventory_unchanged:before.inventory_sha256===after.inventory_sha256,word_regenerated:before.word_sha256!==after.word_sha256,fresh_screenshots:0,application_tests_executed:0,current_ui_verification:'NOT VERIFIED',visual_layout_verification:'NOT VERIFIED'};
 result.previous_word_unchanged=hash(await fs.readFile(root+'/VAYUJIT_OS_Complete_Product_Handbook_Reference_Draft.docx'))===before.word_sha256;
 if(unexpectedSections.length||unexpectedFields.length||result.screenshots_replaced.length||!result.inventory_unchanged||!result.word_regenerated||!result.previous_word_unchanged)result.status='FAIL';
 await fs.writeFile(root+'/quality/r5-update-preservation.json',JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify(result,null,2));if(result.status==='FAIL')process.exitCode=1;
}else throw Error('Expected baseline or verify.');
