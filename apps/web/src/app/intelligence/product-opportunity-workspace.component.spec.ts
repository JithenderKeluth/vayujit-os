import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ComponentFixtureAutoDetect, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { environment } from '../../environments/environment';
import { ProductOpportunityWorkspaceComponent } from './product-opportunity-workspace.component';
import {
  OpportunityDetail,
  ProductOpportunityService,
  SourcingFeasibilityOutput,
} from './product-opportunity.service';

const base = `${environment.apiUrl}/intelligence/product-opportunities/opportunity/assessments/assessment/sourcing-feasibility`;

function setup() {
  TestBed.configureTestingModule({
    imports: [ProductOpportunityWorkspaceComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([]),
      { provide: ComponentFixtureAutoDetect, useValue: false },
    ],
  });
  const fixture = TestBed.createComponent(ProductOpportunityWorkspaceComponent);
  const component = fixture.componentInstance;
  vi.spyOn(component, 'load').mockResolvedValue();
  return {
    fixture,
    component,
    http: TestBed.inject(HttpTestingController),
    service: TestBed.inject(ProductOpportunityService),
  };
}

const detail = {
  id: 'opportunity',
  product_id: 'product',
  name: 'Disposable opportunity',
  current_assessment_id: 'assessment',
  constraints: [],
  assessments: [],
} as unknown as OpportunityDetail;
const output = {
  id: 'projection',
  opportunity_id: 'opportunity',
  assessment_id: 'assessment',
  calculation_version: 'v1',
  created_at: '2026-09-18T00:00:00Z',
  summary: {
    feasibility_state: 'DUE_DILIGENCE_REQUIRED',
    supplier_availability: { discovered: 1, matched: 1, eligible: 0, dd_complete: 0 },
    scenario_availability: 'NO_SCENARIO',
    confidence: 'unknown',
  },
  candidates: [
    {
      supplier: { id: 'supplier', name: 'Fixture supplier' },
      canonical_supplier_id: 'canonical',
      matched_product: { id: 'source-product', title: 'Fixture product' },
      source: { provider: 'MANUAL' },
      country: 'India',
      match_state: 'MATCHED',
      verification: 'UNKNOWN',
      shortlist: { eligibility: 'UNKNOWN' },
      due_diligence: { state: 'INSUFFICIENT' },
      freshness: 'stale',
      alternate_readiness: 'UNKNOWN',
    },
  ],
  upstream_lineage: { portfolio: { concentration: [] } },
  evidence_summary: { contradictions: [] },
  dimensions: [
    {
      dimension: 'MOQ_FIT',
      value: { 'source-product': 'UNKNOWN' },
      classification: 'UNKNOWN',
      evidence_state: 'INSUFFICIENT_EVIDENCE',
      explanation: 'No MOQ evidence.',
      supporting_evidence: [],
      missing_evidence: ['MOQ'],
      freshness: {},
      calculation_version: 'v1',
    },
  ],
  research_gaps: ['MOQ_REQUIRED'],
} as unknown as SourcingFeasibilityOutput;

describe('Product opportunity sourcing feasibility', () => {
  it('renders unknowns, authoritative candidate fields and separate evidence without a winning verdict', () => {
    const { fixture, component, http } = setup();
    component.detail.set(detail);
    component.sourcingFeasibility.set(output);
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    for (const expected of [
      'Fixture supplier',
      'India',
      'INSUFFICIENT',
      'stale',
      'UNKNOWN',
      'MOQ_REQUIRED',
      'Concentration and dependencies',
      'Evidence, contradictions',
    ])
      expect(text).toContain(expected);
    expect(text).not.toContain('[object Object]');
    expect(text).not.toContain('WINNING_PRODUCT');
    http.verify();
  });
  it('calculates through the assessment-bound authenticated API', async () => {
    const { component, http } = setup();
    const pending = component.calculateSourcing(detail);
    const request = http.expectOne(base);
    expect(request.request.method).toBe('POST');
    expect(request.request.withCredentials).toBe(true);
    request.flush(output);
    await pending;
    expect(component.sourcingFeasibility()).toEqual(output);
    http.verify();
  });
  it('starts only a confirmed internal DD context, not external research', async () => {
    const { component, http } = setup();
    const pending = component.handoffSourcing(detail, output.candidates[0]);
    const request = http.expectOne(base + '/handoff');
    expect(request.request.body).toEqual({ supplier_product_id: 'source-product', confirm: true });
    request.flush({ context_id: 'context', external_work_started: false });
    await pending;
    expect(component.handoffMessage()).toContain(
      'No supplier contact or external research was started',
    );
    http.verify();
  });
  it('returns a safe UI error for calculation failure', async () => {
    const { component, http } = setup();
    const pending = component.calculateSourcing(detail);
    http
      .expectOne(base)
      .flush(
        { detail: 'internal database path' },
        { status: 422, statusText: 'Unprocessable Entity' },
      );
    await pending;
    expect(component.error()).toBe('Supplier feasibility could not be calculated.');
    expect(component.error()).not.toContain('database');
    http.verify();
  });
  it('reads historical sections with authentication', async () => {
    const { service, http } = setup();
    const pending = service.getSourcingSection('opportunity', 'assessment', 'history');
    const request = http.expectOne(base + '/history');
    expect(request.request.withCredentials).toBe(true);
    request.flush([{ id: 'projection' }]);
    expect(await pending).toEqual([{ id: 'projection' }]);
    http.verify();
  });
});
