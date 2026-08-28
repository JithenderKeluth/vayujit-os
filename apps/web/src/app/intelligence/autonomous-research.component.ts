import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import {
  AutonomousResearchOverview,
  ExternalResearchPolicy,
  IntelligenceService,
} from './intelligence.service';

@Component({
  selector: 'app-autonomous-research',
  imports: [RouterLink, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="autonomous-page" aria-labelledby="autonomous-title">
      <header class="page-header">
        <div>
          <p class="eyebrow">Slice 5 · controlled research runtime</p>
          <h1 id="autonomous-title">Autonomous research</h1>
          <p class="lede">Durable evidence-first missions with a deterministic local provider.</p>
        </div>
        <a routerLink="/intelligence" class="secondary-button">Back to intelligence</a>
      </header>
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }
      <section class="panel" aria-labelledby="policy-title">
        <h2 id="policy-title">Safety policy</h2>
        <p>
          <strong>Provider:</strong>
          {{ policy()['default_provider_mode'] || 'LOCAL_DETERMINISTIC' }}
        </p>
        <p>
          <strong>External research:</strong>
          {{
            policy()['external_research_enabled']
              ? 'Enabled by configuration'
              : 'Disabled by default'
          }}
        </p>
        <p class="hint">
          Untrusted sources never execute instructions or mutate products, suppliers, campaigns, or
          publishing.
        </p>
      </section>
      <section class="panel" aria-labelledby="external-title">
        <div class="panel-heading">
          <h2 id="external-title">External research</h2>
          <span class="status" role="status">{{ external()?.status || 'DISABLED' }}</span>
        </div>
        <p>
          Provider <strong>{{ external()?.provider || 'deterministic' }}</strong> · Mode
          <strong>{{ external()?.mode || 'DISABLED' }}</strong>
        </p>
        <p class="hint">
          Read-only, allowlisted, bounded, and untrusted by design. Search snippets are discovery
          results, not verified evidence.
        </p>
        <form class="form-grid" (submit)="$event.preventDefault(); searchExternal()">
          <label
            >Search query
            <input name="external-query" required maxlength="500" [(ngModel)]="externalQuery"
          /></label>
          <button type="submit" [disabled]="busy() || externalQuery.trim().length < 1">
            Search approved provider
          </button>
        </form>
        @if (externalResults().length) {
          <div class="external-results" aria-label="External search results">
            @for (result of externalResults(); track result['url']) {
              <article class="row">
                <div>
                  <strong>{{ result['title'] }}</strong
                  ><small>{{ result['domain'] }}</small>
                </div>
                <span>{{ result['snippet'] }}</span
                ><span>{{ result['provider'] }} · rank {{ result['rank'] }}</span>
                <a [href]="result['url']" target="_blank" rel="noreferrer">Open source</a>
              </article>
            }
          </div>
        }
      </section>
      <section class="metric-grid" aria-label="Autonomous research overview">
        <article class="metric">
          <span>Active missions</span><strong>{{ overview()?.active_missions ?? 0 }}</strong>
        </article>
        <article class="metric">
          <span>Queued tasks</span><strong>{{ overview()?.queued_tasks ?? 0 }}</strong>
        </article>
        <article class="metric">
          <span>Completed</span><strong>{{ overview()?.completed_missions ?? 0 }}</strong>
        </article>
        <article class="metric">
          <span>Contradictions</span><strong>{{ overview()?.contradictions ?? 0 }}</strong>
        </article>
        <article class="metric">
          <span>Recovery records</span><strong>{{ overview()?.recovery ?? 0 }}</strong>
        </article>
        <article class="metric">
          <span>AI mode</span><strong>{{ overview()?.ai_mode || 'LOCAL_DETERMINISTIC' }}</strong>
        </article>
      </section>
      <section class="panel" aria-labelledby="mission-create-title">
        <h2 id="mission-create-title">Start a bounded mission</h2>
        <form class="form-grid" (submit)="$event.preventDefault(); createMission()">
          <label
            >Mission type
            <select name="mission-type" [(ngModel)]="draft.mission_type">
              @for (type of missionTypes; track type) {
                <option [value]="type">{{ type }}</option>
              }
            </select>
          </label>
          <label>Goal <input name="goal" required minlength="3" [(ngModel)]="draft.goal" /></label>
          <label>Market <input name="market" [(ngModel)]="draft.market" /></label>
          <label>Category <input name="category" [(ngModel)]="draft.category" /></label>
          <button type="submit" [disabled]="busy()">
            {{ busy() ? 'Starting…' : 'Create mission' }}
          </button>
        </form>
      </section>
      <section class="panel" aria-labelledby="missions-title">
        <div class="panel-heading">
          <h2 id="missions-title">Mission history</h2>
          <button type="button" (click)="load()" [disabled]="busy()">Refresh</button>
        </div>
        @if (missions().length === 0) {
          <p class="empty">No autonomous missions yet.</p>
        }
        @for (mission of missions(); track mission['id']) {
          <article class="row">
            <strong>{{ mission['mission_type'] }}</strong
            ><span>{{ mission['goal'] }}</span
            ><span>{{ mission['status'] }}</span>
            <button
              type="button"
              (click)="runMission(String(mission['id']))"
              [disabled]="busy() || mission['status'] === 'RUNNING'"
            >
              Run local fixture
            </button>
          </article>
        }
      </section>
    </main>
  `,
  styles: `
    :host {
      display: block;
      color: #092b36;
    }
    .autonomous-page {
      max-width: 1180px;
      margin: auto;
      padding: 2rem;
    }
    .page-header,
    .panel-heading {
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      align-items: flex-start;
    }
    .panel {
      border: 1px solid #c9dbe0;
      border-radius: 1rem;
      padding: 1.25rem;
      margin: 1rem 0;
      background: #fff;
    }
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 1rem;
      margin: 1rem 0;
    }
    .metric {
      border: 1px solid #c9dbe0;
      border-radius: 0.75rem;
      padding: 1rem;
      background: #f8fbfc;
    }
    .metric span {
      display: block;
      color: #466a75;
    }
    .metric strong {
      display: block;
      margin-top: 0.5rem;
      font-size: 1.4rem;
    }
    .form-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 1rem;
      align-items: end;
    }
    label {
      display: grid;
      gap: 0.35rem;
    }
    input,
    select,
    button {
      min-height: 2.5rem;
      border: 1px solid #8aacb5;
      border-radius: 0.45rem;
      padding: 0.45rem 0.65rem;
      font: inherit;
    }
    button {
      background: #145c73;
      color: #fff;
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.55;
      cursor: wait;
    }
    .row {
      display: grid;
      grid-template-columns: 1.1fr 2fr 1fr auto;
      gap: 1rem;
      align-items: center;
      border-top: 1px solid #d9e6e9;
      padding: 0.8rem 0;
    }
    .error {
      color: #9b1c31;
      background: #fff0f1;
      padding: 1rem;
    }
    .hint,
    .empty {
      color: #466a75;
    }
    @media (max-width: 700px) {
      .autonomous-page {
        padding: 1rem;
      }
      .page-header,
      .panel-heading,
      .row {
        display: grid;
        grid-template-columns: 1fr;
      }
    }
  `,
})
export class AutonomousResearchComponent {
  private readonly service = inject(IntelligenceService);
  readonly overview = signal<AutonomousResearchOverview | null>(null);
  readonly policy = signal<Record<string, unknown>>({});
  readonly external = signal<ExternalResearchPolicy | null>(null);
  readonly externalResults = signal<Record<string, unknown>[]>([]);
  externalQuery = '';
  readonly missions = signal<Record<string, unknown>[]>([]);
  readonly error = signal('');
  readonly busy = signal(false);
  readonly missionTypes = [
    'PRODUCT_DISCOVERY',
    'PRODUCT_VALIDATION',
    'TREND_RESEARCH',
    'COMPETITOR_RESEARCH',
    'REVIEW_RESEARCH',
    'SUPPLIER_DISCOVERY',
    'SUPPLIER_VERIFICATION',
    'PRICING_RESEARCH',
    'ECONOMICS_RESEARCH',
    'RISK_RESEARCH',
    'SOURCE_REFRESH',
    'FULL_OPPORTUNITY_RESEARCH',
  ];
  readonly draft = {
    mission_type: 'PRODUCT_DISCOVERY',
    goal: 'Evaluate a local fixture opportunity',
    market: 'IN',
    category: 'home',
  };
  constructor() {
    void this.load();
  }
  async load(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      const [overview, policy, missions] = await Promise.all([
        this.service.autonomousOverview(),
        this.service.autonomousPolicy(),
        this.service.autonomousMissions(),
      ]);
      this.overview.set(overview);
      this.policy.set(policy);
      this.missions.set(missions);
      this.external.set({
        provider: 'deterministic',
        mode: 'DISABLED',
        status: 'DISABLED',
        search_enabled: false,
        fetch_enabled: false,
        kill_switch: false,
        provider_kill_switch: false,
        approved_domains_configured: false,
        credentials_configured: false,
      });
    } catch {
      this.error.set(
        'Autonomous research data is unavailable. Check the authenticated API connection.',
      );
    } finally {
      this.busy.set(false);
    }
  }
  async searchExternal(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      const response = await this.service.externalSearch({
        query: this.externalQuery,
        max_results: 10,
        safe_search: true,
      });
      this.externalResults.set((response['results'] as Record<string, unknown>[]) || []);
    } catch {
      this.error.set('External research is disabled or unavailable.');
    } finally {
      this.busy.set(false);
    }
  }
  async createMission(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      await this.service.createAutonomousMission({
        ...this.draft,
        idempotency_key: `web-${Date.now()}`,
        provider_mode: 'LOCAL_DETERMINISTIC',
      });
      await this.load();
    } catch {
      this.error.set('The mission could not be created safely.');
      this.busy.set(false);
    }
  }
  async runMission(id: string): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      await this.service.runAutonomousMission(id);
      await this.load();
    } catch {
      this.error.set('The mission could not be run safely.');
      this.busy.set(false);
    }
  }
  protected readonly String = String;
}
