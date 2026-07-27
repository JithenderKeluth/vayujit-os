import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { AuthService } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('detects first-time setup', async () => {
    const initialization = service.initialize();
    const request = http.expectOne('http://127.0.0.1:8000/api/v1/auth/setup-status');
    expect(request.request.withCredentials).toBe(true);
    request.flush({ ownerExists: false });
    await initialization;
    expect(service.setupRequired()).toBe(true);
    expect(service.initialized()).toBe(true);
  });

  it('restores an authenticated session', async () => {
    const initialization = service.initialize();
    http.expectOne('http://127.0.0.1:8000/api/v1/auth/setup-status').flush({
      ownerExists: true,
    });
    await Promise.resolve();
    http.expectOne('http://127.0.0.1:8000/api/v1/auth/me').flush({
      id: 'owner-id',
      fullName: 'Local Owner',
      email: 'owner@example.com',
      role: 'owner',
    });
    await initialization;
    expect(service.user()?.email).toBe('owner@example.com');
  });

  it('clears local authentication state after logout', async () => {
    service.user.set({
      id: 'owner-id',
      fullName: 'Local Owner',
      email: 'owner@example.com',
      role: 'owner',
    });
    const logout = service.logout();
    const request = http.expectOne('http://127.0.0.1:8000/api/v1/auth/logout');
    expect(request.request.withCredentials).toBe(true);
    request.flush(null);
    await logout;
    expect(service.user()).toBeNull();
  });
});
