import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ExternalResearchWorkspaceComponent } from './external-research-workspace.component';

const base = 'http://127.0.0.1:8000/api/v1/intelligence/external';

function create() {
  TestBed.configureTestingModule({
    imports: [ExternalResearchWorkspaceComponent],
    providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
  });
  const fixture = TestBed.createComponent(ExternalResearchWorkspaceComponent);
  return { fixture, http: TestBed.inject(HttpTestingController) };
}

function flushWorkspace(
  http: HttpTestingController,
  options: {
    history?: Record<string, unknown>;
    searches?: unknown[];
    results?: unknown[];
    fetches?: unknown[];
    evidence?: unknown[];
    tables?: unknown[];
  } = {},
) {
  http.expectOne(`${base}/policy`).flush({
    provider: 'deterministic',
    mode: 'LOCAL_FIXTURE',
    status: 'LOCAL_FIXTURE',
    search_enabled: true,
    fetch_enabled: true,
    kill_switch: false,
    provider_kill_switch: false,
    approved_domains_configured: true,
    credentials_configured: false,
    allowed_modes: ['LOCAL_FIXTURE'],
    robots_policy: 'UNKNOWN',
    terms_status: 'UNKNOWN',
  });
  http.expectOne(`${base}/status`).flush({
    provider: 'deterministic',
    mode: 'LOCAL_FIXTURE',
    status: 'LOCAL_FIXTURE',
    quota: [],
  });
  http.expectOne(`${base}/searches`).flush(options.searches ?? []);
  http.expectOne(`${base}/results`).flush(options.results ?? []);
  http.expectOne(`${base}/fetches`).flush(options.fetches ?? []);
  http.expectOne(`${base}/evidence`).flush(options.evidence ?? []);
  http.expectOne(`${base}/history`).flush(options.history ?? {});
  http.expectOne(`${base}/integrity`).flush({ classification: 'PASS' });
  http.expectOne(`${base}/performance`).flush({
    classification: 'PASS',
    timing_mode: 'local_fixture',
    live_timing_status: 'NOT_MEASURED',
  });
  http.expectOne(`${base}/calendar`).flush([]);
  http.expectOne(`${base}/alerts`).flush([]);
  http.expectOne(`${base}/recovery/catalog`).flush({ actions: ['retry', 'review_source'] });
  http.expectOne(`${base}/executions`).flush([]);
  http.expectOne(`${base}/tables`).flush(options.tables ?? []);
}

describe('ExternalResearchWorkspaceComponent', () => {
  it('renders accessible navigation, truthful local status, empty states, and all status matrices', async () => {
    const { fixture, http } = create();
    flushWorkspace(http);
    await fixture.whenStable();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('main[aria-labelledby="external-title"]')).not.toBeNull();
    expect(root.querySelector('nav[aria-label="External Research sections"]')).not.toBeNull();
    expect(root.textContent).toContain('LIVE SEARCH ? NOT VALIDATED');
    expect(root.textContent).toContain('No searches yet.');
    expect(root.textContent).toContain('No fetch history yet.');
    expect(root.textContent).toContain('No external Evidence yet.');
    expect(root.textContent).toContain('No contradictions detected.');
    expect(root.textContent).toContain('No Alerts.');
    expect(root.textContent).toContain('No Recovery records.');
    for (const state of [
      'DISABLED',
      'LOCAL_FIXTURE',
      'SANDBOX',
      'LIVE_READ_ONLY',
      'DEGRADED',
      'RATE_LIMITED',
      'AUTH_ERROR',
      'UNAVAILABLE',
    ])
      expect(root.textContent).toContain(state);
    for (const state of ['APPROVED', 'BLOCKED', 'REVIEW_REQUIRED', 'UNKNOWN'])
      expect(root.textContent).toContain(state);
    http.verify();
  });

  it('renders safe evidence, search, fetch, contradiction, change, alert, recovery and calendar data', async () => {
    const { fixture, http } = create();
    flushWorkspace(http, {
      history: {
        contradictions: [
          { id: 'c1', contradiction_type: 'PRICE', identity_key: 'sku-1', status: 'OPEN' },
        ],
        changes: [
          {
            id: 'ch1',
            identity_key: 'sku-1',
            field_key: 'price',
            material: true,
            reason: 'source changed',
          },
        ],
        recovery: [
          {
            id: 'r1',
            failure_code: 'fetch_timeout',
            action: 'retry',
            status: 'QUEUED',
            correlation_id: 'corr-1',
          },
        ],
      },
      searches: [
        {
          id: 's1',
          query: '<script>alert(1)</script>',
          provider: 'deterministic',
          mode: 'LOCAL_FIXTURE',
          status: 'COMPLETED',
          result_count: 1,
          correlation_id: 'corr-1',
        },
      ],
      results: [
        {
          id: 'result-1',
          title: '<script>bad</script>',
          url: 'javascript:alert(1)',
          domain: 'example.org',
          snippet: 'DISCOVERY ONLY',
          provider: 'deterministic',
          rank: 1,
          source_classification: 'APPROVED',
        },
      ],
      fetches: [
        {
          id: 'f1',
          requested_url: 'https://example.org/item',
          domain: 'example.org',
          status: 'COMPLETED',
          content_type: 'text/plain',
          content_length: 12,
          freshness: 'FRESH',
          verification_status: 'VERIFIED',
        },
      ],
      evidence: [
        {
          id: 'e1',
          source_reference: 'example.org',
          source_class: 'WEB',
          verification_status: 'VERIFIED',
          freshness_status: 'FRESH',
          evidence_class: 'OBSERVED',
          retrieved_at: '2026-01-01T00:00:00Z',
        },
      ],
    });
    await fixture.whenStable();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('DISCOVERY ONLY');
    expect(root.textContent).toContain('PRICE');
    expect(root.textContent).toContain('MATERIAL');
    expect(root.textContent).toContain('fetch_timeout');
    expect(root.innerHTML).not.toContain('<script>');
    expect(root.textContent).toContain('UNTRUSTED EXTERNAL CONTENT');
    const links = Array.from(root.querySelectorAll('a[target="_blank"]'));
    expect(links.every((link) => link.getAttribute('rel') === 'noopener noreferrer')).toBe(true);
    http.verify();
  });

  it('keeps product-channel lookup owner-scoped and renders a safe error', async () => {
    const { fixture, http } = create();
    flushWorkspace(http);
    await fixture.whenStable();
    fixture.detectChanges();
    const input = fixture.nativeElement.querySelector('#channel-product-id') as HTMLInputElement;
    input.value = 'forged-product';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    const form = fixture.nativeElement.querySelector('.inline-form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit'));
    const request = http.expectOne(`${base}/products/forged-product/channel`);
    request.flush(
      { detail: 'Product not found. SQL traceback / token' },
      { status: 404, statusText: 'Not Found' },
    );
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Product Channel data is unavailable');
    expect(fixture.nativeElement.textContent).not.toContain('traceback');
    http.verify();
  });

  it('shows a safe workspace error when every external endpoint is unavailable', async () => {
    const { fixture, http } = create();
    for (const request of http.match(() => true))
      request.flush({}, { status: 503, statusText: 'Unavailable' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]')).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain('External research data is unavailable');
    expect(fixture.nativeElement.textContent.toLowerCase()).not.toContain('traceback');
    http.verify();
  });
});
