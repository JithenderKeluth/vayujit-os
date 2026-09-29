import { HttpInterceptorFn } from '@angular/common/http';

import { environment } from '../../environments/environment';

/** Attach the existing HttpOnly session cookie to API requests only. */
export const apiCredentialsInterceptor: HttpInterceptorFn = (request, next) => {
  const isApiRequest =
    request.url === environment.apiUrl || request.url.startsWith(`${environment.apiUrl}/`);
  if (!isApiRequest) return next(request);
  return next(request.clone({ withCredentials: true }));
};
