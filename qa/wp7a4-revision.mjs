import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
const files=[];
async function walk(root){for(const e of await fs.readdir(root,{withFileTypes:true})){const p=path.join(root,e.name);if(e.isDirectory())await walk(p);else if(e.isFile()&&/\.(ts|py|css|html|js|json)$/.test(p))files.push(p);}}
await walk('apps/web/src');await walk('apps/api/vayujit_api');await walk('dist/apps/web/browser');
files.push('package-lock.json','apps/api/pyproject.toml','packages/shared/src/index.ts');
const rows=[];for(const file of files.sort())rows.push({file:file.replaceAll('\\','/'),sha256:crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')});
const git=(...a)=>execFileSync('git',['-c','safe.directory='+process.cwd().replaceAll('\\','/'),...a],{encoding:'utf8',windowsHide:true});
const record={captured_at:new Date().toISOString(),head:git('rev-parse','HEAD').trim(),dirty:true,changed_path_count:git('status','--porcelain','--untracked-files=all').split('\n').filter(Boolean).length,files:rows,node:process.version};
await fs.writeFile('tmp/qa-wp7a4/revision-'+(process.argv[2]||'before')+'.json',JSON.stringify(record,null,2));
console.log(JSON.stringify({head:record.head,files:rows.length,node:record.node,dirty:true}));
