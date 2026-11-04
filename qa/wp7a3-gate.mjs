// A bounded browser PASS never silently upgrades the complete WP7A matrix.
export function wp7a3Gate({ entries, requiredIds, browser, backendExit, cleanup, blockers = [] }) {
  const allowedExclusion = (entry) =>
    entry.status === 'NOT_SUPPORTED' &&
    entry.exclusion_reviewed === true &&
    typeof entry.exclusion_reason === 'string' &&
    entry.exclusion_reason.trim().length > 20;
  const open = Array.isArray(entries)
    ? entries
        .filter((e) => e.status !== 'PASS' || e.full_closure !== true)
        .filter((e) => !allowedExclusion(e))
    : [];
  const browserPass =
    browser?.checks?.length === 36 &&
    browser.status === 'PASS' &&
    ['wp7a3-chrome-1440', 'wp7a3-chrome-390', 'wp7a3-msedge-1440', 'wp7a3-msedge-390'].every(
      (context) =>
        ['L-09', 'L-10', 'L-11', 'L-12', 'L-13', 'L-14', 'L-15', 'L-16', 'L-17'].every((id) =>
          browser.checks.some((c) => c.context === context && c.id === id && c.status === 'PASS'),
        ),
    );
  const exactScope = Array.isArray(entries) && Array.isArray(requiredIds) &&
    requiredIds.length === 49 && new Set(requiredIds).size === 49 &&
    entries.length === requiredIds.length && new Set(entries.map(e => e.id)).size === 49 &&
    requiredIds.every(id => entries.some(e => e.id === id));
  const complete =
    exactScope &&
    open.length === 0 &&
    browserPass &&
    backendExit === 0 &&
    cleanup === 'PASS' &&
    blockers.length === 0;
  return {
    status: complete ? 'PASS' : 'INCOMPLETE',
    bounded_browser: browserPass ? 'PASS' : 'INCOMPLETE',
    required_entries: entries?.length ?? 0,
    open_entries: open.map((e) => e.id),
    blockers,
  };
}
