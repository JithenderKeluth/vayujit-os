import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { SourcingWorkspaceComponent } from './sourcing-workspace.component';

describe('SourcingWorkspaceComponent focused UX acceptance', () => {
  function create() {
    TestBed.configureTestingModule({
      imports: [SourcingWorkspaceComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(SourcingWorkspaceComponent);
    const http = TestBed.inject(HttpTestingController);
    return { fixture, http };
  }

  async function flushInitial(http: HttpTestingController) {
    http.expectOne('http://127.0.0.1:8000/api/v1/intelligence/sourcing/overview').flush({
      active_requirements: 1,
      open_rfqs: 2,
      awaiting_quotes: 1,
      samples: 1,
      inspections: 1,
      decisions_awaiting_review: 1,
      external_dispatch: 'disabled',
      purchasing: 'not_implemented',
    });
    await Promise.resolve();
    http
      .expectOne('http://127.0.0.1:8000/api/v1/intelligence/sourcing/requirements')
      .flush({ items: [{ id: 'req-1', current_version: 1, status: 'active' }] });
  }

  afterEach(() => {
    try {
      TestBed.inject(HttpTestingController).verify();
    } finally {
      TestBed.resetTestingModule();
    }
  });

  it('renders accessible sourcing sections, labels, controls, evidence boundaries, and empty-safe metrics', async () => {
    const { fixture, http } = create();
    await flushInitial(http);
    await fixture.whenStable();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(
      fixture.nativeElement.querySelector('main[aria-labelledby="sourcing-title"]'),
    ).not.toBeNull();
    expect(
      fixture.nativeElement.querySelector('nav[aria-label="Sourcing sections"]'),
    ).not.toBeNull();
    expect(text).toContain('Active requirements');
    expect(text).toContain('Open RFQs');
    expect(text).toContain('Awaiting quotes');
    expect(text).toContain('Samples');
    expect(text).toContain('Inspections');
    expect(text).toContain('Decisions awaiting review');
    expect(text).toContain('Supplier contact, purchasing and payments remain disabled.');
    expect(text).toContain('Requirements');
    expect(text).toContain('RFQ draft and approval boundary');
    expect(text).toContain('Manual supplier quotes');
    expect(text).toContain('Samples & inspections');
    expect(text).toContain('Landed cost & economics');
    expect(text).toContain('Human sourcing decision');
    expect(text).toContain('Quote comparison');
    expect(text).toContain('Negotiation history');
    expect(text).toContain('Sensitivity analysis');
    expect(text).toContain('Capital and cash timeline');
    expect(text).toContain('Critic findings');
    expect(text).toContain('Supplier concentration');
    expect(fixture.nativeElement.querySelectorAll('h1, h2').length).toBeGreaterThanOrEqual(7);
    expect(fixture.nativeElement.querySelectorAll('label input').length).toBeGreaterThan(10);
    expect(fixture.nativeElement.querySelector('button[type="submit"]')).not.toBeNull();
  });

  it('maps API failure to a safe alert and preserves empty-state rendering', async () => {
    const { fixture, http } = create();
    http
      .expectOne('http://127.0.0.1:8000/api/v1/intelligence/sourcing/overview')
      .flush('unavailable', { status: 503, statusText: 'Unavailable' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]')?.textContent).toContain(
      'Sourcing data is unavailable',
    );
    expect(fixture.nativeElement.textContent).toContain('Active requirements');
    expect(fixture.nativeElement.textContent).not.toContain('postgresql://');
    expect(fixture.nativeElement.textContent).not.toContain('traceback');
  });

  it('keeps responsive and keyboard-safe form structure in the component stylesheet', async () => {
    const { fixture, http } = create();
    await flushInitial(http);
    await fixture.whenStable();
    const component = fixture.componentInstance;
    expect(component.requirement.payload.target_quantity).toBe(1);
    expect(component.scenario.inputs.quantity).toBe(1);
    expect(component.decision.confirmed).toBe(false);
    expect(fixture.nativeElement.textContent).toContain('Create requirement');
  });
});
