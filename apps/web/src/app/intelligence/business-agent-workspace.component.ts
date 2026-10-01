import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { EvidenceCardComponent } from '../shared/evidence-card.component';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { PageHeaderComponent } from '../shared/page-header.component';
import { StatusBadgeComponent } from '../shared/status-badge.component';
import type { EvidenceDetail, StatusTone } from '../shared/ux-foundation.types';
import type {
  BusinessAgentArtifact,
  BusinessAgentCapability,
  BusinessAgentFinding,
  BusinessAgentGoal,
  BusinessAgentPlan,
  BusinessAgentRun,
  BusinessAgentRunStep,
} from './business-agent.service';
import { BusinessAgentService } from './business-agent.service';
import { CommerceJourneyContextComponent } from '../commerce-journey-context.component';

const CAPABILITY_LABELS: Record<string, string> = {
  'product_opportunity.create': 'Discover product opportunities',
  'demand.intelligence': 'Analyze demand evidence',
  'competition.intelligence': 'Analyze competition',
  'commercial.assessment': 'Assess commercial viability',
  'supplier.discovery': 'Research suppliers',
  'supplier.feasibility': 'Evaluate sourcing evidence',
  'winning_product.score': 'Evaluate product opportunity',
  'winning_product.rank': 'Rank product opportunities',
  'decision_brief.generate': 'Prepare decision brief',
  'sourcing_economics.inspect': 'Review sourcing economics',
  TREND_CONTEXT_RESOLUTION: 'Resolve trend context',
  TREND_INGESTION: 'Collect trend evidence',
  TREND_ANALYSIS: 'Analyze trend evidence',
  TREND_CHANGE_ANALYSIS: 'Analyze trend change',
  TREND_VALIDATION: 'Validate trend evidence',
  TREND_WINNING_PRODUCT_PROJECTION: 'Apply trend product projection',
  COMPETITOR_DISCOVERY: 'Discover competitors',
  COMPETITOR_ANALYSIS: 'Analyze competitors',
  COMPETITOR_CHANGE_ANALYSIS: 'Analyze competitor change',
  REVIEW_INGESTION: 'Collect customer feedback evidence',
  REVIEW_ANALYSIS: 'Understand customer feedback',
  REVIEW_GAP_ANALYSIS: 'Identify review evidence gaps',
  REVIEW_CHANGE_ANALYSIS: 'Analyze review change',
  REVIEW_WINNING_PRODUCT_PROJECTION: 'Apply review product projection',
};

