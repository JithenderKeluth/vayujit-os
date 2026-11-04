// A journey assertion is insufficient when Angular catches rendering errors.
// Only the explicitly injected read outage may produce a resource-error message.
export function wp3UnexpectedSignals(signals) {
  const expected = signals.expected_http_errors || [];
  const matches = (row) => expected.some((e) => e.path === row.path && e.status === row.status);
  const serverErrors = signals.network.filter((row) => row.status >= 500);
  let expectedResourceErrors = serverErrors.filter(
    (row) => row.status === 503 && matches(row),
  ).length;
  // A new anonymous browser legitimately probes its session before sign-in.
  // This is not permission to ignore a 401 on any protected page or API.
  let anonymousSessionProbes = signals.network.filter(
    (row) =>
      row.screen === '/login' &&
      row.method === 'GET' &&
      row.path === '/api/v1/auth/me' &&
      row.status === 401,
  ).length;
  const consoleErrors = signals.console_errors.filter((message) => {
    if (
      expectedResourceErrors > 0 &&
      /^Failed to load resource: the server responded with a status of 503\b/.test(message)
    ) {
      expectedResourceErrors--;
      return false;
    }
    if (
      anonymousSessionProbes > 0 &&
      /^Failed to load resource: the server responded with a status of 401\b/.test(message)
    ) {
      anonymousSessionProbes--;
      return false;
    }
    return true;
  });
  return {
    console_errors: consoleErrors,
    page_errors: signals.page_errors,
    failed_requests: signals.failed_requests,
    denied_requests: signals.denied_requests,
    server_errors: serverErrors.filter((row) => !matches(row)),
  };
}
