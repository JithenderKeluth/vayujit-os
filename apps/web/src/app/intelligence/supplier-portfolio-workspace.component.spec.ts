import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { SupplierPortfolioWorkspaceComponent } from './supplier-portfolio-workspace.component';

const base = 'http://127.0.0.1:8000/api/v1/intelligence/supplier-portfolios';

async function settle(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
}

const portfolio = {
  id: 'portfolio-1',
  name: 'Home essentials suppliers',
  description: 'Fixture portfolio',
  scope_type: 'PRODUCT',
  scope_reference: 'product-1',
  status: 'active',
  current_assessment_version_id: 'assessment-1',
  created_at: '2026-09-01T00:00:00Z',
  updated_at: '2026-09-01T00:00:00Z',
};

function detailResponses(http: HttpTestingController): void {
  http.expectOne(`${base}/portfolio-1`).flush(portfolio);
  http.expectOne(`${base}/portfolio-1/members`).flush([
    {
      id: 'member-1',
      portfolio_id: 'portfolio-1',
      supplier_id: 'supplier-1',
      version: 1,
      associated_products: ['product-1'],
      allocation_percent: 80,
      evidence_freshness: 'FRESH',
      confidence: 0.9,
      risk: 'MEDIUM',
      country_region: 'IN',
      capabilities: ['assembly'],
      alternate_source_status: 'RESEARCH_REQUIRED',
      due_diligence_lineage_id: null,
      shortlist_lineage_id: null,
      sourcing_scenario_lineage_id: null,
    },
  ]);
  http.expectOne(`${base}/portfolio-1/assessment`).flush({
    id: 'assessment-1',
    portfolio_id: 'portfolio-1',
    version: 1,
    status: 'completed',
    idempotency_key: 'assessment-key',
    input_snapshot: {},
    created_at: '2026-09-01T00:00:00Z',
  });
  http.expectOne(`${base}/portfolio-1/history`).flush([]);
  http.expectOne(`${base}/portfolio-1/concentration`).flush({
    largest_supplier_share: 80,
    top_three_supplier_share: 80,
    supplier_hhi: 6400,
    country_hhi: 10000,
    region_hhi: 10000,
    coverage_classification: 'DERIVED',
  });
  http.expectOne(`${base}/portfolio-1/dependencies`).flush({ findings: [] });
  http.expectOne(`${base}/portfolio-1/alternates`).flush({ items: [] });
  http.expectOne(`${base}/portfolio-1/resilience`).flush({
    score: 62,
    classification: 'MODERATE',
    evidence_status: 'SUFFICIENT',
    risk: { classification: 'CONCENTRATION_RISK' },
    confidence: { value: 0.8, classification: 'HIGH' },
    dimensions: [
      {
        dimension: 'SUPPLIER_DIVERSITY',
        score: 20,
        classification: 'LOW',
        evidence_status: 'SUFFICIENT',
        explanation: 'One supplier is present.',
        limitations: [],
        missing_evidence: [],
        calculation_version: '8E.3',
      },
    ],
    recommendations: [
      {
        id: 'recommendation-1',
        recommendation_type: 'CONCENTRATION',
        priority: 'HIGH',
        reason: 'Add a qualified alternate.',
        status: 'OPEN',
        affected_supplier_id: 'supplier-1',
        affected_product_id: 'product-1',
        affected_dependency_type: null,
        dimensions_affected: ['SUPPLIER_DIVERSITY'],
        evidence: [],
        missing_evidence: ['alternate_supplier'],
        recommendation_version: '8E.3',
      },
    ],
  });
  http.expectOne(`${base}/portfolio-1/simulations`).flush([
    {
      id: 'simulation-1',
      simulation_type: 'SUPPLIER_UNAVAILABLE',
      status: 'completed',
      staleness: 'CURRENT',
      assumptions: { supplier_ids: ['supplier-1'] },
      result: { baseline: { score: 62 }, simulated: { score: 20 }, delta: { score: -42 } },
      created_at: '2026-09-01T00:00:00Z',
    },
  ]);
  http
    .expectOne(`${base}/portfolio-1/product-channel`)
    .flush({ events: [], external_dispatch: false });
  http.expectOne(`${base}/portfolio-1/events`).flush([]);
  http.expectOne(`${base}/calendar`).flush([]);
  http.expectOne(`${base}/operations`).flush({
    stale_assessments: 0,
    failed_simulations: 0,
    research_requests: 0,
    due_diligence_requests: 0,
  });
  http.expectOne(`${base}/system-doctor`).flush({ status: 'PASS' });
}

function configure(id: string | null = null) {
  TestBed.configureTestingModule({
    imports: [SupplierPortfolioWorkspaceComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([]),
      {
        provide: ActivatedRoute,
        useValue: { snapshot: { paramMap: { get: () => id } } },
      },
    ],
  });
  const fixture = TestBed.createComponent(SupplierPortfolioWorkspaceComponent);
  return { fixture, http: TestBed.inject(HttpTestingController) };
}

describe('SupplierPortfolioWorkspaceComponent', () => {
  it('renders the owner-scoped list and empty state', async () => {
    const { fixture, http } = configure();
    fixture.detectChanges();
    http.expectOne(base).flush([]);
    await settle();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Portfolio list');
    expect(fixture.nativeElement.textContent).toContain('No supplier portfolios yet');
    http.verify();
  });

  it('renders detail evidence, risk/resilience separation, dimensions, simulation provenance, and actions', async () => {
    const { fixture, http } = configure('portfolio-1');
    fixture.detectChanges();
    detailResponses(http);
    await settle();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Home essentials suppliers');
    expect(text).toContain(
      'Risk is known exposure. Resilience is the ability to withstand disruption.',
    );
    expect(text).toContain('Supplier Diversity');
    expect(text).toContain('SIMULATION ASSUMPTION');
    expect(text).toContain('BASELINE');
    expect(text).toContain('SIMULATED');
    expect(text).toContain('DELTA');
    expect(text).toContain('Acknowledge risk');
    expect(fixture.nativeElement.innerHTML).not.toContain('<script');
    http.verify();
  });

  it('shows a safe not-found error without exposing response internals', async () => {
    const { fixture, http } = configure('missing');
    fixture.detectChanges();
    http
      .expectOne(`${base}/missing`)
      .flush({ detail: 'database URL / traceback' }, { status: 404, statusText: 'Not Found' });
    for (const request of http.match(() => true)) request.flush([]);
    await settle();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]')?.textContent).toContain(
      'could not be loaded',
    );
    expect(fixture.nativeElement.textContent).not.toContain('database URL');
    expect(fixture.nativeElement.textContent).not.toContain('traceback');
    http.verify();
  });

  it('posts bounded simulation assumptions from the workspace', async () => {
    const { fixture, http } = configure('portfolio-1');
    fixture.detectChanges();
    detailResponses(http);
    await settle();
    const component = fixture.componentInstance;
    component.simulationType = 'SUPPLIER_UNAVAILABLE';
    component.simulationSupplierId = 'supplier-1';
    component.simulationPercent = 25;
    component.createSimulation();
    const request = http.expectOne(`${base}/portfolio-1/simulations`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body.assumptions.supplier_ids).toEqual(['supplier-1']);
    expect(request.request.body.assumptions.capacity_reduction_percent).toBe(25);
    request.flush(
      { detail: 'fixture assertion response' },
      { status: 400, statusText: 'Bad Request' },
    );
    await settle();
    http.verify();
  });
});
