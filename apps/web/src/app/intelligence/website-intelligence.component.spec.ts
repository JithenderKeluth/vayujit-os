import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { WebsiteIntelligenceComponent } from './website-intelligence.component';

const base = 'http://127.0.0.1:8000/api/v1/intelligence/websites';

function create() {
  TestBed.configureTestingModule({
    imports: [WebsiteIntelligenceComponent],
    providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
  });
  const fixture = TestBed.createComponent(WebsiteIntelligenceComponent);
  return { fixture, http: TestBed.inject(HttpTestingController) };
}

function flushInitial(
  http: HttpTestingController,
  manufacturers: unknown[] = [],
  jobs: unknown[] = [],
  projections: {
    contradictions?: unknown[];
    changes?: unknown[];
    alerts?: unknown[];
    reports?: unknown[];
  } = {},
) {
  http.expectOne(`${base}/overview`).flush({
    manufacturer_candidates: manufacturers.length,
    supplier_websites: 0,
    offering_count: 0,
    last_researched: null,
    status: 'LOCAL_CERTIFIED',
    queue: 0,
    running: 0,
    failed: 0,
    refresh_backlog: 0,
    stale_sources: 0,
    expired_sources: 0,
    high_risk_suppliers: 0,
    unresolved_contradictions: 0,
    recovery: 0,
  });
  http.expectOne(`${base}/manufacturers`).flush(manufacturers);
  http.expectOne(`${base}/suppliers`).flush([]);
  http.expectOne(`${base}/profiles`).flush({ profiles: [], status: 'NOT_CONFIGURED' });
  http.expectOne(`${base}/refresh/jobs`).flush(jobs);
  http.expectOne(`${base}/calendar`).flush([]);
  http.expectOne(`${base}/history`).flush([]);
  http.expectOne(`${base}/refresh/recovery/catalog`).flush({ failure_codes: [], actions: [] });
  http
    .expectOne((item) => item.url.endsWith('/contradictions'))
    .flush(projections.contradictions ?? []);
  http.expectOne((item) => item.url.endsWith('/changes')).flush(projections.changes ?? []);
  http.expectOne((item) => item.url.endsWith('/alerts')).flush(projections.alerts ?? []);
  http.expectOne((item) => item.url.endsWith('/reports')).flush(projections.reports ?? []);
}

