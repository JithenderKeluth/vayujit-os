import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { provideRouter } from '@angular/router';
import { By } from '@angular/platform-browser';
import { IntelligenceWorkspaceComponent } from './intelligence-workspace.component';

const overview = {
  active_projects: 1,
  recent_runs: 1,
  opportunities: { review: 1 },
  hard_blocked_candidates: 0,
  evidence_freshness: { fresh: 5 },
  enabled_sources: 5,
  source_health: { healthy: 5 },
  rule_counts: { enabled: 1 },
  recent_failures: 0,
};

function responseData() {
  return {
    projects: [
      {
        id: 'project-1',
        name: 'Winning products',
        description: 'Local',
        status: 'active',
        target_market: 'IN',
        target_categories: ['home'],
        risk_profile: 'balanced',
        updated_at: '2026-08-24T00:00:00Z',
      },
    ],
    sources: [
      {
        id: 'source-1',
        display_name: 'Local fixture',
        source_type: 'internal_marketplace_data',
        provider: 'local_deterministic',
        access_method: 'internal',
        enabled: true,
        trust_classification: 'trusted_internal',
        configuration_status: 'ready',
        failure_status: null,
      },
    ],
    opportunities: [
      {
        id: 'opportunity-1',
        title: 'Bamboo Organizer',
        category: 'home',
        market: 'IN',
        status: 'review',
        score: 82,
        confidence: 0.8,
        hard_blocked: false,
        evidence_count: 5,
        freshness_state: 'fresh',
        primary_reasons: ['Evidence-backed demand'],
      },
    ],
    candidates: [
      {
        id: 'candidate-1',
        title: 'Bamboo Organizer',
        category: 'home',
        subcategory: 'storage',
        market: 'IN',
        status: 'promoted',
        observed_price: 799,
        currency: 'INR',
        source_reference: 'local://fixture',
        freshness_state: 'fresh',
      },
    ],
    missions: [
      {
        id: 'mission-1',
        project_id: 'project-1',
        name: 'Daily local run',
        enabled: true,
        frequency: 'daily',
        market: 'IN',
        categories: ['home'],
        status: 'active',
        minimum_score_threshold: 45,
        last_run_at: null,
      },
    ],
  };
}

