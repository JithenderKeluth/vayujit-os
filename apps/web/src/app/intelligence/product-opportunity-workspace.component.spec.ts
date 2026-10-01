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
  ResearchCandidate,
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
describe('Product opportunity GP-3 research results', () => {
  function candidate(id: string, state: ResearchCandidate['candidate_state']): ResearchCandidate {
    return {
      research_run_id: null,
      id,
      name: 'Candidate ' + id,
      description: 'Evidence-backed concept',
      product_concept: 'Reusable product',
      category: 'Home',
      marketplace: 'Amazon India',
      region: 'IN',
      research_state: 'completed',
      evidence_state: 'partial',
      assessment_id: 'assessment-' + id,
      candidate_state: state,
      selected: false,
      score: null,
      why_this_surfaced: ['Insufficient evidence'],
      strengths: [],
      risks: ['Supplier economics remain unknown.'],
      data_gaps: ['Verified quotation'],
      next_validation: ['Research suppliers'],
      evidence: [],
    };
  }

  it('renders bounded candidate comparison and explicit evidence gaps', () => {
    const { fixture, component, http } = setup();
    component.researchResults.set({
      status: 'RESEARCH_COMPLETED_WITH_GAPS',
      summary: { total: 2, ready_for_comparison: 0, needs_more_research: 2 },
      candidates: [candidate('a', 'NEEDS_MORE_RESEARCH'), candidate('b', 'INSUFFICIENT_EVIDENCE')],
      selected_candidate_ids: [],
      human_selection: { provenance: 'UNKNOWN', count: 0 },
    });
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Your product research results');
    expect(text).toContain('Why this product surfaced');
    expect(text).toContain('Insufficient evidence');
    expect(text).toContain('View evidence');
    expect(text).toContain('Compare selected products');

    component.toggleCandidate(candidate('a', 'NEEDS_MORE_RESEARCH'));
    component.toggleCandidate(candidate('b', 'INSUFFICIENT_EVIDENCE'));
    expect(component.canCompareCandidates()).toBe(true);
    expect(component.selectedCandidateIds()).toEqual(['a', 'b']);
    http.verify();
  });

  it('makes local fixture trust and missing imagery explicit on candidate cards', () => {
    const { fixture, component, http } = setup();
    const item = candidate('fixture', 'NEEDS_MORE_RESEARCH');
    item.intelligence_profile = {
      candidate_source: 'LOCAL_DETERMINISTIC_RESEARCH_FIXTURE',
      candidate_provenance: { mode: 'LOCAL_DETERMINISTIC' },
      goal_fit: ['Lightweight preference matched.'],
      detailed_description: 'A compact reusable product concept.',
      image: { available: false, source: 'NOT_AVAILABLE' },
    };
    component.researchResults.set({
      status: 'RESEARCH_COMPLETED_WITH_GAPS',
      summary: { total: 1, ready_for_comparison: 0, needs_more_research: 1 },
      candidates: [item],
      selected_candidate_ids: [],
      human_selection: { provenance: 'UNKNOWN', count: 0 },
    });
    fixture.detectChanges();
    const card = fixture.nativeElement.querySelector('.candidate-card') as HTMLElement;
    expect(card.textContent).toContain('Local demo - not live evidence');
    expect(card.textContent).toContain('Product image not available');
    expect(card.textContent).toContain('Why this product surfaced');
    expect(card.textContent).not.toContain('Price: 0');
    http.verify();
  });

  it('renders bounded comparison dimensions without declaring a winner', () => {
    const { fixture, component, http } = setup();
    const first = candidate('one', 'READY_TO_COMPARE');
    const second = candidate('two', 'READY_TO_COMPARE');
    first.name = 'Insulated Lunch Container';
    second.name = 'Foldable Wardrobe Organizer';
    component.researchResults.set({
      status: 'RESEARCH_COMPLETED',
      summary: { total: 2, ready_for_comparison: 2, needs_more_research: 0 },
      candidates: [first, second],
      selected_candidate_ids: ['one', 'two'],
      human_selection: { provenance: 'UNKNOWN', count: 0 },
    });
    component.selectedCandidateIds.set(['one', 'two']);
    component.comparison.set({
      comparability: 'COMPARABLE',
      reason: 'Same assessment model.',
      items: [],
      ranking: [],
    });
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Dimension');
    expect(text).toContain('Goal fit');
    expect(text).toContain('Important unknowns');
    expect(text).toContain('does not choose a winner');
    expect(text).not.toContain('Winner');
    http.verify();
  });
});

describe('Product opportunity human selection', () => {
  it('records explicit human selection and carries supplier context', async () => {
    const { component, service, http } = setup();
    const selected = {
      ...detail,
      current_assessment_id: 'assessment',
      category: 'Home',
      subcategory: 'Storage',
      target_marketplace: 'AMAZON_IN',
      target_region: 'IN',
      product_concept: 'Reusable storage product',
      intelligence_profile: { research_keywords: ['storage', 'reusable'] },
    } as unknown as OpportunityDetail;
    component.detail.set(selected);
    const decide = vi.spyOn(service, 'decide').mockResolvedValue({ id: 'decision' });
    await component.selectDetailForSupplier(selected);
    expect(decide).toHaveBeenCalledWith('opportunity', 'assessment', {
      action: 'shortlist',
      rationale: 'Human selected this product for supplier research.',
    });
    expect(component.supplierHandoffParams(selected)).toMatchObject({
      opportunity_id: 'opportunity',
      category: 'Home',
      subcategory: 'Storage',
      marketplace: 'AMAZON_IN',
      region: 'IN',
      search_terms: 'storage, reusable',
    });
    http.verify();
  });
});

describe('PR-2 one-candidate selection UX', () => {
  it('explains that comparison is unavailable and preserves the observed source title', () => {
    const { fixture, component, http } = setup();
    const item = {
      research_run_id: null,
      id: 'one',
      name: 'Insulated Food Container',
      description: 'Evidence-backed concept',
      product_concept: 'Reusable food container',
      category: 'Home',
      marketplace: 'Amazon India',
      region: 'IN',
      research_state: 'completed',
      evidence_state: 'partial',
      assessment_id: null,
      score: null,
      candidate_state: 'NEEDS_MORE_RESEARCH',
      selected: false,
      why_this_surfaced: ['Matched live product evidence.'],
      strengths: [],
      risks: [],
      data_gaps: ['Assessment'],
      next_validation: ['Review evidence'],
      evidence: [],
    } as ResearchCandidate;
    item.observed_name = 'Insulated Food Container - Manufacturer from Ahmedabad';
    component.researchResults.set({
      status: 'RESEARCH_COMPLETED_WITH_GAPS',
      summary: { total: 1, ready_for_comparison: 0, needs_more_research: 1 },
      candidates: [item],
      selected_candidate_ids: [],
      human_selection: { provenance: 'UNKNOWN', count: 0 },
    });
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('One meaningful product found');
    expect(text).toContain('comparison is unavailable');
    expect(text).toContain('Observed source title');
    expect(text).toContain('Insulated Food Container - Manufacturer from Ahmedabad');
    http.verify();
  });
});