@Component({
  selector: 'app-business-agent-workspace',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    EvidenceCardComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    PageHeaderComponent,
    StatusBadgeComponent,
    CommerceJourneyContextComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './business-agent-workspace.css',
  template: `
    <main class="agent-page" aria-labelledby="business-agent-title">
      <app-page-header
        eyebrow="Intelligence / Business Agent"
        title="What are you trying to accomplish?"
        headingId="business-agent-title"
        description="Tell VAYUJIT the outcome you want. It will organize supported research, preserve the evidence, and keep consequential decisions under your control."
      >
        <nav page-header-actions class="workspace-nav" aria-label="Business Agent navigation">
          <a routerLink="/intelligence">Intelligence</a>
          <a routerLink="/intelligence/product-opportunities">Product opportunities</a>
          <a routerLink="/intelligence/sourcing">Supplier intelligence</a>
        </nav>
      </app-page-header>
      <app-commerce-journey-context />

      <p class="agent-notice">
        Your plan, evidence, and decisions stay in this workspace. External writes are off.
        <strong>Local demo data - not live market evidence.</strong>
      </p>
      <details class="technical-details">
        <summary>How this workspace operates</summary>
        <p>
          Research uses the local deterministic provider. Plans and runs are owner-scoped, durable,
          and reviewable.
        </p>
      </details>
      @if (error()) {
        <app-error-state
          [message]="error()"
          retryLabel="Reload Business Agent"
          (retry)="refresh()"
        />
      }
      @if (loading()) {
        <app-loading-state message="Loading Business Agent workspace..." />
      }

      <details class="goal-creation" [open]="!goals().length">
        <summary class="goal-creation-summary">
          {{ goals().length ? 'Start another research goal' : 'Start with a business outcome' }}
        </summary>
        <div class="section-heading">
          <div>
            <p class="eyebrow">Goal</p>
            <h2 id="goal-title">
              {{
                goals().length
                  ? 'Tell VAYUJIT what to research next'
                  : 'Start with a business outcome'
              }}
            </h2>
            <p class="lede">
              Use plain language. Constraints that are supported by the runtime stay attached to the
              authoritative goal.
            </p>
          </div>
        </div>
        <form class="goal-form" (ngSubmit)="create()">
          <label class="goal-field">
            <span>What are you trying to accomplish?</span>
            <textarea
              name="goal"
              [(ngModel)]="rawGoal"
              required
              minlength="5"
              rows="4"
              placeholder="Example: Find products I could launch on Amazon India within my budget and risk preferences."
            ></textarea>
          </label>
          <p class="field-help">
            Examples are guidance only; nothing runs until you create a goal and review its plan.
          </p>
          <details class="advanced-options">
            <summary>Advanced research options</summary>
            <div class="advanced-grid">
              <label>
                Marketplace context (optional)
                <input
                  name="marketplace"
                  [(ngModel)]="marketplaceContext"
                  placeholder="AMAZON_IN"
                />
              </label>
              <label class="check-field">
                <input
                  type="checkbox"
                  name="competitor"
                  [(ngModel)]="includeCompetitorIntelligence"
                />
                Include competitor intelligence
              </label>
              <label class="check-field">
                <input type="checkbox" name="review" [(ngModel)]="includeReviewIntelligence" />
                Include customer-feedback evidence
              </label>
              <label class="check-field">
                <input type="checkbox" name="trend" [(ngModel)]="includeTrendIntelligence" />
                Include Trend Intelligence
              </label>
            </div>
            <p class="field-help">
              These options map to existing Business Agent goal fields. Provider credentials,
              budgets, and execution limits remain runtime-owned.
            </p>
          </details>
          <button class="primary-action" type="submit" [disabled]="loading() || !rawGoal.trim()">
            Create research goal
          </button>
        </form>
      </details>

      <section class="history" aria-labelledby="history-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">History</p>
            <h2 id="history-title">Research goals and runs</h2>
            <p class="lede">
              Review the active goal first. Previous research remains available below when you need
              it.
            </p>
          </div>
        </div>
        @if (!loading() && !goals().length) {
          <app-empty-state
            title="Start your first Business Agent research run"
            message="Tell VAYUJIT what you want to accomplish. It will prepare an evidence-backed plan using the capabilities available to your workspace."
          >
            <a class="primary-action" href="#goal-title">Create goal</a>
          </app-empty-state>
        }
        <div class="goal-list">
          @for (goal of activeGoals(); track goal.id) {
            <article class="goal-card" [class.selected]="selectedGoalId === goal.id">
              <header class="goal-card-header">
                <div>
                  <p class="eyebrow">Goal</p>
                  <h3>{{ goal.raw_goal }}</h3>
                  <p class="timestamp">Created {{ goal.created_at }}</p>
                </div>
                <app-status-badge
                  [status]="goal.status"
                  [label]="statusLabel(goal.status)"
                  [tone]="statusTone(goal.status)"
                />
              </header>
              @if (goal.structured_goal['marketplace']) {
                <p class="context-line">
                  <strong>Marketplace:</strong> {{ goal.structured_goal['marketplace'] }}
                </p>
              }
              <div class="constraint-summary" aria-label="Goal details">
                <strong>Goal details</strong>
                <ul>
                  @for (constraint of constraintRows(goal); track constraint.label) {
                    <li>
                      <span>{{ constraint.label }}:</span>
                      <strong>{{ constraint.value }}</strong>
                      <small>{{ constraint.state }}</small>
                    </li>
                  }
                </ul>
              </div>
              @if (goal.unresolved_questions.length) {
                <div class="callout warning">
                  <strong>What is still unknown</strong>
                  <ul>
                    @for (question of goal.unresolved_questions; track question) {
                      <li>{{ question }}</li>
                    }
                  </ul>
                </div>
              }
              @if (goal.assumptions.length) {
                <details class="technical-details">
                  <summary>Goal assumptions and technical details</summary>
                  <ul>
                    @for (assumption of goal.assumptions; track assumption) {
                      <li>{{ assumption }}</li>
                    }
                  </ul>
                  <p>Extraction version: {{ goal.extraction_version }}</p>
                </details>
              }
              <div class="goal-actions">
                <button type="button" (click)="makePlan(goal)" [disabled]="loading()">
                  Create versioned research plan
                </button>
                @if (plans()[goal.id]; as plan) {
                  <span class="quiet"
                    >Plan v{{ plan.version }} · {{ plan.steps.length }} authoritative steps</span
                  >
                  <button type="button" (click)="run(goal, plan)" [disabled]="loading()">
                    Start run
                  </button>
                }
              </div>

              @if (plans()[goal.id]; as plan) {
                <details class="plan-section technical-details">
                  <summary>Research details - plan v{{ plan.version }}</summary>
                  <div class="section-heading compact">
                    <div>
                      <p class="eyebrow">Plan</p>
                      <h4 id="plan-title-{{ goal.id }}">Research plan</h4>
                    </div>
                    <app-status-badge
                      [status]="plan.status"
                      [label]="statusLabel(plan.status)"
                      [tone]="statusTone(plan.status)"
                    />
                  </div>
                  <p class="quiet">Planner: {{ plan.planner }} · Version {{ plan.version }}</p>
                  <ol class="plan-list">
                    @for (step of plan.steps; track step.key) {
                      <li class="plan-step">
                        <app-status-badge
                          [status]="step.status"
                          [label]="statusLabel(step.status)"
                          [tone]="statusTone(step.status)"
                        />
                        <div>
                          <strong>{{
                            step.business_label || capabilityLabel(step.capability_id)
                          }}</strong>
                          @if (step.business_description) {
                            <small>{{ step.business_description }}</small>
                          }
                          <details class="technical-details compact-details">
                            <summary>Execution detail</summary>
                            <small>{{ step.capability_id }}</small>
                          </details>
                          @if (step.dependencies.length) {
                            <small
                              >Waiting on: {{ dependencyLabels(step.dependencies, plan) }}</small
                            >
                          }
                        </div>
                      </li>
                    }
                  </ol>
                </details>
              }

              @if (runs()[goal.id]; as run) {
                <section class="run-section" aria-labelledby="run-title-{{ goal.id }}">
                  <div class="section-heading compact">
                    <div>
                      <p class="eyebrow">Execution</p>
                      <h4 id="run-title-{{ goal.id }}">Research progress</h4>
                    </div>
                    <app-status-badge
                      [status]="run.status"
                      [label]="statusLabel(run.status)"
                      [tone]="statusTone(run.status)"
                    />
                  </div>
                  <p class="run-summary">
                    {{ completedStepCount(run) }} of {{ run.steps.length }} steps complete ·
                    Decision: {{ displayValue(run.result['decision']) || 'Not available' }}
                  </p>
                  <section
                    class="business-run-summary"
                    aria-label="Research outcome"
                    role="status"
                    aria-live="polite"
                  >
                    <div>
                      <p class="eyebrow">What VAYUJIT is doing</p>
                      <p>{{ businessRunStatus(run) }}</p>
                    </div>
                    <div>
                      <p class="eyebrow">What has been found</p>
                      <p>
                        {{ run.candidates?.length || run.findings.length || run.artifacts.length }}
                        evidence-backed result{{
                          (run.candidates?.length ||
                            run.findings.length ||
                            run.artifacts.length) === 1
                            ? ''
                            : 's'
                        }}
                        recorded.
                      </p>
                    </div>
                    @if (researchGaps(run).length) {
                      <div>
                        <p class="eyebrow">What is still missing</p>
                        <p>
                          {{ researchGaps(run).length }} evidence gap{{
                            researchGaps(run).length === 1 ? '' : 's'
                          }}
                          need review.
                        </p>
                      </div>
                    }
                  </section>
                  @if (run.result['outcome'] === 'RESEARCH_COMPLETED_WITH_GAPS') {
                    <div class="callout warning" role="status">
                      <strong>Research completed with gaps</strong>
                      <p>
                        Some evidence steps need attention. Completed findings remain available, and
                        you can resume or retry the affected steps.
                      </p>
                    </div>
                  }
                  @if (run.candidates?.length) {
                    <section
                      class="candidate-section"
                      aria-labelledby="candidate-title-{{ goal.id }}"
                    >
                      <div class="section-heading compact">
                        <div>
                          <p class="eyebrow">Product candidates</p>
                          <h4 id="candidate-title-{{ goal.id }}">What surfaced for review</h4>
                        </div>
                      </div>
                      <a
                        class="secondary-action action-link"
                        routerLink="/intelligence/product-opportunities"
                        >Compare products</a
                      >
                      <div class="candidate-list">
                        @for (candidate of run.candidates; track candidate.id) {
                          <article class="candidate-card">
                            <strong>{{ candidate.name }}</strong>
                            <span>{{ candidate.status }}</span>
                            <p>{{ candidate.description || candidate.product_concept }}</p>
                            <small
                              >Evidence: {{ candidate.evidence_state }} · Research:
                              {{ candidate.research_state }}</small
                            >
                          </article>
                        }
                      </div>
                    </section>
                  }
                  @if (currentStep(run); as current) {
                    <div class="current-step">
                      <strong
                        >Current step:
                        {{
                          current.business_label || capabilityLabel(current.capability_id)
                        }}</strong
                      >
                      <app-status-badge
                        [status]="current.status"
                        [label]="statusLabel(current.status)"
                        [tone]="statusTone(current.status)"
                      />
                      <details class="technical-details compact-details">
                        <summary>Research detail</summary>
                        <span>Attempt {{ current.attempt_count }}</span>
                      </details>
                    </div>
                  }
                  <details class="technical-details execution-details">
                    <summary>Research details and execution timeline</summary>
                    <ol class="timeline" aria-label="Authoritative execution timeline">
                      @for (step of run.steps; track step.id) {
                        <li>
                          <span class="timeline-marker" aria-hidden="true"></span>
                          <div>
                            <strong>{{
                              step.business_label || capabilityLabel(step.capability_id)
                            }}</strong>
                            <app-status-badge
                              [status]="step.status"
                              [label]="statusLabel(step.status)"
                              [tone]="statusTone(step.status)"
                            />
                          </div>
                        </li>
                      }
                    </ol>
                  </details>
                  @if (run.failure['message']) {
                    <div class="callout danger" role="alert">
                      <strong>Research needs attention</strong>
                      <p>{{ displayValue(run.failure['message']) }}</p>
                    </div>
                  }
                  @if (run.checkpoint['step_key']) {
                    <p class="quiet">
                      Durable checkpoint: {{ displayValue(run.checkpoint['step_key']) }}
                    </p>
                  }
                  <div class="run-controls">
                    @if (canPause(run)) {
                      <button type="button" (click)="pause(run)">Pause run</button>
                    }
                    @if (canResume(run)) {
                      <button type="button" (click)="resume(run)">Resume run</button>
                    }
                    @if (canCancel(run)) {
                      <button type="button" class="danger-action" (click)="cancel(run)">
                        Cancel run
                      </button>
                    }
                    @if (canRetry(run)) {
                      <button type="button" (click)="retry(run)">
                        Retry through existing runtime
                      </button>
                    }
                    <button type="button" class="secondary-action" (click)="refreshRun(run)">
                      Refresh run
                    </button>
                  </div>
                  <p class="human-control">
                    VAYUJIT can research and prepare evidence. Consequential actions remain subject
                    to explicit human approval.
                  </p>
                </section>

                @if (pendingApproval(run); as approval) {
                  <section class="approval-section" aria-labelledby="approval-title-{{ goal.id }}">
                    <div class="section-heading compact">
                      <div>
                        <p class="eyebrow">Action required</p>
                        <h4 id="approval-title-{{ goal.id }}">
                          VAYUJIT is waiting for your approval
                        </h4>
                      </div>
                      <app-status-badge
                        [status]="approval.status"
                        [label]="statusLabel(approval.status)"
                        [tone]="statusTone(approval.status)"
                      />
                    </div>
                    <p>{{ approval.reason }}</p>
                    <label
                      >Decision note (optional)<textarea
                        [(ngModel)]="decisionNote"
                        [name]="'note-' + approval.id"
                        rows="2"
                      ></textarea>
                    </label>
                    <div class="run-controls">
                      <button type="button" class="primary-action" (click)="approve(run, approval)">
                        Approve and complete
                      </button>
                      <button type="button" class="danger-action" (click)="reject(run, approval)">
                        Reject and stop
                      </button>
                    </div>
                  </section>
                }

                @if (decisionBrief(run); as brief) {
                  <section class="brief-section" aria-labelledby="brief-title-{{ goal.id }}">
                    <div class="section-heading compact">
                      <div>
                        <p class="eyebrow">Decision brief</p>
                        <h4 id="brief-title-{{ goal.id }}">Evidence-backed outcome</h4>
                      </div>
                      <app-status-badge
                        status="REVIEW_REQUIRED"
                        label="Review required"
                        tone="warning"
                      />
                    </div>
                    <app-evidence-card
                      [title]="artifactTitle(brief)"
                      [classification]="artifactClassification(brief)"
                      [summary]="artifactSummary(brief)"
                      [source]="artifactSource(brief)"
                      [observedAt]="brief.created_at"
                      [details]="artifactDetails(brief)"
                    />
                    @if (brief.payload['opportunity_id']) {
                      <p class="context-line">
                        <strong>Opportunity:</strong>
                        {{ displayValue(brief.payload['opportunity_id']) }}
                      </p>
                    }
                    @if (brief.payload['trend_intelligence']; as trend) {
                      <div class="intelligence-summary">
                        <h5>Trend Intelligence</h5>
                        <dl>
                          @if (objectValue(trend, 'readiness'); as value) {
                            <div>
                              <dt>Readiness</dt>
                              <dd>{{ displayValue(value) }}</dd>
                            </div>
                          }
                          @if (objectValue(trend, 'confidence'); as value) {
                            <div>
                              <dt>Confidence</dt>
                              <dd>{{ displayValue(value) }}</dd>
                            </div>
                          }
                          @if (objectValue(trend, 'freshness'); as value) {
                            <div>
                              <dt>Freshness</dt>
                              <dd>{{ displayValue(value) }}</dd>
                            </div>
                          }
                          @if (objectValue(trend, 'agreement'); as value) {
                            <div>
                              <dt>Agreement</dt>
                              <dd>{{ displayValue(value) }}</dd>
                            </div>
                          }
                        </dl>
                      </div>
                    }
                    @if (brief.payload['review_intelligence']; as review) {
                      <div class="intelligence-summary">
                        <h5>Customer-feedback evidence</h5>
                        <p>{{ displayValue(objectValue(review, 'label')) }}</p>
                      </div>
                    }
                    @if (brief.payload['sourcing_economics']; as economics) {
                      <div class="intelligence-summary">
                        <h5>Sourcing Economics</h5>
                        <p>Factual landed-cost evidence; human review required.</p>
                        <dl>
                          @if (objectValue(economics, 'readiness'); as value) {
                            <div>
                              <dt>Readiness</dt>
                              <dd>{{ displayValue(value) }}</dd>
                            </div>
                          }
                          @if (objectValue(economics, 'status'); as value) {
                            <div>
                              <dt>Status</dt>
                              <dd>{{ displayValue(value) }}</dd>
                            </div>
                          }
                        </dl>
                      </div>
                    }
                    <p class="quiet">
                      Scores, confidence, risk, readiness, trend, and materiality are shown only
                      when the authoritative artifact supplies them; this view does not recalculate
                      them.
                    </p>
                  </section>
                }

                @if (evidenceArtifacts(run).length) {
                  <section class="evidence-section" aria-labelledby="evidence-title-{{ goal.id }}">
                    <div class="section-heading compact">
                      <div>
                        <p class="eyebrow">Evidence</p>
                        <h4 id="evidence-title-{{ goal.id }}">Supporting evidence</h4>
                      </div>
                    </div>
                    <div class="evidence-grid">
                      @for (artifact of evidenceArtifacts(run); track artifact.id) {
                        <app-evidence-card
                          [title]="artifactTitle(artifact)"
                          [classification]="artifactClassification(artifact)"
                          [summary]="artifactSummary(artifact)"
                          [source]="artifactSource(artifact)"
                          [observedAt]="artifact.created_at"
                          [details]="artifactDetails(artifact)"
                        />
                      }
                    </div>
                  </section>
                }

                @if (run.findings.length) {
                  <section class="findings-section" aria-labelledby="findings-title-{{ goal.id }}">
                    <div class="section-heading compact">
                      <div>
                        <p class="eyebrow">Findings</p>
                        <h4 id="findings-title-{{ goal.id }}">What VAYUJIT found</h4>
                      </div>
                    </div>
                    <div class="finding-list">
                      @for (finding of run.findings; track finding.id) {
                        <article class="finding-card">
                          <div>
                            <strong>{{ findingLabel(finding) }}</strong
                            ><app-status-badge
                              [status]="finding.finding_type"
                              [label]="finding.finding_type"
                              [tone]="statusTone(finding.finding_type)"
                            />
                          </div>
                          <p>{{ findingSummary(finding) }}</p>
                          <small
                            >Confidence supplied by runtime: {{ finding.confidence }} · Evidence
                            references: {{ finding.evidence_ids.length }}</small
                          >
                        </article>
                      }
                    </div>
                  </section>
                }

                @if (researchGaps(run).length) {
                  <section class="callout warning" aria-labelledby="gaps-title-{{ goal.id }}">
                    <strong id="gaps-title-{{ goal.id }}">What we still do not know</strong>
                    <ul>
                      @for (gap of researchGaps(run); track gap) {
                        <li>{{ gap }}</li>
                      }
                    </ul>
                  </section>
                }
                @if (contradictions(run).length) {
                  <section
                    class="callout info"
                    aria-labelledby="contradictions-title-{{ goal.id }}"
                  >
                    <strong id="contradictions-title-{{ goal.id }}">Conflicting evidence</strong>
                    <ul>
                      @for (item of contradictions(run); track item) {
                        <li>{{ item }}</li>
                      }
                    </ul>
                  </section>
                }
              }
            </article>
          }
        </div>
        @if (previousGoals().length) {
          <details class="previous-research technical-details">
            <summary>Previous research ({{ previousGoals().length }})</summary>
            <div class="previous-goal-list">
              @for (goal of previousGoals(); track goal.id) {
                <article class="previous-goal">
                  <div>
                    <strong>{{ goal.raw_goal }}</strong>
                    <small>Created {{ goal.created_at }}</small>
                  </div>
                  <app-status-badge
                    [status]="goal.status"
                    [label]="statusLabel(goal.status)"
                    [tone]="statusTone(goal.status)"
                  />
                </article>
              }
            </div>
          </details>
        }
      </section>
    </main>
  `,
})
export class BusinessAgentWorkspaceComponent implements OnInit {
  private readonly service = inject(BusinessAgentService);
  readonly goals = signal<BusinessAgentGoal[]>([]);
  readonly capabilities = signal<BusinessAgentCapability[]>([]);
  readonly plans = signal<Record<string, BusinessAgentPlan>>({});
  readonly runs = signal<Record<string, BusinessAgentRun>>({});
  readonly loading = signal(false);
  readonly error = signal('');
  rawGoal = '';
  marketplaceContext = '';
  idempotencyKey = `business-goal-${Date.now()}`;
  includeCompetitorIntelligence = false;
  includeReviewIntelligence = false;
  includeTrendIntelligence = false;
  decisionNote = '';
  selectedGoalId = '';

