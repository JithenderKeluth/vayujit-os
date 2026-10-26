import test from 'node:test';
import assert from 'node:assert/strict';
import { focusedComplete, resolutionDecisions } from '../phase4a-resolution.mjs';

function fixture() {
  const api = {
    process_exit_code: 0,
    tests: Array.from({ length: 18 }, () => ({ status: 'PASS' })),
    passed: 18,
    failed: 0,
    errors: 0,
    skipped: 0,
  };
  const cleanup = ['desktop', 'mobile'].map((project, i) => ({
    project,
    database: `vayujit_qa${String(i).repeat(16)}_test`,
    status: 'PASS',
    child_exit: 0,
    proof: {
      marker_verified: true,
      database_absent: true,
      database: `vayujit_qa${String(i).repeat(16)}_test`,
    },
  }));
  const make = (ids) => ({
    cleanup,
    reports: ['desktop', 'mobile'].map((project) => ({
      status: 'passed',
      process_exit_code: 0,
      api_results: api,
      tests: ids.map((id) => ({
        id,
        project,
        status: 'passed',
        evidence: [],
        axe: [{ route: '/ads', state: 'axe-surface', violations: [], incomplete: [] }],
      })),
    })),
  });
  return {
    baseline: {
      findings: [
        { id: 'QA-P4-AXE-TEST', route: '/ads', actual: '{"id":"landmark-unique"}' },
        { id: 'QA-P3-GAP-003' },
      ],
    },
    original: { reports: [] },
    focused: make(['QA-P4A-01', 'QA-P4A-02', 'QA-P4A-03']),
    full: make([
      'QA-P4-SURFACE-ADS',
      'QA-P4-TASK-01',
      'QA-P4-TASK-02',
      'QA-P4-TASK-03',
      'QA-P4-TASK-04',
    ]),
    routes: [{ route: '/ads', kind: 'PAGE' }],
    nodes: [],
    hashesVerified: true,
  };
}
test('Phase 4A closes a route/rule only from two actual clean executions, never the stock gap', () => {
  assert.deepEqual(
    resolutionDecisions(fixture()).map((r) => r.resolved),
    [true, false],
  );
});
test('Phase 4A fails closed for modified originals, failed cleanup, duplicate IDs or incomplete rule evidence', () => {
  for (const mutate of [
    (f) => {
      f.hashesVerified = false;
    },
    (f) => {
      f.full.cleanup[0].child_exit = 1;
    },
    (f) => {
      f.focused.reports[0].tests[0].id = 'QA-P4A-02';
    },
    (f) => {
      f.full.reports[0].tests[0].axe[0].incomplete.push({ id: 'landmark-unique' });
    },
    (f) => {
      f.full.reports[1].tests.forEach((t) => {
        t.axe = [];
      });
    },
  ]) {
    const value = fixture();
    mutate(value);
    assert.equal(resolutionDecisions(value)[0].resolved, false);
  }
});
test('Phase 4A cannot resolve clipped captions or historical review without the exact targeted matrix', () => {
  const value = fixture();
  value.baseline.findings = [
    { id: 'QA-P4-A11Y-CAPTION-CLIPPING' },
    { id: 'QA-P3-A11Y-REVIEW-001' },
  ];
  assert.deepEqual(
    resolutionDecisions(value).map((r) => r.resolved),
    [false, false],
  );
  assert.equal(focusedComplete(value.focused), true);
});

