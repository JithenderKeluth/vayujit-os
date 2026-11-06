import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { expect, vi } from 'vitest';
import { AuthPageComponent } from './auth-page.component';
import { AuthService } from './auth.service';

describe('R4 auth-only focus styling', () => {
  function fixture() {
    const auth = {
      error: signal<string | null>(null),
      login: vi.fn().mockResolvedValue(undefined),
    };
    TestBed.configureTestingModule({
      imports: [AuthPageComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: auth },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { queryParamMap: convertToParamMap({}) } },
        },
      ],
    });
    const view = TestBed.createComponent(AuthPageComponent);
    view.detectChanges();
    return { view, auth };
  }

  it('scopes the existing strong focus token to the auth surface', () => {
    const { view } = fixture();
    const surface = view.nativeElement.querySelector('main.auth') as HTMLElement;
    expect(getComputedStyle(surface).getPropertyValue('--vj-focus').trim()).toBe(
      'var(--vj-color-brand-strong)',
    );
    expect(document.documentElement.style.getPropertyValue('--vj-focus')).toBe('');
  });

  it('preserves password states and invalid-submit protection', async () => {
    const { view, auth } = fixture();
    const root = view.nativeElement as HTMLElement;
    const password = root.querySelector('#password') as HTMLInputElement;
    const toggle = root.querySelector('.password-toggle') as HTMLButtonElement;
    expect(password.type).toBe('password');
    expect(root.querySelector<HTMLButtonElement>('button[type=submit]')?.disabled).toBe(true);
    await view.componentInstance.submit();
    expect(auth.login).not.toHaveBeenCalled();
    toggle.click();
    view.detectChanges();
    expect(password.type).toBe('text');
    expect(toggle.getAttribute('aria-pressed')).toBe('true');
    toggle.click();
    view.detectChanges();
    expect(password.type).toBe('password');
    expect(toggle.getAttribute('aria-pressed')).toBe('false');
  });
});
