import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { vi } from 'vitest';
import { AIImageReviewComponent } from './ai-image-review.component';

describe('exact image review identity', () => {
  let http: HttpTestingController;
  let navigate: ReturnType<typeof vi.fn>;
  let id: string;
  beforeEach(() => {
    id = 'source';
    navigate = vi.fn().mockImplementation(() => {
      id = 'child';
      return Promise.resolve(true);
    });
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: Router, useValue: { navigate } },
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: () => id } } } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());
  async function review() {
    const component = TestBed.runInInjectionContext(() => new AIImageReviewComponent());
    http
      .expectOne((r) => r.url.endsWith('/outputs/source'))
      .flush({
        id: 'source',
        status: 'approved',
        media_id: 'private-media',
        approval_feedback: null,
      });
    await Promise.resolve();
    await Promise.resolve();
    return component;
  }
  it('uses the credential-protected media preview endpoint, not a public asset', async () => {
    const c = await review();
    expect(c.previewUrl('private-media')).toBe(
      'http://127.0.0.1:8000/api/v1/media/private-media/preview',
    );
  });
  it('reloads the rich projection after a summary-only HUMAN decision response', async () => {
    const c = await review();
    const action = c.approve();
    http
      .expectOne((r) => r.url.endsWith('/outputs/source/approve'))
      .flush({ id: 'source', status: 'approved' });
    await Promise.resolve();
    await Promise.resolve();
    http
      .expectOne((r) => r.url.endsWith('/outputs/source'))
      .flush({
        id: 'source',
        status: 'approved',
        lineage: ['source'],
        readiness: { status: 'ready' },
      });
    await action;
    expect(c.detail()?.lineage).toEqual(['source']);
  });
  it('navigates to the actual queued child and does not inherit source approval', async () => {
    const c = await review();
    const action = c.regenerate();
    const req = http.expectOne((r) => r.url.endsWith('/outputs/source/regenerate'));
    expect(req.request.withCredentials).toBe(true);
    req.flush({ outputs: [{ id: 'child' }] });
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    http
      .expectOne((r) => r.url.endsWith('/outputs/child'))
      .flush({ id: 'child', status: 'queued', media_id: null });
    await action;
    expect(navigate).toHaveBeenCalledWith(['/ai/images/assets', 'child']);
    expect(c.detail()?.status).toBe('queued');
  });
  it('retries only the exact failed image job and prevents duplicate requests', async () => {
    const c = TestBed.runInInjectionContext(() => new AIImageReviewComponent());
    http
      .expectOne((r) => r.url.endsWith('/outputs/source'))
      .flush({ id: 'source', job_id: 'job', status: 'failed', media_id: null });
    await Promise.resolve();
    await Promise.resolve();
    http
      .expectOne((r) => r.url.endsWith('/studio/recovery/actions'))
      .flush({
        status: 'failed',
        retryable: true,
        safe_error_message: 'Local provider unavailable',
      });
    await Promise.resolve();
    await Promise.resolve();
    const pending = c.retryOutput();
    void c.retryOutput();
    const request = http.expectOne((r) => r.url.endsWith('/studio/recovery/actions'));
    expect(request.request.body).toEqual({ action: 'retry_generation', job_id: 'job' });
    request.flush({ status: 'retry_wait' });
    await Promise.resolve();
    await Promise.resolve();
    http
      .expectOne((r) => r.url.endsWith('/outputs/source'))
      .flush({ id: 'source', job_id: 'job', status: 'queued', media_id: null });
    await pending;
    expect(c.detail()?.id).toBe('source');
    expect(navigate).not.toHaveBeenCalled();
  });
  it('does not claim or navigate to a child on failed regeneration', async () => {
    const c = await review();
    const action = c.regenerate();
    http
      .expectOne((r) => r.url.endsWith('/outputs/source/regenerate'))
      .flush({}, { status: 409, statusText: 'Conflict' });
    await action;
    expect(navigate).not.toHaveBeenCalled();
    expect(c.error()).toBeTruthy();
    expect(c.detail()?.id).toBe('source');
  });
});
