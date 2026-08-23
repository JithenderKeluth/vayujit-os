import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  IntelligenceOpportunity,
  IntelligenceOverview,
  IntelligenceProject,
  IntelligenceService,
  IntelligenceSource,
} from './intelligence.service';

@Component({
  selector: 'app-intelligence-workspace',
  imports: [RouterLink],
  template: `
    <main class="intelligence-page" aria-labelledby="intelligence-title">
      <header class="page-header">
        <div>
          <p class="eyebrow">Product Research &amp; Supplier Intelligence</p>
          <h1 id="intelligence-title">Intelligence foundation</h1>
          <p class="lede">Evidence-first research with deterministic rules and human review.</p>
        </div>
        <a routerLink="/dashboard" class="secondary-button">Back to dashboard</a>
      </header>

      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }
      @if (loading()) {
        <p class="loading" aria-live="polite">Loading Intelligence foundation…</p>
      } @else {
        <section class="metric-grid" aria-label="Intelligence overview">
          <article class="metric">
            <span>Active projects</span><strong>{{ overview()?.active_projects ?? 0 }}</strong>
          </article>
          <article class="metric">
            <span>Research runs</span><strong>{{ overview()?.recent_runs ?? 0 }}</strong>
          </article>
          <article class="metric">
            <span>Review candidates</span
            ><strong>{{ overview()?.opportunities?.['review'] ?? 0 }}</strong>
          </article>
          <article class="metric">
            <span>Fresh evidence</span
            ><strong>{{ overview()?.evidence_freshness?.['fresh'] ?? 0 }}</strong>
          </article>
          <article class="metric">
            <span>Enabled sources</span><strong>{{ overview()?.enabled_sources ?? 0 }}</strong>
          </article>
          <article class="metric">
            <span>Hard blocks</span><strong>{{ overview()?.hard_blocked_candidates ?? 0 }}</strong>
          </article>
        </section>

        <nav class="workspace-tabs" aria-label="Intelligence sections">
          <a href="#research">Research</a><a href="#opportunities">Opportunities</a
          ><a href="#sources">Sources</a><a href="#rules">Rules</a>
        </nav>

        <section id="research" class="panel">
          <div class="panel-heading">
            <div>
              <h2>Research projects</h2>
              <p>Owner-scoped projects; archival preserves history.</p>
            </div>
            <button type="button" (click)="createDemoProject()">Create foundation project</button>
          </div>
          @if (projects().length === 0) {
            <p class="empty">No research projects yet. Create a foundation project to begin.</p>
          }
          <div class="rows">
            @for (project of projects(); track project.id) {
              <div class="row">
                <strong>{{ project.name }}</strong
                ><span>{{ project.status }}</span
                ><span>{{ project.target_market || 'Market not set' }}</span>
              </div>
            }
          </div>
        </section>

        <section id="opportunities" class="panel">
          <div class="panel-heading">
            <div>
              <h2>Opportunities</h2>
              <p>Facts, rule results, and AI interpretation remain separate.</p>
            </div>
          </div>
          @if (opportunities().length === 0) {
            <p class="empty">No opportunities discovered yet.</p>
          }
          <div class="rows">
            @for (item of opportunities(); track item.id) {
              <div class="row">
                <strong>{{ item.title }}</strong
                ><span>{{ item.status }}</span
                ><span>Score {{ item.score }}</span
                ><span>{{ item.hard_blocked ? 'Hard blocked' : 'Eligible for review' }}</span>
              </div>
            }
          </div>
        </section>

        <section id="sources" class="panel">
          <div class="panel-heading">
            <div>
              <h2>Sources</h2>
              <p>External research is disabled by default; manual evidence remains supported.</p>
            </div>
          </div>
          @if (sources().length === 0) {
            <p class="empty">No sources registered yet.</p>
          }
          <div class="rows">
            @for (source of sources(); track source.id) {
              <div class="row">
                <strong>{{ source.display_name }}</strong
                ><span>{{ source.source_type }}</span
                ><span>{{ source.access_method }}</span
                ><span>{{ source.enabled ? 'Enabled' : 'Disabled' }}</span>
              </div>
            }
          </div>
        </section>

        <section id="rules" class="panel">
          <div class="panel-heading">
            <div>
              <h2>Rules</h2>
              <p>
                Physical, logistics, safety, regulatory, economics, market, competition, supplier,
                and risk categories are versioned independently.
              </p>
            </div>
          </div>
          <p class="empty">
            Configure deterministic rule categories through the API. No autonomous decisions are
            enabled.
          </p>
        </section>
      }
    </main>
  `,
  styles: [
    `
      :host {
        display: block;
        color: #102a31;
      }
      .intelligence-page {
        max-width: 1180px;
        margin: 0 auto;
        padding: 48px 32px 80px;
      }
      .page-header {
        display: flex;
        justify-content: space-between;
        gap: 24px;
        align-items: flex-start;
      }
      .eyebrow {
        color: #17647a;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }
      .lede {
        color: #4e6670;
        font-size: 1.1rem;
      }
      .secondary-button,
      button {
        border: 1px solid #17647a;
        border-radius: 8px;
        padding: 11px 16px;
        background: #17647a;
        color: #fff;
        text-decoration: none;
        font: inherit;
        cursor: pointer;
      }
      .secondary-button {
        background: #fff;
        color: #17647a;
      }
      h1 {
        font-size: 2.4rem;
        margin: 0.2rem 0;
      }
      h2 {
        margin: 0 0 4px;
      }
      .metric-grid {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 14px;
        margin: 34px 0;
      }
      .metric,
      .panel {
        border: 1px solid #cbd9de;
        border-radius: 12px;
        background: #fff;
      }
      .metric {
        padding: 18px;
        min-height: 76px;
      }
      .metric span {
        display: block;
        color: #5d747c;
        font-size: 0.85rem;
      }
      .metric strong {
        display: block;
        font-size: 1.7rem;
        margin-top: 8px;
      }
      .workspace-tabs {
        display: flex;
        gap: 20px;
        border-bottom: 1px solid #cbd9de;
        padding-bottom: 12px;
        margin-bottom: 22px;
      }
      .workspace-tabs a {
        color: #17647a;
        font-weight: 700;
      }
      .panel {
        padding: 24px;
        margin: 18px 0;
      }
      .panel-heading {
        display: flex;
        justify-content: space-between;
        gap: 20px;
        align-items: flex-start;
      }
      .panel-heading p {
        margin-top: 0;
        color: #5d747c;
      }
      .rows {
        margin-top: 18px;
      }
      .row {
        display: grid;
        grid-template-columns: 2fr 1fr 1.5fr 1.5fr;
        gap: 12px;
        padding: 13px 0;
        border-top: 1px solid #e2eaed;
      }
      .empty,
      .loading {
        color: #5d747c;
      }
      .error {
        padding: 14px;
        border-left: 4px solid #a32626;
        background: #fff0f0;
        color: #8a1c1c;
      }
      @media (max-width: 900px) {
        .metric-grid {
          grid-template-columns: repeat(2, 1fr);
        }
        .page-header,
        .panel-heading {
          flex-direction: column;
        }
        .row {
          grid-template-columns: 1fr 1fr;
        }
      }
    `,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class IntelligenceWorkspaceComponent {
  private readonly service = inject(IntelligenceService);
  readonly overview = signal<IntelligenceOverview | null>(null);
  readonly projects = signal<IntelligenceProject[]>([]);
  readonly sources = signal<IntelligenceSource[]>([]);
  readonly opportunities = signal<IntelligenceOpportunity[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');

  constructor() {
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const [overview, projects, sources, opportunities] = await Promise.all([
        this.service.overview(),
        this.service.projects(),
        this.service.sources(),
        this.service.opportunities(),
      ]);
      this.overview.set(overview);
      this.projects.set(projects);
      this.sources.set(sources);
      this.opportunities.set(opportunities);
    } catch {
      this.error.set('Intelligence data is unavailable. Check the authenticated API connection.');
    } finally {
      this.loading.set(false);
    }
  }

  async createDemoProject(): Promise<void> {
    try {
      await this.service.createProject({
        name: `Research project ${new Date().toISOString().slice(0, 10)}`,
        description: 'Foundation project; configure sources and rules before execution.',
        target_market: '',
      });
      await this.load();
    } catch {
      this.error.set('The research project could not be created.');
    }
  }
}
