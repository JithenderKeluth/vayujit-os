import { provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';

import { AlibabaDiscoveryComponent } from './alibaba-discovery.component';
import { IntelligenceService } from './intelligence.service';

describe('AlibabaDiscoveryComponent', () => {
  function configure(service: Partial<IntelligenceService>) {
    return TestBed.configureTestingModule({
      imports: [AlibabaDiscoveryComponent],
      providers: [provideRouter([]), { provide: IntelligenceService, useValue: service }],
    }).compileComponents();
  }

  it('renders readiness, history, discovery-only results, and claims', async () => {
    await configure({
      alibabaPreflight: () =>
        Promise.resolve({
          provider: 'ALIBABA',
          mode: 'LOCAL_FIXTURE',
          status: 'READY',
          credentials_configured: false,
          live_validation: 'NOT_RUN',
          read_only: true,
          network_call: false,
        }),
      alibabaHistory: () =>
        Promise.resolve([
          {
            id: 'run-1',
            provider: 'ALIBABA',
            mode: 'LOCAL_FIXTURE',
            status: 'completed',
            query: 'trail bottle',
            result_count: 1,
            correlation_id: 'corr',
            idempotency_key: 'key',
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        ]),
    });
    const fixture = TestBed.createComponent(AlibabaDiscoveryComponent);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Alibaba read-only discovery');
    expect(fixture.nativeElement.textContent).toContain('LOCAL_FIXTURE');
    expect(fixture.nativeElement.textContent).toContain('Discovery history');
    expect(fixture.nativeElement.textContent).toContain('trail bottle');
    expect(fixture.nativeElement.textContent).toContain('DISCOVERY ONLY');
  });

  it('shows the safe error state when the authenticated API is unavailable', async () => {
    await configure({
      alibabaPreflight: () => Promise.reject(new Error('offline')),
      alibabaHistory: () => Promise.reject(new Error('offline')),
    });
    const fixture = TestBed.createComponent(AlibabaDiscoveryComponent);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain(
      'Alibaba discovery is unavailable. Check the authenticated API connection.',
    );
    expect(fixture.nativeElement.querySelector('[role="alert"]')).not.toBeNull();
  });

  it('keeps landmarks, labels, captions, alerts, and keyboard controls accessible', async () => {
    await configure({
      alibabaPreflight: () =>
        Promise.resolve({
          provider: 'ALIBABA',
          mode: 'LOCAL_FIXTURE',
          status: 'READY',
          credentials_configured: false,
          live_validation: 'NOT_RUN',
          read_only: true,
          network_call: false,
        }),
      alibabaHistory: () =>
        Promise.resolve([
          {
            id: 'run-1',
            provider: 'ALIBABA',
            mode: 'LOCAL_FIXTURE',
            status: 'completed',
            query: 'trail bottle',
            result_count: 1,
            correlation_id: 'corr',
            idempotency_key: 'key',
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        ]),
    });
    const fixture = TestBed.createComponent(AlibabaDiscoveryComponent);
    await fixture.whenStable();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('main[aria-labelledby="alibaba-title"]')).not.toBeNull();
    expect(root.querySelectorAll('h1')).toHaveLength(1);
    expect(root.querySelector('form[aria-label="Alibaba discovery request"]')).not.toBeNull();
    expect(root.querySelectorAll('label').length).toBeGreaterThanOrEqual(4);
    expect(root.querySelector('caption')).not.toBeNull();
    expect(root.querySelectorAll('button').length).toBeGreaterThan(0);
  });

  it('defines bounded table scrolling and mobile breakpoints for 390, 768, and 1280 layouts', () => {
    const source = String(AlibabaDiscoveryComponent);
    expect(source).toContain('overflow-x: auto');
    expect(source).toContain('@media (max-width: 768px)');
    expect(source).toContain('@media (max-width: 390px)');
    expect(source).toContain('max-width: 1200px');
  });

  it('covers the final accessibility assertions', async () => {
    await configure({
      alibabaPreflight: () => new Promise(() => undefined),
      alibabaHistory: () => Promise.resolve([]),
    });
    const fixture = TestBed.createComponent(AlibabaDiscoveryComponent);
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    const source = String(AlibabaDiscoveryComponent);
    expect(root.querySelector('[role="alert"]')).toBeNull();
    expect(root.querySelector('[aria-live="polite"]')).not.toBeNull();
    expect(root.textContent).toContain('Risk status: unverified claims require human review.');
    expect(source).toContain(':focus-visible');
    expect(source).toContain('"scope"');
    expect(source).toContain('"col"');
  });
});
