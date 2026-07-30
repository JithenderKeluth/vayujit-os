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

  it('previews bounded timezone-aware recurring occurrences', async () => {
    const result = service.previewSchedule({
      local_scheduled_at: '2026-08-10T09:00:00',
      timezone_name: 'Asia/Kolkata',
      schedule_type: 'recurring',
      recurrence: { frequency: 'daily', interval: 1, fold: 0 },
      count: 5,
    });
    const request = http.expectOne((candidate) => candidate.url.endsWith('/schedules/preview'));
    expect(request.request.body.timezone_name).toBe('Asia/Kolkata');
    expect(request.request.body.count).toBe(5);
    request.flush({
      occurrences: [{ local: '2026-08-10T09:00:00', utc: '2026-08-10T03:30:00Z' }],
      dst_warning: null,
    });
    expect((await result).occurrences[0].utc).toContain('03:30');
  });

  it('requires an explicit missed-occurrence policy when resuming', async () => {
    const result = service.scheduleAction('schedule-1', 'resume', 'one_catch_up');
    const request = http.expectOne((candidate) =>
      candidate.url.endsWith('/schedules/schedule-1/resume'),
    );
    expect(request.request.body).toEqual({ policy: 'one_catch_up' });
    request.flush({ id: 'schedule-1', paused: false });
    expect((await result).paused).toBe(false);
  });

  it('loads safe job attempts and operations worker details', async () => {
    const attempts = service.jobAttempts('job-1');
    http
      .expectOne((candidate) => candidate.url.endsWith('/jobs/job-1/attempts'))
      .flush([{ id: 'attempt-1', outcome: 'lease_lost' }]);
    expect((await attempts)[0].outcome).toBe('lease_lost');

    const worker = service.worker('worker-safe');
    const request = http.expectOne((candidate) =>
      candidate.url.endsWith('/operations/workers/worker-safe'),
    );
    request.flush({ worker_id: 'worker-safe', recent_jobs: [] });
    expect((await worker).worker_id).toBe('worker-safe');
    expect(request.request.url).not.toContain('database');
  });
});
