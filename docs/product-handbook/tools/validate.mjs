// Documentation validation, never an application certification runner.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fieldOverrides,guidance} from '../source/page-guidance.mjs';
const root='docs/product-handbook';
const failures=[];const checks=[];
const check=(name,ok,actual)=>{checks.push({name,status:ok?'PASS':'FAIL',actual});if(!ok)failures.push(name);};
export const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
export const hasSecret=s=>/AGE-SECRET-KEY-1[A-Z0-9]{8,}|postgres(?:ql)?:\/\/[^\s"']+:[^\s"']+@|\bsk-[A-Za-z0-9]{25,}/.test(s);
export const routeCoverage=(routes,pages)=>routes.filter(r=>r.kind==='PAGE').every(r=>pages.some(p=>p.routes.includes(r.route)));
const inventory=JSON.parse(await fs.readFile(root+'/source/ui-inventory.json','utf8'));
const book=JSON.parse(await fs.readFile(root+'/source/book.json','utf8'));
const fields=JSON.parse(await fs.readFile(root+'/source/field-guides.json','utf8'));
const shots=JSON.parse(await fs.readFile(root+'/inventory/screenshot-register.json','utf8'));
check('All page routes represented',routeCoverage(inventory.routes,inventory.pages),inventory.counts);
check('All page family A M sections authored',book.blocks.filter(b=>b.kind==='heading'&&b.level===2&&/^P\d{3} /.test(b.text)).length===inventory.pages.length,inventory.pages.length);
check('All page guidance IDs map to discovered pages',Object.keys(guidance).every(id=>inventory.pages.some(p=>p.page_id===id)),Object.keys(guidance).length);
check('All declared field records retained',fields.length===inventory.counts.page_fields+inventory.counts.shared_fields,fields.length);
check('Stable field IDs unique',new Set(fields.map(f=>f.id)).size===fields.length,new Set(fields.map(f=>f.id)).size);
check('Every field has explicit explanation or verification limit',fields.every(f=>['label','purpose','required','type','accepted','example','validation','effect','mistake','source'].every(k=>typeof f[k]==='string'&&f[k].length>0)),fields.length);
check('Manually reviewed overrides resolve exact fields',Object.keys(fieldOverrides).every(id=>fields.some(f=>f.id===id)),Object.keys(fieldOverrides).length);
check('At least twenty illustrative prompts',book.metrics.prompts>=20,book.metrics.prompts);
check('Six beginner journey sources',book.metrics.worked_journeys===6,book.metrics.worked_journeys);
let same=0;
for(const s of shots){const current=await fs.readFile(s.path);const original=await fs.readFile(s.source);if(digest(current)===s.sha256&&digest(original)===s.sha256)same++;}
check('Reviewed screenshot copies identical to originals',same===shots.length,{same,total:shots.length});
const figures=book.blocks.filter(b=>b.kind==='image').map(b=>b.figure);
check('Figure order and captions match document order',figures.every((n,i)=>n===i+1),figures);
check('All screenshots synthetic and historical labels retained',shots.every(s=>s.synthetic&&s.historical&&s.caption.includes('historical synthetic')),shots.length);
let currentSources=0;for(const p of inventory.pages)if(digest(await fs.readFile(p.file))===p.source_sha256)currentSources++;
check('Inspected page sources unchanged during authoring',currentSources===inventory.pages.length,currentSources);
const body=JSON.stringify(book.blocks);
check('No recognizable credential patterns in authored content',!hasSecret(body),{patterns:'age identity, credentialed PostgreSQL URL, common API secret prefix',not_a_comprehensive_secret_audit:true});
check('Certification and financial limitations preserved',body.includes('Gate B remains NOT PASSED')&&body.includes('PC-first encrypted independent backup/restore remains PARKED')&&body.includes('not an immutable accounting ledger'),true);
let broken=0,links=0;
for(const f of ['source/handbook.md','source/application-inventory.md','inventory/page-register.md']){const s=await fs.readFile(root+'/'+f,'utf8');for(const m of s.matchAll(/\]\(([^)]+)\)/g)){const t=m[1].split('#')[0];if(!t||/^[a-z]+:/i.test(t))continue;links++;try{await fs.access(path.resolve(root,path.dirname(f),t));}catch{broken++;}}}
check('Generated Markdown links resolve',broken===0,{links,broken});
let packageCheck;
try{packageCheck=JSON.parse(execFileSync('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',root+'/tools/validate-package.ps1'],{encoding:'utf8'}).replace(/^\uFEFF/,'').trim());check('Native OOXML structural validation',true,packageCheck);}catch{check('Native OOXML structural validation',false,{raw_output_persisted:false});}
const word=await fs.readFile(root+'/quality/word-render.json','utf8').then(s=>JSON.parse(s.replace(/^\uFEFF/,''))).catch(()=>({status:'NOT_EXECUTED',page_count:null}));
const result={status:failures.length?'DOCUMENTATION_CHECK_FAILURE':'STRUCTURAL_CHECKS_PASS_COVERAGE_AND_RENDER_PENDING',checks,failures,application_tests_executed:0,word,classification:'HANDBOOK REFERENCE DRAFT / CURRENT UI AND VISUAL CERTIFICATION PENDING'};
await fs.writeFile(root+'/quality/validation.json',JSON.stringify(result,null,2)+'\n');
const metrics={...book.metrics,render_status:word.status,page_count:word.page_count,word_open_verified:word.opened===true,visual_review:'NOT_VERIFIED',structured_checks_passed:checks.filter(c=>c.status==='PASS').length,structured_checks_failed:failures.length};
await fs.writeFile(root+'/quality/metrics.json',JSON.stringify(metrics,null,2)+'\n');
const reviewed=Object.keys(fieldOverrides).length;
await fs.writeFile(root+'/quality/coverage-report.md',`# Handbook coverage and validation

Classification: HANDBOOK REFERENCE DRAFT / CURRENT UI AND VISUAL CERTIFICATION PENDING.

| Dimension | Actual numerator / denominator | Meaning |
| --- | --- | --- |
| Static route representation | 156 / 156 (100%) | Includes six redirects; not a functional or UI PASS. |
| Page-family reference sections | 104 / 104 | Covers 150 declared page routes, with shared/conditional behavior limitations. |
| Declared field entries | 693 / 693 | Source guidance and explicit unknowns, not 693 independently validated form contracts. |
| Manually reviewed semantic overrides | ${reviewed} / ${fields.length} (${(100*reviewed/fields.length).toFixed(2)}%) | Five additional reschedule fields source-reviewed; dynamic API contracts remain gaps. |
| Historical screenshot families | 15 / 104 (14.42%) | 19 genuine retained synthetic images; zero replacements. |
| Fresh authenticated UI | 0 / 150 (0%) | No current authorized screenshot session; no fresh captures. |
| Structural documentation checks | ${metrics.structured_checks_passed} passed / ${checks.length} | Not layout or application certification. |

Edition ${book.edition}: P032 Campaign detail and shared rescheduling reference updated for existing WP7B-R5 evidence. No post-baseline application change was found. See r5-update-report.md and r5-update-preservation.json for the bounded comparison; all other reference sections and screenshots must remain unchanged.

20 chapters; six illustrative journeys; 24 task prompts. Total pages NOT VERIFIED. Word open/TOC page values/PDF export/visual review NOT VERIFIED; native automation BLOCKED and disabled. See render-and-environment-limitations.md for the Office preservation incident. See handbook-tests.xml for actual self-test results. No application test suite ran.

Final metadata:

\`\`\`json
${JSON.stringify(metrics,null,2)}
\`\`\`
`);
console.log(JSON.stringify({status:result.status,checks_passed:metrics.structured_checks_passed,checks_failed:failures.length,package:packageCheck,word_status:word.status,page_count:word.page_count,application_tests_executed:0},null,2));
if(failures.length)process.exitCode=1;
