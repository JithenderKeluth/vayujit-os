// Fixed local checks only. Persist outcomes/counts, never raw subprocess output or environment.
import fs from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
const python = 'apps/api/.venv/Scripts/python.exe';
const backend = [
  'ai/bulk_service.py',
  'ai/studio_worker.py',
  'ai/studio_router.py',
  'ai/seo_router.py',
  'video/bulk.py',
  'video/channels.py',
  'intelligence/trend_router.py',
]
  .map((v) => 'apps/api/vayujit_api/' + v)
  .join(' ');
const frontend = [
  'ai/ai-wp7a5.spec.ts',
  'ai/ai-seo.component.ts',
  'campaigns/campaign-video.component.ts',
  'ai/ai-video.component.ts',
  'ai/ai-video-bulk.component.ts',
  'ai/ai-image-review.component.ts',
  'social/social.service.ts',
  'social/social-workspace.component.ts',
  'social/social-workspace.component.spec.ts',
  'ads/marketing-plan.component.ts',
  'ads/marketing-plan.component.spec.ts',
  'ai/ai-image-review.component.spec.ts',
  'ai/ai.service.ts',
  'intelligence/trend-intelligence.service.ts',
  'intelligence/trend-intelligence-workspace.component.ts',
  'intelligence/trend-intelligence-workspace.component.spec.ts',
]
  .map((v) => 'apps/web/src/app/' + v)
  .join(' ');
const qa =
  'qa/wp7a5_snapshot.py qa/wp7a5_lifecycle_status.py qa/wp7a5_recover_approved.py qa/wp7a5_final_audit.py qa/wp4_final_audit.py qa/wp7a4_final_audit.py';
const checks = [
  ['node_qa', 'npm.cmd run qa:unit'],
  ['python_qa', `${python} -m pytest qa/unit -q`],
  ['angular', 'npm.cmd run test --workspace @vayujit/web'],
  ['build', 'npm.cmd run build --workspace @vayujit/web'],
  ['lint', `npx.cmd eslint ${frontend}`],
  ['typescript_app', 'npx.cmd tsc -p apps/web/tsconfig.app.json --noEmit'],
  ['typescript_spec', 'npx.cmd tsc -p apps/web/tsconfig.spec.json --noEmit'],
  [
    'mypy',
    `apps/api/.venv/Scripts/mypy.exe --strict --config-file apps/api/pyproject.toml ${backend}`,
  ],
  [
    'ruff',
    `apps/api/.venv/Scripts/ruff.exe check ${backend} apps/api/tests/test_seller_wp7a5.py ${qa}`,
  ],
  [
    'black_backend',
    `apps/api/.venv/Scripts/black.exe --check --config apps/api/pyproject.toml ${backend} apps/api/tests/test_seller_wp7a5.py apps/api/tests/test_ai_video_bulk_e2e.py apps/api/tests/test_trend_analysis_api.py`,
  ],
  ['black_qa', `apps/api/.venv/Scripts/black.exe --check ${qa}`],
  [
    'compile',
    `${python} -m compileall -q qa apps/api/vayujit_api/ai apps/api/vayujit_api/video apps/api/vayujit_api/intelligence/trend_router.py`,
  ],
  [
    'parser',
    "$tokens=$null; $errors=$null; [void][Management.Automation.Language.Parser]::ParseFile((Join-Path (Get-Location) 'scripts/test-seller-wp7a5.ps1'),[ref]$tokens,[ref]$errors); if($errors.Count){exit 1}; node --check qa/wp7a5-scenarios.mjs; if($LASTEXITCODE){exit $LASTEXITCODE}; node --check qa/wp7a5-safety.mjs; exit $LASTEXITCODE",
  ],
  ['diff', 'git -c safe.directory=C:/Users/jithe/Documents/vayujit-os diff --check'],
];
const report = { started_at: new Date().toISOString(), raw_output_persisted: false, checks: [] };
try {
  const previous = JSON.parse(await fs.readFile('tmp/qa-wp7a5/quality.json', 'utf8'));
  await fs.writeFile(
    'tmp/qa-wp7a5/quality-' + previous.started_at.replaceAll(/[^0-9TZ]/g, '') + '.json',
    JSON.stringify(previous, null, 2),
    { flag: 'wx' },
  );
} catch (error) {
  if (!['ENOENT', 'EEXIST'].includes(error.code)) throw error;
}
for (const [id, command] of checks) {
  const start = Date.now();
  const result = spawnSync(
    'powershell.exe',
    ['-NoProfile', '-NonInteractive', '-Command', command],
    {
      encoding: 'utf8',
      windowsHide: true,
      timeout: 900000,
      maxBuffer: 16 * 1024 * 1024,
    },
  );
  const output = (result.stdout || '') + (result.stderr || '');
  const count =
    id === 'angular'
      ? /Tests\s+(\d+) passed/.exec(output)?.[1]
      : id === 'node_qa'
        ? /pass (\d+)/.exec(output)?.[1]
        : id === 'python_qa'
          ? /(\d+) passed/.exec(output)?.[1]
          : undefined;
  const row = {
    id,
    command,
    exit_code: result.status,
    status: result.status === 0 ? 'PASS' : 'FAIL',
    duration_seconds: (Date.now() - start) / 1000,
    ...(count ? { passed: Number(count) } : {}),
    reported_error_lines: (output.match(/\berror\b/gi) || []).length,
  };
  report.checks.push(row);
  await fs.writeFile('tmp/qa-wp7a5/quality.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(row));
}
report.completed_at = new Date().toISOString();
await fs.writeFile('tmp/qa-wp7a5/quality.json', JSON.stringify(report, null, 2));
process.exitCode = report.checks.every((r) => r.status === 'PASS') ? 0 : 1;
