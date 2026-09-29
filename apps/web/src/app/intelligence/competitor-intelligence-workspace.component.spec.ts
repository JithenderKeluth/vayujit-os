import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';

import { CompetitorIntelligenceWorkspaceComponent } from './competitor-intelligence-workspace.component';
import { CompetitorIntelligenceService } from './competitor-intelligence.service';
import { CommerceJourneyService } from '../commerce-journey.service';

describe('CompetitorIntelligenceWorkspaceComponent', () => {
  function configure(service: Partial<CompetitorIntelligenceService>) {
    return TestBed.configureTestingModule({
      imports: [CompetitorIntelligenceWorkspaceComponent],
      providers: [provideRouter([]), { provide: CompetitorIntelligenceService, useValue: service }],
    }).compileComponents();
  }

  it('renders owner-scoped contexts, entities, products, and integrity status', async () => {
    await configure({
      contexts: () =>
        Promise.resolve([
          {
            id: 'context-1',
            subject_type: 'PRODUCT_OPPORTUNITY',
            subject_reference: 'opportunity-1',
            marketplace: 'amazon',
            market: 'IN',
            category: 'Home',
            currency: 'INR',
            status: 'ACTIVE',
            version: 1,
            updated_at: '2026-01-01T00:00:00Z',
          },
        ]),
      entities: () =>
        Promise.resolve([
          {
            id: 'entity-1',
            display_name: 'Fixture seller',
            entity_type: 'SELLER',
            canonical_name: 'fixture seller',
            evidence_state: 'PARTIAL',
            website_domain: null,
            updated_at: '2026-01-01T00:00:00Z',
          },
        ]),
      doctor: () => Promise.resolve({ status: 'PASS', counts: {}, duplicate_counts: {} }),
    });
    const fixture = TestBed.createComponent(CompetitorIntelligenceWorkspaceComponent);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Competitor intelligence');
    expect(fixture.nativeElement.textContent).toContain('Competitors');
    expect(fixture.nativeElement.textContent).not.toContain('Easy market');
    expect(fixture.nativeElement.textContent).toContain('amazon');
    expect(fixture.nativeElement.textContent).toContain('Fixture seller');
    expect(fixture.nativeElement.textContent).toContain('PASS');
    expect(
      fixture.nativeElement.querySelector('main[aria-labelledby="competitor-title"]'),
    ).not.toBeNull();
  });

  it('shows a safe error when the authenticated API is unavailable', async () => {
    await configure({
      contexts: () => Promise.reject(new Error('database URL leaked')),
      entities: () => Promise.reject(new Error('offline')),
      doctor: () => Promise.reject(new Error('offline')),
    });
    const fixture = TestBed.createComponent(CompetitorIntelligenceWorkspaceComponent);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain(
      'Competitor data is unavailable. Check the authenticated API connection.',
    );
    expect(fixture.nativeElement.textContent).not.toContain('database URL');
    expect(fixture.nativeElement.querySelector('[role="alert"]')).not.toBeNull();
  });

  it('reuses the selected opportunity context without starting discovery', async () => {
    const context = {
      id: 'competitor-context-1',
      subject_type: 'PRODUCT_OPPORTUNITY',
      subject_reference: 'opportunity-1',
      product_opportunity_id: 'opportunity-1',
      product_id: 'product-1',
      marketplace: 'amazon',
      market: 'IN',
      category: 'Home',
      currency: 'INR',
      status: 'ACTIVE',
      version: 1,
      updated_at: '2026-01-01T00:00:00Z',
    };
    const service: Partial<CompetitorIntelligenceService> = {
      contexts: vi.fn().mockResolvedValue([context]),
      entities: vi.fn().mockResolvedValue([]),
      doctor: vi.fn().mockResolvedValue({ status: 'PASS', counts: {}, duplicate_counts: {} }),
      createContext: vi.fn(),
      products: vi.fn().mockResolvedValue([]),
      currentChanges: vi.fn().mockResolvedValue({ items: [] }),
      createDiscoveryRequest: vi.fn(),
    };
    await TestBed.resetTestingModule()
      .configureTestingModule({
        imports: [CompetitorIntelligenceWorkspaceComponent],
        providers: [
          provideRouter([]),
          { provide: CompetitorIntelligenceService, useValue: service },
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
    const fixture = TestBed.createComponent(CompetitorIntelligenceWorkspaceComponent);
    await fixture.whenStable();
    expect(fixture.componentInstance.selectedContext()?.id).toBe('competitor-context-1');
    expect(service.createContext).not.toHaveBeenCalled();
    expect(service.createDiscoveryRequest).not.toHaveBeenCalled();
  });
});
