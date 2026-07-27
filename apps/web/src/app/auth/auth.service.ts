import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type { AuthenticatedUserResponse, LoginRequest, OwnerSetupRequest } from '@vayujit/shared';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  readonly initialized = signal(false);
  readonly setupRequired = signal(false);
  readonly user = signal<AuthenticatedUserResponse | null>(null);
  readonly error = signal<string | null>(null);
  private request<T>(path: string, body?: unknown): Promise<T> {
    return firstValueFrom(
      body === undefined
        ? this.http.get<T>(`${environment.apiUrl}/auth/${path}`, { withCredentials: true })
        : this.http.post<T>(`${environment.apiUrl}/auth/${path}`, body, { withCredentials: true }),
    );
  }
  async initialize(): Promise<void> {
    this.error.set(null);
    try {
      const status = await this.request<{ ownerExists: boolean }>('setup-status');
      this.setupRequired.set(!status.ownerExists);
      if (status.ownerExists) {
        try {
          this.user.set(await this.request<AuthenticatedUserResponse>('me'));
        } catch {
          this.user.set(null);
        }
      }
    } catch {
      this.user.set(null);
      this.setupRequired.set(false);
      this.error.set(
        'Cannot connect to the local VAYUJIT API. Confirm the API is running and the database is migrated.',
      );
    } finally {
      this.initialized.set(true);
    }
  }
  async setup(data: OwnerSetupRequest): Promise<void> {
    this.error.set(null);
    try {
      this.user.set(
        await this.request<AuthenticatedUserResponse>('setup-owner', {
          full_name: data.fullName,
          email: data.email,
          password: data.password,
          password_confirmation: data.passwordConfirmation,
        }),
      );
      this.setupRequired.set(false);
    } catch (e) {
      this.fail(e);
    }
  }
  async login(data: LoginRequest): Promise<void> {
    this.error.set(null);
    try {
      this.user.set(await this.request<AuthenticatedUserResponse>('login', data));
    } catch (e) {
      this.fail(e);
    }
  }
  async logout(): Promise<void> {
    try {
      await this.request('logout', {});
    } finally {
      this.user.set(null);
    }
  }
  private fail(error: unknown): never {
    const responseBody: unknown = error instanceof HttpErrorResponse ? error.error : null;
    const detail =
      typeof responseBody === 'object' &&
      responseBody !== null &&
      'detail' in responseBody &&
      typeof responseBody.detail === 'string'
        ? responseBody.detail
        : null;
    const message = detail ?? 'Unable to complete authentication.';
    this.error.set(message);
    throw error;
  }
}
