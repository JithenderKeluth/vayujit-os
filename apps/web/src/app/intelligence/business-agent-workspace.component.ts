import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import {
  BusinessAgentCapability,
  BusinessAgentGoal,
  BusinessAgentPlan,
  BusinessAgentRun,
  BusinessAgentService,
} from './business-agent.service';

@Component({
  selector: 'app-business-agent-workspace',
  standalone: true,
  imports: [FormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="workspace" aria-labelledby="business-agent-title">
      <header class="page-header">
        <div>
          <p class="eyebrow">Intelligence / Business AI</p>
          <h1 id="business-agent-title">Business Agent orchestration</h1>
          <p class="lede">Evidence-first plans with bounded, reviewable execution.</p>
        </div>
        <a routerLink="/intelligence">Back to Intelligence</a>
      </header>
      <p class="notice">
        Local deterministic mode. No external writes, spend, messages, or provider credentials are
        used.
      </p>
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }
      <section class="panel" aria-labelledby="goal-title">
        <h2 id="goal-title">Describe a business goal</h2>
        <form (ngSubmit)="create()">
          <label
            >Goal <textarea name="goal" [(ngModel)]="rawGoal" required minlength="5"></textarea>
          </label>
          <label>Idempotency key <input name="key" [(ngModel)]="idempotencyKey" required /></label>
          <label>
            <input type="checkbox" name="competitor" [(ngModel)]="includeCompetitorIntelligence" />
            Include competitor intelligence in the bounded run
          </label>
          <button type="submit" [disabled]="loading() || !rawGoal.trim()">Create goal</button>
        </form>
      </section>
      <section class="panel" aria-labelledby="goals-title">
        <h2 id="goals-title">Goals and plans</h2>
        @for (goal of goals(); track goal.id) {
          <article class="list-item">
            <strong>{{ goal.raw_goal }}</strong>
            <span
              >Status: {{ goal.status }} · Marketplace:
              {{ goal.structured_goal.marketplace || 'unresolved' }}</span
            >
            <div class="actions">
              <button type="button" (click)="makePlan(goal)" [disabled]="loading()">
                Create versioned plan
              </button>
              @if (plans()[goal.id]; as plan) {
                <button type="button" (click)="run(goal, plan)" [disabled]="loading()">
                  Run locally
                </button>
                <small>Plan v{{ plan.version }} · {{ plan.steps.length }} bounded steps</small>
              }
            </div>
            @if (runs()[goal.id]; as run) {
              <p role="status">
                Run {{ run.status }} · {{ run.result?.decision || 'checkpointed' }}
              </p>
              @if (run.result?.integrated_slices?.length) {
                <small>Integrated slices: {{ integratedSlices(run) }}</small>
              }
              @if (run.artifacts?.length) {
                <small
                  >Review artifacts: {{ artifactCount(run) }}; Findings:
                  {{ findingCount(run) }}</small
                >
              }
            }
          </article>
        } @empty {
          <p>No business goals yet.</p>
        }
      </section>
      <section class="panel" aria-labelledby="capabilities-title">
        <h2 id="capabilities-title">Capability safety</h2>
        @for (capability of capabilities(); track capability.id) {
          <p>
            <strong>{{ capability.id }}</strong> · {{ capability.execution_class }} · side effect:
            {{ capability.side_effect_class }} · {{ capability.availability }}
          </p>
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
  rawGoal = 'Find three winning products for Amazon India within INR 300000 capital.';
  idempotencyKey = `business-goal-${Date.now()}`;
  includeCompetitorIntelligence = false;

  integratedSlices(run: BusinessAgentRun): string {
    return run.result?.integrated_slices?.join(', ') || '';
  }

  artifactCount(run: BusinessAgentRun): number {
    return run.artifacts?.length || 0;
  }

  findingCount(run: BusinessAgentRun): number {
    return run.findings?.length || 0;
  }

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
    try {
      await this.service.createGoal({
        raw_goal: this.rawGoal,
        idempotency_key: this.idempotencyKey,
        structured_goal: this.includeCompetitorIntelligence
          ? { marketplace: 'AMAZON_IN', include_competitor_intelligence: true }
          : undefined,
      });
      await this.refresh();
    } catch {
      this.error.set('The business goal could not be created.');
      this.loading.set(false);
    }
  }

  async makePlan(goal: BusinessAgentGoal): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const value = await this.service.plan(goal.id);
      this.plans.update((plans) => ({ ...plans, [goal.id]: value }));
    } catch {
      this.error.set('The bounded plan could not be created.');
    } finally {
      this.loading.set(false);
    }
  }

  async run(goal: BusinessAgentGoal, plan: BusinessAgentPlan): Promise<void> {
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
      this.error.set('The local agent run could not be started.');
    } finally {
      this.loading.set(false);
    }
  }
}
