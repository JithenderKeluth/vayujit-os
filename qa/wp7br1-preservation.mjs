import fs from 'node:fs/promises';import crypto from 'node:crypto';
const files=['assessment-report.md','gate.json','manual-accessibility-evidence.md','accessibility-inventory.md','residual-risk-register.md','certification-provenance.md'].map(n=>'docs/qa/seller-experience/wp7b-'+n);
for(const token of ['071d1158209292db','66af017c1429b89e'])files.push('tmp/qa-seller-browser/'+token+'/wp7b-browser.json');
const destination='tmp/qa-wp7br1/preserved-wp7b.json';
const hash=async f=>crypto.createHash('sha256').update(await fs.readFile(f)).digest('hex');
if(process.argv.includes('--record')){try{await fs.access(destination);throw Error('PRESERVATION_BASELINE_ALREADY_EXISTS');}catch(e){if(e.code!=='ENOENT')throw e;}const rows=[];for(const file of files)rows.push({file,sha256:await hash(file)});await fs.writeFile(destination,JSON.stringify({package:'WP7B-R1',files:rows},null,2));console.log(JSON.stringify({recorded:rows.length}));}
else{const r=JSON.parse(await fs.readFile(destination,'utf8'));const changed=[];for(const item of r.files)if(await hash(item.file)!==item.sha256)changed.push(item.file);console.log(JSON.stringify({files:r.files.length,unchanged:!changed.length,changed}));process.exitCode=changed.length?1:0;}
