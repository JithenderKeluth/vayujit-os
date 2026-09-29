import { HttpClient } from '@angular/common/http';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../environments/environment';
import { apiCredentialsInterceptor } from './api-credentials.interceptor';

describe('apiCredentialsInterceptor', () => {
  let http: HttpClient;
  let requests: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiCredentialsInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    requests = TestBed.inject(HttpTestingController);
  });

  afterEach(() => requests.verify());

  it('sends the existing session cookie only to the configured API', () => {
    http.get(`${environment.apiUrl}/intelligence/competitors/contexts`).subscribe();
    const apiRequest = requests.expectOne(
      `${environment.apiUrl}/intelligence/competitors/contexts`,
    );
    expect(apiRequest.request.withCredentials).toBe(true);
    apiRequest.flush([]);

    http.get('https://example.invalid/health').subscribe();
    const externalRequest = requests.expectOne('https://example.invalid/health');
    expect(externalRequest.request.withCredentials).toBe(false);
    externalRequest.flush({});
  });
});