test('caption closure requires every width/context and historical review additionally requires all four financial nodes per viewport', () => {
  const value = fixture();
  value.baseline.findings = [
    { id: 'QA-P4-A11Y-CAPTION-CLIPPING' },
    { id: 'QA-P3-A11Y-REVIEW-001' },
  ];
  const passing = {
    text_horizontally_in_view: true,
    violations: [],
    incomplete: [],
    passes: ['color-contrast'],
  };
  value.nodes = ['desktop', 'mobile'].flatMap((project) =>
    [360, 390, 768, 1440].flatMap((width) =>
      ['due-0', 'economics-0', 'economics-1', 'stale-0', 'decision-0', 'decision-1'].map(
        (name) => ({
          ...passing,
          project,
          viewport: { width },
          suite: 'focused',
          name: `node-review-${name}-${width}`,
        }),
      ),
    ),
  );
  assert.deepEqual(
    resolutionDecisions(value).map((r) => r.resolved),
    [true, false],
  );
  value.nodes.push(
    ...['desktop', 'mobile'].flatMap((project) =>
      [0, 1, 2, 3].map((i) => ({
        ...passing,
        project,
        suite: 'original',
        name: `node-review-financial-${i}`,
      })),
    ),
  );
  assert.deepEqual(
    resolutionDecisions(value).map((r) => r.resolved),
    [true, true],
  );
  value.nodes[0].text_horizontally_in_view = false;
  assert.deepEqual(
    resolutionDecisions(value).map((r) => r.resolved),
    [false, false],
  );
  value.nodes[0].text_horizontally_in_view = true;
  value.nodes[0].incomplete = [{ id: 'color-contrast' }];
  assert.deepEqual(
    resolutionDecisions(value).map((r) => r.resolved),
    [false, false],
  );
});

test('website contrast closure needs both original exposed selectors in both contexts, not a clean unrelated node', () => {
  const value = fixture();
  value.baseline.findings = [
    { id: 'QA-P4-AXE-WEBSITE', route: '/intelligence/websites', actual: '{"id":"color-contrast"}' },
  ];
  for (const r of value.full.reports)
    for (const t of r.tests)
      t.axe = [
        {
          route: '/intelligence/websites',
          state: 'axe-website',
          violations: [],
          incomplete: [
            { id: 'color-contrast', nodes: [{ target: ['unrelated-obscured-table-cell'] }] },
          ],
        },
      ];
  assert.equal(resolutionDecisions(value)[0].resolved, false);
  value.nodes = ['desktop', 'mobile'].flatMap((project) =>
    ['state-high', 'state-expired'].map((state) => ({
      project,
      name: `node-review-state-contrast-${state}-0`,
      route: '/intelligence/websites',
      suite: 'focused',
      text_horizontally_in_view: true,
      violations: [],
      incomplete: [],
      passes: ['color-contrast'],
    })),
  );
  assert.equal(resolutionDecisions(value)[0].resolved, true);
  value.nodes[0].incomplete = [{ id: 'color-contrast' }];
  assert.equal(resolutionDecisions(value)[0].resolved, false);
  value.nodes[0].incomplete = [];
  value.full.reports[0].tests[0].axe[0].violations.push({ id: 'color-contrast' });
  assert.equal(resolutionDecisions(value)[0].resolved, false);
});

test('progress closure preserves unrelated incomplete divs and requires actual role/value witnesses in both contexts', () => {
  const value = fixture();
  value.baseline.findings = [
    { id: 'QA-P4-AXE-PROGRESS', route: '/ai/video', actual: '{"id":"aria-prohibited-attr"}' },
  ];
  for (const r of value.full.reports)
    for (const t of r.tests)
      t.axe = [
        {
          route: '/ai/video',
          state: 'axe-video',
          violations: [],
          incomplete: [{ id: 'aria-prohibited-attr', nodes: [{ target: ['.quick-actions'] }] }],
        },
      ];
  assert.equal(resolutionDecisions(value)[0].resolved, false);
  for (const r of value.focused.reports) {
    r.tests[0].evidence = [{ name: 'semantics-assertions', path: 'witness.json' }];
    r.tests[0].axe = [{ route: '/ai/video', violations: [], incomplete: [] }];
  }
  assert.equal(resolutionDecisions(value)[0].resolved, true);
  value.full.reports[0].tests[0].axe[0].incomplete[0].nodes[0].target = ['.progress'];
  assert.equal(resolutionDecisions(value)[0].resolved, false);
});
