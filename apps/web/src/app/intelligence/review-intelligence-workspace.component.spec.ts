import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';

import { ReviewIntelligenceWorkspaceComponent } from './review-intelligence-workspace.component';
import { ReviewIntelligenceService } from './review-intelligence.service';
import { CommerceJourneyService } from '../commerce-journey.service';

describe('ReviewIntelligenceWorkspaceComponent', () => {
  it('renders owner-scoped review contexts and integrity status', async () => {
    await TestBed.configureTestingModule({
      imports: [ReviewIntelligenceWorkspaceComponent],
      providers: [
        provideRouter([]),
        {
          provide: ReviewIntelligenceService,
          useValue: {
            contexts: () =>
              Promise.resolve([
                {
                  id: 'context-1',
                  name: 'Kitchen reviews',
                  product_id: null,
                  product_opportunity_id: null,
                  marketplace: 'amazon',
                  market: 'IN',
                  status: 'ACTIVE',
                  version: 1,
                },
              ]),
            doctor: () => Promise.resolve({ status: 'PASS', counts: {} }),
          },
        },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(ReviewIntelligenceWorkspaceComponent);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Review Intelligence');
    expect(fixture.nativeElement.textContent).toContain('Customer Reviews');
    expect(fixture.nativeElement.textContent).toContain('Kitchen reviews');
    expect(fixture.nativeElement.textContent).toContain('PASS');
  });

  it('renders review bodies as text and exposes safe errors', async () => {
    const service: Partial<ReviewIntelligenceService> = {
      contexts: () => Promise.resolve([]),
      doctor: () => Promise.reject(new Error('database URL leaked')),
    };
    await TestBed.configureTestingModule({
      imports: [ReviewIntelligenceWorkspaceComponent],
      providers: [provideRouter([]), { provide: ReviewIntelligenceService, useValue: service }],
    }).compileComponents();

    const fixture = TestBed.createComponent(ReviewIntelligenceWorkspaceComponent);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain(
      'Review data is unavailable. Check the authenticated API connection.',
    );
    expect(fixture.nativeElement.textContent).not.toContain('database URL');
    expect(fixture.nativeElement.querySelector('[role="alert"]')).not.toBeNull();
  });

  it('reuses the selected opportunity context without starting ingestion', async () => {
    const context = {
      id: 'review-context-1',
      name: 'Selected product reviews',
      product_id: 'product-1',
      product_opportunity_id: 'opportunity-1',
      marketplace: 'amazon',
      market: 'IN',
      status: 'ACTIVE',
      version: 1,
    };
    const service: Partial<ReviewIntelligenceService> = {
      contexts: vi.fn().mockResolvedValue([context]),
      doctor: vi.fn().mockResolvedValue({ status: 'PASS', counts: {} }),
      createContext: vi.fn(),
      reviews: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 }),
      statistics: vi.fn().mockResolvedValue({
        review_count: 0,
        rated_review_count: 0,
        unrated_review_count: 0,
        rating_scales: {},
        verified_purchase_count: 0,
        unknown_verified_purchase_count: 0,
        source_counts: {},
        freshness_counts: {},
        evidence_counts: {},
        review_date_min: null,
        review_date_max: null,
      }),
      snapshots: vi.fn().mockResolvedValue([]),
      ingestions: vi.fn().mockResolvedValue([]),
      currentGapAnalysis: vi.fn().mockResolvedValue(null),
      analyses: vi.fn().mockResolvedValue([]),
      currentChangeComparison: vi.fn().mockResolvedValue(null),
      ingest: vi.fn(),
    };
    await TestBed.resetTestingModule()
      .configureTestingModule({
        imports: [ReviewIntelligenceWorkspaceComponent],
        providers: [
          provideRouter([]),
          { provide: ReviewIntelligenceService, useValue: service },
          {
            provide: CommerceJourneyService,
            useValue: {
              active: () =>
                Promise.resolve({
                  id: 'journey-1',
                  goal_id: 'goal-1',
                  status: 'ACTIVE',
                  stages: [],
                  completed_stage_count: 0,
                  total_stage_count: 0,
                  next_action: {
                    code: 'REVIEW',
                    title: 'Review',
                    detail: 'Review',
                    route: '/intelligence',
                    human_controlled: true,
                  },
                  counts: {},
                  context: {
                    values: {
                      product_id: 'product-1',
                      selected_product_opportunity_id: 'opportunity-1',
                    },
                  },
                  context_confirmation: { required: false, source: 'test' },
                  remaining_requirements: [],
                  human_controlled: true,
                }),
            },
          },
        ],
      })
      .compileComponents();
    const fixture = TestBed.createComponent(ReviewIntelligenceWorkspaceComponent);
    await fixture.whenStable();
    expect(fixture.componentInstance.selectedContext()?.id).toBe('review-context-1');
    expect(service.createContext).not.toHaveBeenCalled();
    expect(service.ingest).not.toHaveBeenCalled();
  });
});
