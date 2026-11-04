// Fixed installed tools only; captured output never persisted (may contain secrets).
import fs from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
const py = 'apps/api/.venv/Scripts/python.exe';
const backend = 'apps/api/vayujit_api/commerce/amazon_router.py';
const tests =
  'apps/api/tests/test_seller_wp7a6.py apps/api/tests/test_pr_sos_02_amazon_controls.py';
const frontend =
  'apps/web/src/app/social/social-workspace.component.ts apps/web/src/app/social/social.service.ts apps/web/src/app/social/social-workspace.component.spec.ts';
const qa =
  'qa/wp7a6_snapshot.py qa/wp7a6_final_audit.py qa/wp7a4_final_audit.py qa/wp4_final_audit.py qa/wp7a_fixture.py qa/wp7a2_fixture.py qa/wp7a3_fixture.py qa/wp7a4_fixture.py qa/fixture_server.py';
const checks = [
  ['node_qa', 'npm.cmd run qa:unit'],
  ['python_qa', `${py} -m pytest qa/unit -q`],
  ['angular', 'npm.cmd run test --workspace @vayujit/web'],
  ['build', 'npm.cmd run build --workspace @vayujit/web'],
  ['lint', `npx.cmd eslint ${frontend}`],
  ['typescript_app', 'npx.cmd tsc -p apps/web/tsconfig.app.json --noEmit'],
  ['typescript_spec', 'npx.cmd tsc -p apps/web/tsconfig.spec.json --noEmit'],
  [
    'mypy',
    `apps/api/.venv/Scripts/mypy.exe --strict --config-file apps/api/pyproject.toml ${backend}`,
  ],
  ['ruff', `apps/api/.venv/Scripts/ruff.exe check ${backend} ${tests} ${qa}`],
  [
    'black_backend',
    `apps/api/.venv/Scripts/black.exe --check --config apps/api/pyproject.toml ${backend} ${tests}`,
  ],
  ['black_qa', `apps/api/.venv/Scripts/black.exe --check ${qa}`],
  ['compile', `${py} -m compileall -q ${backend} ${tests} ${qa}`],
  [
    'parser',
    "$tokens=$null; $errors=$null; [void][Management.Automation.Language.Parser]::ParseFile((Join-Path (Get-Location) 'scripts/test-seller-wp7a6.ps1'),[ref]$tokens,[ref]$errors); if($errors.Count){exit 1}; node --check qa/wp7a6-scenarios.mjs; if($LASTEXITCODE){exit $LASTEXITCODE}; node --check qa/wp7a6-safety.mjs; exit $LASTEXITCODE",
  ],
  ['diff', 'git -c safe.directory=C:/Users/jithe/Documents/vayujit-os diff --check'],
];
const report = { started_at: new Date().toISOString(), raw_output_persisted: false, checks: [] };
try {
  const previous = JSON.parse(await fs.readFile('tmp/qa-wp7a6/quality.json', 'utf8'));
  await fs.writeFile(
    'tmp/qa-wp7a6/quality-' + previous.started_at.replaceAll(/[^0-9TZ]/g, '') + '.json',
    JSON.stringify(previous, null, 2),
    { flag: 'wx' },
  );
} catch (error) {
  if (!['ENOENT', 'EEXIST'].includes(error.code)) throw error;
}
for (const [id, command] of checks) {
  const r = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', command], {
    windowsHide: true,
    encoding: 'utf8',
    timeout: 900000,
    maxBuffer: 16 * 1024 * 1024,
  });
  const out = (r.stdout || '') + (r.stderr || '');
  const count =
    id === 'angular'
      ? /Tests\s+(\d+) passed/.exec(out)?.[1]
      : id === 'node_qa'
        ? /pass (\d+)/.exec(out)?.[1]
        : id === 'python_qa'
          ? /(\d+) passed/.exec(out)?.[1]
          : undefined;
  const row = {
    id,
    command,
    exit_code: r.status,
    status: r.status === 0 ? 'PASS' : 'FAIL',
    ...(count ? { passed: Number(count) } : {}),
  };
  report.checks.push(row);
  await fs.writeFile('tmp/qa-wp7a6/quality.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(row));
}
report.completed_at = new Date().toISOString();
await fs.writeFile('tmp/qa-wp7a6/quality.json', JSON.stringify(report, null, 2));
process.exitCode = report.checks.every((c) => c.status === 'PASS') ? 0 : 1;
