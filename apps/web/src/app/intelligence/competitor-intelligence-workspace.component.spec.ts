import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { CompetitorIntelligenceWorkspaceComponent } from './competitor-intelligence-workspace.component';
import { CompetitorIntelligenceService } from './competitor-intelligence.service';

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
});
