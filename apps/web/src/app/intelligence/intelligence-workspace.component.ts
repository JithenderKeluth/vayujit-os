import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { JsonPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import {
  IntelligenceCandidate,
  IntelligenceMission,
  IntelligenceOpportunity,
  IntelligenceOverview,
  IntelligenceProject,
  IntelligenceService,
  IntelligenceSource,
  IntelligenceHistory,
  IntelligenceMissionRun,
  IntelligenceProfile,
  IntelligenceRule,
  IntelligenceEvidence,
  IntelligenceReport,
} from './intelligence.service';

@Component({
  selector: 'app-intelligence-workspace',
  imports: [RouterLink, FormsModule, JsonPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: ` <main class="intelligence-page" aria-labelledby="intelligence-title">
    <header class="page-header">
      <div>
        <p class="eyebrow">Product Research &amp; Supplier Intelligence</p>
        <h1 id="intelligence-title">Winning product research</h1>
        <p class="lede">Evidence-first deterministic research with human review.</p>
      </div>
      <a routerLink="/dashboard" class="secondary-button">Back to dashboard</a>
    </header>
    @if (error()) {
      <p class="error" role="alert">{{ error() }}</p>
    }
    @if (loading()) {
      <p class="loading" aria-live="polite">Loading intelligence...</p>
    } @else {
      <section id="overview" class="metric-grid" aria-label="Intelligence overview">
        <article class="metric">
          <span>Active missions</span><strong>{{ overview()?.active_projects ?? 0 }}</strong>
        </article>
        <article class="metric">
          <span>Recent runs</span><strong>{{ overview()?.recent_runs ?? 0 }}</strong>
        </article>
        <article class="metric">
          <span>Candidates</span><strong>{{ candidates().length }}</strong>
        </article>
        <article class="metric">
          <span>Strong opportunities</span
          ><strong>{{ overview()?.opportunities?.['strong'] ?? 0 }}</strong>
        </article>
        <article class="metric">
          <span>Promising opportunities</span
          ><strong>{{ overview()?.opportunities?.['promising'] ?? 0 }}</strong>
        </article>
        <article class="metric">
          <span>Research more</span
          ><strong>{{ overview()?.opportunities?.['research_more'] ?? 0 }}</strong>
        </article>
        <article class="metric">
          <span>Blocked</span><strong>{{ overview()?.hard_blocked_candidates ?? 0 }}</strong>
        </article>
        <article class="metric">
          <span>Stale evidence</span
          ><strong>{{ overview()?.evidence_freshness?.['stale'] ?? 0 }}</strong>
        </article>
        <article class="metric"><span>Recovery</span><strong>Protected</strong></article>
        <article class="metric"><span>Trend summary</span><strong>Local</strong></article>
        <article class="metric">
          <span>Recent failures</span><strong>{{ overview()?.recent_failures ?? 0 }}</strong>
        </article>
        <article class="metric"><span>External research</span><strong>Disabled</strong></article>
      </section>

      <nav class="workspace-tabs" aria-label="Intelligence sections">
        <a href="#overview" (click)="setSection('overview')">Overview</a>
        <a href="#missions-workspace" (click)="setSection('missions')">Missions</a>
        <a href="#candidates-workspace" (click)="setSection('candidates')">Candidates</a>
        <a href="#opportunities-workspace" (click)="setSection('opportunities')">Opportunities</a>
        <a href="#rules-workspace" (click)="setSection('rules')">Rules</a>
        <a href="#profiles-workspace" (click)="setSection('profiles')">Profiles</a>
        <a href="#comparison-workspace" (click)="setSection('comparison')">Comparison</a>
        <a href="#reports-workspace" (click)="setSection('reports')">Reports</a>
        <a href="#history-workspace" (click)="setSection('history')">History</a>
        <a href="#evidence-workspace" (click)="setSection('evidence')">Sources &amp; evidence</a>
      </nav>

      <section id="research" class="panel">
        <div class="panel-heading">
          <div>
            <h2>Research projects</h2>
            <p>Owner-scoped projects; archival preserves history.</p>
          </div>
          <button type="button" (click)="createDemoProject()">Create project</button>
        </div>
        @if (projects().length === 0) {
          <p class="empty">No research projects yet.</p>
        }
        @for (project of projects(); track project.id) {
          <div class="row">
            <strong>{{ project.name }}</strong
            ><span>{{ project.status }}</span
            ><span>{{ project.target_market || 'Market not set' }}</span>
          </div>
        }
      </section>

      <section id="mission-create" class="panel" aria-labelledby="mission-create-title">
        <h2 id="mission-create-title">Create mission</h2>
        <form class="form-grid" (submit)="$event.preventDefault(); createMission()">
          <label
            >Name <input name="mission-name" required minlength="2" [(ngModel)]="missionForm.name"
          /></label>
          <label
            >Project
            <select name="mission-project" required [(ngModel)]="missionForm.project_id">
              <option value="">Select project</option>
              @for (project of projects(); track project.id) {
                <option [value]="project.id">{{ project.name }}</option>
              }
            </select></label
          >
          <label>Market <input name="mission-market" [(ngModel)]="missionForm.market" /></label>
          <label
            >Categories
            <input
              name="mission-categories"
              placeholder="home, storage"
              [(ngModel)]="missionForm.categories"
          /></label>
          <label
            >Frequency
            <select name="mission-frequency" [(ngModel)]="missionForm.frequency">
              <option value="manual">Manual</option>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
            </select></label
          >
          <label
            >Timezone <input name="mission-timezone" [(ngModel)]="missionForm.timezone"
          /></label>
          <label
            >Minimum score
            <input
              type="number"
              min="0"
              max="100"
              name="mission-score"
              [(ngModel)]="missionForm.minimum_score_threshold"
          /></label>
          <button type="submit" [disabled]="submitting() !== ''">
            {{ submitting() === 'create-mission' ? 'Creating…' : 'Create mission' }}
          </button>
        </form>
      </section>

      <section id="missions-workspace" class="panel" aria-labelledby="missions-title">
        <h2 id="missions-title">Research missions</h2>
        @if (missions().length === 0) {
          <p class="empty">No research missions.</p>
        }
        @for (mission of missions(); track mission.id) {
          <div class="row mission-row">
            <strong>{{ mission.name }}</strong>
            <span>{{ mission.status }} · {{ mission.enabled ? 'Enabled' : 'Paused' }}</span>
            <span
              >{{ mission.market || 'Market not set' }} ·
              {{ mission.categories.join(', ') || 'All categories' }}</span
            >
            <span>{{ mission.frequency }} · {{ mission.timezone || 'UTC' }}</span>
            <span
              >Last {{ mission.last_run_at || 'Never' }} · Next
              {{ mission.next_run_at || 'Not scheduled' }}</span
            >
            <button
              type="button"
              (click)="runMission(mission)"
              [disabled]="submitting() !== '' || mission.status === 'paused'"
            >
              Run now
            </button>
            <button type="button" (click)="pauseOrResume(mission)" [disabled]="submitting() !== ''">
              {{ mission.status === 'paused' ? 'Resume' : 'Pause' }}
            </button>
            <button
              type="button"
              (click)="scheduleMission(mission)"
              [disabled]="submitting() !== ''"
            >
              Save schedule
            </button>
            <button type="button" (click)="editMission(mission)" [disabled]="submitting() !== ''">
              Save edits
            </button>
            <button type="button" (click)="loadMissionHistory(mission.project_id)">History</button>
          </div>
        }
      </section>

      <section id="candidates-workspace" class="panel" aria-labelledby="candidates-title">
        <h2 id="candidates-title">Research candidates</h2>
        <div class="filter-grid" aria-label="Candidate filters">
          <label
            >Status
            <input name="candidate-status" [(ngModel)]="candidateFilter.status" placeholder="all"
          /></label>
          <label
            >Market
            <input name="candidate-market" [(ngModel)]="candidateFilter.market" placeholder="IN"
          /></label>
          <label
            >Category
            <input
              name="candidate-category"
              [(ngModel)]="candidateFilter.category"
              placeholder="home"
          /></label>
        </div>
        @if (candidates().length === 0) {
          <p class="empty">No candidates.</p>
        }
        @for (candidate of candidates(); track candidate.id) {
          <div class="row">
            <strong>{{ candidate.title }}</strong
            ><span>{{ candidate.category }} · {{ candidate.market }}</span
            ><span>{{ candidate.status }} · {{ candidate.freshness_state }}</span
            ><span
              >Score {{ candidate.score ?? 'UNKNOWN' }} · Recommendation
              {{ candidate.recommendation || 'REVIEW_REQUIRED' }}</span
            ><span
              >Evidence {{ candidate.evidence_count ?? 'UNKNOWN' }} · Rule outcome
              {{ candidate.status }}</span
            >
            <button type="button" (click)="toggleCandidate(candidate)">
              {{ selectedCandidateIds().includes(candidate.id) ? '✓ Selected' : 'Compare' }}
            </button>
            <button
              type="button"
              (click)="selectCandidate(candidate)"
              [disabled]="submitting() !== ''"
            >
              Details
            </button>
          </div>
        }
        <button
          type="button"
          (click)="compareSelected()"
          [disabled]="submitting() !== '' || selectedCandidateIds().length < 2"
        >
          Compare {{ selectedCandidateIds().length }} selected
        </button>
      </section>

      <section
        id="candidate-detail-workspace"
        class="panel"
        aria-labelledby="candidate-detail-title"
      >
        <h2 id="candidate-detail-title">Candidate detail</h2>
        @if (selectedCandidate(); as candidate) {
          <h3>{{ candidate.title }}</h3>
          <p>
            {{ candidate.normalized_title || candidate.title }} · {{ candidate.market }} ·
            {{ candidate.category }} · {{ candidate.status }}
          </p>
          <p>
            Source {{ candidate.source_reference }} · Brand
            {{ candidate.observed_brand || 'UNKNOWN' }} · Freshness {{ candidate.freshness_state }}
          </p>
          <p>
            Score {{ candidate.score ?? 'UNKNOWN' }} · Promotion
            {{ candidate.status === 'promoted' ? 'PROMOTED' : 'NOT PROMOTED' }} · Rules
            {{ candidate.recommendation || 'REVIEW_REQUIRED' }}
          </p>
          <h3>Signals and trend history</h3>
          <pre class="safe-data">{{ candidateSignals() | json }}</pre>
          <pre class="safe-data">{{ candidateTrends() | json }}</pre>
        } @else {
          <p class="empty">
            Select a candidate to inspect identity, signals, rules, evidence, freshness, and
            promotion status.
          </p>
        }
      </section>

      <section id="opportunities-workspace" class="panel" aria-labelledby="opportunities-title">
        <h2 id="opportunities-title">Opportunities</h2>
        <div class="filter-grid" aria-label="Opportunity filters">
          <label
            >Recommendation <input name="opportunity-status" [(ngModel)]="opportunityFilter.status"
          /></label>
          <label
            >Market <input name="opportunity-market" [(ngModel)]="opportunityFilter.market"
          /></label>
          <label
            >Category <input name="opportunity-category" [(ngModel)]="opportunityFilter.category"
          /></label>
          <label
            >Freshness
            <input name="opportunity-freshness" [(ngModel)]="opportunityFilter.freshness"
          /></label>
        </div>
        @if (opportunities().length === 0) {
          <p class="empty">No opportunities discovered yet.</p>
        }
        @for (item of opportunities(); track item.id) {
          <div class="row">
            <strong>{{ item.title }}</strong
            ><span>Winning Product Score {{ item.score }}</span
            ><span>{{ item.status }} · Confidence {{ item.confidence }}</span
            ><span
              >{{ item.market }} · {{ item.freshness_state }} · Risk
              {{ item.risk_summary || 'UNKNOWN' }}</span
            ><button
              type="button"
              (click)="selectOpportunity(item)"
              [disabled]="submitting() !== ''"
            >
              Inspect
            </button>
          </div>
        }
      </section>

      <div class="evidence-grid" aria-label="Evidence legend">
        <span class="evidence observed">OBSERVED EVIDENCE</span
        ><span class="evidence derived">DERIVED SIGNAL</span
        ><span class="evidence assumed">ASSUMPTION</span
        ><span class="evidence rule">DETERMINISTIC RULE</span>
      </div>
      <section
        id="opportunity-detail-workspace"
        class="panel"
        aria-labelledby="opportunity-detail-title"
      >
        <h2 id="opportunity-detail-title">Opportunity detail</h2>
        @if (selectedOpportunity(); as detail) {
          <h3>{{ detail.title }}</h3>
          <p>
            Score {{ detail.score }} · Recommendation {{ detail.status }} · Confidence
            {{ detail.confidence }}
          </p>
          <p>
            Market {{ detail.market }} · Category {{ detail.category }} · Freshness
            {{ detail.freshness_state }}
          </p>
          <h3>
            Score breakdown, demand, competition, pricing, trend, economics, capital, risk,
            legal/IP, rules, and provenance
          </h3>
          <div class="evidence-grid">
            <span class="evidence observed">OBSERVED EVIDENCE</span
            ><span class="evidence derived">DERIVED SIGNAL</span
            ><span class="evidence assumed">ASSUMPTION</span
            ><span class="evidence rule">DETERMINISTIC RULE</span>
          </div>
          <p>LEGAL REVIEW MAY BE REQUIRED</p>
          <pre class="safe-data">{{ detail | json }}</pre>
        } @else {
          <p class="empty">
            Select an opportunity to inspect its immutable score model and evidence lineage.
          </p>
        }
      </section>

      <section id="competitors" class="panel">
        <h2>Competitor intelligence</h2>
        <p>External research is disabled by default.</p>
        <p>
          Observed price, rating, review count, brand, features, observation time, snapshot history,
          and source evidence remain bounded to stored evidence.
        </p>
      </section>
      <section id="reviews" class="panel">
        <h2>Review intelligence</h2>
        <p>
          Positive themes, negative themes, pain points, quality, packaging, durability, size,
          usability, feature requests, frequency, confidence, and evidence.
        </p>
      </section>

      <section id="rules-workspace" class="panel" aria-labelledby="rules-title">
        <h2 id="rules-title">Rule configuration and simulation</h2>
        <p>
          GLOBAL → MARKET → MARKETPLACE → CATEGORY → PROFILE/MISSION. GLOBAL BLOCK WINS unless an
          authorized override exists.
        </p>
        <div class="evidence-grid">
          <span class="evidence rule">ALLOW</span><span class="evidence rule">WARN</span
          ><span class="evidence rule">REVIEW_REQUIRED</span
          ><span class="evidence rule">BLOCK</span>
        </div>
        @if (rules().length === 0) {
          <p class="empty">No rules configured.</p>
        }
        @for (rule of rules(); track rule.id) {
          <div class="row">
            <strong>{{ rule.name }}</strong
            ><span>{{ rule.scope || 'GLOBAL' }}</span
            ><span>{{ rule.action || 'REVIEW_REQUIRED' }}</span
            ><span>{{ rule.enabled ? 'Enabled' : 'Disabled' }}</span>
          </div>
        }
        <p>
          Rule simulation is preview-only and does not mutate configuration. Physical units are
          normalized by the backend contract.
        </p>
      </section>

      <section id="profiles-workspace" class="panel" aria-labelledby="profiles-title">
        <h2 id="profiles-title">Research profile editor</h2>
        <form class="form-grid" (submit)="$event.preventDefault(); createProfile()">
          <label
            >Name <input name="profile-name" required minlength="2" [(ngModel)]="profileForm.name"
          /></label>
          <label>Market <input name="profile-market" [(ngModel)]="profileForm.market" /></label>
          <label
            >Currency
            <input
              name="profile-currency"
              minlength="3"
              maxlength="3"
              [(ngModel)]="profileForm.currency"
          /></label>
          <label
            >Categories <input name="profile-categories" [(ngModel)]="profileForm.categories"
          /></label>
          <label
            >Excluded categories
            <input name="profile-excluded" [(ngModel)]="profileForm.excluded_categories"
          /></label>
          <label
            >Min price
            <input
              type="number"
              min="0"
              name="profile-min"
              [(ngModel)]="profileForm.min_selling_price"
          /></label>
          <label
            >Max price
            <input
              type="number"
              min="0"
              name="profile-max"
              [(ngModel)]="profileForm.max_selling_price"
          /></label>
          <label
            >Minimum margin
            <input
              type="number"
              min="0"
              max="1"
              step="0.01"
              name="profile-margin"
              [(ngModel)]="profileForm.minimum_margin"
          /></label>
          <button type="submit" [disabled]="submitting() !== ''">Create profile</button>
        </form>
        @if (profiles().length === 0) {
          <p class="empty">No research profiles.</p>
        }
        @for (profile of profiles(); track profile.id) {
          <div class="row">
            <strong>{{ profile.name }}</strong
            ><span>{{ profile.market }} · {{ profile.currency }}</span
            ><span>{{ profile.categories.join(', ') }}</span>
          </div>
        }
      </section>

      <section id="comparison-workspace" class="panel" aria-labelledby="comparison-title">
        <h2 id="comparison-title">Comparison workspace</h2>
        <p>
          Select two to five candidates and highlight evidence differences without implying an
          automatic winner.
        </p>
        @if (compareResult(); as comparison) {
          <pre class="safe-data">{{ comparison | json }}</pre>
        } @else {
          <p class="empty">No comparison requested.</p>
        }
      </section>

      <section id="history-workspace" class="panel" aria-labelledby="history-title">
        <h2 id="history-title">Mission, score, report, and recovery history</h2>
        @if (missionRuns().length === 0) {
          <p class="empty">No mission history.</p>
        }
        @for (run of missionRuns(); track run.id) {
          <div class="row">
            <strong>{{ run.id }}</strong
            ><span>{{ run.status }}</span
            ><span>{{ run.started_at || 'Not started' }} → {{ run.completed_at || 'Pending' }}</span
            ><span>{{ run.provider_mode || 'local_deterministic' }}</span>
          </div>
        }
        @if (historyResult(); as history) {
          <pre class="safe-data">{{ history | json }}</pre>
        }
      </section>

      <section id="reports-workspace" class="panel" aria-labelledby="reports-title">
        <h2 id="reports-title">Report workspace</h2>
        <p>
          Generate and view JSON, Markdown, or HTML reports with bounded provenance and assumptions.
        </p>
        @if (reports().length === 0) {
          <p class="empty">No reports.</p>
        }
        @for (report of reports(); track report.id) {
          <article>
            <h3>{{ report.title }}</h3>
            <p>{{ report.format }} · {{ report.created_at }}</p>
            <pre class="safe-data">{{ report.content }}</pre>
          </article>
        }
      </section>

      <section id="evidence-workspace" class="panel" aria-labelledby="evidence-title">
        <h2 id="evidence-title">Evidence inspector</h2>
        @if (evidence().length === 0) {
          <p class="empty">No competitor or review evidence.</p>
        }
        @for (item of evidence(); track item.id) {
          <article class="row">
            <strong>{{ item.source_type || 'Source' }}</strong
            ><span>{{ item.source_reference }}</span
            ><span>{{ item.freshness }}</span
            ><span>{{ item.observed_at }}</span>
          </article>
        }
        <p>AI INTERPRETATION — NOT ENABLED (AI INTERPRETATION DISABLED)</p>
      </section>
    }
  </main>`,
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
      .status-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 12px;
        margin: 14px 0;
      }
      .status-grid article {
        border: 1px solid #cbd9de;
        border-radius: 10px;
        background: #fff;
        padding: 14px;
      }
      .status-grid strong,
      .status-grid span {
        display: block;
      }
      .status-grid span {
        color: #5d747c;
        font-size: 0.82rem;
        margin-top: 6px;
      }
      .form-grid,
      .filter-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin: 16px 0;
      }
      .form-grid label,
      .filter-grid label {
        display: grid;
        gap: 5px;
        font-weight: 700;
      }
      input,
      select {
        border: 1px solid #9db7bf;
        border-radius: 6px;
        padding: 9px;
        font: inherit;
        min-width: 0;
      }
      .safe-data {
        overflow: auto;
        white-space: pre-wrap;
        background: #f4f8f9;
        border-radius: 8px;
        padding: 12px;
      }
      .workspace-tabs {
        display: flex;
        flex-wrap: wrap;
        gap: 18px;
        margin: 24px 0;
      }
      .evidence-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 16px 0;
      }

      .evidence {
        border-radius: 999px;
        padding: 6px 10px;
        font-size: 0.78rem;
        font-weight: 700;
      }

      .observed {
        background: #e3f4e9;
        color: #1d6539;
      }
      .derived {
        background: #e8f0ff;
        color: #24518a;
      }
      .assumed {
        background: #fff3d6;
        color: #805d13;
      }
      .rule {
        background: #f0e7ff;
        color: #5d3487;
      }
      .disabled {
        background: #eef1f2;
        color: #5d747c;
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
        gap: 16px;
        align-items: flex-start;
      }
      .rows {
        display: grid;
        gap: 10px;
        margin-top: 16px;
      }
      .row {
        display: grid;
        grid-template-columns: 2fr 1fr 1fr auto;
        gap: 12px;
        align-items: center;
        padding: 12px;
        border: 1px solid #e0eaed;
        border-radius: 8px;
      }
      .empty,
      .loading {
        color: #5d747c;
      }
      .error {
        padding: 12px;
        background: #fff0f0;
        color: #a02a2a;
      }
      @media (max-width: 520px) {
        .intelligence-page {
          padding: 24px 14px 48px;
        }
        .status-grid,
        .form-grid,
        .filter-grid,
        .metric-grid {
          grid-template-columns: 1fr;
        }
        .workspace-tabs {
          gap: 10px;
        }
        .panel {
          padding: 16px;
          overflow-x: auto;
        }
      }
      @media (max-width: 900px) {
        .status-grid,
        .form-grid,
        .filter-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .metric-grid {
          grid-template-columns: repeat(2, 1fr);
        }
        .page-header {
          flex-direction: column;
        }
        .row {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class IntelligenceWorkspaceComponent {
  private readonly service = inject(IntelligenceService);
  readonly overview = signal<IntelligenceOverview | null>(null);
  readonly projects = signal<IntelligenceProject[]>([]);
  readonly sources = signal<IntelligenceSource[]>([]);
  readonly opportunities = signal<IntelligenceOpportunity[]>([]);
  readonly candidates = signal<IntelligenceCandidate[]>([]);
  readonly missions = signal<IntelligenceMission[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly selectedSection = signal('overview');
  readonly selectedCandidate = signal<IntelligenceCandidate | null>(null);
  readonly candidateSignals = signal<Record<string, unknown>[]>([]);
  readonly candidateTrends = signal<Record<string, unknown>[]>([]);
  readonly selectedOpportunity = signal<IntelligenceOpportunity | null>(null);
  readonly profiles = signal<IntelligenceProfile[]>([]);
  readonly rules = signal<IntelligenceRule[]>([]);
  readonly ruleCategories = signal<Record<string, unknown>[]>([]);
  readonly ruleSimulation = signal<Record<string, unknown> | null>(null);
  readonly selectedEvidence = signal<IntelligenceEvidence | null>(null);
  readonly evidence = signal<IntelligenceEvidence[]>([]);
  readonly missionRuns = signal<IntelligenceMissionRun[]>([]);
  readonly historyResult = signal<IntelligenceHistory | null>(null);
  readonly compareResult = signal<Record<string, unknown> | null>(null);
  readonly reports = signal<IntelligenceReport[]>([]);
  readonly selectedCandidateIds = signal<string[]>([]);
  readonly submitting = signal('');
  readonly missionForm = {
    name: '',
    project_id: '',
    profile_id: '',
    market: '',
    categories: '',
    frequency: 'manual',
    timezone: 'UTC',
    ruleset_version: 'default-v1',
    minimum_score_threshold: 45,
    notification_threshold: 65,
  };
  readonly profileForm = {
    name: '',
    market: '',
    currency: 'INR',
    categories: '',
    excluded_categories: '',
    min_selling_price: null as number | null,
    max_selling_price: null as number | null,
    minimum_margin: null as number | null,
    max_sourcing_estimate: null as number | null,
    max_weight_kg: null as number | null,
    max_length_cm: null as number | null,
    max_width_cm: null as number | null,
    max_height_cm: null as number | null,
    competition_tolerance: 'balanced',
    risk_tolerance: 'balanced',
  };
  candidateFilter = { status: '', market: '', category: '', freshness: '', rule: '', score: '' };
  opportunityFilter = {
    status: '',
    market: '',
    category: '',
    freshness: '',
    hard_blocked: false,
    risk: '',
    score: '',
  };
  constructor() {
    void this.load();
  }
  setSection(section: string): void {
    this.selectedSection.set(section);
    if (section === 'profiles' && !this.profiles().length) void this.loadProfiles();
    if (section === 'rules' && !this.rules().length) {
      void this.loadRules();
      void this.loadRuleCategories();
    }
    if (section === 'evidence' && !this.evidence().length) void this.loadEvidence();
  }
  async createDemoProject(): Promise<void> {
    if (this.submitting() || !this.confirmAction('Create a local deterministic research project?'))
      return;
    this.submitting.set('create-project');
    try {
      await this.service.createProject({
        name: 'Winning products',
        description: 'Evidence-first local deterministic research.',
        target_market: 'IN',
      });
      await this.load();
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'The research project could not be created.'));
    } finally {
      this.submitting.set('');
    }
  }
  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const [overview, projects, sources, opportunities, candidates, missions] = await Promise.all([
        this.service.overview(),
        this.service.projects(),
        this.service.sources(),
        this.service.opportunities(),
        this.service.candidates(),
        this.service.missions(),
      ]);
      this.overview.set(overview);
      this.projects.set(projects);
      this.sources.set(sources);
      this.opportunities.set(opportunities);
      this.candidates.set(candidates);
      this.missions.set(missions);
    } catch {
      this.error.set('Intelligence data is unavailable. Check the authenticated API connection.');
    } finally {
      this.loading.set(false);
    }
  }
  async runMission(mission: IntelligenceMission): Promise<void> {
    if (this.submitting() || !this.confirmAction('Run this mission now?')) return;
    this.submitting.set('run-' + mission.id);
    this.error.set('');
    try {
      const result = await this.service.runMission(mission.id);
      this.error.set(
        result.status === 'reused' ? 'Existing run reused safely.' : 'Mission run accepted safely.',
      );
      await this.load();
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'The local research mission could not be started.'));
    } finally {
      this.submitting.set('');
    }
  }
  async createMission(): Promise<void> {
    if (
      this.submitting() ||
      this.missionForm.name.trim().length < 2 ||
      !this.missionForm.project_id
    ) {
      this.error.set('Mission name and project are required.');
      return;
    }
    this.submitting.set('create-mission');
    try {
      await this.service.createMission({
        project_id: this.missionForm.project_id,
        profile_id: this.missionForm.profile_id || null,
        name: this.missionForm.name.trim(),
        frequency: this.missionForm.frequency,
        timezone: this.missionForm.timezone,
        market: this.missionForm.market,
        categories: this.missionForm.categories
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        ruleset_version: this.missionForm.ruleset_version,
        minimum_score_threshold: this.missionForm.minimum_score_threshold,
        notification_threshold: this.missionForm.notification_threshold,
      });
      this.missionForm.name = '';
      this.missionForm.categories = '';
      await this.load();
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'The research mission could not be created.'));
    } finally {
      this.submitting.set('');
    }
  }
  async editMission(mission: IntelligenceMission): Promise<void> {
    if (
      this.submitting() ||
      !this.confirmAction('Save changes to this mission? Historical runs remain unchanged.')
    )
      return;
    this.submitting.set('edit-' + mission.id);
    try {
      await this.service.updateMission(mission.id, {
        frequency: mission.frequency,
        timezone: mission.timezone,
        categories: mission.categories,
        minimum_score_threshold: mission.minimum_score_threshold,
      });
      await this.load();
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'The mission could not be updated.'));
    } finally {
      this.submitting.set('');
    }
  }

  async pauseOrResume(mission: IntelligenceMission): Promise<void> {
    if (
      this.submitting() ||
      !this.confirmAction((mission.status === 'paused' ? 'Resume' : 'Pause') + ' this mission?')
    )
      return;
    this.submitting.set('state-' + mission.id);
    try {
      if (mission.status === 'paused') await this.service.resumeMission(mission.id);
      else await this.service.pauseMission(mission.id);
      await this.load();
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'The mission state could not be changed.'));
    } finally {
      this.submitting.set('');
    }
  }

  async scheduleMission(mission: IntelligenceMission): Promise<void> {
    if (this.submitting() || !this.confirmAction('Apply this schedule?')) return;
    this.submitting.set('schedule-' + mission.id);
    try {
      await this.service.scheduleMission(mission.id, {
        frequency: mission.frequency || 'manual',
        timezone: mission.timezone || 'UTC',
      });
      await this.load();
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'The mission schedule could not be saved.'));
    } finally {
      this.submitting.set('');
    }
  }
  async loadProfiles(): Promise<void> {
    try {
      this.profiles.set(await this.service.profiles());
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'Profiles are unavailable.'));
    }
  }

  async loadRules(): Promise<void> {
    try {
      this.rules.set(await this.service.rules());
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'Rules are unavailable.'));
    }
  }

  async loadRuleCategories(): Promise<void> {
    try {
      this.ruleCategories.set(await this.service.ruleCategories());
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'Rule categories are unavailable.'));
    }
  }

  async simulateRules(): Promise<void> {
    const ids = this.selectedCandidateIds();
    if (!ids.length) {
      this.error.set('Select at least one candidate before simulating rules.');
      return;
    }
    this.submitting.set('rule-simulation');
    try {
      this.ruleSimulation.set(await this.service.simulateRules(ids));
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'Rule simulation is unavailable.'));
    } finally {
      this.submitting.set('');
    }
  }
  async loadEvidence(): Promise<void> {
    try {
      this.evidence.set(await this.service.evidence());
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'Evidence is unavailable.'));
    }
  }

  async loadMissionHistory(projectId: string): Promise<void> {
    try {
      const runs = await this.service.missionRuns(projectId);
      this.missionRuns.set(runs);
      if (runs[0]) {
        const history = await this.service.history(runs[0].id);
        this.historyResult.set(history);
        this.reports.set(history.reports ?? []);
      }
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'Mission history is unavailable.'));
    }
  }
  async selectEvidence(item: IntelligenceEvidence): Promise<void> {
    this.submitting.set('evidence-' + item.id);
    try {
      this.selectedEvidence.set(await this.service.evidenceDetail(item.id));
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'Evidence detail is unavailable.'));
    } finally {
      this.submitting.set('');
    }
  }

  async generateReport(
    runId: string,
    format: 'json' | 'markdown' | 'html' = 'markdown',
  ): Promise<void> {
    if (this.submitting() || !this.confirmAction('Generate this bounded research report?')) return;
    this.submitting.set('report-' + runId);
    try {
      const report = await this.service.report(runId, format);
      this.reports.set([report, ...this.reports().filter((item) => item.id !== report.id)]);
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'The report could not be generated.'));
    } finally {
      this.submitting.set('');
    }
  }
  async selectCandidate(candidate: IntelligenceCandidate): Promise<void> {
    this.selectedCandidate.set(candidate);
    this.submitting.set('candidate-' + candidate.id);
    try {
      const result = await Promise.all([
        this.service.candidate(candidate.id),
        this.service.signals(candidate.id),
        this.service.trends(candidate.id),
      ]);
      this.selectedCandidate.set(result[0]);
      this.candidateSignals.set(result[1]);
      this.candidateTrends.set(result[2]);
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'Candidate detail is unavailable.'));
    } finally {
      this.submitting.set('');
    }
  }

  async selectOpportunity(opportunity: IntelligenceOpportunity): Promise<void> {
    this.selectedOpportunity.set(opportunity);
    this.submitting.set('opportunity-' + opportunity.id);
    try {
      this.selectedOpportunity.set(await this.service.opportunity(opportunity.id));
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'Opportunity detail is unavailable.'));
    } finally {
      this.submitting.set('');
    }
  }
  toggleCandidate(candidate: IntelligenceCandidate): void {
    const ids = this.selectedCandidateIds();
    if (ids.includes(candidate.id))
      this.selectedCandidateIds.set(ids.filter((id) => id !== candidate.id));
    else if (ids.length < 5) this.selectedCandidateIds.set([...ids, candidate.id]);
  }

  async compareSelected(): Promise<void> {
    const ids = this.selectedCandidateIds();
    if (ids.length < 2 || ids.length > 5) {
      this.error.set('Select between two and five candidates to compare.');
      return;
    }
    this.submitting.set('compare');
    try {
      this.compareResult.set(await this.service.compare(ids));
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'Comparison is unavailable.'));
    } finally {
      this.submitting.set('');
    }
  }
  async createProfile(): Promise<void> {
    if (this.submitting() || this.profileForm.name.trim().length < 2) {
      this.error.set('Profile name is required.');
      return;
    }
    if (
      this.profileForm.min_selling_price !== null &&
      this.profileForm.max_selling_price !== null &&
      this.profileForm.min_selling_price > this.profileForm.max_selling_price
    ) {
      this.error.set('Minimum price cannot exceed maximum price.');
      return;
    }
    this.submitting.set('create-profile');
    try {
      await this.service.createProfile({
        name: this.profileForm.name.trim(),
        market: this.profileForm.market,
        currency: this.profileForm.currency,
        categories: this.profileForm.categories
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        excluded_categories: this.profileForm.excluded_categories
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        min_selling_price: this.profileForm.min_selling_price,
        max_selling_price: this.profileForm.max_selling_price,
        minimum_margin: this.profileForm.minimum_margin,
        max_sourcing_estimate: this.profileForm.max_sourcing_estimate,
        max_weight_kg: this.profileForm.max_weight_kg,
        max_length_cm: this.profileForm.max_length_cm,
        max_width_cm: this.profileForm.max_width_cm,
        max_height_cm: this.profileForm.max_height_cm,
        competition_tolerance: this.profileForm.competition_tolerance,
        risk_tolerance: this.profileForm.risk_tolerance,
      });
      await this.loadProfiles();
    } catch (error: unknown) {
      this.error.set(this.apiError(error, 'The research profile could not be created.'));
    } finally {
      this.submitting.set('');
    }
  }
  private confirmAction(message: string): boolean {
    try {
      if (typeof window === 'undefined') return true;
      const confirmed = window.confirm(message);
      return confirmed !== false;
    } catch {
      return true;
    }
  }
  private apiError(error: unknown, fallback: string): string {
    const detail = (error as { error?: { detail?: unknown } })?.error?.detail;
    return typeof detail === 'string' ? detail : fallback;
  }
}
