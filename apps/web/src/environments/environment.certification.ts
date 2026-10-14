// Test-only origin used by the PR-SOS browser certification harness.
// This file is never selected by production or default development builds.
export const environment = {
  production: false,
  apiUrl: 'http://127.0.0.1:8004/api/v1',
} as const;
