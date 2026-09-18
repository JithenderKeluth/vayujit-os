import { DatePipe, JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import {
  CommercialOutput,
  IntelligenceOutput,
  OpportunityConstraintPayload,
  OpportunityDetail,
  ProductOpportunity,
  ProductOpportunityService,
  ProductOpportunityScore,
  ProductOpportunityScoreHistory,
  ProductOpportunityComparison,
  SourcingFeasibilityOutput,
  RiskEvidenceSynthesisOutput,
  SourcingCandidate,
} from './product-opportunity.service';

@Component({
  selector: 'app-product-opportunity-workspace',
  standalone: true,
  imports: [DatePipe, JsonPipe, FormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="workspace" aria-labelledby="opportunities-title">
      <header class="page-header">
        <div>
          <p class="eyebrow">Intelligence / Winning products</p>
          <h1 id="opportunities-title">Product opportunities</h1>
          <p class="lede">
            Owner-scoped concepts with versioned constraints and human-reviewed assessments.
          </p>
        </div>
        <a routerLink="/intelligence">Back to Intelligence</a>
      </header>

      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }
      @if (loading()) {
        <p role="status" aria-live="polite">Loading opportunities...</p>
      }

      <section class="panel" aria-labelledby="create-title">
        <h2 id="create-title">Create opportunity</h2>
        <form (ngSubmit)="create()">
          <label
            >Name <input name="name" [(ngModel)]="name" required minlength="2" maxlength="200"
          /></label>
          <label
            >Product concept
            <textarea name="concept" [(ngModel)]="concept" maxlength="10000"></textarea>
          </label>
          <label>Category <input name="category" [(ngModel)]="category" maxlength="120" /></label>
          <label
            >Marketplace <input name="marketplace" [(ngModel)]="marketplace" maxlength="120"
          /></label>
          <label>Region <input name="region" [(ngModel)]="region" maxlength="120" /></label>
          <label
            >Origin
            <select name="origin" [(ngModel)]="origin">
              @for (value of origins; track value) {
                <option [value]="value">{{ value }}</option>
              }
            </select>
          </label>
          <button type="submit" [disabled]="loading() || !name.trim()">Create opportunity</button>
        </form>
      </section>

      <section class="panel" aria-labelledby="list-title">
        <h2 id="list-title">Your opportunities</h2>
        @for (item of opportunities(); track item.id) {
          <button class="list-item" type="button" (click)="select(item.id)">
            <strong>{{ item.name }}</strong>
            <span>{{ item.lifecycle_status }} ï¿½ {{ item.evidence_state }}</span>
          </button>
        } @empty {
          <p>No product opportunities yet.</p>
        }
      </section>
      <section class="panel" aria-labelledby="comparison-title">
        <div class="section-heading">
          <h2 id="comparison-title">Compare scored opportunities</h2>
          <span>Bounded, same-model decision support</span>
        </div>
        <button
          type="button"
          (click)="compareOpportunities()"
          [disabled]="loading() || !canCompare()"
        >
          Compare top five scored opportunities
        </button>
        @if (comparison(); as result) {
          <p role="status">{{ result.comparability }} — {{ result.reason }}</p>
          @if (result.ranking?.length) {
            <ol>
              @for (entry of result.ranking; track entry.assessment_id) {
                <li>
                  Rank {{ entry.rank }} · {{ entry.score ?? 'Unavailable' }} ·
                  {{ entry.classification }} · confidence {{ entry.confidence }} · readiness
                  {{ entry.readiness }}
                </li>
              }
            </ol>
          } @else {
            <p>These assessments are not comparable and receive no ordinary rank.</p>
          }
        }
      </section>
      @if (detail(); as item) {
        <section class="panel" aria-labelledby="detail-title">
          <div class="section-heading">
            <h2 id="detail-title">{{ item.name }}</h2>
            <span>{{ item.lifecycle_status }}</span>
          </div>
          <p>{{ item.description || item.product_concept || 'No description recorded.' }}</p>
          <dl>
            <dt>Origin</dt>
            <dd>{{ item.origin }}</dd>
            <dt>Marketplace</dt>
            <dd>{{ item.target_marketplace || 'Unknown' }}</dd>
            <dt>Evidence</dt>
            <dd>{{ item.evidence_state }}</dd>
            <dt>Updated</dt>
            <dd>{{ item.updated_at | date: 'medium' }}</dd>
          </dl>
          <button
            type="button"
            (click)="archive(item.id)"
            [disabled]="loading() || item.lifecycle_status === 'archived'"
          >
            Archive
          </button>
        </section>

        <section class="panel" aria-labelledby="constraints-title">
          <h2 id="constraints-title">Constraint history</h2>
          @for (constraint of item.constraints; track constraint.id) {
            <p>
              Version {{ constraint.version }} ï¿½
              {{ constraint.currency || 'Currency unknown' }} ï¿½ landed cost
              {{ constraint.maximum_landed_cost || 'unknown' }}
            </p>
          } @empty {
            <p>No constraint versions yet.</p>
          }
          <form (ngSubmit)="addConstraint(item.id)">
            <label
              >Currency
              <input name="constraintCurrency" [(ngModel)]="constraint.currency" maxlength="3"
            /></label>
            <label
              >Maximum landed cost
              <input
                name="landedCost"
                [(ngModel)]="constraint.maximum_landed_cost"
                inputmode="decimal"
            /></label>
            <button type="submit" [disabled]="loading()">Add constraint version</button>
          </form>
        </section>

        <section class="panel" aria-labelledby="assessment-title">
          <h2 id="assessment-title">Assessment history</h2>
          @for (assessment of item.assessments; track assessment.id) {
            <p>
              Version {{ assessment.version }} ï¿½ {{ assessment.status }} ï¿½
              {{ assessment.evidence_state }}
            </p>
          } @empty {
            <p>No assessments yet. Assessments remain append-only.</p>
          }
        </section>

        @if (item.current_assessment_id) {
          <section class="panel" aria-labelledby="intelligence-title">
            <div class="section-heading">
              <h2 id="intelligence-title">Demand &amp; competition intelligence</h2>
              <span>Assessment-bound, deterministic evidence</span>
            </div>
            <div class="intelligence-actions">
              <button type="button" (click)="calculateDemand(item)" [disabled]="loading()">
                Calculate demand
              </button>
              <button type="button" (click)="calculateCompetition(item)" [disabled]="loading()">
                Calculate competition
              </button>
            </div>
            @for (output of intelligenceOutputs(); track output.id) {
              <article class="intelligence-output">
                <h3>{{ output.kind }} intelligence</h3>
                <p class="muted">
                  Calculation {{ output.calculation_version }} ï¿½
                  {{ output.created_at | date: 'medium' }}
                </p>
                <div class="dimension-grid">
                  @for (dimension of output.dimensions; track dimension.dimension) {
                    <div class="dimension">
                      <strong>{{ dimension.dimension }}</strong>
                      <span>{{ dimension.value ?? 'Unavailable' }}</span>
                      <small
                        >{{ dimension.classification }} ï¿½ {{ dimension.evidence_state }}</small
                      >
                      <p>{{ dimension.explanation }}</p>
                      @if (dimension.missing_evidence.length) {
                        <small>Missing: {{ dimension.missing_evidence.join(', ') }}</small>
                      }
                    </div>
                  }
                </div>
                @if (output.research_gaps.length) {
                  <p class="muted">Research gaps remain; no recommendation is inferred.</p>
                }
              </article>
            } @empty {
              <p>No demand or competition output has been calculated for this assessment.</p>
            }
          </section>
          <section class="panel" aria-labelledby="economics-title">
            <div class="section-heading">
              <h2 id="economics-title">Economics</h2>
              <span>Assessment-bound commercial viability</span>
            </div>
            <button type="button" (click)="calculateCommercial(item)" [disabled]="loading()">
              Calculate economics
            </button>
            @if (commercialOutput(); as commercial) {
              <dl class="economics-summary">
                <dt>Market price evidence</dt>
                <dd>{{ commercial.evidence_summary['prices'] ? 'Available' : 'Unknown' }}</dd>
                <dt>Selling price assumption</dt>
                <dd>
                  {{ commercial.economics['selling_price'] ?? 'UNKNOWN' }}
                  {{ commercial.economics['currency'] ?? '' }}
                </dd>
                <dt>Landed cost</dt>
                <dd>{{ commercial.economics['landed_cost_per_unit'] ?? 'UNKNOWN' }}</dd>
                <dt>Contribution / unit</dt>
                <dd>{{ commercial.economics['contribution_per_unit'] ?? 'UNKNOWN' }}</dd>
                <dt>Contribution margin</dt>
                <dd>{{ commercial.economics['contribution_margin_percent'] ?? 'UNKNOWN' }}%</dd>
                <dt>MOQ / capital</dt>
                <dd>
                  {{ commercial.economics['moq'] ?? 'UNKNOWN' }} /
                  {{ commercial.economics['known_total_initial_capital'] ?? 'UNKNOWN' }}
                </dd>
                <dt>Break-even units</dt>
                <dd>{{ commercial.economics['break_even_units'] ?? 'UNKNOWN' }}</dd>
              </dl>
              <h3>Commercial dimensions</h3>
              <div class="dimension-grid">
                @for (dimension of commercial.dimensions; track dimension.dimension) {
                  <div class="dimension">
                    <strong>{{ dimension.dimension }}</strong
                    ><span>{{ dimension.value ?? 'UNKNOWN' }}</span
                    ><small>{{ dimension.classification }} · {{ dimension.evidence_state }}</small>
                    <p>{{ dimension.explanation }}</p>
                  </div>
                }
              </div>
              <p class="muted">
                Sensitivity includes bounded BASELINE / SCENARIO / DELTA results. Missing evidence:
                {{ commercial.research_gaps.length }} gap(s).
              </p>
            } @else {
              <p>No commercial viability output has been calculated for this assessment.</p>
            }
            <section class="panel" aria-labelledby="risk-evidence-title">
              <div class="section-heading">
                <h2 id="risk-evidence-title">Risk &amp; evidence synthesis</h2>
                <span>Confidence and readiness are not business outcomes</span>
              </div>
              <button type="button" (click)="calculateRiskEvidence(item)" [disabled]="loading()">
                Synthesize risk &amp; evidence
              </button>
              @if (riskEvidence(); as synthesis) {
                <dl class="economics-summary">
                  <dt>Assessment readiness</dt>
                  <dd>{{ synthesis.summary['assessment_readiness'] }}</dd>
                  <dt>Confidence</dt>
                  <dd>{{ synthesis.summary['confidence'] }}</dd>
                  <dt>Material risks</dt>
                  <dd>{{ synthesis.summary['risk_count'] }}</dd>
                </dl>
                <h3>Domain readiness</h3>
                <pre>{{ synthesis.domain_readiness | json }}</pre>
                <h3>Material risks</h3>
                <pre>{{ synthesis.risks | json }}</pre>
                <h3>Evidence coverage and gaps</h3>
                <pre>{{ synthesis.evidence_summary | json }}</pre>
                <p class="muted">Changes: {{ synthesis.changes | json }}</p>
              } @else {
                <p>No risk/evidence synthesis has been calculated for this assessment.</p>
              }
            </section>
            <section class="panel" aria-labelledby="sourcing-feasibility-title">
              <div class="section-heading">
                <h2 id="sourcing-feasibility-title">Supplier &amp; sourcing feasibility</h2>
                <span>Evidence-backed assessment projection</span>
              </div>
              <button type="button" (click)="calculateSourcing(item)" [disabled]="loading()">
                Assess sourcing feasibility
              </button>
              @if (sourcingFeasibility(); as sourcing) {
                <dl class="economics-summary">
                  <dt>Feasibility state</dt>
                  <dd>{{ sourcing.summary['feasibility_state'] }}</dd>
                  <dt>Suppliers discovered / matched</dt>
                  <dd>
                    {{ sourcing.summary['supplier_availability']?.discovered ?? 0 }} /
                    {{ sourcing.summary['supplier_availability']?.matched ?? 0 }}
                  </dd>
                  <dt>Eligible / due diligence complete</dt>
                  <dd>
                    {{ sourcing.summary['supplier_availability']?.eligible ?? 0 }} /
                    {{ sourcing.summary['supplier_availability']?.dd_complete ?? 0 }}
                  </dd>
                  <dt>Scenario availability</dt>
                  <dd>{{ sourcing.summary['scenario_availability'] }}</dd>
                  <dt>Evidence confidence</dt>
                  <dd>{{ sourcing.summary['confidence'] }}</dd>
                </dl>
                <h3>Supplier candidates</h3>
                @if (sourcing.candidates.length) {
                  <div class="candidate-table" role="table" aria-label="Supplier candidates">
                    @for (
                      candidate of sourcing.candidates;
                      track candidate['matched_product']?.['id']
                    ) {
                      <div class="candidate-row" role="row">
                        <strong>{{ candidate['supplier']?.['name'] }}</strong>
                        <span
                          >Source: {{ candidate.source | json }} ·
                          {{ candidate.country ?? 'UNKNOWN' }} /
                          {{ candidate.region ?? 'UNKNOWN' }}</span
                        >
                        <span>Match explanation: {{ candidate.match_explanation | json }}</span>
                        <span>Shortlist: {{ candidate.shortlist | json }}</span>
                        <span>Due diligence: {{ candidate.due_diligence | json }}</span>
                        <span
                          >Availability: {{ candidate.availability ?? 'UNKNOWN' }} · Alternate
                          readiness: {{ candidate.alternate_readiness ?? 'UNKNOWN' }}</span
                        >
                        <span
                          >Risk: {{ candidate.risk_warnings | json }} · Freshness:
                          {{ candidate.freshness ?? 'UNKNOWN' }}</span
                        >
                        @if (candidate.canonical_supplier_id && item.product_id) {
                          <button
                            type="button"
                            (click)="handoffSourcing(item, candidate)"
                            [disabled]="loading()"
                          >
                            Create internal DD context (no external work)
                          </button>
                        }
                        <span>{{ candidate['matched_product']?.['title'] }}</span>
                        <span
                          >{{ candidate['verification'] }} · {{ candidate['match_state'] }}</span
                        >
                        <span
                          >{{ candidate['currency'] ?? '' }}
                          {{ candidate['price'] ?? 'UNKNOWN' }}</span
                        >
                        <span
                          >MOQ {{ candidate['moq'] ?? 'UNKNOWN' }} ·
                          {{ candidate['lead_time_days'] ?? 'UNKNOWN' }} days</span
                        >
                      </div>
                    }
                  </div>
                } @else {
                  <p>No supplier evidence is available for this assessment.</p>
                }
                <p>
                  Projection {{ sourcing.calculation_version }} ·
                  {{ sourcing.created_at | date: 'medium' }}. No supplier selection or procurement
                  is performed.
                </p>
                <h3>Scenarios, alternatives and resilience</h3>
                <p>
                  These remain separate descriptive dimensions below; UNKNOWN means supporting
                  evidence is unavailable.
                </p>
                <h3>Concentration and dependencies</h3>
                <pre>{{ sourcing.upstream_lineage['portfolio'] | json }}</pre>
                <h3>Evidence, contradictions and observed changes</h3>
                <pre>{{ sourcing.evidence_summary | json }}</pre>
                <p role="status">{{ handoffMessage() }}</p>
                <h3>Feasibility dimensions</h3>
                <div class="dimension-grid">
                  @for (dimension of sourcing.dimensions; track dimension['dimension']) {
                    <div class="dimension">
                      <strong>{{ dimension['dimension'] }}</strong>
                      <pre>{{ dimension['value'] | json }}</pre>
                      <small
                        >{{ dimension['classification'] }} ·
                        {{ dimension['evidence_state'] }}</small
                      >
                      <p>{{ dimension['explanation'] }}</p>
                    </div>
                  }
                </div>
                @if (sourcing.research_gaps.length) {
                  <p class="muted">Research gaps: {{ sourcing.research_gaps.join(', ') }}</p>
                }
              } @else {
                <p>No sourcing feasibility projection has been calculated for this assessment.</p>
              }
            </section>
            <section class="panel" aria-labelledby="score-title">
              <div class="section-heading">
                <h2 id="score-title">Score / decision</h2>
                <span>Decision support only; no autonomous product selection</span>
              </div>
              <button type="button" (click)="calculateScore(item)" [disabled]="loading()">
                Calculate Winning Product score
              </button>
              @if (score(); as result) {
                <dl class="economics-summary">
                  <dt>Attractiveness score</dt>
                  <dd>{{ result.overall_score ?? 'Unavailable' }} / 100</dd>
                  <dt>Eligibility</dt>
                  <dd>{{ result.eligibility }}</dd>
                  <dt>Classification</dt>
                  <dd>{{ result.classification }}</dd>
                  <dt>Decision-support label</dt>
                  <dd>{{ result.decision_label }}</dd>
                  <dt>Confidence</dt>
                  <dd>{{ result.confidence }}</dd>
                  <dt>Risk</dt>
                  <dd>{{ result.risk_level }}</dd>
                  <dt>Assessment readiness</dt>
                  <dd>{{ result.assessment_readiness }}</dd>
                </dl>
                <h3>Why this score?</h3>
                <div class="dimension-grid">
                  @for (dimension of result.dimensions; track dimension['dimension']) {
                    <div class="dimension">
                      <strong>{{ dimension['dimension'] }}</strong>
                      <span>{{ dimension['normalized_score'] ?? 'Unavailable' }}</span>
                      <small
                        >Raw input {{ dimension['raw_input'] ?? 'Unavailable' }} · Contribution
                        {{ dimension['weighted_contribution'] ?? 'Unavailable' }}</small
                      >
                      <small
                        >Weight {{ dimension['weight'] }} · {{ dimension['evidence_state'] }}</small
                      >
                      <p>{{ dimension['explanation'] }}</p>
                    </div>
                  }
                </div>
                <p class="muted">
                  Positive drivers: {{ result.positive_drivers.join('; ') || 'None recorded.' }}
                </p>
                <p class="muted">
                  Negative drivers: {{ result.negative_drivers.join('; ') || 'None recorded.' }}
                </p>
                <p class="muted">
                  Evidence improvements:
                  {{ result.improvement_areas.join('; ') || 'None recorded.' }}
                </p>
                <p class="muted">Sensitivity: {{ result.sensitivity | json }}</p>
                <div class="intelligence-actions">
                  <button
                    type="button"
                    (click)="recordDecision(item, 'shortlist')"
                    [disabled]="loading() || result.eligibility === 'BLOCKED'"
                  >
                    Shortlist for human review
                  </button>
                  <button
                    type="button"
                    (click)="recordDecision(item, 'research_more')"
                    [disabled]="loading()"
                  >
                    Request more research
                  </button>
                  <button
                    type="button"
                    (click)="recordDecision(item, 'watch')"
                    [disabled]="loading()"
                  >
                    Watch
                  </button>
                </div>
                <p role="status">{{ decisionMessage() }}</p>
                <h3>Score history</h3>
                @if (scoreHistory().length) {
                  <ul>
                    @for (entry of scoreHistory(); track entry.id) {
                      <li>
                        {{ entry.created_at | date: 'medium' }} ·
                        {{ entry.overall_score ?? 'Unavailable' }} · {{ entry.classification }} ·
                        {{ entry.eligibility }}
                      </li>
                    }
                  </ul>
                } @else {
                  <p>No immutable score history is available yet.</p>
                }
              } @else {
                <p>
                  No score has been calculated for this assessment. Missing evidence remains
                  unavailable.
                </p>
              }
            </section>
          </section>
        }
      }
    </main>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .workspace {
        max-width: 1100px;
        margin: 0 auto;
        padding: 2rem;
      }
      .page-header,
      .section-heading {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
      }
      .panel {
        margin: 1.25rem 0;
        padding: 1.25rem;
        border: 1px solid #cbd9df;
        border-radius: 12px;
        background: #fff;
      }
      .panel form {
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
        align-items: end;
      }
      .panel label {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        min-width: 180px;
      }
      .panel input,
      .panel textarea,
      .panel select {
        padding: 0.6rem;
        border: 1px solid #9bb4bf;
        border-radius: 6px;
      }
      .panel textarea {
        min-height: 5rem;
      }
      .panel button {
        padding: 0.65rem 1rem;
        border: 0;
        border-radius: 6px;
        background: #155e75;
        color: #fff;
        cursor: pointer;
      }
      .panel button:disabled {
        opacity: 0.55;
        cursor: not-allowed;
      }
      .list-item {
        display: flex !important;
        justify-content: space-between;
        width: 100%;
        margin: 0.5rem 0;
        text-align: left;
      }
      .error {
        padding: 1rem;
        background: #fff0f0;
        color: #9b1c1c;
      }
      .eyebrow {
        color: #155e75;
      }
      .lede,
      .muted {
        color: #476b7c;
      }
      dl {
        display: grid;
        grid-template-columns: max-content 1fr;
        gap: 0.4rem 1rem;
      }
      dt {
        font-weight: 600;
      }
      .intelligence-actions {
        display: flex;
        gap: 0.75rem;
        margin-bottom: 1rem;
      }
      .intelligence-output {
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid #d8e3e7;
      }
      .dimension-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.75rem;
      }
      .dimension {
        display: grid;
        gap: 0.25rem;
        padding: 0.75rem;
        border: 1px solid #d8e3e7;
        border-radius: 8px;
      }
      .dimension p {
        margin: 0;
      }
      .candidate-table {
        display: grid;
        gap: 0.5rem;
      }
      pre {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }
      .candidate-row {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 0.5rem;
        padding: 0.65rem;
        border: 1px solid #d8e3e7;
        border-radius: 6px;
      }
    `,
  ],
})
export class ProductOpportunityWorkspaceComponent implements OnInit {
  private readonly service = inject(ProductOpportunityService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly opportunities = signal<ProductOpportunity[]>([]);
  readonly detail = signal<OpportunityDetail | null>(null);
  readonly intelligenceOutputs = signal<IntelligenceOutput[]>([]);
  readonly commercialOutput = signal<CommercialOutput | null>(null);
  readonly sourcingFeasibility = signal<SourcingFeasibilityOutput | null>(null);
  readonly riskEvidence = signal<RiskEvidenceSynthesisOutput | null>(null);
  readonly score = signal<ProductOpportunityScore | null>(null);
  readonly scoreHistory = signal<ProductOpportunityScoreHistory[]>([]);
  readonly comparison = signal<ProductOpportunityComparison | null>(null);
  readonly decisionMessage = signal('');
  readonly handoffMessage = signal('');
  readonly loading = signal(false);
  readonly error = signal('');
  readonly origins = [
    'manual',
    'marketplace_discovery',
    'trend_research',
    'competitor_research',
    'review_research',
    'external_research',
    'ai_research',
    'supplier_discovery',
    'import',
  ];
  name = '';
  concept = '';
  category = '';
  marketplace = '';
  region = '';
  origin = 'manual';
  constraint: OpportunityConstraintPayload = {};

  ngOnInit(): void {
    void this.load();
    const id = this.route.snapshot.paramMap.get('opportunityId');
    if (id) void this.loadDetail(id);
  }

  async load(): Promise<void> {
    this.loading.set(true);
    try {
      this.opportunities.set(await this.service.list());
    } catch {
      this.error.set('Product opportunity data is unavailable.');
    } finally {
      this.loading.set(false);
    }
  }

  async create(): Promise<void> {
    if (!this.name.trim()) return;
    this.loading.set(true);
    this.error.set('');
    try {
      const created = await this.service.create({
        name: this.name.trim(),
        product_concept: this.concept,
        category: this.category,
        target_marketplace: this.marketplace,
        target_region: this.region,
        origin: this.origin,
      });
      this.name = '';
      this.concept = '';
      await this.load();
      await this.select(created.id);
    } catch {
      this.error.set('The product opportunity could not be created.');
    } finally {
      this.loading.set(false);
    }
  }

  async select(id: string): Promise<void> {
    await this.router.navigate(['/intelligence/product-opportunities', id]);
    await this.loadDetail(id);
  }

  async loadDetail(id: string): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const detail = await this.service.get(id);
      this.detail.set(detail);
      this.intelligenceOutputs.set([]);
      this.commercialOutput.set(null);
      this.sourcingFeasibility.set(null);
      this.riskEvidence.set(null);
      this.score.set(null);
      this.scoreHistory.set([]);
      this.comparison.set(null);
      this.decisionMessage.set('');
      this.handoffMessage.set('');
      if (detail.current_assessment_id) {
        try {
          this.riskEvidence.set(
            await this.service.getRiskEvidenceSynthesis(id, detail.current_assessment_id),
          );
        } catch (error: unknown) {
          if (error && typeof error === 'object' && 'status' in error && error.status !== 404) {
            this.error.set('Risk and evidence data is unavailable.');
          }
        }
      }
      if (detail.current_assessment_id) {
        try {
          this.sourcingFeasibility.set(
            await this.service.getSourcingFeasibility(id, detail.current_assessment_id),
          );
        } catch (error: unknown) {
          if (!(error && typeof error === 'object' && 'status' in error && error.status === 404)) {
            this.error.set('Sourcing feasibility data is unavailable.');
          }
        }
      }
      if (detail.current_assessment_id) {
        try {
          this.score.set(await this.service.getScore(id, detail.current_assessment_id));
        } catch (error: unknown) {
          if (!(error && typeof error === 'object' && 'status' in error && error.status === 404)) {
            this.error.set('Winning Product score is unavailable.');
          }
        }
      }
      if (detail.current_assessment_id) {
        try {
          this.scoreHistory.set(await this.service.getScoreHistory(id));
        } catch {
          this.error.set('Winning Product score history is unavailable.');
        }
      }
      if (detail.current_assessment_id) {
        try {
          this.intelligenceOutputs.set(
            await this.service.listIntelligence(id, detail.current_assessment_id),
          );
        } catch {
          /* Intelligence is optional until calculated. */
        }
      }
    } catch {
      this.error.set('The product opportunity could not be loaded.');
    } finally {
      this.loading.set(false);
    }
  }

  async archive(id: string): Promise<void> {
    this.loading.set(true);
    try {
      await this.service.archive(id);
      await this.load();
      await this.loadDetail(id);
    } catch {
      this.error.set('The product opportunity could not be archived.');
    } finally {
      this.loading.set(false);
    }
  }

  async addConstraint(id: string): Promise<void> {
    this.loading.set(true);
    try {
      await this.service.createConstraint(id, this.constraint);
      this.constraint = {};
      await this.loadDetail(id);
    } catch {
      this.error.set('The constraint version could not be created.');
    } finally {
      this.loading.set(false);
    }
  }

  canCompare(): boolean {
    return this.opportunities().filter((item) => Boolean(item.current_assessment_id)).length >= 2;
  }

  async compareOpportunities(): Promise<void> {
    const assessmentIds = this.opportunities()
      .map((item) => item.current_assessment_id)
      .filter((id): id is string => Boolean(id))
      .slice(0, 5);
    if (assessmentIds.length < 2) return;
    this.loading.set(true);
    this.error.set('');
    try {
      this.comparison.set(await this.service.rankScores(assessmentIds));
    } catch {
      this.error.set('Opportunity comparison is unavailable for these assessments.');
    } finally {
      this.loading.set(false);
    }
  }
  async calculateScore(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    this.loading.set(true);
    this.error.set('');
    try {
      this.score.set(await this.service.calculateScore(item.id, item.current_assessment_id));
    } catch {
      this.error.set('Winning Product score could not be calculated.');
    } finally {
      this.loading.set(false);
    }
  }

  async recordDecision(item: OpportunityDetail, action: string): Promise<void> {
    if (!item.current_assessment_id) return;
    this.loading.set(true);
    try {
      await this.service.decide(item.id, item.current_assessment_id, {
        action,
        rationale: `Human decision recorded from the Score / decision workspace: ${action}.`,
      });
      this.decisionMessage.set(`Human decision recorded: ${action}.`);
    } catch {
      this.error.set('The human decision could not be recorded.');
    } finally {
      this.loading.set(false);
    }
  }
  async calculateDemand(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    this.loading.set(true);
    this.error.set('');
    try {
      this.upsertIntelligence(
        await this.service.calculateDemand(item.id, item.current_assessment_id),
      );
    } catch {
      this.error.set('Demand intelligence could not be calculated.');
    } finally {
      this.loading.set(false);
    }
  }

  async calculateCommercial(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    this.loading.set(true);
    this.error.set('');
    try {
      this.commercialOutput.set(
        await this.service.calculateCommercial(item.id, item.current_assessment_id, {
          selling_price: '100',
          selling_price_currency: 'INR',
        }),
      );
    } catch {
      this.error.set('Commercial economics could not be calculated.');
    } finally {
      this.loading.set(false);
    }
  }

  async calculateRiskEvidence(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    this.loading.set(true);
    this.error.set('');
    try {
      this.riskEvidence.set(
        await this.service.calculateRiskEvidenceSynthesis(item.id, item.current_assessment_id),
      );
    } catch {
      this.error.set('Risk and evidence synthesis could not be calculated.');
    } finally {
      this.loading.set(false);
    }
  }

  async calculateSourcing(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    this.loading.set(true);
    this.error.set('');
    try {
      this.sourcingFeasibility.set(
        await this.service.calculateSourcingFeasibility(item.id, item.current_assessment_id),
      );
    } catch {
      this.error.set('Supplier feasibility could not be calculated.');
    } finally {
      this.loading.set(false);
    }
  }
  async handoffSourcing(item: OpportunityDetail, candidate: SourcingCandidate): Promise<void> {
    if (
      !item.current_assessment_id ||
      !candidate.matched_product?.id ||
      !candidate.canonical_supplier_id
    )
      return;
    this.loading.set(true);
    this.error.set('');
    try {
      const result = await this.service.handoffSourcing(
        item.id,
        item.current_assessment_id,
        candidate.matched_product.id,
      );
      this.handoffMessage.set(
        `Internal DD context ${result.context_id} is ready. No supplier contact or external research was started.`,
      );
    } catch {
      this.error.set('The internal due-diligence handoff is unavailable.');
    } finally {
      this.loading.set(false);
    }
  }

  async calculateCompetition(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    this.loading.set(true);
    this.error.set('');
    try {
      this.upsertIntelligence(
        await this.service.calculateCompetition(item.id, item.current_assessment_id),
      );
    } catch {
      this.error.set('Competition intelligence could not be calculated.');
    } finally {
      this.loading.set(false);
    }
  }

  private upsertIntelligence(output: IntelligenceOutput): void {
    this.intelligenceOutputs.update((items) => [
      ...items.filter((item) => item.kind !== output.kind),
      output,
    ]);
  }
}
