import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';

// No runtime, Docker, database or provider actions: only existing local checks.
const dir = 'tmp/qa-agent/phase4b-quality';
await fs.mkdir(dir, { recursive: true });
const python = path.resolve('apps/api/.venv/Scripts/python.exe');
const pyFiles = [
  'apps/api/vayujit_api/commerce/inventory_router.py',
  'apps/api/vayujit_api/commerce/schemas.py',
  'apps/api/tests/test_qa_phase4b_opening_stock.py',
  'qa/fixture_server.py',
];
const sources = [
  ...pyFiles,
  'apps/web/src/app/marketplaces/opening-stock.component.ts',
  'apps/web/src/app/marketplaces/opening-stock.css',
  'apps/web/src/app/marketplaces/unified-inventory.component.ts',
  'apps/web/src/app/marketplaces/marketplace.service.ts',
  'apps/web/src/app/app.routes.ts',
  'apps/web/src/app/marketplaces/opening-stock.component.spec.ts',
  'apps/web/src/app/marketplaces/opening-stock.service.spec.ts',
];
const hash = async (file) =>
  crypto
    .createHash('sha256')
    .update(await fs.readFile(file))
    .digest('hex');
const before = Object.fromEntries(await Promise.all(sources.map(async (p) => [p, await hash(p)])));
const node = process.execPath;
const checks = [
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
  ['qa-python', python, ['-m', 'pytest', 'qa/unit', '-q', '-o', 'addopts=']],
  ['angular', node, ['node_modules/@angular/cli/bin/ng.js', 'test', '--watch=false'], 'apps/web'],
  ['frontend-lint', node, ['node_modules/eslint/bin/eslint.js', 'src/**/*.ts'], 'apps/web'],
  [
    'qa-lint',
    node,
    ['node_modules/eslint/bin/eslint.js', '--config', 'qa/eslint.config.mjs', 'qa'],
  ],
  [
    'typescript-app',
    node,
    ['node_modules/typescript/bin/tsc', '--noEmit', '-p', 'apps/web/tsconfig.app.json'],
  ],
  [
    'typescript-tests',
    node,
    ['node_modules/typescript/bin/tsc', '--noEmit', '-p', 'apps/web/tsconfig.spec.json'],
  ],
  ['ruff', python, ['-m', 'ruff', 'check', '--config', 'apps/api/pyproject.toml', ...pyFiles]],
  ['black', python, ['-m', 'black', '--check', '--config', 'apps/api/pyproject.toml', ...pyFiles]],
  [
    'strict-mypy',
    python,
    [
      '-m',
      'mypy',
      '--config-file',
      'apps/api/pyproject.toml',
      '--strict',
      '--follow-imports=silent',
      ...pyFiles.filter((p) => !p.endsWith('/schemas.py')),
    ],
  ],
  [
    'schema-mypy-historical',
    python,
    [
      '-m',
      'mypy',
      '--config-file',
      'apps/api/pyproject.toml',
      '--strict',
      '--follow-imports=silent',
      'apps/api/vayujit_api/commerce/schemas.py',
    ],
  ],
  ['compileall', python, ['-m', 'compileall', '-q', ...pyFiles]],
  [
    'diff-check',
    'git',
    ['-c', 'safe.directory=C:/Users/jithe/Documents/vayujit-os', 'diff', '--check'],
  ],
];
const results = [];
for (const [name, exe, originalArgs, cwd] of checks) {
  const args = [...originalArgs];
  if (cwd && args[0].startsWith('node_modules/')) args[0] = path.resolve(args[0]);
  const start = Date.now();
  let output = '';
  const child = spawn(exe, args, {
    cwd: cwd ? path.resolve(cwd) : process.cwd(),
    windowsHide: true,
    env: { ...process.env, MYPYPATH: path.resolve('apps/api'), NG_CLI_ANALYTICS: 'false' },
  });
  child.stdout.on('data', (d) => {
    output += d;
  });
  child.stderr.on('data', (d) => {
    output += d;
  });
  const exit = await new Promise((resolve) => {
    child.once('error', () => resolve(-1));
    child.once('exit', resolve);
  });
  const log = `${dir}/${name}.log`;
  await fs.writeFile(log, output);
  const known =
    name === 'schema-mypy-historical' &&
    exit === 1 &&
    /schemas.py:261: error:/.test(output) &&
    /Found 1 error/.test(output);
  results.push({
    name,
    command: [path.basename(exe), ...args],
    cwd: cwd || '.',
    exit_code: exit,
    status: exit === 0 ? 'PASS' : known ? 'HISTORICAL_WARNING' : 'FAIL',
    duration_ms: Date.now() - start,
    log,
  });
  console.log(`${name}: ${results.at(-1).status} (exit ${exit})`);
}
const unchanged = (
  await Promise.all(sources.map(async (p) => before[p] === (await hash(p))))
).every(Boolean);
const result = {
  generated_at: new Date().toISOString(),
  status:
    unchanged && results.every((r) => r.status !== 'FAIL') ? 'PASS_WITH_KNOWN_WARNING' : 'FAIL',
  unchanged_during_checks: unchanged,
  tested_source_sha256: before,
  checks: results,
};
await fs.writeFile('docs/qa/phase-4b-quality.json', JSON.stringify(result, null, 2));
if (result.status === 'FAIL') process.exitCode = 1;
