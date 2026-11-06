// Correct the explicit formatter config, without rewriting historical results.
import fs from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
const checks=[
 ['node_after_sampler','npm.cmd run qa:unit'],
 ['black_configured','apps/api/.venv/Scripts/black.exe --config apps/api/pyproject.toml --check apps/api/vayujit_api/ads/router.py apps/api/vayujit_api/ads/service.py qa/wp7br1_diagnostics.py apps/api/tests/test_seller_wp7br1.py scripts/wp7br1-final-audit.py'],
 ['black_changed_functions','apps/api/.venv/Scripts/black.exe --config apps/api/pyproject.toml --check --line-ranges 104-135 --line-ranges 1036-1210 apps/api/vayujit_api/ads/optimization.py'],
 ['ruff_changed','apps/api/.venv/Scripts/ruff.exe check apps/api/vayujit_api/ads/optimization.py qa/wp7br1_diagnostics.py apps/api/tests/test_seller_wp7br1.py scripts/wp7br1-final-audit.py'],
 ['mypy_changed','apps/api/.venv/Scripts/mypy.exe --strict --config-file apps/api/pyproject.toml apps/api/vayujit_api/ads/router.py apps/api/vayujit_api/ads/service.py apps/api/vayujit_api/ads/optimization.py qa/wp7br1_diagnostics.py apps/api/tests/test_seller_wp7br1.py'],
 ['prettier_angular','npx.cmd prettier --check apps/web/src/app/ads/ads-optimization.component.ts apps/web/src/app/intelligence/business-agent-workspace.component.ts apps/web/src/app/intelligence/business-agent-workspace.component.spec.ts'],
 ['compile','apps/api/.venv/Scripts/python.exe -m compileall -q apps/api/vayujit_api/ads qa/fixture_server.py qa/wp7br1_diagnostics.py scripts/wp7br1-final-audit.py'],
 ['diff','git -c safe.directory=C:/Users/jithe/Documents/vayujit-os diff --check']
];
const report={package:'WP7B-R1',started_at:new Date().toISOString(),raw_output_persisted:false,scope:'Supplement to retained quality.json; formatter uses canonical API config and changed Ads function ranges, not a broad historical rewrite',checks:[]};
for(const[id,command]of checks){const r=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',command],{encoding:'utf8',windowsHide:true,timeout:180000,maxBuffer:2*1024*1024});const passed=id==='node_after_sampler'?/pass (\d+)/.exec((r.stdout||'')+(r.stderr||''))?.[1]:null;const row={id,command,exit_code:r.status,status:r.status===0?'PASS':'FAIL',...(passed?{passed:Number(passed)}:{})};report.checks.push(row);console.log(JSON.stringify(row));}
report.completed_at=new Date().toISOString();await fs.writeFile('tmp/qa-wp7br1/quality-supplement.json',JSON.stringify(report,null,2));process.exitCode=report.checks.every(x=>x.status==='PASS')?0:1;
