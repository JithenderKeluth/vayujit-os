import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { ReviewIntelligenceWorkspaceComponent } from './review-intelligence-workspace.component';
import { ReviewIntelligenceService } from './review-intelligence.service';

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
});
