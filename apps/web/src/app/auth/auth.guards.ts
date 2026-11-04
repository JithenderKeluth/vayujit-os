import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';
import { authReturnUrl } from './auth-return-url';
async function ready(auth: AuthService) {
  if (!auth.initialized()) await auth.initialize();
}
export const authGuard: CanActivateFn = async (_route, state) => {
  const a = inject(AuthService),
    r = inject(Router);
  await ready(a);
  return a.user()
    ? true
    : r.createUrlTree([a.setupRequired() ? '/setup' : '/login'], {
        queryParams: { returnUrl: authReturnUrl(state.url) },
      });
};
export const guestGuard: CanActivateFn = async (route) => {
  const a = inject(AuthService),
    r = inject(Router);
  await ready(a);
  const returnUrl = authReturnUrl(route.queryParamMap.get('returnUrl'));
  if (a.user()) return r.parseUrl(returnUrl);
  if (route.routeConfig?.path === 'setup' && !a.setupRequired())
    return r.createUrlTree(['/login'], { queryParams: { returnUrl } });
  if (route.routeConfig?.path === 'login' && a.setupRequired())
    return r.createUrlTree(['/setup'], { queryParams: { returnUrl } });
  return true;
};
