// Capture quality outcomes, not arbitrary command output or environment values.
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
const python = path.resolve('apps/api/.venv/Scripts/python.exe');
const jobs = [
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
    'eslint',
    process.execPath,
    ['../../node_modules/eslint/bin/eslint.js', 'src/**/*.ts', '--format', 'json'],
    'apps/web',
  ],
  [
    'ruff',
    python,
    [
      '-m',
      'ruff',
      'check',
      '--config',
      'apps/api/pyproject.toml',
      'apps/api/vayujit_api',
      '--output-format',
      'json',
    ],
  ],
  [
    'black',
    python,
    ['-m', 'black', '--check', '--config', 'apps/api/pyproject.toml', 'apps/api/vayujit_api'],
  ],
  [
    'mypy',
    python,
    ['-m', 'mypy', '--strict', '--config-file', 'apps/api/pyproject.toml', 'apps/api/vayujit_api'],
  ],
  [
    'mypy-money',
    python,
    [
      '-m',
      'mypy',
      '--strict',
      '--config-file',
      'apps/api/pyproject.toml',
      'apps/api/vayujit_api/commerce/money.py',
    ],
  ],
  ['compileall', python, ['-m', 'compileall', '-q', 'apps/api/vayujit_api', 'qa']],
];
const results = [];
await fs.mkdir('tmp/qa-wp7', { recursive: true });
for (const [name, cmd, args, cwd] of jobs) {
  const t = Date.now(),
    child = spawn(cmd, args, {
      cwd: cwd || process.cwd(),
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  let stdout = '',
    stderr = '';
  child.stdout.on('data', (d) => (stdout += d));
  child.stderr.on('data', (d) => (stderr += d));
  const code = await new Promise((r) => {
    child.on('error', () => r(-1));
    child.on('exit', r);
  });
  const row = {
    name,
    exit_code: code,
    status: code === 0 ? 'PASS' : 'FAIL',
    duration_ms: Date.now() - t,
    raw_output_persisted: false,
  };
  if (name === 'eslint') {
    try {
      const v = JSON.parse(stdout);
      row.errors = v.reduce((n, f) => n + f.errorCount, 0);
      row.warnings = v.reduce((n, f) => n + f.warningCount, 0);
      row.findings = v
        .filter((f) => f.messages.length)
        .map((f) => ({
          file: path.relative(process.cwd(), f.filePath).replaceAll('\\', '/'),
          messages: f.messages.map((m) => ({
            rule: m.ruleId,
            line: m.line,
            column: m.column,
            severity: m.severity,
          })),
        }));
    } catch {
      row.diagnostic = 'TOOL_OUTPUT_NOT_PARSED';
    }
  }
  if (name === 'ruff') {
    try {
      const v = JSON.parse(stdout);
      row.errors = v.length;
      row.findings = v.map((f) => ({
        file: path.relative(process.cwd(), f.filename).replaceAll('\\', '/'),
        code: f.code,
        line: f.location.row,
      }));
    } catch {
      row.diagnostic = 'TOOL_OUTPUT_NOT_PARSED';
    }
  }
  if (name.startsWith('mypy') || name.startsWith('typescript')) {
    row.diagnostics = stdout
      .split(/\r?\n/)
      .filter((l) => /^[^\r\n]+(?:\.py:\d+:|\.ts\(\d+,\d+\):)\s*(error|warning)/.test(l))
      .map((l) => ({
        location: l.split(/:\s*(?:error|warning)/)[0],
        code: l.match(/\[([a-z-]+)\]$/)?.[1] || l.match(/error (TS\d+)/)?.[1] || 'UNCLASSIFIED',
      }));
    row.diagnostic_count = row.diagnostics.length;
  }
  if (name === 'black') {
    row.files_needing_format = stderr
      .split(/\r?\n/)
      .filter((l) => l.startsWith('would reformat '))
      .map((l) => l.slice(15));
  }
  results.push(row);
  await fs.writeFile('tmp/qa-wp7/static-checks.json', JSON.stringify(results, null, 2));
  console.log(
    JSON.stringify({
      name,
      status: row.status,
      exit_code: code,
      errors: row.errors,
      warnings: row.warnings,
      diagnostics: row.diagnostic_count,
      files: row.files_needing_format?.length,
    }),
  );
}
process.exitCode = results.every((r) => r.status === 'PASS') ? 0 : 1;
