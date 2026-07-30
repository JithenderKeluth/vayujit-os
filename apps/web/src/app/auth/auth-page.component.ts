import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';
@Component({
  selector: 'app-auth-page',
  imports: [ReactiveFormsModule],
  template: ` <main class="auth">
    <form [formGroup]="form" (ngSubmit)="submit()">
      <p>VAYUJIT OS · Local owner account</p>
      <h1>{{ setup() ? 'Create your owner account' : 'Welcome back' }}</h1>
      @if (setup()) {
        <label>Full name<input formControlName="fullName" autocomplete="name" /></label>
      }
      <label>Email<input type="email" formControlName="email" autocomplete="email" /></label>
      <label
        >Password<input
          [type]="show() ? 'text' : 'password'"
          formControlName="password"
          [autocomplete]="setup() ? 'new-password' : 'current-password'"
      /></label>
      @if (setup()) {
        <label
          >Confirm password<input
            [type]="show() ? 'text' : 'password'"
            formControlName="confirmation"
            autocomplete="new-password"
        /></label>
      }
      <button type="button" (click)="show.set(!show())">
        {{ show() ? 'Hide' : 'Show' }} password
      </button>
      @if (auth.error()) {
        <p role="alert">{{ auth.error() }}</p>
      }
      <button type="submit" [disabled]="form.invalid || busy()">
        {{ busy() ? 'Please wait…' : setup() ? 'Create owner' : 'Sign in' }}
      </button>
    </form>
  </main>`,
  styles: [
    `
      .auth {
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #eef4f2;
      }
      form {
        width: min(26rem, 90vw);
        display: grid;
        gap: 1rem;
        background: white;
        padding: 2rem;
        border-radius: 1rem;
        box-shadow: 0 1rem 3rem #16302b20;
      }
      label {
        display: grid;
        gap: 0.4rem;
      }
      input,
      button {
        padding: 0.8rem;
        font: inherit;
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
