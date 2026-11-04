import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
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
  it('does not upgrade missing verification or synthetic observations to verified market evidence', () => {
    const component = fixture.componentInstance;
    component.selected.set({
      id: 'qa',
      name: 'Synthetic',
      subject_type: 'CUSTOM',
      subject_key: 'fixture',
      status: 'DRAFT',
      version: 1,
      created_at: '',
      updated_at: '',
    });
    component.observations.set([
      {
        id: 'observation',
        signal_definition_id: 'signal',
        observed_at: '2026-10-20T00:00:00Z',
        measurement_type: 'INDEX',
        value_numeric: '10.0000000000',
        geography_scope: 'GLOBAL',
        freshness_state: 'STALE',
        quality_state: 'UNKNOWN',
        source_reference: 'fixture',
        raw_metadata: { synthetic: true },
        provenance_note: 'Invented test index',
      },
    ]);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent || '';
    expect(text).toContain('UNKNOWN');
    expect(text).toContain('SYNTHETIC TEST DATA, not live market evidence');
    expect(text).toContain('Invented test index');
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
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelectorAll('#context-heading')).toHaveLength(1);
    expect(root.querySelector('#trend-context-list-heading')).not.toBeNull();
    expect(root.querySelectorAll('main')).toHaveLength(0);
  });
  it.each(['owned', 'missing'])(
    'resolves the exact %s deep link without substituting journey context',
    async (requested: string) => {
      const context = {
        id: 'owned',
        name: 'Owned context',
        subject_type: 'CUSTOM',
        subject_key: 'synthetic',
        status: 'DRAFT',
        version: 1,
        created_at: '',
        updated_at: '',
      };
      const active = vi.fn();
      const service = {
        contexts: () => of([context]),
        createContext: vi.fn(),
        ingestions: () => of([]),
        observations: () => of({ items: [] }),
        snapshots: () => of([]),
        currentValidation: () => of(null),
        analyses: () => of({ items: [] }),
        changes: () => of({ items: [] }),
      };
      TestBed.resetTestingModule().configureTestingModule({
        providers: [
          provideRouter([]),
          {
            provide: ActivatedRoute,
            useValue: { snapshot: { paramMap: convertToParamMap({ contextId: requested }) } },
          },
          { provide: TrendIntelligenceService, useValue: service },
          { provide: CommerceJourneyService, useValue: { active } },
        ],
      });
      const c = TestBed.runInInjectionContext(() => new TrendIntelligenceWorkspaceComponent());
      await Promise.resolve();
      expect(c.selected()?.id ?? null).toBe(requested === 'owned' ? 'owned' : null);
      expect(active).not.toHaveBeenCalled();
      expect(service.createContext).not.toHaveBeenCalled();
      if (requested === 'missing') expect(c.error()).toContain('No other context was substituted');
    },
  );
});