describe('WebsiteIntelligenceComponent', () => {
  afterEach(() => vi.restoreAllMocks());

  it('renders complete navigation, truthful runtime boundary, loading and empty states', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('main[aria-labelledby="website-intelligence-title"]')).not.toBeNull();
    expect(root.querySelector('nav[aria-label="Website Intelligence sections"]')).not.toBeNull();
    expect(root.textContent).toContain('LIVE BROAD WEB');
    expect(root.textContent).toContain('RECURSIVE CRAWLING');
    expect(root.textContent).toContain('EXTERNAL AI');
    expect(root.textContent).toContain('SUPPLIER CONTACT');
    expect(root.textContent).toContain('No manufacturers match these server-aligned filters.');
    expect(root.textContent).toContain('No source profiles yet.');
    expect(root.textContent).toContain('No refresh jobs yet.');
    expect(root.textContent).toContain('No history yet.');
    expect(root.textContent).toContain('No reports yet.');
    for (const label of [
      'Overview',
      'Manufacturers',
      'Supplier Websites',
      'Offerings',
      'Capabilities',
      'Certifications',
      'Commercial Intelligence',
      'Risk',
      'Contradictions',
      'Changes',
      'Alerts',
      'Source Profiles',
      'Refresh',
      'Recovery',
      'History',
      'Reports',
      'Product Channel',
      'Calendar',
      'Operations',
    ])
      expect(root.textContent).toContain(label);
    http.verify();
  });

  it('renders server-backed manufacturer fields and all status matrices', async () => {
    const manufacturer = {
      id: 'm1',
      name: '<script>blocked</script>',
      website: 'https://example.test',
      domain: 'example.test',
      country: 'IN',
      region: 'KA',
      business_type: 'Manufacturer',
      verification: 'UNVERIFIED',
      freshness: 'FRESH',
      confidence: 0.35,
      risk: ['missing_legal_identity'],
      source_count: 1,
      evidence_count: 2,
    };
    const { fixture, http } = create();
    flushInitial(http, [manufacturer]);
    await fixture.whenStable();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('Manufacturer');
    expect(root.textContent).toContain('UNVERIFIED');
    expect(root.textContent).toContain('POSSIBLE_MATCH');
    expect(root.textContent).toContain('NO_LONGER_OBSERVED');
    expect(root.textContent).toContain('DOCUMENT_REFERENCED');
    expect(root.textContent).toContain('RESOLVED / NO_LONGER_ACTIVE');
    expect(root.innerHTML).not.toContain('<script>');
    http.verify();
  });

  it('uses server-aligned filters and renders safe API failures', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.detectChanges();
    fixture.componentInstance.filters.country = 'IN';
    const reload = fixture.componentInstance.reloadManufacturers();
    const request = http.expectOne(
      (item) => item.urlWithParams === `${base}/manufacturers?country=IN`,
    );
    request.flush([], { status: 503, statusText: 'Unavailable' });
    await reload;
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Manufacturer data is unavailable.');
    expect(fixture.nativeElement.textContent.toLowerCase()).not.toContain('traceback');
    http.verify();
  });

  it('guards duplicate refresh clicks and offers only catalog actions', async () => {
    const job = {
      id: 'j1',
      source_profile_id: 'p1',
      target_type: 'WEBSITE_SOURCE',
      scheduled_for: '2026-08-29T00:00:00Z',
      status: 'FAILED',
      failure_code: 'fetch_timeout',
      mission_id: null,
    };
    const { fixture, http } = create();
    flushInitial(http, [], [job]);
    await fixture.whenStable();
    fixture.detectChanges();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const first = fixture.componentInstance.runRefresh(job);
    const second = fixture.componentInstance.runRefresh(job);
    const requests = http.match(`${base}/refresh/jobs/j1/run`);
    expect(requests).toHaveLength(1);
    requests[0].flush({ id: 'j1', status: 'SUCCEEDED' });
    await Promise.resolve();
    flushInitial(http, [], [job]);
    await first;
    await second;
    await fixture.whenStable();
    http.verify();
  });
  it('renders server-backed projection data and a detail response', async () => {
    const { fixture, http } = create();
    flushInitial(http, [], [], {
      contradictions: [
        {
          id: 'c1',
          field: 'MOQ',
          source_a: 'a.example',
          source_b: 'b.example',
          resolution_state: 'UNRESOLVED',
          correlation_id: 'corr-1',
        },
      ],
      changes: [
        {
          id: 'ch1',
          field: 'lead_time',
          materiality: 'MATERIAL',
          reason: 'increase',
          correlation_id: 'corr-2',
        },
      ],
      alerts: [
        {
          id: 'al1',
          type: 'HIGH_RISK_CONTRADICTION',
          severity: 'HIGH',
          title: 'Review contradiction',
          review_state: 'OPEN',
          correlation_id: 'corr-3',
        },
      ],
      reports: [
        {
          id: 'r1',
          mission_id: 'm1',
          format: 'JSON',
          status: 'AVAILABLE',
          correlation_id: 'corr-4',
        },
      ],
    });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('HIGH_RISK_CONTRADICTION');
    expect(fixture.nativeElement.textContent).toContain('lead_time');
    expect(fixture.nativeElement.textContent).toContain('corr-4');
    const view = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent?.trim() === 'View');
    view!.click();
    http
      .expectOne(`${base}/contradictions/c1`)
      .flush({ id: 'c1', reason: 'Needs review', correlation_id: 'corr-1' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Needs review');
    http.verify();
  });

  it('loads and renders the selected Product Channel projection', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.componentInstance.productChannelId = 'product-1';
    const requestPromise = fixture.componentInstance.loadProductChannel();
    expect(fixture.componentInstance.productChannelLoading()).toBe(true);
    http.expectOne(`${base}/product-channel/product-1`).flush({
      product_id: 'product-1',
      website_research_status: 'available',
      manufacturer_candidate_count: 2,
      supplier_website_candidate_count: 1,
      offering_count: 3,
      freshness: 'FRESH',
      confidence: 0.91,
      risk: ['LOW'],
      verification: 'VERIFIED',
      material_change_count: 0,
      open_contradiction_count: 0,
      active_alert_count: 0,
      refresh_due: false,
      follow_up_required: false,
    });
    await requestPromise;
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('website_research_status');
    expect(fixture.nativeElement.textContent).toContain('0.91');
    expect(fixture.nativeElement.textContent).toContain('VERIFIED');
    expect(fixture.componentInstance.productChannelLoading()).toBe(false);
    http.verify();
  });

  it('does not request a Product Channel projection without a Product', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    await fixture.componentInstance.loadProductChannel();
    expect(fixture.nativeElement.textContent).toContain('Enter an owner-scoped Product ID');
    http.expectNone((request) => request.url.includes('/product-channel/'));
    http.verify();
  });

  it('renders the no-research state without inventing conclusions', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.componentInstance.productChannelId = 'product-2';
    const promise = fixture.componentInstance.loadProductChannel();
    http.expectOne(`${base}/product-channel/product-2`).flush({
      website_research_status: 'not_started',
      manufacturer_candidate_count: 0,
      supplier_website_candidate_count: 0,
      offering_count: 0,
      freshness: 'UNKNOWN',
      confidence: 'UNKNOWN',
      risk: 'UNKNOWN',
      verification: 'UNKNOWN',
      material_change_count: 0,
      open_contradiction_count: 0,
      active_alert_count: 0,
      refresh_due: false,
      follow_up_required: false,
    });
    await promise;
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('not_started');
    expect(fixture.nativeElement.textContent).toContain('UNKNOWN');
    http.verify();
  });

  it('renders a safe Product Channel error for owner rejection', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.componentInstance.productChannelId = 'foreign-product';
    const promise = fixture.componentInstance.loadProductChannel();
    http
      .expectOne(`${base}/product-channel/foreign-product`)
      .flush({ detail: 'not found' }, { status: 404, statusText: 'Not Found' });
    await promise;
    fixture.detectChanges();
    const text = (fixture.nativeElement.textContent as string).toLowerCase();
    expect(text).toContain('product channel data is unavailable');
    expect(text).not.toContain('traceback');
    expect(text).not.toContain('sql');
    expect(text).not.toContain('token');
    http.verify();
  });

  it('renders backend Product Channel values unchanged', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.componentInstance.productChannelId = 'product-3';
    const promise = fixture.componentInstance.loadProductChannel();
    http.expectOne(`${base}/product-channel/product-3`).flush({
      website_research_status: 'available',
      confidence: 0.1234,
      risk: ['HIGH', 'CERTIFICATION_EXPIRED'],
      verification: 'SOURCE_PROVIDED',
      material_change_count: 7,
      open_contradiction_count: 4,
      active_alert_count: 2,
      refresh_due: true,
      follow_up_required: true,
    });
    await promise;
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('0.1234');
    expect(text).toContain('HIGH, CERTIFICATION_EXPIRED');
    expect(text).toContain('SOURCE_PROVIDED');
    expect(text).toContain('true');
    http.verify();
  });

  it('exposes no invented Product Channel action buttons', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.componentInstance.productChannelId = 'product-4';
    const promise = fixture.componentInstance.loadProductChannel();
    http.expectOne(`${base}/product-channel/product-4`).flush({
      website_research_status: 'available',
      actions: [],
    });
    await promise;
    fixture.detectChanges();
    const section = fixture.nativeElement.querySelector('#product-channel') as HTMLElement;
    expect(section.textContent).not.toContain('contact_supplier');
    expect(section.textContent).not.toContain('send_rfq');
    expect(section.textContent).not.toContain('purchase');
    http.verify();
  });

  it('keeps Product Channel context bounded to the selected Product reference', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.componentInstance.productChannelId = 'product/encoded';
    const promise = fixture.componentInstance.loadProductChannel();
    http.expectOne(`${base}/product-channel/product%2Fencoded`).flush({
      product_id: 'product/encoded',
      website_research_status: 'not_started',
    });
    await promise;
    expect(fixture.componentInstance.productChannel()?.['product_id']).toBe('product/encoded');
    http.verify();
  });

  it('keeps the Product Channel control keyboard-accessible', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.detectChanges();
    const section = fixture.nativeElement.querySelector('#product-channel') as HTMLElement;
    expect(section.querySelector('h2')).not.toBeNull();
    expect(section.querySelector('label[for="website-channel-product-id"]')).not.toBeNull();
    expect(section.querySelector('button[type="submit"]')).not.toBeNull();
    http.verify();
  });
});
