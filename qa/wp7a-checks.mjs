// Scoped quality evidence: counts and safe locations only, never raw tool output.
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
const python = path.resolve('apps/api/.venv/Scripts/python.exe');
const py = [
  'qa/wp7a_fixture.py',
  'qa/wp7a_probe.py',
  'apps/api/tests/test_seller_wp7a.py',
  'apps/api/tests/test_seller_wp6a_migration.py',
  'apps/api/alembic/versions/20261207_0150_ai_job_optional_recovery.py',
  'apps/api/vayujit_api/intelligence/business_agent_service.py',
  'qa/wp7a_final_audit.py',
  'qa/wp4_final_audit.py',
];
const js = (await fs.readdir('qa'))
  .filter((f) => /^wp7a[-_].*\.mjs$/.test(f))
  .map((f) => 'qa/' + f);
const jobs = [
  ['node-qa', process.execPath, ['--test', '--test-reporter=tap', 'qa/unit/*.test.mjs']],
  ['python-qa', python, ['-m', 'unittest', 'discover', '-s', 'qa/unit', '-p', 'test_*.py']],
  [
    'angular',
    process.execPath,
    ['node_modules/@angular/cli/bin/ng.js', 'test', '--watch=false'],
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
    [
      'node_modules/eslint/bin/eslint.js',
      '--config',
      'qa/eslint.config.mjs',
      ...js,
      'qa/wp7-run.mjs',
      'qa/unit/wp7a-safety.test.mjs',
    ],
  ],
  ['ruff', python, ['-m', 'ruff', 'check', '--config', 'apps/api/pyproject.toml', ...py]],
  ['black', python, ['-m', 'black', '--check', '--config', 'apps/api/pyproject.toml', ...py]],
  [
    'mypy-migration',
    python,
    [
      '-m',
      'mypy',
      '--strict',
      '--follow-imports=skip',
      '--config-file',
      'apps/api/pyproject.toml',
      py[4],
    ],
  ],
  [
    'mypy-research',
    python,
    [
      '-m',
      'mypy',
      '--strict',
      '--follow-imports=skip',
      '--config-file',
      'apps/api/pyproject.toml',
      py[5],
    ],
  ],
  [
    'compileall',
    python,
    ['-m', 'compileall', '-q', 'qa', 'apps/api/alembic/versions', 'apps/api/vayujit_api'],
  ],
  [
    'powershell-parser',
    'powershell.exe',
    [
      '-NoProfile',
      '-NonInteractive',
      '-Command',
      "$e=$null;$t=$null;[System.Management.Automation.Language.Parser]::ParseFile((Join-Path (Get-Location) 'scripts/test-seller-wp7a.ps1'),[ref]$t,[ref]$e)|Out-Null;if($e.Count){exit 1}",
    ],
  ],
  [
    'diff-check',
    'git',
    ['-c', 'safe.directory=' + process.cwd().replaceAll('\\', '/'), 'diff', '--check'],
  ],
];
const rows = [];
try {
  await fs.copyFile(
    'tmp/qa-wp7a/quality-checks.json',
    'tmp/qa-wp7a/quality-checks-history-' + Date.now() + '.json',
    fs.constants.COPYFILE_EXCL,
  );
} catch (error) {
  if (!['EEXIST', 'ENOENT'].includes(error.code)) throw error;
}
for (const [name, command, args, cwd] of jobs) {
  const actual = args.map((a) =>
    cwd && a === 'node_modules/@angular/cli/bin/ng.js' ? '../../' + a : a,
  );
  const child = spawn(command, actual, {
    cwd: cwd || process.cwd(),
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let output = '';
  child.stdout.on('data', (d) => (output += d));
  child.stderr.on('data', (d) => (output += d));
  const code = await new Promise((resolve) => {
    child.once('error', () => resolve(-1));
    child.once('exit', resolve);
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
      const files = JSON.parse(output);
      row.errors = files.reduce((n, f) => n + f.errorCount, 0);
      row.warnings = files.reduce((n, f) => n + f.warningCount, 0);
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
  await fs.mkdir('tmp/qa-wp7a', { recursive: true });
  await fs.writeFile('tmp/qa-wp7a/quality-checks.json', JSON.stringify(rows, null, 2));
  console.log(JSON.stringify(row));
}
process.exitCode = rows.every((r) => r.status === 'PASS') ? 0 : 1;
