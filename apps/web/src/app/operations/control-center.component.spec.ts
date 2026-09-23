import { provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';

import { ControlCenterComponent } from './control-center.component';
import { OperationsService } from './operations.service';

const overview = {
  status: 'healthy',
  environment: 'LOCAL',
  provider_modes: { shopify: 'SANDBOX', default: 'FAKE' },
  app_version: '0.1.0',
  health: { status: 'healthy', components: [] },
  workers: { enabled: true, items: [] },
  scheduler: {},
  jobs: {},
  recovery: { recoverable: 0 },
  providers: [],
  backup: { status: 'not_configured', latest: null },
  storage: { total_bytes: 0 },
  security: { emergency_stop: true },
  configuration: {},
  release: {},
  alerts: [],
};

describe('ControlCenterComponent', () => {
  it('renders named keyboard-reachable navigation and healthy state', async () => {
    await TestBed.configureTestingModule({
      imports: [ControlCenterComponent],
      providers: [
        provideRouter([]),
        {
          provide: OperationsService,
          useValue: {
            controlOverview: () => Promise.resolve(overview),
          } as unknown as OperationsService,
        },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(ControlCenterComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('h1')?.id).toBe('operations-title');
    expect(root.querySelector('nav')?.getAttribute('aria-label')).toBe('Operations sections');
    expect(root.querySelectorAll('nav a').length).toBeGreaterThanOrEqual(10);
    expect(root.querySelector('[role="status"]')).toBeNull();
    expect(root.textContent).toContain('No active operational alerts');
    expect(root.textContent).toContain('Nothing needs your attention');
    expect(root.textContent).toContain('No active work');
    expect(root.textContent).toContain('Open Calendar');
    expect(root.textContent).toContain('Open execution history');
    expect(root.querySelectorAll('a, button').length).toBeGreaterThan(8);
  });

  it('presents authoritative attention and provider-mode details without inventing priority', async () => {
    await TestBed.configureTestingModule({
      imports: [ControlCenterComponent],
      providers: [
        provideRouter([]),
        {
          provide: OperationsService,
          useValue: {
            controlOverview: () =>
              Promise.resolve({
                ...overview,
                provider_modes: { shopify: 'SANDBOX', default: 'FAKE' },
                alerts: [
                  {
                    code: 'failed_jobs',
                    severity: 'warning',
                    message: '1 durable publishing job requires review.',
                  },
                ],
                recovery: { recoverable: 1 },
                jobs: { failed: 1 },
                scheduler: { scheduled_jobs: 2, due_jobs: 1, overdue_schedules: 0 },
              }),
          } as unknown as OperationsService,
        },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(ControlCenterComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('Publishing jobs need review');
    expect(root.textContent).toContain('Recoverable execution failures');
    expect(root.textContent).toContain('SANDBOX');
    expect(root.textContent).not.toContain('CRITICAL');
    expect(root.querySelector('a[href="/operations/recovery"]')).not.toBeNull();
  });

  it('exposes loading and failure states through status/alert regions', async () => {
    let rejectOverview!: (reason?: unknown) => void;
    const pending = new Promise<unknown>((_resolve, reject) => {
      rejectOverview = reject;
    });
    await TestBed.configureTestingModule({
      imports: [ControlCenterComponent],
      providers: [
        provideRouter([]),
        {
          provide: OperationsService,
          useValue: { controlOverview: () => pending } as unknown as OperationsService,
        },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(ControlCenterComponent);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="status"]')?.textContent).toContain(
      'Loading operational overview',
    );

    rejectOverview(new Error('unavailable'));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]')?.textContent).toContain(
      'Operations data is unavailable',
    );
  });
});
