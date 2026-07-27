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
});
