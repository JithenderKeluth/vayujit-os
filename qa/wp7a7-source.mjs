// Fingerprints only: no environment, configuration contents, credentials or output bodies.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
export async function sourceFingerprint() {
  const files=[];
  const walk=async root=>{for(const item of await fs.readdir(root,{withFileTypes:true})) {
    const name=root+'/'+item.name;
    if(item.isDirectory() && !['__pycache__','node_modules','.venv'].includes(item.name)) await walk(name);
    else if(item.isFile() && /\.(?:py|ts|mjs|js|css|html)$/.test(item.name)) files.push(name);
  }};
  for(const root of ['apps/api/vayujit_api','apps/web/src','dist/apps/web/browser','qa']) await walk(root);
  const result={};
  for(const name of files.sort()) result[name]=crypto.createHash('sha256').update(await fs.readFile(name)).digest('hex');
  return result;
}
