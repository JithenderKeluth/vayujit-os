import { HttpErrorResponse } from '@angular/common/http';

function detailFrom(error: HttpErrorResponse): string {
  const body: unknown = error.error;
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const detail = body.detail;
    if (typeof detail === 'string') return detail;
    if (typeof detail === 'object' && detail !== null && 'message' in detail) {
      const message = detail.message;
      if (typeof message === 'string') return message;
    }
  }
  return '';
}

export function intelligenceErrorMessage(
  error: unknown,
  fallback = 'Unable to load intelligence data. Retry.',
): string {
  if (!(error instanceof HttpErrorResponse)) return fallback;
  if (error.status === 0) return 'VAYUJIT API is unavailable.';
  if (error.status === 401) return 'Your session has expired. Please sign in again.';
  const detail = detailFrom(error);
  const normalized = detail.toLowerCase();
  if (error.status === 403) {
    if (normalized.includes('disabled')) return 'This capability is currently disabled.';
    return 'You do not have access to this workspace.';
  }
  if (
    normalized.includes('provider') &&
    (normalized.includes('unavailable') || normalized.includes('disabled'))
  ) {
    return 'This research provider is not currently available.';
  }
  if (error.status >= 500) return 'Something went wrong while loading this information. Try again.';
  if (detail && !/(traceback|sql|database|stack trace|token)/i.test(detail)) return detail;
  return fallback;
}
