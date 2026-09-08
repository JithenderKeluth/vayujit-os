import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { SupplierShortlistingComponent } from './supplier-shortlisting.component';

const base = '/api/v1/intelligence/supplier-shortlisting';

function create() {
  TestBed.configureTestingModule({
    imports: [SupplierShortlistingComponent],
    providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
  });
  const fixture = TestBed.createComponent(SupplierShortlistingComponent);
  return { fixture, http: TestBed.inject(HttpTestingController) };
}

function flushOperations(http: HttpTestingController, metrics: Record<string, unknown> = {}) {
  http.expectOne(base + '/operations').flush({
    active_contexts: 0,
    shortlist_count: 0,
    handoff_count: 0,
    ...metrics,
  });
}

describe('SupplierShortlistingComponent', () => {
  it('renders loading and successful empty states accessibly', async () => {
    const { fixture, http } = create();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="status"]')).not.toBeNull();
    flushOperations(http);
    await fixture.whenStable();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('main[aria-labelledby="shortlisting-title"]')).not.toBeNull();
    expect(root.querySelector('h1#shortlisting-title')).not.toBeNull();
    expect(root.querySelector('label[for="context-id"]')).not.toBeNull();
    expect(root.querySelector('button[type="button"]')).not.toBeNull();
    expect(root.textContent).toContain('Active contexts 0');
    expect(root.textContent).toContain('Shortlists 0');
    expect(root.textContent).toContain('INTERNAL HANDOFF ONLY');
    expect(root.textContent).toContain('Human approval is required');
    expect(root.querySelector('[role="alert"]')).toBeNull();
    http.verify();
  });

  it('renders a safe API error without diagnostics', async () => {
    const { fixture, http } = create();
    const operation = http.expectOne(base + '/operations');
    operation.flush({ detail: 'SQL traceback token' }, { status: 503, statusText: 'Unavailable' });
    await fixture.whenStable();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('[role="alert"]')).not.toBeNull();
    expect(root.textContent).toContain('Supplier shortlisting data is unavailable.');
    expect(root.textContent?.toLowerCase()).not.toContain('traceback');
    expect(root.textContent?.toLowerCase()).not.toContain('token');
    http.verify();
  });

  it('keeps evaluation server-authoritative and blocks duplicate pending action', async () => {
    const { fixture, http } = create();
    flushOperations(http, { active_contexts: 1, shortlist_count: 2, handoff_count: 0 });
    await fixture.whenStable();
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component.contextId = 'context-1';
    fixture.detectChanges();
    const evaluate = component.evaluate();
    const request = http.expectOne(base + '/contexts/context-1/shortlists');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toMatchObject({ context_version: 1, top_n: 5 });
    fixture.detectChanges();
    expect((fixture.nativeElement.querySelector('button') as HTMLButtonElement).disabled).toBe(
      true,
    );
    request.flush({ status: 'succeeded', shortlist: [{ supplier_id: 'supplier-1', score: 91 }] });
    await evaluate;
    await fixture.whenStable();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('supplier-1');
    expect(root.textContent).toContain(
      'Eligibility, scoring, evidence, risk, freshness, and contradiction gates are server-derived.',
    );
    expect((fixture.nativeElement.querySelector('button') as HTMLButtonElement).disabled).toBe(
      false,
    );
    http.verify();
  });

  it('renders untrusted response data as text rather than executable HTML', async () => {
    const { fixture, http } = create();
    flushOperations(http);
    await fixture.whenStable();
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component.contextId = 'context-x';
    const evaluate = component.evaluate();
    const request = http.expectOne(base + '/contexts/context-x/shortlists');
    request.flush({ status: 'succeeded', message: '<script>alert(1)</script>' });
    await evaluate;
    await fixture.whenStable();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.innerHTML).not.toContain('<script>');
    expect(root.textContent).toContain('<script>alert(1)</script>');
    http.verify();
  });
});
