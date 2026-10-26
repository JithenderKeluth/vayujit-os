import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import Ajv2020 from 'ajv/dist/2020.js';
import { serve } from '../server.mjs';
import { phase2ApiComplete } from '../safety.mjs';

test('Phase 2 cannot pass with missing, failed, skipped or zero API scenarios', () => {
  const result = {
    process_exit_code: 0,
    tests: Array.from({ length: 11 }, () => ({ status: 'PASS' })),
    passed: 11,
    failed: 0,
    errors: 0,
    skipped: 0,
  };
  assert.equal(phase2ApiComplete(result), true);
  for (const invalid of [
    undefined,
    {},
    { ...result, tests: [] },
    { ...result, process_exit_code: 1 },
    { ...result, skipped: 1 },
    { ...result, failed: 1 },
    { ...result, tests: [{ status: 'FAIL' }] },
  ]) {
    assert.equal(phase2ApiComplete(invalid), false);
  }
});

test('Phase 2 finding schema requires seller impact and preserves Phase 1 compatibility', () => {
  const base = JSON.parse(fs.readFileSync(new URL('../finding.schema.json', import.meta.url)));
  const schema = JSON.parse(fs.readFileSync(new URL('../finding-v2.schema.json', import.meta.url)));
  const ajv = new Ajv2020({ allErrors: true });
  ajv.addSchema(base, 'finding.schema.json');
  const validate = ajv.compile(schema);
  const prior = JSON.parse(fs.readFileSync('docs/qa/initial-report.json')).confirmed_bugs[0];
  assert.equal(validate(prior), false);
  assert.equal(
    validate({
      ...prior,
      area: 'Research',
      journey: 'Seller decision',
      business_impact: 'Evidence cannot be read.',
    }),
    true,
  );
  assert.equal(ajv.getSchema('finding.schema.json')(prior), true);
  const reviewed = JSON.parse(fs.readFileSync('docs/qa/phase-2-reviewed-findings.json'));
  for (const item of reviewed) assert.equal(validate(item), true, JSON.stringify(validate.errors));
  if (fs.existsSync('docs/qa/phase-2-report.json')) {
    const generated = JSON.parse(fs.readFileSync('docs/qa/phase-2-report.json'));
    const findings = [
      ...generated.findings,
      ...generated.confirmed_bugs,
      ...generated.usability_findings,
      ...(generated.resolved_findings || []),
    ];
    for (const item of findings)
      assert.equal(validate(item), true, JSON.stringify(validate.errors));
    assert.equal(new Set(findings.map((f) => f.id)).size, findings.length);
    const phase1 = JSON.parse(fs.readFileSync('docs/qa/initial-report.json'));
    assert.deepEqual(generated.inherited_phase1_findings, [
      ...phase1.confirmed_bugs,
      ...phase1.findings,
      ...phase1.usability_findings,
    ]);
  }
});

test('Phase 2 proxy rejects live or missing supplier mode before any upstream call', async (t) => {
  if (!fs.existsSync('dist/apps/web/browser/index.html')) {
    t.skip('Build Angular first to execute the real proxy regression; not a PASS.');
    return;
  }
  const server = await serve(0, 1, '2');
  try {
    const origin = `http://127.0.0.1:${server.address().port}`;
    for (const data of [{ mode: 'LIVE_READ_ONLY' }, {}, { mode: 'PROVIDER_NEUTRAL' }]) {
      const response = await fetch(origin + '/api/v1/intelligence/suppliers/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      assert.equal(response.status, 403);
    }
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
