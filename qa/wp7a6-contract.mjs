export const ids = [
  'R-3feda36d',
  'R-55e822d5',
  'R-551d2f8c',
  'R-db243c36',
  'R-d6a495d5',
  'L-16',
  'L-17',
];
export const contexts = ['chrome-1440', 'chrome-390', 'msedge-1440', 'msedge-390'].map(
  (v) => 'wp7a6-' + v,
);
export const assertions = {
  'R-3feda36d': [
    'image_only_created',
    'context_provenance',
    'preview_validation',
    'save_reload',
    'edit_stale_review',
    'duplicate_concurrent',
    'failure_recovery',
    'approval_no_publish',
    'owner_isolation',
  ],
  'R-55e822d5': [
    'configured_not_connected',
    'missing_credentials',
    'fake_validated_label',
    'invalid_expired_revoked',
    'account_mismatch',
    'reload_recovery',
    'default_deny',
  ],
  'R-551d2f8c': [
    'missing_prerequisite',
    'legitimate_resolution',
    'human_review',
    'authorization_states',
    'exact_fingerprint',
    'stale_mismatch',
    'repeat_concurrent',
    'reload_failure_recovery',
    'no_submission',
    'owner_isolation',
  ],
  'R-db243c36': [
    'missing_readiness',
    'manual_resolution',
    'review_boundaries',
    'unsupported_live_truthful',
    'stale_duplicate',
    'reload_failure_recovery',
    'no_dispatch',
    'owner_isolation',
  ],
  'R-d6a495d5': [
    'missing_prerequisite',
    'legitimate_resolution',
    'human_review',
    'authorization_states',
    'exact_fingerprint',
    'stale_mismatch',
    'repeat_concurrent',
    'reload_failure_recovery',
    'no_submission',
    'owner_isolation',
  ],
  'L-16': [
    'draft_identity',
    'artifact_versions',
    'dependency_graph',
    'changed_preview_stale',
    'fingerprint_confirmation',
    'concurrent_replay',
    'interrupted_recovery',
    'reload_owned',
    'no_release',
  ],
  'L-17': [
    'creative_content_image',
    'exact_versions',
    'missing_invalid_prerequisites',
    'authorization_states',
    'preview_fingerprint',
    'human_confirm',
    'stale_concurrent',
    'failure_recovery_latest',
    'reload_owned',
    'no_spend',
  ],
};

export function gate({ entries = [], audit, quality, backend, blockers = [] }) {
  const exact =
    entries.length === 48 &&
    new Set(entries.map((e) => e.id)).size === 48 &&
    entries.filter((e) => e.wp7a6_target).length === 7 &&
    ids.every((id) => entries.some((e) => e.id === id && e.wp7a6_target));
  const closed = (e) =>
    !e.wp7a6_target
      ? e.inherited_closed === true && e.status === 'PASS'
      : e.acceptance_review?.complete === true &&
        e.evidence_integrity === true &&
        contexts.every((context) => {
          const a = (e.attempts || []).findLast((a) => a.context === context);
          return (
            a?.status === 'PASS' &&
            a.screenshot &&
            a.trace &&
            assertions[e.id].every((key) => a.acceptance_assertions?.includes(key)) &&
            a.persisted_state_verified === true
          );
        });
  const open = entries.filter((e) => !closed(e)).map((e) => e.id);
  const cleanup =
    audit?.database_absence_status === 'PASS' &&
    audit.historical_baseline_unchanged === true &&
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
    checks.every((id) => quality?.checks?.some((c) => c.id === id && c.status === 'PASS')) &&
    backend?.complete === true &&
    backend.tests > 0 &&
    backend.failures === 0 &&
    backend.errors === 0 &&
    backend.skipped === 0;
  return {
    package: 'WP7A-6',
    status:
      exact && open.length === 0 && cleanup && regressions && !blockers.length
        ? 'PASS'
        : 'INCOMPLETE',
    application_certification: 'INCOMPLETE',
    original_denominator: 48,
    inherited_closed: 41,
    targeted: 7,
    closed: entries.filter(closed).length,
    remaining: open.length,
    open_entries: open,
    exact_scope: exact,
    cleanup: cleanup ? 'PASS' : 'INCOMPLETE',
    regressions: regressions ? 'PASS' : 'INCOMPLETE',
    blockers,
  };
}