  ngOnInit(): void {
    void this.refresh();
  }

  async refresh(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      this.goals.set(await this.service.goals());
      this.capabilities.set(await this.service.capabilities());
    } catch {
      this.error.set('Business Agent data is unavailable. Check the authenticated API connection.');
    } finally {
      this.loading.set(false);
    }
  }

  async create(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    const structured: Record<string, unknown> = {};
    if (this.marketplaceContext.trim()) structured['marketplace'] = this.marketplaceContext.trim();
    if (this.includeCompetitorIntelligence) structured['include_competitor_intelligence'] = true;
    if (this.includeReviewIntelligence) structured['include_review_intelligence'] = true;
    try {
      const goal = await this.service.createGoal({
        raw_goal: this.rawGoal,
        idempotency_key: this.idempotencyKey,
        ...(Object.keys(structured).length ? { structured_goal: structured } : {}),
        ...(this.includeTrendIntelligence ? { include_trend_intelligence: true } : {}),
      });
      this.selectedGoalId = goal.id;
      this.idempotencyKey = `business-goal-${Date.now()}`;
      await this.refresh();
    } catch {
      this.error.set('The business goal could not be created.');
      this.loading.set(false);
    }
  }

  async makePlan(goal: BusinessAgentGoal): Promise<void> {
    this.selectedGoalId = goal.id;
    this.loading.set(true);
    this.error.set('');
    try {
      const value = await this.service.plan(goal.id);
      this.plans.update((plans) => ({ ...plans, [goal.id]: value }));
    } catch {
      this.error.set('The authoritative research plan could not be created.');
    } finally {
      this.loading.set(false);
    }
  }

  async run(goal: BusinessAgentGoal, plan: BusinessAgentPlan): Promise<void> {
    this.selectedGoalId = goal.id;
    this.loading.set(true);
    this.error.set('');
    try {
      const created = await this.service.createRun(goal.id, {
        idempotency_key: `${this.idempotencyKey}-${goal.id}`,
        max_steps: plan.steps.length,
      });
      const value = await this.service.start(created.id);
      this.runs.update((runs) => ({ ...runs, [goal.id]: value }));
    } catch {
      this.error.set('The Business Agent run could not be started.');
    } finally {
      this.loading.set(false);
    }
  }

  async refreshRun(run: BusinessAgentRun): Promise<void> {
    await this.runAction(run, (id) => this.service.run(id));
  }

  async pause(run: BusinessAgentRun): Promise<void> {
    await this.runAction(run, (id) => this.service.pause(id));
  }

  async resume(run: BusinessAgentRun): Promise<void> {
    await this.runAction(run, (id) => this.service.resume(id));
  }

  async retry(run: BusinessAgentRun): Promise<void> {
    await this.runAction(run, (id) => this.service.retry(id));
  }

  async cancel(run: BusinessAgentRun): Promise<void> {
    if (
      !globalThis.confirm('Cancel this Business Agent run? Completed evidence remains inspectable.')
    )
      return;
    await this.runAction(run, (id) => this.service.cancel(id));
  }

  async approve(run: BusinessAgentRun, approval: { id: string }): Promise<void> {
    await this.decision(run, () => this.service.approve(approval.id, this.decisionNote));
  }

  async reject(run: BusinessAgentRun, approval: { id: string }): Promise<void> {
    if (!globalThis.confirm('Reject this approval and stop the run?')) return;
    await this.decision(run, () => this.service.reject(approval.id, this.decisionNote));
  }

  private async decision(run: BusinessAgentRun, action: () => Promise<unknown>): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      await action();
      this.decisionNote = '';
      await this.refreshRun(run);
    } catch {
      this.error.set('The approval decision could not be completed.');
    } finally {
      this.loading.set(false);
    }
  }

  private async runAction(
    run: BusinessAgentRun,
    action: (id: string) => Promise<BusinessAgentRun>,
  ): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const value = await action(run.id);
      this.runs.update((runs) => ({ ...runs, [run.goal_id]: value }));
    } catch {
      this.error.set('The Business Agent run action could not be completed.');
    } finally {
      this.loading.set(false);
    }
  }

  activeGoals(): BusinessAgentGoal[] {
    return this.goals().slice(0, 1);
  }

  previousGoals(): BusinessAgentGoal[] {
    return this.goals().slice(1);
  }

  constraintRows(goal: BusinessAgentGoal): Array<{
    label: string;
    value: string;
    state: string;
  }> {
    const structured = goal.structured_goal;
    const rows: Array<{ label: string; value: string; state: string }> = [];
    const marketplace = this.displayValue(structured['marketplace']);
    if (marketplace)
      rows.push({ label: 'Marketplace', value: marketplace, state: 'Provided by you' });
    const market = this.displayValue(structured['market']);
    if (market) rows.push({ label: 'Market', value: market, state: 'Provided by you' });
    const category = this.displayValue(structured['category']);
    if (category) rows.push({ label: 'Category', value: category, state: 'Provided by you' });
    if (goal.unresolved_questions.length) {
      rows.push({
        label: 'Open questions',
        value: String(goal.unresolved_questions.length),
        state: 'Needs your input',
      });
    }
    if (goal.assumptions.length && !goal.unresolved_questions.length) {
      rows.push({
        label: 'Runtime assumptions',
        value: String(goal.assumptions.length),
        state: 'Proposed by VAYUJIT',
      });
    }
    if (!rows.length) rows.push({ label: 'Constraints', value: 'Not specified', state: 'Unknown' });
    return rows;
  }

  businessRunStatus(run: BusinessAgentRun): string {
    const current = this.currentStep(run);
    if (run.result['outcome'] === 'RESEARCH_COMPLETED_WITH_GAPS') {
      return 'Research completed, but some important evidence is still missing.';
    }
    if (run.status === 'COMPLETED') return 'Research is complete and ready for review.';
    if (run.status === 'WAITING_APPROVAL')
      return 'Research is ready for your review before any consequential action.';
    if (run.status === 'FAILED') return 'Research needs attention before it can continue.';
    if (current) {
      return (
        'VAYUJIT is ' +
        (current.business_label || this.capabilityLabel(current.capability_id)).toLowerCase() +
        '.'
      );
    }
    return 'VAYUJIT is preparing evidence for your goal.';
  }

  capabilityLabel(id: string): string {
    if (CAPABILITY_LABELS[id]) return CAPABILITY_LABELS[id];
    return id
      .split(/[._-]+/)
      .filter(Boolean)
      .map((part) => part.charAt(0) + part.slice(1).toLowerCase())
      .join(' ');
  }

  dependencyLabels(keys: string[], plan: BusinessAgentPlan): string {
    return keys
      .map((key) => {
        const step = plan.steps.find((item) => item.key === key);
        return step ? this.capabilityLabel(step.capability_id) : key;
      })
      .join(', ');
  }

  statusLabel(status: string): string {
    const labels: Record<string, string> = {
      RESEARCH_COMPLETED_WITH_GAPS: 'Research completed with gaps',
      PROVIDER_UNAVAILABLE: 'Research source unavailable',
      LOCAL_DETERMINISTIC: 'Local demo mode',
      WAITING_APPROVAL: 'Needs your review',
      REVIEW_REQUIRED: 'Needs your review',
      IN_PROGRESS: 'In progress',
      NOT_STARTED: 'Not started',
    };
    if (labels[status]) return labels[status];
    return status
      .replaceAll('_', ' ')
      .toLowerCase()
      .replace(/(^| )\w/g, (value) => value.toUpperCase());
  }

  statusTone(status: string): StatusTone {
    const normalized = status.toUpperCase();
    if (['COMPLETED', 'SUCCEEDED', 'APPROVED', 'DONE'].includes(normalized)) return 'success';
    if (['FAILED', 'CANCELLED', 'REJECTED', 'ERROR'].includes(normalized)) return 'danger';
    if (['WAITING_APPROVAL', 'WAITING', 'PAUSED', 'RETRYABLE'].includes(normalized))
      return 'warning';
    if (['RUNNING', 'QUEUED', 'READY', 'PENDING', 'DRAFT'].includes(normalized)) return 'info';
    return 'neutral';
  }

  currentStep(run: BusinessAgentRun): BusinessAgentRunStep | undefined {
    return (
      run.steps.find((step) =>
        ['RUNNING', 'WAITING', 'WAITING_APPROVAL', 'READY'].includes(step.status),
      ) ??
      run.steps.find(
        (step) => !['COMPLETED', 'SUCCEEDED', 'DONE', 'CANCELLED'].includes(step.status),
      )
    );
  }

  completedStepCount(run: BusinessAgentRun): number {
    return run.steps.filter((step) => ['COMPLETED', 'SUCCEEDED', 'DONE'].includes(step.status))
      .length;
  }

  pendingApproval(run: BusinessAgentRun): BusinessAgentRun['approvals'][number] | undefined {
    return run.approvals.find((approval) => approval.status === 'PENDING');
  }

  canPause(run: BusinessAgentRun): boolean {
    return ['QUEUED', 'RUNNING'].includes(run.status);
  }

  canResume(run: BusinessAgentRun): boolean {
    return !['CANCELLED', 'COMPLETED', 'WAITING_APPROVAL'].includes(run.status);
  }

  canCancel(run: BusinessAgentRun): boolean {
    return !['CANCELLED', 'COMPLETED', 'WAITING_APPROVAL'].includes(run.status);
  }

  canRetry(run: BusinessAgentRun): boolean {
    return !['COMPLETED', 'WAITING_APPROVAL'].includes(run.status);
  }

  decisionBrief(run: BusinessAgentRun): BusinessAgentArtifact | undefined {
    return run.artifacts.find((artifact) => artifact.artifact_type === 'BUSINESS_DECISION_BRIEF');
  }

  evidenceArtifacts(run: BusinessAgentRun): BusinessAgentArtifact[] {
    return run.artifacts.filter((artifact) => artifact.artifact_type !== 'BUSINESS_DECISION_BRIEF');
  }

  artifactTitle(artifact: BusinessAgentArtifact): string {
    return (
      this.displayValue(artifact.payload['title']) || this.capabilityLabel(artifact.artifact_type)
    );
  }

  artifactClassification(artifact: BusinessAgentArtifact): string {
    return this.displayValue(artifact.payload['classification']) || artifact.artifact_type;
  }

  artifactSummary(artifact: BusinessAgentArtifact): string {
    return (
      this.displayValue(artifact.payload['summary']) ||
      'Authoritative evidence reference recorded by the Business Agent.'
    );
  }

  artifactSource(artifact: BusinessAgentArtifact): string {
    return (
      this.displayValue(artifact.provenance['source']) ||
      this.displayValue(artifact.provenance['provider'])
    );
  }

  artifactDetails(artifact: BusinessAgentArtifact): EvidenceDetail[] {
    return [
      { label: 'Artifact ID', value: artifact.id },
      { label: 'Provider mode', value: this.displayValue(artifact.provenance['provider']) || null },
      { label: 'Context', value: this.displayValue(artifact.payload['context_id']) || null },
      { label: 'Snapshot', value: this.displayValue(artifact.payload['snapshot_id']) || null },
    ].filter((detail) => detail.value !== null && detail.value !== '');
  }

  findingLabel(finding: BusinessAgentFinding): string {
    return this.capabilityLabel(finding.finding_type);
  }

  findingSummary(finding: BusinessAgentFinding): string {
    return (
      this.displayValue(finding.value['summary']) ||
      this.displayValue(finding.value['status']) ||
      'Authoritative finding recorded.'
    );
  }

  researchGaps(run: BusinessAgentRun): string[] {
    const values: unknown[] = [
      run.result['trend_evidence_gaps'],
      run.result['review_evidence_gaps'],
    ];
    for (const artifact of run.artifacts)
      values.push(artifact.payload['research_gaps'], artifact.payload['evidence_gaps']);
    return this.listValues(
      values.flatMap((value): unknown[] => (Array.isArray(value) ? (value as unknown[]) : [])),
    );
  }

  contradictions(run: BusinessAgentRun): string[] {
    const values: unknown[] = [];
    for (const artifact of run.artifacts) {
      const contradictions = artifact.payload['contradictions'];
      if (Array.isArray(contradictions)) values.push(...(contradictions as unknown[]));
    }
    return this.listValues(values);
  }
  objectValue(value: unknown, key: string): unknown {
    return typeof value === 'object' && value !== null && key in value
      ? (value as Record<string, unknown>)[key]
      : null;
  }

  displayValue(value: unknown): string {
    if (typeof value === 'string' || typeof value === 'number') return String(value);
    return '';
  }

  private listValues(values: unknown[]): string[] {
    return values
      .map((value) => {
        if (typeof value === 'string') return value;
        if (typeof value === 'object' && value !== null) {
          for (const key of ['message', 'reason', 'label', 'description', 'code']) {
            const candidate = (value as Record<string, unknown>)[key];
            if (typeof candidate === 'string') return candidate;
          }
        }
        return '';
      })
      .filter(Boolean);
  }
}