describe('IntelligenceWorkspaceComponent', () => {
  afterEach(() => vi.restoreAllMocks());
  function create() {
    TestBed.configureTestingModule({
      imports: [IntelligenceWorkspaceComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(IntelligenceWorkspaceComponent);
    const http = TestBed.inject(HttpTestingController);
    return { fixture, http };
  }

  function flushInitial(http: HttpTestingController) {
    const data = responseData();
    http.expectOne('http://127.0.0.1:8000/api/v1/intelligence/overview').flush(overview);
    http.expectOne('http://127.0.0.1:8000/api/v1/intelligence/projects').flush(data.projects);
    http.expectOne('http://127.0.0.1:8000/api/v1/intelligence/sources').flush(data.sources);
    http
      .expectOne('http://127.0.0.1:8000/api/v1/intelligence/opportunities')
      .flush(data.opportunities);
    http.expectOne('http://127.0.0.1:8000/api/v1/intelligence/candidates').flush(data.candidates);
    http.expectOne('http://127.0.0.1:8000/api/v1/intelligence/missions').flush(data.missions);
  }

  it('renders all evidence panels and accessible workspace navigation', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(
      fixture.nativeElement.querySelector('main[aria-labelledby="intelligence-title"]'),
    ).not.toBeNull();
    expect(
      fixture.nativeElement.querySelector('nav[aria-label="Intelligence sections"]'),
    ).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain('OBSERVED EVIDENCE');
    expect(fixture.nativeElement.textContent).toContain('DERIVED SIGNAL');
    expect(fixture.nativeElement.textContent).toContain('ASSUMPTION');
    expect(fixture.nativeElement.textContent).toContain('DETERMINISTIC RULE');
    expect(fixture.nativeElement.textContent).toContain('AI INTERPRETATION DISABLED');
    expect(fixture.nativeElement.textContent).toContain('Competitor intelligence');
    expect(fixture.nativeElement.textContent).toContain('Review intelligence');
    expect(fixture.nativeElement.textContent).toContain('Comparison');
    expect(fixture.nativeElement.textContent).toContain('Reports');
    http.verify();
  });

  it('renders owner-scoped overview, candidate, mission, and opportunity data', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Winning products');
    expect(fixture.nativeElement.textContent).toContain('Bamboo Organizer');
    expect(fixture.nativeElement.textContent).toContain('Daily local run');
    expect(fixture.nativeElement.textContent).toContain('Score 82');
    expect(fixture.nativeElement.textContent).toContain(
      'External research is disabled by default.',
    );
    http.verify();
  });

  it('supports mission run-now without leaving the workspace', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.detectChanges();
    const buttons = fixture.nativeElement.querySelectorAll(
      'button',
    ) as NodeListOf<HTMLButtonElement>;
    const button = Array.from(buttons).find(
      (value) => value.textContent?.trim() === 'Run now',
    ) as HTMLButtonElement;
    expect(button).toBeTruthy();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    button.click();
    http
      .expectOne(
        (request) =>
          request.url === 'http://127.0.0.1:8000/api/v1/intelligence/missions/mission-1/run-now',
      )
      .flush({
        id: 'run-1',
        status: 'completed',
      });
    await fixture.whenStable();
    flushInitial(http);
    await fixture.whenStable();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Daily local run');
    http.verify();
  });

  it('shows a safe authenticated-API boundary when loading fails', async () => {
    const { fixture, http } = create();
    http
      .expectOne('http://127.0.0.1:8000/api/v1/intelligence/overview')
      .flush({}, { status: 503, statusText: 'Unavailable' });
    http
      .expectOne('http://127.0.0.1:8000/api/v1/intelligence/projects')
      .flush({}, { status: 503, statusText: 'Unavailable' });
    http
      .expectOne('http://127.0.0.1:8000/api/v1/intelligence/sources')
      .flush({}, { status: 503, statusText: 'Unavailable' });
    http
      .expectOne('http://127.0.0.1:8000/api/v1/intelligence/opportunities')
      .flush({}, { status: 503, statusText: 'Unavailable' });
    http
      .expectOne('http://127.0.0.1:8000/api/v1/intelligence/candidates')
      .flush({}, { status: 503, statusText: 'Unavailable' });
    http
      .expectOne('http://127.0.0.1:8000/api/v1/intelligence/missions')
      .flush({}, { status: 503, statusText: 'Unavailable' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain(
      'Intelligence data is unavailable. Check the authenticated API connection.',
    );
    expect(fixture.nativeElement.textContent).not.toContain('traceback');
    http.verify();
  });

  it('exposes the complete workspace navigation contract', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.detectChanges();
    const labels = fixture.debugElement
      .queryAll(By.css('nav a'))
      .map((link) => String(link.nativeElement.textContent ?? '').trim());
    expect(labels).toEqual([
      'Overview',
      'Missions',
      'Candidates',
      'Opportunities',
      'Rules',
      'Profiles',
      'Comparison',
      'Reports',
      'History',
      'Sources & evidence',
    ]);
    http.verify();
  });

  it('creates a mission with the validated owner-scoped payload', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component.missionForm.name = 'Weekly home run';
    component.missionForm.project_id = 'project-1';
    component.missionForm.market = 'IN';
    component.missionForm.categories = 'home, storage';
    void component.createMission();
    const request = http.expectOne('http://127.0.0.1:8000/api/v1/intelligence/missions');
    expect(request.request.body).toMatchObject({
      project_id: 'project-1',
      name: 'Weekly home run',
      market: 'IN',
      categories: ['home', 'storage'],
    });
    request.flush(responseData().missions[0]);
    await fixture.whenStable();
    flushInitial(http);
    await fixture.whenStable();
    http.verify();
  });

  it('blocks invalid mission creation and duplicate run clicks', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component.missionForm.name = '';
    component.missionForm.project_id = '';
    await component.createMission();
    expect(component.error()).toContain('Mission name and project are required.');
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const button = fixture.debugElement
      .queryAll(By.css('button'))
      .find((value) => value.nativeElement.textContent?.trim() === 'Run now')
      ?.nativeElement as HTMLButtonElement;
    button.click();
    button.click();
    const requests = http.match(
      'http://127.0.0.1:8000/api/v1/intelligence/missions/mission-1/run-now',
    );
    expect(requests).toHaveLength(1);
    requests[0].flush({ id: 'run-1', status: 'accepted' });
    await fixture.whenStable();
    flushInitial(http);
    await fixture.whenStable();
    http.verify();
  });

  it('loads candidate and opportunity detail through authenticated service calls', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    fixture.detectChanges();
    const component = fixture.componentInstance;
    void component.selectCandidate(responseData().candidates[0]);
    http
      .expectOne('http://127.0.0.1:8000/api/v1/intelligence/candidates/candidate-1')
      .flush(responseData().candidates[0]);
    http
      .expectOne('http://127.0.0.1:8000/api/v1/intelligence/candidates/candidate-1/signals')
      .flush([]);
    http
      .expectOne('http://127.0.0.1:8000/api/v1/intelligence/candidates/candidate-1/trends')
      .flush([]);
    await fixture.whenStable();
    expect(component.selectedCandidate()?.id).toBe('candidate-1');
    void component.selectOpportunity(responseData().opportunities[0]);
    http
      .expectOne('http://127.0.0.1:8000/api/v1/intelligence/opportunities/opportunity-1')
      .flush(responseData().opportunities[0]);
    await fixture.whenStable();
    expect(component.selectedOpportunity()?.id).toBe('opportunity-1');
    http.verify();
  });

  it('validates profile bounds before making a write request', async () => {
    const { fixture, http } = create();
    flushInitial(http);
    await fixture.whenStable();
    const component = fixture.componentInstance;
    component.profileForm.name = 'Retail profile';
    component.profileForm.min_selling_price = 1000;
    component.profileForm.max_selling_price = 100;
    await component.createProfile();
    expect(component.error()).toContain('Minimum price cannot exceed maximum price.');
    http.verify();
  });
});
