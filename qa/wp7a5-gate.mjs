export const ids = [
  'R-184826c3',
  'R-794214d7',
  'R-3feda36d',
  'R-55e822d5',
  'R-551d2f8c',
  'R-db243c36',
  'R-d6a495d5',
  'L-10',
  'L-12',
  'L-13',
  'L-15',
  'L-16',
  'L-17',
  'L-21',
  'L-22',
  'L-23',
];
export const contexts = ['chrome-1440', 'chrome-390', 'msedge-1440', 'msedge-390'].map(
  (v) => 'wp7a5-' + v,
);
export function gate({ entries = [], audit, quality, backend, blockers = [] }) {
  const exact =
    entries.length === 16 &&
    new Set(entries.map((e) => e.id)).size === 16 &&
    ids.every((id) => entries.some((e) => e.id === id));
  const closed = (e) =>
    e.acceptance_review?.complete === true &&
    e.evidence_integrity === true &&
    contexts.every((context) => {
      const attempt = e.attempts.findLast((a) => a.context === context);
      return attempt?.status === 'PASS' && attempt.screenshot && attempt.trace;
    });
  const open = entries.filter((e) => !closed(e)).map((e) => e.id);
  const cleanup =
    audit?.database_absence_status === 'PASS' &&
    audit?.historical_baseline_unchanged === true &&
    audit.databases?.length > 0 &&
    audit.databases.every((d) => d.absent && d.state === 'DROPPED');
  const checks = [
    'node_qa',
    'python_qa',
    'angular',
    'build',
    'lint',
    'typescript_app',
    'typescript_spec',
    'mypy',
    'ruff',
    'black_backend',
    'black_qa',
    'compile',
    'parser',
    'diff',
  ];
  const regressions =
    checks.every((id) => quality?.checks?.find((c) => c.id === id)?.status === 'PASS') &&
    backend?.complete === true &&
    backend.tests > 0 &&
    backend.failures === 0 &&
    backend.errors === 0 &&
    backend.skipped === 0;
  return {
    package: 'WP7A-5',
    status:
      exact && open.length === 0 && cleanup && regressions && blockers.length === 0
        ? 'PASS'
        : 'INCOMPLETE',
    application_certification: 'INCOMPLETE',
    original_denominator: 48,
    inherited_closed: 32,
    targeted: 16,
    newly_closed: entries.filter(closed).length,
    open_entries: open,
    exact_scope: exact,
    cleanup: cleanup ? 'PASS' : 'INCOMPLETE',
    regressions: regressions ? 'PASS' : 'INCOMPLETE',
    blockers,
  };
}
