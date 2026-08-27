import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AutonomousResearchComponent } from './autonomous-research.component';

const base = 'http://127.0.0.1:8000/api/v1/intelligence/autonomous';
const overview = {
  active_missions: 1,
  queued_tasks: 2,
  completed_missions: 3,
  partial_missions: 1,
  failed_missions: 0,
  stale_opportunities: 0,
  evidence_refresh_backlog: 1,
  contradictions: 1,
  recovery: 1,
  external_research: 'DISABLED',
  ai_mode: 'LOCAL_DETERMINISTIC',
};

function create() {
  TestBed.configureTestingModule({
    imports: [AutonomousResearchComponent],
    providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
  });
  const fixture = TestBed.createComponent(AutonomousResearchComponent);
  const http = TestBed.inject(HttpTestingController);
  return { fixture, http };
}

function flushInitial(http: HttpTestingController, missions: Record<string, unknown>[] = []) {
  http.expectOne(`${base}/overview`).flush(overview);
  http.expectOne(`${base}/policy`).flush({
    default_provider_mode: 'LOCAL_DETERMINISTIC',
    external_research_enabled: false,
  });
  http.expectOne(`${base}/missions`).flush(missions);
}

describe('AutonomousResearchComponent', () => {
  it('renders safe policy, metrics, empty state, and accessible regions', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(
      fixture.nativeElement.querySelector('main[aria-labelledby="autonomous-title"]'),
    ).not.toBeNull();
    expect(fixture.nativeElement.querySelector('[role="alert"]')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Disabled by default');
    expect(fixture.nativeElement.textContent).toContain('LOCAL_DETERMINISTIC');
    expect(fixture.nativeElement.textContent).toContain('No autonomous missions yet.');
    http.verify();
  });

  it('renders active mission history and supports local execution', async () => {
    const { fixture, http } = create();
    flushInitial(http, [
      { id: 'mission-1', mission_type: 'PRODUCT_DISCOVERY', goal: 'Local', status: 'QUEUED' },
    ]);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('PRODUCT_DISCOVERY');
    const root = fixture.nativeElement as HTMLElement;
    const buttons = Array.from(root.querySelectorAll('button'));
    const button = buttons.find((item) => item.textContent?.includes('Run local fixture'));
    expect(button).toBeTruthy();
    if (!button) throw new Error('Run local fixture button not found');
    button.click();
    http.expectOne(`${base}/missions/mission-1/run`).flush({ status: 'COMPLETED' });
    await fixture.whenStable();
    flushInitial(http, []);
    await fixture.whenStable();
    fixture.detectChanges();
    http.verify();
  });

  it('shows a safe API failure without exposing internals', async () => {
    const { fixture, http } = create();
    http.expectOne(`${base}/overview`).flush({}, { status: 503, statusText: 'Unavailable' });
    http.expectOne(`${base}/policy`).flush({}, { status: 503, statusText: 'Unavailable' });
    http.expectOne(`${base}/missions`).flush({}, { status: 503, statusText: 'Unavailable' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Autonomous research data is unavailable');
    expect(fixture.nativeElement.textContent.toLowerCase()).not.toContain('traceback');
    http.verify();
  });
});
