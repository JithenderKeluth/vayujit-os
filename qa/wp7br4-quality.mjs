import {spawnSync} from 'node:child_process';
import fs from 'node:fs/promises';
const commands=[
 ['angular_auth','npm.cmd run test --workspace @vayujit/web -- --include=src/app/auth/*.spec.ts'],
 ['eslint_auth','npx.cmd --no-install eslint apps/web/src/app/auth/auth-page.component.ts apps/web/src/app/auth/auth-focus-r4.spec.ts'],
 ['ts_app','npx.cmd --no-install tsc -p apps/web/tsconfig.app.json --noEmit'],
 ['ts_spec','npx.cmd --no-install tsc -p apps/web/tsconfig.spec.json --noEmit'],
 ['prettier_auth','npx.cmd --no-install prettier --check apps/web/src/app/auth/auth-page.component.ts apps/web/src/app/auth/auth-focus-r4.spec.ts'],
 ['qa_focused','node --test qa/unit/wp7br1-contrast.test.mjs qa/unit/wp7br1-startup.test.mjs'],
 ['diff','git -c safe.directory=C:/Users/jithe/Documents/vayujit-os diff --check'],
];
const report={package:'WP7B-R4',at:new Date().toISOString(),raw_output_persisted:false,checks:[]};
for(const [id,command]of commands){const r=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',command],{encoding:'utf8',windowsHide:true,timeout:300000,maxBuffer:4*1024*1024});const text=(r.stdout||'')+(r.stderr||'');
 const count=id==='angular_auth'?/Tests\s+(\d+) passed/.exec(text)?.[1]:id==='qa_focused'?/pass (\d+)/.exec(text)?.[1]:null;
 report.checks.push({id,command,status:r.status===0?'PASS':'FAIL',exit:r.status,...(count?{passed:Number(count)}:{})});
 await fs.writeFile('tmp/qa-wp7br4/quality.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report.checks.at(-1)));
}
process.exitCode=report.checks.every(r=>r.status==='PASS')?0:1;
