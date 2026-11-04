import { TestBed } from '@angular/core/testing';
import { expect, vi } from 'vitest';
import { signal } from '@angular/core';
import {
  ActivatedRoute,
  ActivatedRouteSnapshot,
  Router,
  RouterStateSnapshot,
  convertToParamMap,
  provideRouter,
} from '@angular/router';
import { authReturnUrl } from './auth-return-url';
import { authGuard, guestGuard } from './auth.guards';
import { AuthService } from './auth.service';
import { AuthPageComponent } from './auth-page.component';

describe('WP6 safe authentication continuity', () => {
  for (const value of [
    'https://evil.invalid',
    '//evil.invalid/a',
    '/\\evil.invalid',
    '/%2fexample.invalid',
    '/%252fexample.invalid',
    '/login?returnUrl=/catalog',
    '/setup',
    '/catalog/../login',
    '/(other:evil)',
    '/catalog\n/secret',
    '/%ZZ',
  ]) {
    it(`rejects unsafe/looping return route ${JSON.stringify(value)}`, () =>
      expect(authReturnUrl(value)).toBe('/dashboard'));
  }
  it('preserves exact internal product scope, query and fragment', () =>
    expect(authReturnUrl('/catalog/owned?goal_id=abc#images')).toBe(
      '/catalog/owned?goal_id=abc#images',
    ));
  it('uses dashboard only when no intended route exists', () =>
    expect(authReturnUrl(null)).toBe('/dashboard'));
  const auth = () => ({
    initialized: signal(true),
    setupRequired: signal(false),
    user: signal<unknown>(null),
    error: signal(null),
    login: vi.fn().mockResolvedValue(undefined),
  });
  it('guard carries intended scope without permitting unauthenticated access', async () => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthService, useValue: auth() }],
    });
    const result = await TestBed.runInInjectionContext(() =>
      authGuard(
        {} as ActivatedRouteSnapshot,
        { url: '/catalog/owned?x=1#images' } as RouterStateSnapshot,
      ),
    );
    expect(TestBed.inject(Router).serializeUrl(result as ReturnType<Router['parseUrl']>)).toBe(
      '/login?returnUrl=%2Fcatalog%2Fowned%3Fx%3D1%23images',
    );
  });
  it('authenticated login revisit restores the validated route', async () => {
    const a = auth();
    a.user.set({ id: 'owner' });
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthService, useValue: a }],
    });
    const result = await TestBed.runInInjectionContext(() =>
      guestGuard(
        {
          queryParamMap: convertToParamMap({ returnUrl: '/catalog/owned' }),
          routeConfig: { path: 'login' },
        } as ActivatedRouteSnapshot,
        {} as RouterStateSnapshot,
      ),
    );
    expect(TestBed.inject(Router).serializeUrl(result as ReturnType<Router['parseUrl']>)).toBe(
      '/catalog/owned',
    );
  });
  it('successful form submission replaces Login with intended internal route and blocks duplicates', async () => {
    const a = auth();
    TestBed.configureTestingModule({
      imports: [AuthPageComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: a },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              queryParamMap: convertToParamMap({ returnUrl: '/catalog/owned?tab=media#images' }),
            },
          },
        },
      ],
    });
    const c = TestBed.createComponent(AuthPageComponent).componentInstance;
    const navigation = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    c.form.patchValue({ email: 'qa@example.com', password: 'SyntheticOnly123!' });
    const first = c.submit();
    await c.submit();
    await first;
    expect(a.login).toHaveBeenCalledTimes(1);
    expect(navigation).toHaveBeenCalledWith('/catalog/owned?tab=media#images', {
      replaceUrl: true,
    });
  });
});
