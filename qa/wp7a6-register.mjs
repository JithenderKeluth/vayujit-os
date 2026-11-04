// Additive registration only. Historical ledgers, evidence and recovery records are never rewritten.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import { ids, assertions } from './wp7a6-contract.mjs';
const root = 'docs/qa/seller-experience/';
const fourth = JSON.parse(await fs.readFile(root + 'wp7a4-coverage-ledger.json', 'utf8'));
const fifth = JSON.parse(await fs.readFile(root + 'wp7a5-coverage-ledger.json', 'utf8'));
const overlays = new Map(fifth.entries.map((e) => [e.id, e]));
const originals = fourth.entries.map((e) => overlays.get(e.id) || e);
if (
  originals.length !== 48 ||
  originals.filter((e) => e.full_closure).length !== 41 ||
  originals.filter((e) => !e.full_closure).length !== 7 ||
  ids.some((id) => !originals.some((e) => e.id === id && !e.full_closure))
)
  throw Error('EXACT_48_AND_SEVEN_REQUIRED');
await fs.access(root + 'wp7a6-closure-plan.md');
await fs.mkdir('tmp/qa-wp7a6', { recursive: true });
const files = (await fs.readdir(root)).filter(
  (n) => /^wp7a(?:2|3|4|5)?-/.test(n) || /^wp7-journey-coverage-matrix/.test(n),
);
const recovery = (await fs.readdir('docs/seller-os'))
  .filter((n) => /^local-database-/.test(n))
  .map((n) => 'docs/seller-os/' + n);
const baseline = [];
for (const file of [...files.map((n) => root + n), ...recovery])
  baseline.push({
    file,
    sha256: crypto
      .createHash('sha256')
      .update(await fs.readFile(file))
      .digest('hex'),
  });
await fs
  .writeFile('tmp/qa-wp7a6/baseline.json', JSON.stringify({ files: baseline }, null, 2), {
    flag: 'wx',
  })
  .catch((e) => {
    if (e.code !== 'EEXIST') throw e;
  });
const ledger = {
  package: 'WP7A-6',
  original_denominator: 48,
  inherited_closed: 41,
  targeted: 7,
  status: 'PLANNED',
  source: root + 'wp7a5-coverage-ledger.json',
  entries: originals.map((e) => ({
    id: e.id,
    route: e.route,
    group: e.group,
    capability: e.capability || e.required_behavior,
    prior_status: e.full_closure ? 'PASS' : 'PARTIAL',
    status: e.full_closure ? 'PASS' : 'NOT_TESTED',
    inherited_closed: !!e.full_closure,
    wp7a6_target: ids.includes(e.id),
    full_closure: !!e.full_closure,
    history_source: root + (overlays.has(e.id) ? 'wp7a5' : 'wp7a4') + '-coverage-ledger.json',
    already_verified: e.acceptance_review?.remaining || e.final_disposition,
    acceptance: e.acceptance || e.closure,
    required_assertions: assertions[e.id] || [],
    required_browser:
      'Installed Chrome and Edge, 1440/390, actual actions, negative/recovery/reload, screenshot/trace/axe',
    attempts: [],
    evidence: [],
    acceptance_review: { complete: !!e.full_closure },
  })),
};
await fs
  .writeFile(root + 'wp7a6-coverage-ledger.json', JSON.stringify(ledger, null, 2), { flag: 'wx' })
  .catch((e) => {
    if (e.code !== 'EEXIST') throw e;
  });
console.log(
  JSON.stringify({
    original: 48,
    inherited_closed: 41,
    targeted: ids,
    historical_files: baseline.length,
  }),
);
