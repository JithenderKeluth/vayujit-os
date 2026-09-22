import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';
@Component({
  selector: 'app-auth-page',
  imports: [ReactiveFormsModule],
  template: ` <main class="auth" aria-labelledby="auth-title">
    <section class="auth-panel">
      <div class="auth-mark" aria-hidden="true">VJ</div>
      <p class="auth-kicker">VAYUJIT OS · Local owner account</p>
      <h1 id="auth-title">{{ setup() ? 'Create your owner account' : 'Welcome back' }}</h1>
      <p class="auth-intro">
        {{ setup() ? 'Set up the private workspace for your business.' : 'Sign in to continue to your workspace.' }}
      </p>
      <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
      @if (setup()) {
        <label for="full-name">Full name<input id="full-name" formControlName="fullName" autocomplete="name" /></label>
      }
      <label for="email">Email<input id="email" type="email" formControlName="email" autocomplete="email" /></label>
      <label
        for="password"
        >Password<input
          id="password"
          [type]="show() ? 'text' : 'password'"
          formControlName="password"
          [autocomplete]="setup() ? 'new-password' : 'current-password'"
      /></label>
      @if (setup()) {
        <label
          for="confirmation"
          >Confirm password<input
            id="confirmation"
            [type]="show() ? 'text' : 'password'"
            formControlName="confirmation"
            autocomplete="new-password"
        /></label>
      }
      <button class="password-toggle" type="button" (click)="show.set(!show())" [attr.aria-pressed]="show()">
        {{ show() ? 'Hide' : 'Show' }} password
      </button>
      @if (auth.error()) {
        <p role="alert">{{ auth.error() }}</p>
      }
      <button type="submit" [disabled]="form.invalid || busy()">
        {{ busy() ? 'Please wait…' : setup() ? 'Create owner' : 'Sign in' }}
      </button>
      </form>
      <p class="auth-footnote">Your data stays in this local workspace.</p>
    </section>
  </main>`,
  styles: [
    `
      .auth {
        min-height: 100vh;
        display: grid;
        place-items: center;
        padding: 2rem 1rem;
        background: var(--vj-color-bg);
      }
      .auth-panel {
        width: min(28rem, 100%);
        display: grid;
        gap: 0.75rem;
        background: var(--vj-color-surface);
        padding: clamp(1.5rem, 5vw, 2.5rem);
        border: 1px solid var(--vj-color-border);
        border-radius: var(--vj-radius-lg);
        box-shadow: var(--vj-shadow-md);
      }
      .auth-mark {
        display: grid;
        place-items: center;
        width: 2.75rem;
        height: 2.75rem;
        border-radius: 0.8rem;
        background: var(--vj-color-brand);
        color: #fff;
        font-weight: 800;
        letter-spacing: 0.08em;
      }
      .auth-kicker {
        margin: 0.5rem 0 0;
        color: var(--vj-color-brand);
        font-size: 0.78rem;
        font-weight: 750;
        letter-spacing: 0.1em;
        text-transform: uppercase;
      }
      h1 {
        margin: 0;
        color: var(--vj-color-ink);
        font-size: clamp(1.8rem, 6vw, 2.5rem);
        line-height: 1.1;
      }
      .auth-intro,
      .auth-footnote {
        margin: 0;
        color: var(--vj-color-ink-soft);
      }
      form {
        display: grid;
        gap: 1rem;
        margin-top: 0.75rem;
      }
      label {
        display: grid;
        gap: 0.4rem;
        color: var(--vj-color-ink);
        font-weight: 650;
      }
      input,
      button {
        min-height: 2.75rem;
        padding: 0.65rem 0.8rem;
        font: inherit;
      }
      input {
        width: 100%;
      }
      button {
        border: 0;
        border-radius: var(--vj-radius-sm);
        background: var(--vj-color-brand-strong);
        color: #fff;
        cursor: pointer;
        font-weight: 700;
      }
      .password-toggle {
        justify-self: start;
        min-height: auto;
        padding: 0;
        background: transparent;
        color: var(--vj-color-brand-strong);
        font-size: 0.9rem;
      }
      [role='alert'] {
        margin: 0;
        padding: 0.75rem;
        border-left: 4px solid var(--vj-color-error);
        border-radius: var(--vj-radius-sm);
        background: #fff1f1;
        color: var(--vj-color-error);
      }
    `,
  ],
})
export class AuthPageComponent {
  readonly auth = inject(AuthService);
  private fb = inject(FormBuilder);
  private router = inject(Router);
  readonly show = signal(false);
  readonly busy = signal(false);
  readonly setup = signal(location.pathname === '/setup');
  readonly form = this.fb.nonNullable.group({
    fullName: [
      '',
      this.setup() ? [Validators.required, Validators.minLength(2), Validators.maxLength(120)] : [],
    ],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(10)]],
    confirmation: ['', this.setup() ? [Validators.required] : []],
  });
  async submit() {
    if (this.form.invalid) return;
    this.busy.set(true);
    try {
      const v = this.form.getRawValue();
      if (this.setup()) {
        if (v.password !== v.confirmation) {
          this.auth.error.set('Passwords do not match.');
          return;
        }
        await this.auth.setup({
          fullName: v.fullName,
          email: v.email,
          password: v.password,
          passwordConfirmation: v.confirmation,
        });
      } else await this.auth.login({ email: v.email, password: v.password });
      await this.router.navigateByUrl('/dashboard');
    } catch {
      // AuthService owns the safe user-facing error state.
    } finally {
      this.busy.set(false);
    }
  }
}
