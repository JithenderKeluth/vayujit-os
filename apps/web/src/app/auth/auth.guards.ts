import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';
async function ready(auth: AuthService) {
  if (!auth.initialized()) await auth.initialize();
}
export const authGuard: CanActivateFn = async () => {
  const a = inject(AuthService),
    r = inject(Router);
  await ready(a);
  return a.user() ? true : r.createUrlTree([a.setupRequired() ? '/setup' : '/login']);
};
export const guestGuard: CanActivateFn = async (route) => {
  const a = inject(AuthService),
    r = inject(Router);
  await ready(a);
  if (a.user()) return r.createUrlTree(['/dashboard']);
  if (route.routeConfig?.path === 'setup' && !a.setupRequired()) return r.createUrlTree(['/login']);
  if (route.routeConfig?.path === 'login' && a.setupRequired()) return r.createUrlTree(['/setup']);
  return true;
};
