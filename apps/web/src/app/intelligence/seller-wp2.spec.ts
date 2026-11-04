import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { BrandService } from '../brands/brand.service';
import { OpportunityNextActionsComponent } from './opportunity-next-actions.component';
import {
  ProductOpportunityService,
  OpportunityDetail,
  ResearchResults,
} from './product-opportunity.service';
import { ProductOpportunityWorkspaceComponent } from './product-opportunity-workspace.component';
import { SellerResearchComponent } from './seller-research.component';
import { BusinessAgentService } from './business-agent.service';

const opportunity = {
  id: 'op-a',
  name: 'Manual product',
  current_assessment_id: 'assessment-a',
  lifecycle_status: 'draft',
} as OpportunityDetail;
function setup() {
  const service = {
    decisions: vi.fn().mockResolvedValue([]),
    decide: vi.fn().mockResolvedValue({}),
    convert: vi.fn().mockResolvedValue({ product: { id: 'product-a' } }),
  };
  TestBed.configureTestingModule({
    providers: [
      provideRouter([]),
      { provide: ProductOpportunityService, useValue: service },
      {
        provide: BrandService,
        useValue: {
          list: vi.fn().mockResolvedValue({ items: [{ id: 'brand-a', name: 'Brand' }] }),
        },
      },
    ],
  });
  const c = TestBed.createComponent(OpportunityNextActionsComponent).componentInstance;
  c.opportunity = opportunity;
  return { c, service };
}
describe('WP2 current HUMAN intent and Catalog handoff', () => {
  it('never infers selection from a past shortlist followed by reject', async () => {
    const { c, service } = setup();
    service.decisions.mockResolvedValue([
      { id: 'new', action: 'reject', assessment_id: 'assessment-a' },
      { id: 'old', action: 'shortlist', assessment_id: 'assessment-a' },
    ]);
    await c.reload();
    expect(c.selected()).toBe(false);
    expect(c.status()).toContain('Rejected');
  });
  it('does not create a catalog product without explicit confirmation', async () => {
    const { c, service } = setup();
    service.decisions.mockResolvedValue([{ action: 'shortlist', assessment_id: 'assessment-a' }]);
    await c.reload();
    c.brandId = 'brand-a';
    await c.convert();
    expect(service.convert).not.toHaveBeenCalled();
  });
  it('preserves exact scope and prevents in-flight duplicate conversion', async () => {
    const { c, service } = setup();
    service.decisions.mockResolvedValue([{ action: 'shortlist', assessment_id: 'assessment-a' }]);
    await c.reload();
    c.brandId = 'brand-a';
    c.goalId = 'goal-a';
    c.confirmed = true;
    const first = c.convert();
    await c.convert();
    await first;
    expect(service.convert).toHaveBeenCalledTimes(1);
    expect(service.convert).toHaveBeenCalledWith('op-a', {
      brand_id: 'brand-a',
      goal_id: 'goal-a',
      idempotency_key: 'catalog-opportunity-op-a',
    });
    expect(c.catalogId()).toBe('product-a');
  });
  it('blocks stale assessment and preserves failed-conversion context', async () => {
    const { c, service } = setup();
    service.decisions.mockResolvedValue([{ action: 'shortlist', assessment_id: 'old' }]);
    await c.reload();
    expect(c.selected()).toBe(false);
    expect(c.status()).toContain('stale');
    c.history.set([
      {
        id: 'd',
        opportunity_id: 'op-a',
        action: 'shortlist',
        assessment_id: 'assessment-a',
        rationale: 'HUMAN',
        created_at: '',
      },
    ]);
    c.brandId = 'brand-a';
    c.confirmed = true;
    service.convert.mockRejectedValue({ status: 409 });
    await c.convert();
    expect(c.error()).toContain('not confirmed');
    expect(c.opportunity.id).toBe('op-a');
    expect(c.catalogId()).toBe('');
    expect(c.recordedSelection()).toBe(true);
    expect(c.selected()).toBe(false);
  });
  it('cancelled HUMAN rejection performs no request', async () => {
    const { c, service } = setup();
    await c.reload();
    const confirm = vi.spyOn(globalThis, 'confirm').mockReturnValue(false);
    await c.decide('reject');
    expect(service.decide).not.toHaveBeenCalled();
    confirm.mockRestore();
  });
  it('retries the same explicit decision identity after a failed request', async () => {
    const { c, service } = setup();
    await c.reload();
    const confirm = vi.spyOn(globalThis, 'confirm').mockReturnValue(true);
    service.decide.mockRejectedValueOnce({ status: 503 });
    await c.decide('shortlist');
    const key = (service.decide.mock.calls[0][2] as { idempotency_key: string }).idempotency_key;
    await c.reload();
    await c.decide('shortlist');
    expect(service.decide.mock.calls[1][2].idempotency_key).toBe(key);
    confirm.mockRestore();
  });
});
describe('WP2 research truthfulness', () => {
  it('uses unexecuted state rather than RESEARCH COMPLETE', () => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const c = TestBed.createComponent(ProductOpportunityWorkspaceComponent).componentInstance;
    const results = {
      candidates: [],
      research_execution: { run_count: 0, latest_status: null },
    } as unknown as ResearchResults;
    expect(c.researchStageLabel(results)).toBe('Research not started');
    expect(c.emptyResearchMessage(results)).toContain('No research run has executed');
  });
  it('shows an actionable missing-projection result without a synthetic success', async () => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const c = TestBed.createComponent(ProductOpportunityWorkspaceComponent).componentInstance;
    c.detail.set(opportunity);
    vi.spyOn(TestBed.inject(ProductOpportunityService), 'getTrendProjection').mockRejectedValue({
      status: 404,
    });
    await c.loadTrend(opportunity);
    expect(c.sectionFeedback()[0].message).toContain('No saved assessment');
    expect(c.trendProjection()).toBeNull();
    expect(c.detail()?.id).toBe('op-a');
  });
  it('keeps unavailable saved research distinct from empty', async () => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: BusinessAgentService,
          useValue: { goals: vi.fn().mockRejectedValue({ status: 503 }) },
        },
      ],
    });
    const c = TestBed.createComponent(SellerResearchComponent).componentInstance;
    await c.load();
    expect(c.error()).toBe(true);
    expect(c.loading()).toBe(false);
  });
});
