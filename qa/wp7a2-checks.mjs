// Scoped quality execution. Store counts and source locations, never raw output.
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
const python = path.resolve('apps/api/.venv/Scripts/python.exe');
const py = [
  'qa/wp7a2_fixture.py',
  'qa/wp7a2_reconstruct.py',
  'qa/wp7a2_recover.py',
  'qa/wp7a2-typing-review.py',
  'qa/unit/test_wp7a2_recovery.py',
  'qa/wp7a2_final_audit.py',
  'qa/wp4_final_audit.py',
  'apps/api/tests/test_seller_wp7a2.py',
  'apps/api/tests/test_ads_failure_acceptance.py',
  'apps/api/vayujit_api/video/service.py',
  'apps/api/vayujit_api/ads/router.py',
  'apps/api/vayujit_api/ads/service.py',
];
const js = [
  'qa/wp7a2-browser.mjs',
  'qa/wp7a2-safety.mjs',
  'qa/wp7a2-baseline.mjs',
  'qa/wp7a2-checks.mjs',
  'qa/wp7a2-sanitize-evidence.mjs',
  'qa/wp7a2-report.mjs',
  'qa/wp7-run.mjs',
  'qa/unit/wp7a2-safety.test.mjs',
];
const jobs = [
  ['node-qa', process.execPath, ['--test', '--test-reporter=tap', 'qa/unit/*.test.mjs']],
  ['python-qa', python, ['-m', 'unittest', 'discover', '-s', 'qa/unit', '-p', 'test_*.py']],
  [
    'production-build',
    process.execPath,
    ['../../node_modules/@angular/cli/bin/ng.js', 'build', '--configuration', 'production'],
    'apps/web',
  ],
  [
    'angular',
    process.execPath,
    ['../../node_modules/@angular/cli/bin/ng.js', 'test', '--watch=false'],
    'apps/web',
  ],
  [
    'typescript-app',
    process.execPath,
    ['node_modules/typescript/bin/tsc', '--noEmit', '-p', 'apps/web/tsconfig.app.json'],
  ],
  [
    'typescript-spec',
    process.execPath,
    ['node_modules/typescript/bin/tsc', '--noEmit', '-p', 'apps/web/tsconfig.spec.json'],
  ],
  [
    'eslint-web',
    process.execPath,
    ['../../node_modules/eslint/bin/eslint.js', 'src/**/*.ts', '--format', 'json'],
    'apps/web',
  ],
  [
    'eslint-qa',
    process.execPath,
    ['node_modules/eslint/bin/eslint.js', '--config', 'qa/eslint.config.mjs', ...js],
  ],
  ['ruff', python, ['-m', 'ruff', 'check', '--config', 'apps/api/pyproject.toml', ...py]],
  ['black', python, ['-m', 'black', '--check', '--config', 'apps/api/pyproject.toml', ...py]],
  ...['video/service.py', 'ads/router.py', 'ads/service.py'].map((f) => [
    'mypy-' + f,
    python,
    [
      '-m',
      'mypy',
      '--strict',
      '--follow-imports=skip',
      '--config-file',
      'apps/api/pyproject.toml',
      'apps/api/vayujit_api/' + f,
    ],
  ]),
  ['compileall', python, ['-m', 'compileall', '-q', ...py]],
  [
    'powershell-parser',
    'powershell.exe',
    [
      '-NoProfile',
      '-NonInteractive',
      '-Command',
      "$e=$null;$t=$null;[System.Management.Automation.Language.Parser]::ParseFile((Join-Path (Get-Location) 'scripts/test-seller-wp7a2.ps1'),[ref]$t,[ref]$e)|Out-Null;if($e.Count){exit 1}",
    ],
  ],
  [
    'diff-check',
    'git',
    ['-c', 'safe.directory=' + process.cwd().replaceAll('\\', '/'), 'diff', '--check'],
  ],
];
const rows = [];
await fs.mkdir('tmp/qa-wp7a2', { recursive: true });
const postAudit = process.argv.includes('--post-audit');
const destination =
  'tmp/qa-wp7a2/' + (postAudit ? 'post-audit-' : 'quality-') + Date.now() + '.json';
for (const [name, command, args, cwd] of jobs.filter(
  ([name]) =>
    !postAudit ||
    [
      'node-qa',
      'production-build',
      'python-qa',
      'eslint-qa',
      'ruff',
      'black',
      'compileall',
      'powershell-parser',
      'diff-check',
    ].includes(name),
)) {
  const child = spawn(command, args, {
    cwd: cwd || process.cwd(),
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let output = '';
  child.stdout.on('data', (d) => (output += d));
  child.stderr.on('data', (d) => (output += d));
  const code = await new Promise((r) => {
    child.once('error', () => r(-1));
    child.once('exit', r);
  });
  const clean = output.replace(new RegExp(String.fromCharCode(27) + '\\[[0-9;]*m', 'g'), '');
  const row = {
    name,
    status: code === 0 ? 'PASS' : 'FAIL',
    exit_code: code,
    raw_output_persisted: false,
  };
  if (name === 'node-qa')
    for (const key of ['tests', 'pass', 'fail', 'skipped'])
      row[key] = Number(clean.match(new RegExp(`# ${key} (\\d+)`))?.[1] ?? -1);
  if (name === 'python-qa') row.tests = Number(clean.match(/Ran (\d+) tests/)?.[1] ?? -1);
  if (name === 'angular') {
    row.passed = Number(clean.match(/Tests\s+(\d+) passed/)?.[1] ?? -1);
    row.test_files = Number(clean.match(/Test Files\s+(\d+) passed/)?.[1] ?? -1);
  }
  if (name === 'eslint-web') {
    try {
      const f = JSON.parse(output);
      row.errors = f.reduce((n, f) => n + f.errorCount, 0);
      row.warnings = f.reduce((n, f) => n + f.warningCount, 0);
    } catch {
      row.parse_error = true;
    }
  }
  if (name.startsWith('mypy-'))
    row.diagnostics = clean
      .split('\n')
      .filter((l) => l.includes(': error:'))
      .map((l) => l.replace(/: error:.*/, ''));
  rows.push(row);
  await fs.writeFile(destination, JSON.stringify(rows, null, 2));
  console.log(JSON.stringify(row));
}
process.exitCode = rows.every((r) => r.status === 'PASS') ? 0 : 1;
