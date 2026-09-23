import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ComponentFixtureAutoDetect, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { environment } from '../../environments/environment';
import { ProductOpportunityWorkspaceComponent } from './product-opportunity-workspace.component';
import {
  CompetitionProjection,
  OpportunityDetail,
  ProductOpportunityService,
  SourcingFeasibilityOutput,
  ProductOpportunityScore,
  TrendWinningProductProjection,
} from './product-opportunity.service';

const base = `${environment.apiUrl}/intelligence/product-opportunities/opportunity/assessments/assessment/sourcing-feasibility`;
const competitionProjectionBase = `${environment.apiUrl}/intelligence/product-opportunities/opportunity/assessments/assessment/competition-projection`;

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
  it('renders the compact authoritative competition projection with a workspace link', () => {
    const { fixture, component, http } = setup();
    component.detail.set(detail);
    component.competitionProjection.set({
      id: 'projection',
      source_state: 'DEDICATED_COMPETITOR_INTELLIGENCE',
      contract_version: 'competitor-winning-product-v1',
      nine_b_calculation_version: 'product-opportunity-intelligence-v1',
      ten_c_calculation_version: 'competitor-commercial-v1',
      ten_d_calculation_version: null,
      freshness_state: 'CURRENT',
      contradiction_state: 'NONE',
      research_gaps: [],
      projection: {
        cohort: { authoritative_count: 18 },
        analysis: {
          pricing: { sample_size: 14 },
          concentration: { brand: { hhi: '0.25' } },
          review: { barrier: 'UNKNOWN' },
          evidence_coverage: { products: 18 },
          differentiation: [{ type: 'POTENTIAL_DIFFERENTIATOR' }],
        },
      },
    } satisfies CompetitionProjection);
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Competition Intelligence');
    expect(text).toContain('DEDICATED_COMPETITOR_INTELLIGENCE');
    expect(text).toContain('18');
    expect(text).toContain('Open Competitor Intelligence');
    http.verify();
  });

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

  it('loads the competition projection through the authenticated API', async () => {
    const { service, http } = setup();
    const pending = service.getCompetitionProjection('opportunity', 'assessment');
    const request = http.expectOne(competitionProjectionBase);
    expect(request.request.method).toBe('GET');
    expect(request.request.withCredentials).toBe(true);
    request.flush({ source_state: 'INSUFFICIENT_EVIDENCE', research_gaps: [] });
    await expect(pending).resolves.toMatchObject({ source_state: 'INSUFFICIENT_EVIDENCE' });
    http.verify();
  });
});

describe('Product opportunity UX-4 context hub', () => {
  it('uses the UX-1 empty state and supported research CTAs for an empty list', () => {
    const { fixture, component, http } = setup();
    component.detail.set(null);
    component.opportunities.set([]);
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('No product opportunities yet');
    expect(text).toContain('Start Product Research');
    expect(text).toContain('Ask VAYUJIT');
    expect(fixture.nativeElement.querySelector('app-empty-state')).toBeTruthy();
    http.verify();
  });

  it('loads an opportunity detail with one request and does not fan out into module requests', async () => {
    const { component, service, http } = setup();
    const get = vi.spyOn(service, 'get').mockResolvedValue(detail);
    await component.loadDetail('opportunity');
    expect(get).toHaveBeenCalledTimes(1);
    expect(component.detail()).toEqual(detail);
    expect(component.trendProjection()).toBeNull();
    expect(component.competitionProjection()).toBeNull();
    expect(component.reviewProjection()).toBeNull();
    expect(component.sourcingFeasibility()).toBeNull();
    http.verify();
  });

  it('keeps score, confidence, risk, readiness, and eligibility visibly separate', () => {
    const { fixture, component, http } = setup();
    component.detail.set(detail);
    component.score.set({
      overall_score: '78',
      classification: 'PROMISING',
      confidence: 'HIGH',
      risk_level: 'MODERATE',
      assessment_readiness: 'PARTIAL',
      eligibility: 'ELIGIBLE',
      dimensions: [],
      positive_drivers: [],
      negative_drivers: [],
      improvement_areas: [],
    } as unknown as ProductOpportunityScore);
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    for (const expected of [
      'Opportunity score',
      'Evidence confidence',
      'Risk',
      'Research readiness',
      'Eligibility',
      '78',
      'HIGH',
      'MODERATE',
      'PARTIAL',
      'ELIGIBLE',
    ])
      expect(text).toContain(expected);
    expect(text).not.toContain('WINNER');
    expect(text).not.toContain('LAUNCH NOW');
    http.verify();
  });

  it('keeps partial research distinct from a negative or fabricated score', () => {
    const { fixture, component, http } = setup();
    component.detail.set(detail);
    component.score.set(null);
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Assessment summary not loaded');
    expect(text).toContain('Missing intelligence is not treated as a negative score.');
    expect(text).not.toContain('0 / 100');
    expect(text).toContain('Trend projection not loaded or not researched.');
    http.verify();
  });

  it('renders hostile evidence as inert text', () => {
    const { fixture, component, http } = setup();
    component.detail.set({ ...detail, description: '<script>alert(1)</script>' });
    component.sourcingFeasibility.set({
      ...output,
      candidates: [
        {
          ...output.candidates[0],
          supplier: { id: 'supplier', name: '<img src=x onerror=alert(1)>' },
        },
      ],
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('script')).toBeNull();
    expect(fixture.nativeElement.querySelector('img')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('<script>alert(1)</script>');
    http.verify();
  });

  it('renders authoritative gaps and contradictions without inferring them', () => {
    const { fixture, component, http } = setup();
    component.detail.set(detail);
    component.trendProjection.set({
      research_gaps: [{ reason: 'LIMITED_HISTORY' }],
      contradictions: [{ reason: 'SOURCES_DISAGREE' }],
      signal_summaries: [],
      momentum_summaries: [],
      evidence_confidence: { state: 'MODERATE' },
      freshness: { state: 'CURRENT' },
      readiness: 'PARTIAL',
      source_state: 'VALIDATED',
      created_at: '2026-09-18T00:00:00Z',
    } as unknown as TrendWinningProductProjection);
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('What we still do not know');
    expect(text).toContain('LIMITED_HISTORY');
    expect(text).toContain('SOURCES_DISAGREE');
    http.verify();
  });
});
