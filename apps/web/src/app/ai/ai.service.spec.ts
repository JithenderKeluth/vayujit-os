import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AIService } from './ai.service';

describe('AIService', () => {
  let service: AIService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AIService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('creates a credentialed generation request', async () => {
    const result = service.generate({
      product_id: 'product-1',
      additional_instructions: 'Friendly',
    });
    const request = http.expectOne('http://127.0.0.1:8000/api/v1/ai/generations');
    expect(request.request.withCredentials).toBe(true);
    expect(request.request.body.additional_instructions).toBe('Friendly');
    request.flush({ id: 'generation-1', status: 'completed', artifact_id: 'artifact-1' });
    expect((await result).artifact_id).toBe('artifact-1');
  });

  it('passes history filters and pagination', async () => {
    const result = service.history({ productId: 'product-1', artifactStatus: 'approved', page: 2 });
    const request = http.expectOne(
      (candidate) =>
        candidate.url.endsWith('/ai/generations') &&
        candidate.params.get('product_id') === 'product-1' &&
        candidate.params.get('artifact_status') === 'approved' &&
        candidate.params.get('page') === '2',
    );
    request.flush({ items: [], page: 2, page_size: 20, total: 0, pages: 0 });
    expect((await result).page).toBe(2);
  });

  it('uses explicit review endpoints', async () => {
    const approving = service.approve('artifact-1');
    http
      .expectOne((request) => request.url.endsWith('/artifacts/artifact-1/approve'))
      .flush({ id: 'artifact-1', status: 'approved' });
    expect((await approving).status).toBe('approved');

    const rejecting = service.reject('artifact-2', 'Needs work');
    const request = http.expectOne((candidate) =>
      candidate.url.endsWith('/artifacts/artifact-2/reject'),
    );
    expect(request.request.body).toEqual({ reason: 'Needs work' });
    request.flush({ id: 'artifact-2', status: 'rejected' });
    expect((await rejecting).status).toBe('rejected');
  });

  it('saves provider credentials only in a backend request', async () => {
    const result = service.saveProvider({
      api_key: 'temporary-secret',
      base_url: 'https://api.example.com/v1',
      default_model: 'product-model',
      manual_model_allowed: false,
      enabled: true,
      fallback_provider_key: 'deterministic_mock_v1',
      request_timeout_seconds: 45,
      max_retry_attempts: 3,
    });
    const request = http.expectOne('http://127.0.0.1:8000/api/v1/ai/providers/openai_compatible');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body.api_key).toBe('temporary-secret');
    request.flush({
      provider_key: 'openai_compatible',
      configured: true,
      credential_source: 'application',
      masked_credential: '••••cret',
    });
    const response = await result;
    expect(response.masked_credential).toBe('••••cret');
    expect('api_key' in response).toBe(false);
  });

  it('loads models, usage, attempts, validation, and cancellation from bounded endpoints', async () => {
    const models = service.models();
    http
      .expectOne((request) => request.url.endsWith('/providers/openai_compatible/models'))
      .flush([{ identifier: 'model-1' }]);
    expect((await models)[0]?.identifier).toBe('model-1');

    const usage = service.usage();
    http
      .expectOne((request) => request.url.endsWith('/usage/summary'))
      .flush({ requests: 1, total_tokens: 50 });
    expect((await usage).total_tokens).toBe(50);

    const attempts = service.attempts('generation-1');
    http
      .expectOne((request) => request.url.endsWith('/generations/generation-1/attempts'))
      .flush([{ id: 'attempt-1', status: 'succeeded' }]);
    expect((await attempts)[0]?.status).toBe('succeeded');

    const validation = service.validateProvider();
    http
      .expectOne((request) => request.url.endsWith('/providers/openai_compatible/validate'))
      .flush({ valid: true, correlation_id: 'correlation-1' });
    expect((await validation).valid).toBe(true);

    const cancellation = service.cancel('generation-2');
    http
      .expectOne((request) => request.url.endsWith('/generations/generation-2/cancel'))
      .flush({ id: 'generation-2', status: 'cancelled', remote_cancellation: false });
    expect((await cancellation).remote_cancellation).toBe(false);
  });
});
