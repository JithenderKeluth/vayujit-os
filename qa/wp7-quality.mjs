// Certification is independent of the number of green test assertions.
export const journeyIds = [...'ABCDEFGHIJKLM'];
// Pytest JUnit emits both self-closing passes and paired failure elements.
// Non-greedy attributes prevent a pass from consuming the next failure body.
export function junitCases(xml) {
  return [...xml.matchAll(/<testcase\b([^>]*?)(?:\/>|>([\s\S]*?)<\/testcase>)/g)].map((m) => ({
    key:
      (m[1].match(/classname="([^"]*)"/)?.[1] || '') +
      '::' +
      (m[1].match(/\bname="([^"]*)"/)?.[1] || ''),
    status: /<failure\b|<error\b/.test(m[2] || '')
      ? 'FAIL'
      : /<skipped\b/.test(m[2] || '')
        ? 'SKIPPED'
        : 'PASS',
  }));
}
export function certificationDecision(evidence) {
  const reasons = [];
  if (!evidence.cleanup_verified) reasons.push('QA_CLEANUP_NOT_VERIFIED');
  if (evidence.unresolved_p0_p1 > 0) reasons.push('UNRESOLVED_CRITICAL_DEFECTS');
  if (evidence.critical_integrity_or_authorization_failure)
    reasons.push('CRITICAL_INTEGRITY_OR_AUTHORIZATION_FAILURE');
  if (evidence.significant_required_coverage_missing)
    reasons.push('SIGNIFICANT_REQUIRED_COVERAGE_MISSING');
  for (const id of journeyIds)
    if (evidence.journeys?.find((r) => r.id === id)?.status !== 'PASS')
      reasons.push('JOURNEY_' + id + '_NOT_DEMONSTRATED');
  if (!evidence.required_accessibility_dispositions)
    reasons.push('REQUIRED_ACCESSIBILITY_DISPOSITIONS_MISSING');
  return {
    decision: reasons.length
      ? 'FAIL'
      : evidence.lower_severity_conditions?.length
        ? 'CONDITIONAL'
        : 'PASS',
    reasons,
    production_launch: 'NOT_CERTIFIED',
    live_integrations: 'NOT_CERTIFIED',
    backup_restore: 'PARKED',
    wp8_started: false,
  };
}
