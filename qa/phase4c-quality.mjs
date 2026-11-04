import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';

const node = process.execPath;
const py = path.resolve('apps/api/.venv/Scripts/python.exe');
const dir = 'tmp/qa-agent/phase4c-quality';
await fs.mkdir(dir, { recursive: true });
const checks = [];
const commands = [
  [
    'qa-node',
    node,
    [
      '--test',
      ...(await fs.readdir('qa/unit'))
        .filter((f) => f.endsWith('.test.mjs'))
        .map((f) => 'qa/unit/' + f),
    ],
  ],
  ['qa-python', py, ['-m', 'pytest', 'qa/unit', '-q', '-o', 'addopts=']],
  ['angular', node, ['node_modules/@angular/cli/bin/ng.js', 'test', '--watch=false'], 'apps/web'],
  [
    'qa-eslint',
    node,
    ['node_modules/eslint/bin/eslint.js', '--config', 'qa/eslint.config.mjs', 'qa'],
  ],
  ['qa-prettier', node, ['node_modules/prettier/bin/prettier.cjs', '--check', 'qa']],
  [
    'web-lint',
    node,
    [path.resolve('node_modules/eslint/bin/eslint.js'), 'src/**/*.ts'],
    'apps/web',
  ],
  [
    'typescript-app',
    node,
    ['node_modules/typescript/bin/tsc', '--noEmit', '-p', 'apps/web/tsconfig.app.json'],
  ],
  [
    'typescript-spec',
    node,
    ['node_modules/typescript/bin/tsc', '--noEmit', '-p', 'apps/web/tsconfig.spec.json'],
  ],
  ['ruff', py, ['-m', 'ruff', 'check', '--config', 'apps/api/pyproject.toml', 'qa']],
  ['black', py, ['-m', 'black', '--check', '--config', 'apps/api/pyproject.toml', 'qa']],
  ['compileall', py, ['-m', 'compileall', '-q', 'qa']],
];
// Resolve the CLI entry point before changing cwd.
commands.find((c) => c[0] === 'angular')[2][0] = path.resolve(
  'node_modules/@angular/cli/bin/ng.js',
);
for (const [name, exe, args, cwd] of commands) {
  const started = Date.now();
  let output = '';
  const child = spawn(exe, args, {
    cwd: path.resolve(cwd || '.'),
    windowsHide: true,
    env: { ...process.env, NG_CLI_ANALYTICS: 'false' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  child.stdout.on('data', (data) => {
    output += data;
  });
  child.stderr.on('data', (data) => {
    output += data;
  });
  const exit = await new Promise((resolve) => {
    child.once('error', () => resolve('LAUNCH_FAILED'));
    child.once('exit', (code) => resolve(code));
  });
  const log = path.posix.join(dir, name + '.log');
  await fs.writeFile(log, output);
  checks.push({
    name,
    command: [exe, ...args],
    cwd: cwd || '.',
    exit_code: exit,
    elapsed_ms: Date.now() - started,
    log,
  });
  await fs.writeFile(
    'docs/qa/phase-4c-quality.json',
    JSON.stringify({ generated_at: new Date().toISOString(), checks }, null, 2),
  );
  console.log(`${name}: ${exit}`);
}
if (checks.some((c) => c.exit_code !== 0)) process.exitCode = 1;
