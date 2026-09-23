import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';

import { BusinessAgentWorkspaceComponent } from './business-agent-workspace.component';
import type {
  BusinessAgentGoal,
  BusinessAgentPlan,
  BusinessAgentRun,
} from './business-agent.service';
import { BusinessAgentService } from './business-agent.service';

const goal: BusinessAgentGoal = {
  id: 'goal-1',
  raw_goal: 'Find evidence-backed products for Amazon India.',
  status: 'DRAFT',
  structured_goal: { marketplace: 'AMAZON_IN', include_trend_intelligence: true },
  provenance: { source: 'owner_input' },
  assumptions: ['Owner-scoped deterministic capabilities only.'],
  unresolved_questions: ['available capital'],
  extraction_version: 'business-goal-v1',
  idempotency_key: 'goal-key',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const plan: BusinessAgentPlan = {
  id: 'plan-1',
  goal_id: 'goal-1',
  version: 1,
  status: 'READY',
  planner: 'deterministic-local',
  plan_hash: 'plan-hash',
  steps: [
    {
      key: 'trend',
      capability_id: 'TREND_ANALYSIS',
      dependencies: [],
      execution_mode: 'LOCAL_READ_ONLY',
      side_effect_class: 'NONE',
      status: 'READY',
    },
    {
      key: 'future_unknown',
      capability_id: 'FUTURE_CAPABILITY',
      dependencies: ['trend'],
      execution_mode: 'LOCAL_READ_ONLY',
      side_effect_class: 'NONE',
      status: 'QUEUED',
    },
  ],
};

const run: BusinessAgentRun = {
  id: 'run-1',
  goal_id: 'goal-1',
  plan_id: 'plan-1',
  status: 'WAITING_APPROVAL',
  idempotency_key: 'run-key',
  correlation_id: 'correlation-1',
  budget: { max_steps: 2 },
  usage: { steps: 2 },
  result: {
    decision: 'REVIEW_REQUIRED',
    trend_enabled: true,
    trend_evidence_gaps: [{ reason: 'Historical coverage is limited.' }],
  },
  failure: {},
  checkpoint: { step_key: 'trend' },
  approvals: [
    {
      id: 'approval-1',
      run_id: 'run-1',
      step_id: null,
      status: 'PENDING',
      reason: 'Business Decision Brief requires explicit owner approval.',
      decision_note: null,
      created_at: '2026-01-01T00:00:00Z',
      decided_at: null,
    },
  ],
  steps: [
    {
      id: 'step-1',
      key: 'trend',
      capability_id: 'TREND_ANALYSIS',
      status: 'SUCCEEDED',
      attempt_count: 1,
      result: {},
    },
    {
      id: 'step-2',
      key: 'future_unknown',
      capability_id: 'FUTURE_CAPABILITY',
      status: 'WAITING_APPROVAL',
      attempt_count: 1,
      result: {},
    },
  ],
  artifacts: [
    {
      id: 'brief-1',
      artifact_type: 'BUSINESS_DECISION_BRIEF',
      payload: {
        summary: 'Evidence-first opportunity brief ready for human decision.',
        opportunity_id: 'opportunity-1',
        trend_intelligence: {
          readiness: 'READY',
          confidence: 'MODERATE',
          freshness: 'FRESH',
          agreement: 'ALIGNED',
        },
      },
      provenance: { source: 'business-agent', provider: 'LOCAL_DETERMINISTIC' },
      created_at: '2026-01-01T00:00:00Z',
    },
    {
      id: 'evidence-1',
      artifact_type: 'TREND_ANALYSIS_SUMMARY',
      payload: {
        summary: 'Observed signal evidence.',
        contradictions: [{ message: 'Signals disagree on direction.' }],
      },
      provenance: { source: 'trend-intelligence' },
      created_at: '2026-01-01T00:00:00Z',
    },
  ],
  findings: [
    {
      id: 'finding-1',
      finding_type: 'TREND_RESEARCH_GAP',
      value: { status: 'EVIDENCE_GAP' },
      evidence_ids: ['evidence-1'],
      confidence: 0,
      created_at: '2026-01-01T00:00:00Z',
    },
  ],
  tool_invocations: [],
};

describe('BusinessAgentWorkspaceComponent', () => {
  const service = {
    goals: vi.fn(),
    capabilities: vi.fn(),
    createGoal: vi.fn(),
    plan: vi.fn(),
    createRun: vi.fn(),
    start: vi.fn(),
    run: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    cancel: vi.fn(),
    retry: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
  };

  async function create({ fail = false } = {}) {
    service.goals.mockReset();
    service.capabilities.mockReset();
    if (fail) service.goals.mockRejectedValue(new Error('backend details'));
    else service.goals.mockResolvedValue([goal]);
    service.capabilities.mockResolvedValue([]);
    await TestBed.configureTestingModule({
      imports: [BusinessAgentWorkspaceComponent],
      providers: [provideRouter([]), { provide: BusinessAgentService, useValue: service }],
    }).compileComponents();
    const fixture = TestBed.createComponent(BusinessAgentWorkspaceComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    await new Promise((resolve) => setTimeout(resolve, 10));
    fixture.detectChanges();
    return fixture;
  }

  it('renders goal-first creation with only supported research options', async () => {
    const fixture = await create();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('h1')?.textContent).toContain(
      'What are you trying to accomplish?',
    );
    expect(element.querySelector('textarea')?.getAttribute('placeholder')).toContain(
      'Amazon India',
    );
    expect(element.textContent).toContain('Advanced research options');
    expect(element.textContent).toContain('Include Trend Intelligence');
    expect(element.querySelector('input[name="provider"]')).toBeNull();
  });

  it('sends only supported goal constraints to the existing goal endpoint', async () => {
    const fixture = await create();
    const component = fixture.componentInstance;
    service.createGoal.mockResolvedValue(goal);
    component.rawGoal = 'Research suppliers for an Amazon India product.';
    component.marketplaceContext = 'AMAZON_IN';
    component.includeCompetitorIntelligence = true;
    component.includeReviewIntelligence = true;
    component.includeTrendIntelligence = true;
    await component.create();
    expect(service.createGoal).toHaveBeenCalledWith(
      expect.objectContaining({
        raw_goal: component.rawGoal,
        structured_goal: {
          marketplace: 'AMAZON_IN',
          include_competitor_intelligence: true,
          include_review_intelligence: true,
        },
        include_trend_intelligence: true,
      }),
    );
  });
  it('presents the authoritative plan, dependency labels, and safe capability fallback', async () => {
    const fixture = await create();
    const component = fixture.componentInstance;
    component.plans.set({ 'goal-1': plan });
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Analyze trend evidence');
    expect(text).toContain('Future Capability');
    expect(text).toContain('Waiting on: Analyze trend evidence');
    expect(text).toContain('FUTURE_CAPABILITY');
  });

  it('presents execution, approval, evidence, findings, gaps, contradictions, and brief values', async () => {
    const fixture = await create();
    const component = fixture.componentInstance;
    component.plans.set({ 'goal-1': plan });
    component.runs.set({ 'goal-1': run });
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    const text = element.textContent ?? '';
    expect(text).toContain('Research progress');
    expect(text).toContain('1 of 2 steps complete');
    expect(text).toContain('VAYUJIT is waiting for your approval');
    expect(text).toContain('Decision brief');
    expect(text).toContain('Observed signal evidence.');
    expect(text).toContain('Confidence');
    expect(text).toContain('Historical coverage is limited.');
    expect(text).toContain('Signals disagree on direction.');
    expect(element.querySelector('[data-status="WAITING_APPROVAL"]')).toBeTruthy();
    expect(element.querySelector('app-evidence-card')).toBeTruthy();
  });

  it('keeps completed and failed work inspectable with runtime-gated controls', async () => {
    const fixture = await create();
    const component = fixture.componentInstance;
    component.runs.set({ 'goal-1': { ...run, status: 'COMPLETED', approvals: [] } });
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Completed');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Decision brief');
    component.runs.set({
      'goal-1': {
        ...run,
        status: 'FAILED',
        failure: { code: 'PROVIDER_UNAVAILABLE', message: 'Provider unavailable.' },
        approvals: [],
      },
    });
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Research needs attention');
    expect(text).toContain('Retry through existing runtime');
    expect(text).toContain('Provider unavailable.');
  });
  it('keeps provider content inert and uses a shared error state', async () => {
    const fixture = await create({ fail: true });
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('[role="alert"]')?.textContent).toContain(
      'Business Agent data is unavailable.',
    );
    expect(element.textContent).not.toContain('backend details');
    const component = fixture.componentInstance;
    component.goals.set([{ ...goal, raw_goal: '<script>ignore</script>' }]);
    fixture.detectChanges();
    expect(element.querySelector('script')).toBeNull();
    expect(element.textContent).toContain('<script>ignore</script>');
  });
});
