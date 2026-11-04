import { requiredContexts } from './wp7a4-rollup.mjs';

export function wp7a4Gate({ requiredIds, entries, cleanup, regressions, blockers = [] }) {
  const exact =
    requiredIds?.length === 48 &&
    new Set(requiredIds).size === 48 &&
    entries?.length === 48 &&
    new Set(entries.map((e) => e.id)).size === 48 &&
    requiredIds.every((id) => entries.some((e) => e.id === id));
  const excluded = (e) =>
    e.status === 'NOT_SUPPORTED' &&
    e.exclusion_reviewed === true &&
    e.exclusion_scope_accurate === true &&
    e.exclusion_reason?.length > 40;
  const closed = (e) =>
    e.status === 'PASS' &&
    e.full_closure === true &&
    e.evidence_integrity === true &&
    requiredContexts.every(
      (context) => e.attempts.findLast((a) => a.context === context)?.status === 'PASS',
    );
  const open = (entries || []).filter((e) => !closed(e) && !excluded(e));
  const safeCleanup =
    cleanup?.database_absence_status === 'PASS' &&
    cleanup?.databases?.length > 0 &&
    cleanup.databases.every((d) => d.absent && d.state === 'DROPPED') &&
    cleanup.historical_baseline_unchanged === true;
  const regressionPass =
    regressions &&
    [
      'backend',
      'angular',
      'node_qa',
      'python_qa',
      'build',
      'lint',
      'typescript',
      'mypy',
      'ruff_black',
      'compile_parser',
      'diff',
    ].every((k) => regressions[k]?.status === 'PASS');
  return {
    package: 'WP7A-4',
    status:
      exact && open.length === 0 && safeCleanup && regressionPass && blockers.length === 0
        ? 'PASS'
        : 'INCOMPLETE',
    application_certification: 'INCOMPLETE',
    required_entries: 48,
    exact_scope: exact,
    closed: entries?.filter(closed).length || 0,
    open_entries: open.map((e) => e.id),
    cleanup: safeCleanup ? 'PASS' : 'INCOMPLETE',
    regressions: regressionPass ? 'PASS' : 'INCOMPLETE',
    blockers,
  };
}
