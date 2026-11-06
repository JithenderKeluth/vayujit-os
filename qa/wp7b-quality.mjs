// Fixed local commands; output held in memory, never raw diagnostics/credentials.
import {spawnSync} from 'node:child_process';
import fs from 'node:fs/promises';
const r1=process.env.QA_ASSESSMENT_PACKAGE==='WP7BR1',root=r1?'tmp/qa-wp7br1':'tmp/qa-wp7b';
const commands=[['node','npm.cmd run qa:unit'],['python','apps/api/.venv/Scripts/python.exe -m pytest qa/unit -q'],['angular','npm.cmd run test --workspace @vayujit/web'],['lint','npx.cmd eslint apps/web/src/app/marketplaces/marketplace-accounts.component.ts apps/web/src/app/marketplaces/meesho-workspace.component.ts apps/web/src/app/ads/ads-optimization.component.ts'],['types','npx.cmd tsc -p apps/web/tsconfig.app.json --noEmit'],['mypy_ads','apps/api/.venv/Scripts/mypy.exe --strict --config-file apps/api/pyproject.toml apps/api/vayujit_api/ads/router.py apps/api/vayujit_api/ads/service.py'],['build','npm.cmd run build --workspace @vayujit/web'],['diff','git -c safe.directory=C:/Users/jithe/Documents/vayujit-os diff --check']];
commands.splice(4,0,['lint_specs','npx.cmd eslint apps/web/src/app/marketplaces/marketplace-accounts.component.spec.ts apps/web/src/app/marketplaces/meesho-workspace.component.spec.ts apps/web/src/app/ads/ads-optimization.component.spec.ts'],['lint_web','npm.cmd run lint --workspace @vayujit/web'],['types_spec','npx.cmd tsc -p apps/web/tsconfig.spec.json --noEmit'],['ruff_ads','apps/api/.venv/Scripts/ruff.exe check apps/api/vayujit_api/ads/router.py apps/api/vayujit_api/ads/service.py'],['black_ads','apps/api/.venv/Scripts/black.exe --check apps/api/vayujit_api/ads/router.py apps/api/vayujit_api/ads/service.py'],['compile_ads','apps/api/.venv/Scripts/python.exe -m compileall -q apps/api/vayujit_api/ads']);
if(r1)for(const c of commands){
 if(c[0]==='lint')c[1]+=' apps/web/src/app/intelligence/business-agent-workspace.component.ts';
 if(c[0]==='lint_specs')c[1]+=' apps/web/src/app/intelligence/business-agent-workspace.component.spec.ts';
 if(['mypy_ads','ruff_ads'].includes(c[0]))c[1]+=' apps/api/vayujit_api/ads/optimization.py qa/wp7br1_diagnostics.py apps/api/tests/test_seller_wp7br1.py';
 if(c[0]==='black_ads')c[1]+=' qa/wp7br1_diagnostics.py apps/api/tests/test_seller_wp7br1.py';
 if(c[0]==='black_ads')c[1]+=' --config apps/api/pyproject.toml';
 if(c[0]==='compile_ads')c[1]+=' qa/wp7br1_diagnostics.py';
}
if(r1)commands.splice(commands.findIndex(c=>c[0]==='black_ads')+1,0,['black_changed_ads_functions','apps/api/.venv/Scripts/black.exe --config apps/api/pyproject.toml --check --line-ranges 104-135 --line-ranges 1036-1210 apps/api/vayujit_api/ads/optimization.py']);
const report={package:r1?'WP7B-R1':'WP7B',started_at:new Date().toISOString(),raw_output_persisted:false,checks:[]};
await fs.mkdir(root,{recursive:true});
for(const [id,command]of commands){const r=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',command],{encoding:'utf8',windowsHide:true,timeout:900000,maxBuffer:8*1024*1024});const text=(r.stdout||'')+(r.stderr||'');const passed=id==='node'?/pass (\d+)/.exec(text)?.[1]:id==='python'?/(\d+) passed/.exec(text)?.[1]:id==='angular'?/Tests\s+(\d+) passed/.exec(text)?.[1]:null;const row={id,command,exit_code:r.status,status:r.status===0?'PASS':'FAIL',...(passed?{passed:Number(passed)}:{})};report.checks.push(row);await fs.writeFile(root+'/quality-'+report.started_at.replace(/[^0-9TZ]/g,'')+'.json',JSON.stringify(report,null,2));console.log(JSON.stringify(row));}
report.completed_at=new Date().toISOString();await fs.writeFile(root+'/quality.json',JSON.stringify(report,null,2));process.exitCode=report.checks.every(c=>c.status==='PASS')?0:1;
