import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { WorkflowService } from './workflow.service';

describe('WorkflowService', () => {
  let service: WorkflowService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(WorkflowService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('sends owner session credentials and complete list filters', async () => {
    const result = service.list({
      brandId: 'b1',
      productId: 'p1',
      destinationId: 'd1',
      status: 'failed',
      currentStep: 'publish_content',
      retryable: true,
      page: 2,
    });
    const request = http.expectOne(
      (candidate) =>
        candidate.url.endsWith('/workflows') &&
        candidate.params.get('brand_id') === 'b1' &&
        candidate.params.get('product_id') === 'p1' &&
        candidate.params.get('destination_id') === 'd1' &&
        candidate.params.get('status') === 'failed' &&
        candidate.params.get('current_step') === 'publish_content' &&
        candidate.params.get('retryable') === 'true' &&
        candidate.params.get('page') === '2',
    );
    expect(request.request.withCredentials).toBe(true);
    request.flush({ items: [], page: 2, page_size: 20, total: 0, pages: 0 });
    expect((await result).page).toBe(2);
  });

  it('creates only with the constrained workflow inputs', async () => {
    const result = service.create({
      product_id: 'p1',
      destination_id: 'd1',
      workflow_template_id: 't1',
      additional_instructions: null,
    });
    const request = http.expectOne('http://127.0.0.1:8000/api/v1/workflows');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      product_id: 'p1',
      destination_id: 'd1',
      workflow_template_id: 't1',
      additional_instructions: null,
    });
    request.flush({ id: 'w1' });
    expect((await result).id).toBe('w1');
  });

  it('uses explicit state transition endpoints', async () => {
    for (const action of ['start', 'continue', 'retry', 'cancel'] as const) {
      const response = service[action]('w1');
      const request = http.expectOne(`http://127.0.0.1:8000/api/v1/workflows/w1/${action}`);
      expect(request.request.method).toBe('POST');
      request.flush({ id: 'w1', status: action === 'cancel' ? 'cancelled' : 'running' });
      expect((await response).id).toBe('w1');
    }
  });
});
