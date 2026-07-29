import { readFileSync } from 'node:fs';

const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'));
const unknown = [];
const copyleft = [];
for (const [path, value] of Object.entries(lock.packages ?? {})) {
  if (!path || value.dev) continue;
  const name = value.name ?? path.replace(/^node_modules\//, '');
  const license = String(value.license ?? '');
  if (!license) unknown.push(name);
  if (/(^|-)A?GPL/.test(license)) copyleft.push(`${name}: ${license}`);
}
process.stdout.write(
  `${JSON.stringify(
    {
      status: unknown.length || copyleft.length ? 'WARN' : 'PASS',
      scope: 'production engineering visibility; not legal approval',
      unknown_licenses: unknown,
      gpl_agpl_flags: copyleft,
    },
    null,
    2,
  )}\n`,
);
