export const requiredContexts = [
  'wp7a4-chrome-1440',
  'wp7a4-chrome-390',
  'wp7a4-msedge-1440',
  'wp7a4-msedge-390',
];
export function rollup(entry, contexts = requiredContexts) {
  const latest = contexts.map((context) =>
    entry.attempts.findLast((a) => a.context === context),
  );
  const attempts = latest.filter(Boolean);
  const status = attempts.some((a) => a.status === 'FAIL')
    ? 'FAIL'
    : attempts.some((a) => a.status === 'BLOCKED')
      ? 'BLOCKED'
      : attempts.length === 4 && attempts.every((a) => a.status === 'PASS')
        ? 'PASS'
        : attempts.length
          ? 'PARTIAL'
          : entry.prior_status;
  return {
    status,
    full_closure: status === 'PASS',
    final_disposition:
      status === 'PASS'
        ? 'VERIFIED_LOCAL_SCOPE'
        : attempts.find((a) => a.status !== 'PASS')?.reason || 'FOUR_CONTEXT_EVIDENCE_REQUIRED',
  };
}
