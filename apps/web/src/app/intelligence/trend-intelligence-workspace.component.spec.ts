import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { TrendIntelligenceWorkspaceComponent } from './trend-intelligence-workspace.component';
import { TrendIntelligenceService } from './trend-intelligence.service';
import { CommerceJourneyService } from '../commerce-journey.service';
import { of } from 'rxjs';

describe('TrendIntelligenceWorkspaceComponent', () => {
  let fixture: ComponentFixture<TrendIntelligenceWorkspaceComponent>;
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TrendIntelligenceWorkspaceComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(TrendIntelligenceWorkspaceComponent);
    fixture.detectChanges();
  });
  it('renders an evidence-first workspace', () => {
    expect(fixture.nativeElement.textContent).toContain('Trend Intelligence');
    expect(fixture.nativeElement.textContent).toContain('Evidence-first');
    expect(fixture.nativeElement.querySelector('[aria-label=Breadcrumb]')).not.toBeNull();
  });

  it('reuses the selected opportunity context without starting research', async () => {
    const context = {
      id: 'trend-context-1',
      name: 'Selected product trends',
      subject_type: 'PRODUCT',
      subject_key: 'product-1',
      product_id: 'product-1',
      product_opportunity_id: 'opportunity-1',
      status: 'ACTIVE',
      version: 1,
      created_at: '',
      updated_at: '',
    };
    const service: Partial<TrendIntelligenceService> = {
      contexts: () => of([context]),
      createContext: vi.fn(),
      ingestions: () => of([]),
      observations: () => of({ items: [], total: 0, limit: 50, offset: 0 }),
      snapshots: () => of([]),
      currentValidation: () => of(null),
      analyses: () => of({ items: [], total: 0, limit: 50, offset: 0 }),
      changes: () => of({ items: [], total: 0, limit: 50, offset: 0 }),
      ingest: vi.fn(),
    };
    await TestBed.resetTestingModule()
      .configureTestingModule({
        imports: [TrendIntelligenceWorkspaceComponent],
        providers: [
          provideRouter([]),
          { provide: TrendIntelligenceService, useValue: service },
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
    const fixture = TestBed.createComponent(TrendIntelligenceWorkspaceComponent);
    await fixture.whenStable();
    expect(fixture.componentInstance.selected()?.id).toBe('trend-context-1');
    expect(service.createContext).not.toHaveBeenCalled();
    expect(service.ingest).not.toHaveBeenCalled();
  });
});
