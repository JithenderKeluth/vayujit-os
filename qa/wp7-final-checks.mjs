// Final changed-file checks. Persist counts/status only, never raw tool output.
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
const python = path.resolve('apps/api/.venv/Scripts/python.exe');
const qaFiles = (await fs.readdir('qa'))
  .filter((f) => /^wp7[-_].*\.mjs$/.test(f))
  .map((f) => `qa/${f}`);
const pyFiles = (await fs.readdir('qa')).filter((f) => /^wp7.*\.py$/.test(f)).map((f) => `qa/${f}`);
pyFiles.push(
  'qa/unit/test_wp7_orphan_reconcile.py',
  'qa/wp4_final_audit.py',
  'apps/api/tests/test_pr_sos_05_financials.py',
);
const tests = [
  ['node-qa', process.execPath, ['--test', '--test-reporter=tap', 'qa/unit/*.test.mjs']],
  ['python-qa', python, ['-m', 'unittest', 'discover', '-s', 'qa/unit', '-p', 'test_*.py']],
  [
    'focused-eslint',
    process.execPath,
    [
      'node_modules/eslint/bin/eslint.js',
      '--config',
      'qa/eslint.config.mjs',
      ...qaFiles,
      'qa/unit/wp7-quality.test.mjs',
      'qa/wp4-browser-retest.mjs',
    ],
  ],
  [
    'focused-ruff',
    python,
    ['-m', 'ruff', 'check', '--config', 'apps/api/pyproject.toml', ...pyFiles],
  ],
  [
    'focused-black',
    python,
    ['-m', 'black', '--check', '--config', 'apps/api/pyproject.toml', ...pyFiles],
  ],
  ['compileall', python, ['-m', 'compileall', '-q', 'qa', 'apps/api/vayujit_api']],
  [
    'powershell-parser',
    'powershell.exe',
    [
      '-NoProfile',
      '-NonInteractive',
      '-Command',
      "$e=$null;$t=$null;[System.Management.Automation.Language.Parser]::ParseFile((Join-Path (Get-Location) 'scripts/test-seller-wp7.ps1'),[ref]$t,[ref]$e)|Out-Null;if($e.Count){exit 1}",
    ],
  ],
  [
    'diff-check',
    'git',
    ['-c', 'safe.directory=' + process.cwd().replaceAll('\\', '/'), 'diff', '--check'],
  ],
];
const results = [];
for (const [name, command, args] of tests) {
  const child = spawn(command, args, { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  let output = '';
  child.stdout.on('data', (data) => (output += data));
  child.stderr.on('data', (data) => (output += data));
  const code = await new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('exit', resolve);
  });
  const row = {
    name,
    status: code === 0 ? 'PASS' : 'FAIL',
    exit_code: code,
    raw_output_persisted: false,
  };
  if (name === 'node-qa') {
    for (const key of ['tests', 'pass', 'fail', 'skipped'])
      row[key] = Number(output.match(new RegExp(`# ${key} (\\d+)`))?.[1] ?? -1);
  }
  if (name === 'python-qa') row.tests = Number(output.match(/Ran (\d+) tests/)?.[1] ?? -1);
  results.push(row);
  await fs.writeFile('tmp/qa-wp7/final-checks.json', JSON.stringify(results, null, 2));
  console.log(JSON.stringify(row));
}
process.exitCode = results.every((r) => r.status === 'PASS') ? 0 : 1;
