import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { PublishingService } from './publishing.service';

describe('PublishingService', () => {
  let service: PublishingService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(PublishingService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('loads destination filters and pagination with credentials', async () => {
    const result = service.destinations({
      search: 'store',
      brandId: 'brand-1',
      status: 'active',
      page: 2,
    });
    const request = http.expectOne(
      (candidate) =>
        candidate.url.endsWith('/publishing/destinations') &&
        candidate.params.get('search') === 'store' &&
        candidate.params.get('brand_id') === 'brand-1' &&
        candidate.params.get('status') === 'active' &&
        candidate.params.get('page') === '2',
    );
    expect(request.request.withCredentials).toBe(true);
    request.flush({ items: [], page: 2, page_size: 20, total: 0, pages: 0 });
    expect((await result).page).toBe(2);
  });

  it('passes complete execution history filters', async () => {
    const result = service.executions({
      productId: 'p1',
      destinationId: 'd1',
      retryable: true,
      dateFrom: '2026-01-01T00:00:00Z',
    });
    const request = http.expectOne(
      (candidate) =>
        candidate.url.endsWith('/publishing/executions') &&
        candidate.params.get('product_id') === 'p1' &&
        candidate.params.get('destination_id') === 'd1' &&
        candidate.params.get('retryable') === 'true',
    );
    request.flush({ items: [], page: 1, page_size: 20, total: 0, pages: 0 });
    expect((await result).total).toBe(0);
  });

  it('preserves the supplied idempotency key', async () => {
    const publishing = service.publish({
      artifact_id: 'a1',
      destination_id: 'd1',
      idempotency_key: 'intent-key-1',
    });
    const request = http.expectOne('http://127.0.0.1:8000/api/v1/publishing/executions');
    expect(request.request.body.idempotency_key).toBe('intent-key-1');
    request.flush({ id: 'e1', status: 'succeeded' });
    expect((await publishing).id).toBe('e1');
  });

  it('calls explicit destination lifecycle and execution retry endpoints', async () => {
    const disabling = service.destinationStatus('d1', 'disable');
    http
      .expectOne((candidate) => candidate.url.endsWith('/destinations/d1/disable'))
      .flush({ id: 'd1', status: 'disabled' });
    expect((await disabling).status).toBe('disabled');
    const retrying = service.retry('e1');
    const request = http.expectOne((candidate) => candidate.url.endsWith('/executions/e1/retry'));
    request.flush({ id: 'e1', status: 'succeeded' });
    expect((await retrying).status).toBe('succeeded');
  });
});
