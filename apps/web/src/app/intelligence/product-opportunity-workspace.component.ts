import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { EvidenceCardComponent } from '../shared/evidence-card.component';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import { PageHeaderComponent } from '../shared/page-header.component';
import { StatusBadgeComponent } from '../shared/status-badge.component';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import type { BreadcrumbItem, EvidenceDetail, StatusTone } from '../shared/ux-foundation.types';

import {
  CommercialOutput,
  CompetitionProjection,
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
  ReviewWinningProductProjection,
  TrendWinningProductProjection,
  SourcingCandidate,
} from './product-opportunity.service';

@Component({
  selector: 'app-product-opportunity-workspace',
  standalone: true,
  imports: [
    BreadcrumbsComponent,
    DatePipe,
    EmptyStateComponent,
    ErrorStateComponent,
    EvidenceCardComponent,
    FormsModule,
    LoadingStateComponent,
    PageHeaderComponent,
    RouterLink,
    StatusBadgeComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-breadcrumbs [items]="detail() ? detailBreadcrumbs(detail()!) : listBreadcrumbs" />
    <main class="workspace" aria-labelledby="opportunities-title">
      <app-page-header
        [title]="detail() ? detail()!.name : 'Product opportunities'"
        eyebrow="Intelligence / Winning Product"
        [description]="
          detail()
            ? 'Evidence-backed product research context for a human decision.'
            : 'Scan the opportunities you are researching and open one to review its evidence.'
        "
        headingId="opportunities-title"
      >
        <ng-container page-header-actions>
          @if (detail()) {
            <button type="button" class="secondary" (click)="backToList()">
              All opportunities
            </button>
          }
          <a class="secondary action-link" routerLink="/intelligence">Intelligence</a>
        </ng-container>
      </app-page-header>

      @if (error()) {
        <app-error-state
          title="Product opportunity data is unavailable"
          [message]="error()"
          retryLabel="Retry"
          (retry)="retryLoad()"
        />
      }
      @if (loading()) {
        <app-loading-state
          message="Loading product opportunity dataÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦"
        />
      }

      @if (!detail()) {
        <section class="intro-grid" aria-label="Product opportunity overview">
          <div class="intro-copy">
            <p class="eyebrow">Context hub</p>
            <h2>What are you researching?</h2>
            <p>
              Product Opportunities collect the current assessment, evidence strength, risks and
              open research questions. Deep analysis remains in its dedicated workspace.
            </p>
            <a class="primary action-link" routerLink="/intelligence/business-agent">
              Ask VAYUJIT
            </a>
          </div>
          <div class="principle-callout">
            <strong>Human decision support</strong>
            <p>
              A score is not a verdict. Confidence, risk, readiness and eligibility remain separate
              authoritative states.
            </p>
          </div>
        </section>

        <section class="panel create-panel" id="create-opportunity" aria-labelledby="create-title">
          <details>
            <summary id="create-title">Start a product opportunity</summary>
            <p class="muted">
              Create the existing Product Opportunity record; assessment remains a separate governed
              step.
            </p>
            <form (ngSubmit)="create()" class="create-form">
              <label
                >Name <input name="name" [(ngModel)]="name" required minlength="2" maxlength="200"
              /></label>
              <label class="wide"
                >Product concept
                <textarea name="concept" [(ngModel)]="concept" maxlength="10000"></textarea>
              </label>
              <label
                >Category <input name="category" [(ngModel)]="category" maxlength="120"
              /></label>
              <label
                >Marketplace <input name="marketplace" [(ngModel)]="marketplace" maxlength="120"
              /></label>
              <label>Region <input name="region" [(ngModel)]="region" maxlength="120" /></label>
              <label
                >Research origin
                <select name="origin" [(ngModel)]="origin">
                  @for (value of origins; track value) {
                    <option [value]="value">{{ value }}</option>
                  }
                </select>
              </label>
              <button class="primary" type="submit" [disabled]="loading() || !name.trim()">
                Create opportunity
              </button>
            </form>
          </details>
        </section>

        <section class="panel" aria-labelledby="list-title">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Owner-scoped research</p>
              <h2 id="list-title">Your opportunities</h2>
            </div>
            <span class="muted">{{ opportunities().length }} record(s)</span>
          </div>
          @if (opportunities().length === 0 && !loading()) {
            <app-empty-state
              title="No product opportunities yet"
              message="Start a research journey with Business Agent or create a supported Product Opportunity record."
              actionLabel="Start Product Research"
              (action)="focusCreate()"
            />
          } @else {
            <div class="opportunity-list">
              @for (item of opportunities(); track item.id) {
                <article class="opportunity-card">
                  <div class="opportunity-card-heading">
                    <div>
                      <p class="eyebrow">{{ item.category || 'Product opportunity' }}</p>
                      <h3>{{ item.name }}</h3>
                    </div>
                    <app-status-badge
                      [status]="item.lifecycle_status"
                      [label]="statusLabel(item.lifecycle_status)"
                      [tone]="statusTone(item.lifecycle_status)"
                    />
                  </div>
                  <p class="card-description">
                    {{
                      item.description || item.product_concept || 'No concept description recorded.'
                    }}
                  </p>
                  <dl class="compact-facts">
                    <div>
                      <dt>Marketplace</dt>
                      <dd>{{ item.target_marketplace || 'Unknown' }}</dd>
                    </div>
                    <div>
                      <dt>Region</dt>
                      <dd>{{ item.target_region || 'Unknown' }}</dd>
                    </div>
                    <div>
                      <dt>Evidence state</dt>
                      <dd>{{ item.evidence_state || 'UNKNOWN' }}</dd>
                    </div>
                    <div>
                      <dt>Assessment</dt>
                      <dd>{{ item.current_assessment_id ? 'Available' : 'Not started' }}</dd>
                    </div>
                    <div>
                      <dt>Updated</dt>
                      <dd>{{ item.updated_at | date: 'mediumDate' }}</dd>
                    </div>
                  </dl>
                  <div class="card-actions">
                    <button type="button" class="primary" (click)="select(item.id)">
                      Open opportunity
                    </button>
                    @if (item.current_assessment_id) {
                      <span class="muted">Assessment-bound evidence can be inspected next.</span>
                    }
                  </div>
                </article>
              }
            </div>
          }
        </section>

        @if (canCompare()) {
          <section class="panel" aria-labelledby="comparison-title">
            <div class="section-heading">
              <div>
                <p class="eyebrow">Existing scoring endpoint</p>
                <h2 id="comparison-title">Compare assessed opportunities</h2>
              </div>
              <span class="muted">Same-model comparison only</span>
            </div>
            <button
              class="secondary"
              type="button"
              (click)="compareOpportunities()"
              [disabled]="loading()"
            >
              Compare up to five assessments
            </button>
            @if (comparison(); as result) {
              <p class="callout" role="status">
                {{ result.comparability }} ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â {{ result.reason }}
              </p>
              @if (result.ranking?.length) {
                <ol class="ranking-list">
                  @for (entry of result.ranking; track entry.assessment_id) {
                    <li>
                      <strong>Rank {{ entry.rank }}</strong> ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
                      {{ entry.score ?? 'Unavailable' }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
                      {{ entry.classification }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· confidence
                      {{ entry.confidence }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· readiness {{ entry.readiness }}
                    </li>
                  }
                </ol>
              } @else {
                <p class="muted">
                  These assessments are not comparable and receive no ordinary rank.
                </p>
              }
            }
          </section>
        }
      } @else {
        @if (detail(); as item) {
          <section class="context-header panel" aria-labelledby="context-title">
            <div class="context-copy">
              <p class="eyebrow">Current product research context</p>
              <h2 id="context-title">{{ item.name }}</h2>
              <p>
                {{ item.description || item.product_concept || 'No concept description recorded.' }}
              </p>
            </div>
            <div class="context-actions">
              <a class="primary action-link" routerLink="/intelligence/business-agent"
                >Continue research with VAYUJIT</a
              >
              <button
                class="secondary"
                type="button"
                (click)="archive(item.id)"
                [disabled]="loading() || item.lifecycle_status === 'archived'"
              >
                Archive opportunity
              </button>
            </div>
            <dl class="context-facts compact-facts">
              <div>
                <dt>Marketplace</dt>
                <dd>{{ item.target_marketplace || 'Unknown' }}</dd>
              </div>
              <div>
                <dt>Category</dt>
                <dd>{{ item.category || 'Unknown' }}</dd>
              </div>
              <div>
                <dt>Region</dt>
                <dd>{{ item.target_region || 'Unknown' }}</dd>
              </div>
              <div>
                <dt>Origin</dt>
                <dd>{{ item.origin }}</dd>
              </div>
              <div>
                <dt>Research state</dt>
                <dd>{{ item.research_state || 'UNKNOWN' }}</dd>
              </div>
              <div>
                <dt>Evidence state</dt>
                <dd>{{ item.evidence_state || 'UNKNOWN' }}</dd>
              </div>
              <div>
                <dt>Updated</dt>
                <dd>{{ item.updated_at | date: 'medium' }}</dd>
              </div>
            </dl>
          </section>

          <section class="panel" aria-labelledby="assessment-title">
            <div class="section-heading">
              <div>
                <p class="eyebrow">Authoritative assessment</p>
                <h2 id="assessment-title">Assessment summary</h2>
              </div>
              <span class="muted">No frontend scoring or verdicts</span>
            </div>
            @if (score(); as result) {
              <div class="assessment-grid">
                <article class="assessment-card score-card">
                  <p>Opportunity score</p>
                  <strong>{{ result.overall_score ?? 'Unavailable' }}<small>/100</small></strong
                  ><span>{{ result.classification }}</span>
                </article>
                <article class="assessment-card confidence-card">
                  <p>Evidence confidence</p>
                  <app-status-badge
                    [status]="result.confidence"
                    [label]="result.confidence"
                    [tone]="statusTone(result.confidence)"
                  /><span>Strength of available supporting evidence</span>
                </article>
                <article class="assessment-card risk-card">
                  <p>Risk</p>
                  <app-status-badge
                    [status]="result.risk_level"
                    [label]="result.risk_level"
                    [tone]="statusTone(result.risk_level)"
                  /><span>Authoritative risk state</span>
                </article>
                <article class="assessment-card readiness-card">
                  <p>Research readiness</p>
                  <app-status-badge
                    [status]="result.assessment_readiness"
                    [label]="result.assessment_readiness"
                    [tone]="statusTone(result.assessment_readiness)"
                  /><span>Assessment completeness state</span>
                </article>
                <article class="assessment-card eligibility-card">
                  <p>Eligibility</p>
                  <app-status-badge
                    [status]="result.eligibility"
                    [label]="result.eligibility"
                    [tone]="statusTone(result.eligibility)"
                  /><span>Governed eligibility state</span>
                </article>
              </div>
              <p class="semantic-note">
                A high score does not imply high confidence, low risk, or a launch decision.
              </p>
              <section class="subsection" aria-labelledby="score-components-title">
                <div class="section-heading">
                  <h3 id="score-components-title">How this score was formed</h3>
                  <span class="muted">Returned components only</span>
                </div>
                @if (result.dimensions.length) {
                  <div class="dimension-grid">
                    @for (dimension of result.dimensions; track dimension['dimension']) {
                      <article class="dimension">
                        <strong>{{ dimension['dimension'] }}</strong
                        ><span>{{ dimension['normalized_score'] ?? 'Unavailable' }}</span
                        ><small
                          >Raw input
                          {{ dimension['raw_input'] ?? 'Unavailable' }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
                          Contribution
                          {{ dimension['weighted_contribution'] ?? 'Unavailable' }}</small
                        >
                        <p>{{ dimension['explanation'] || 'No explanation returned.' }}</p>
                      </article>
                    }
                  </div>
                } @else {
                  <p class="muted">No score components were returned.</p>
                }
                <dl class="driver-list">
                  @if (result.positive_drivers.length) {
                    <div>
                      <dt>Positive drivers</dt>
                      <dd>{{ result.positive_drivers.join('; ') }}</dd>
                    </div>
                  }
                  @if (result.negative_drivers.length) {
                    <div>
                      <dt>Negative drivers</dt>
                      <dd>{{ result.negative_drivers.join('; ') }}</dd>
                    </div>
                  }
                  @if (result.improvement_areas.length) {
                    <div>
                      <dt>Evidence improvements</dt>
                      <dd>{{ result.improvement_areas.join('; ') }}</dd>
                    </div>
                  }
                </dl>
              </section>
            } @else {
              <app-empty-state
                title="Assessment summary not loaded"
                message="Load the existing Winning Product assessment when you are ready. Missing intelligence is not treated as a negative score."
              >
                <button
                  type="button"
                  class="secondary"
                  (click)="loadScore(item)"
                  [disabled]="loading()"
                >
                  Load authoritative assessment
                </button>
              </app-empty-state>
            }
          </section>

          @if (!item.current_assessment_id) {
            <app-empty-state
              title="Assessment has not started"
              message="Add a supported constraint version and assessment before reviewing score or intelligence."
              actionLabel="Continue research with VAYUJIT"
              (action)="openBusinessAgent()"
            />
          }

          <section class="panel" aria-labelledby="overview-title">
            <div class="section-heading">
              <div>
                <p class="eyebrow">Context</p>
                <h2 id="overview-title">What we know</h2>
              </div>
              <span class="muted">Only persisted opportunity data</span>
            </div>
            <div class="overview-grid">
              <div>
                <h3>Research objective</h3>
                <p>{{ item.research_objective || 'No research objective recorded.' }}</p>
              </div>
              <div>
                <h3>Customer / business context</h3>
                <p>
                  {{ item.customer_segment || 'Customer segment not recorded.' }}
                  ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
                  {{ item.business_model || 'Business model not recorded.' }}
                </p>
              </div>
              <div>
                <h3>Brand strategy</h3>
                <p>{{ item.brand_strategy || 'No brand strategy recorded.' }}</p>
              </div>
              <div>
                <h3>Tags</h3>
                <p>{{ (item.tags || []).length ? item.tags.join(', ') : 'No tags recorded.' }}</p>
              </div>
            </div>
          </section>

          <section class="panel" aria-labelledby="areas-title">
            <div class="section-heading">
              <div>
                <p class="eyebrow">Evidence areas</p>
                <h2 id="areas-title">Research areas</h2>
              </div>
              <span class="muted">Deep analysis remains in dedicated workspaces</span>
            </div>
            <div class="research-grid">
              <article class="research-card trend-area">
                <div class="research-heading">
                  <h3>Trend</h3>
                  <a routerLink="/intelligence/trends">Open Trend Intelligence</a>
                </div>
                @if (trendProjection(); as trend) {
                  <dl class="compact-facts">
                    <div>
                      <dt>Projection state</dt>
                      <dd>{{ trend.source_state }}</dd>
                    </div>
                    <div>
                      <dt>Readiness</dt>
                      <dd>{{ trend.readiness }}</dd>
                    </div>
                    <div>
                      <dt>Confidence</dt>
                      <dd>{{ displayValue(trend.evidence_confidence['state']) }}</dd>
                    </div>
                    <div>
                      <dt>Freshness</dt>
                      <dd>{{ displayValue(trend.freshness['state']) }}</dd>
                    </div>
                    <div>
                      <dt>Signals / momentum</dt>
                      <dd>
                        {{ trend.signal_summaries.length }} / {{ trend.momentum_summaries.length }}
                      </dd>
                    </div>
                  </dl>
                  <p class="semantic-note">
                    Observed signal change is not direct evidence of sales, revenue, or future
                    demand.
                  </p>
                } @else {
                  <p class="muted">Trend projection not loaded or not researched.</p>
                  <button
                    class="secondary"
                    type="button"
                    (click)="loadTrend(item)"
                    [disabled]="loading()"
                  >
                    Load Trend evidence
                  </button>
                }
              </article>
              <article class="research-card">
                <div class="research-heading">
                  <h3>Competition Intelligence</h3>
                  <a routerLink="/intelligence/competitors">Open Competitor Intelligence</a>
                </div>
                @if (competitionProjection(); as projection) {
                  <dl class="compact-facts">
                    <div>
                      <dt>Source state</dt>
                      <dd>{{ projection.source_state }}</dd>
                    </div>
                    <div>
                      <dt>Authoritative cohort</dt>
                      <dd>{{ projection.projection.cohort?.authoritative_count ?? 'UNKNOWN' }}</dd>
                    </div>
                    <div>
                      <dt>Freshness</dt>
                      <dd>{{ projection.freshness_state }}</dd>
                    </div>
                    <div>
                      <dt>Contradictions</dt>
                      <dd>{{ projection.contradiction_state }}</dd>
                    </div>
                    <div>
                      <dt>Research gaps</dt>
                      <dd>{{ projection.research_gaps.length }}</dd>
                    </div>
                  </dl>
                } @else {
                  <p class="muted">Competitor projection not loaded or not researched.</p>
                  <button
                    class="secondary"
                    type="button"
                    (click)="loadCompetition(item)"
                    [disabled]="loading()"
                  >
                    Load competition evidence
                  </button>
                }
              </article>
              <article class="research-card">
                <div class="research-heading">
                  <h3>Customers / reviews</h3>
                  <a routerLink="/intelligence/reviews">Open Customer Reviews</a>
                </div>
                @if (reviewProjection(); as review) {
                  <dl class="compact-facts">
                    <div>
                      <dt>Readiness</dt>
                      <dd>{{ review.readiness }}</dd>
                    </div>
                    <div>
                      <dt>Reviews</dt>
                      <dd>{{ displayValue(review.cohort['review_count']) }}</dd>
                    </div>
                    <div>
                      <dt>Rated reviews</dt>
                      <dd>{{ displayValue(review.cohort['rated_review_count']) }}</dd>
                    </div>
                    <div>
                      <dt>Source state</dt>
                      <dd>{{ review.source_state }}</dd>
                    </div>
                    <div>
                      <dt>Freshness</dt>
                      <dd>{{ displayValue(review.freshness['state']) }}</dd>
                    </div>
                  </dl>
                  <p class="muted">
                    Reviews are customer-feedback evidence, not sales or conversion evidence.
                  </p>
                } @else {
                  <p class="muted">Customer-feedback projection not loaded or not researched.</p>
                  <button
                    class="secondary"
                    type="button"
                    (click)="loadReview(item)"
                    [disabled]="loading()"
                  >
                    Load customer evidence
                  </button>
                }
              </article>
              <article class="research-card">
                <div class="research-heading">
                  <h3>Suppliers / sourcing</h3>
                  <a routerLink="/intelligence/sourcing">View Suppliers</a>
                </div>
                @if (sourcingFeasibility(); as sourcing) {
                  <dl class="compact-facts">
                    <div>
                      <dt>Feasibility</dt>
                      <dd>{{ sourcing.summary['feasibility_state'] }}</dd>
                    </div>
                    <div>
                      <dt>Discovered / matched</dt>
                      <dd>
                        {{ sourcing.summary['supplier_availability']?.discovered ?? 'UNKNOWN' }} /
                        {{ sourcing.summary['supplier_availability']?.matched ?? 'UNKNOWN' }}
                      </dd>
                    </div>
                    <div>
                      <dt>Eligible / DD complete</dt>
                      <dd>
                        {{ sourcing.summary['supplier_availability']?.eligible ?? 'UNKNOWN' }} /
                        {{ sourcing.summary['supplier_availability']?.dd_complete ?? 'UNKNOWN' }}
                      </dd>
                    </div>
                    <div>
                      <dt>Confidence</dt>
                      <dd>{{ sourcing.summary['confidence'] }}</dd>
                    </div>
                    <div>
                      <dt>Gaps</dt>
                      <dd>{{ sourcing.research_gaps.length }}</dd>
                    </div>
                  </dl>
                  <div class="card-actions">
                    <a class="secondary action-link" routerLink="/intelligence/due-diligence"
                      >Review Due Diligence</a
                    ><a class="secondary action-link" routerLink="/intelligence/sourcing-scenarios"
                      >Compare Sourcing Scenarios</a
                    >
                  </div>
                  @if (sourcing.candidates.length) {
                    <h4>Candidate evidence</h4>
                    <ul class="candidate-list">
                      @for (
                        candidate of sourcing.candidates;
                        track candidate.matched_product?.id || candidate.supplier?.id
                      ) {
                        <li>
                          <strong>{{ candidate.supplier?.name || 'UNKNOWN supplier' }}</strong>
                          <span
                            >{{ candidate.country || 'UNKNOWN' }} ·
                            {{ displayValue(candidate.due_diligence) }} ·
                            {{ candidate.freshness || 'UNKNOWN' }} ·
                            {{ candidate.match_state || 'UNKNOWN' }}</span
                          >
                        </li>
                      }
                    </ul>
                  }
                  <p class="muted">
                    Concentration and dependencies:
                    {{ displayValue(sourcing.upstream_lineage['portfolio']) }}
                  </p>
                  <p class="muted">
                    Evidence, contradictions: {{ displayValue(sourcing.evidence_summary) }}
                  </p>
                } @else {
                  <p class="muted">Supplier evidence not loaded or not researched.</p>
                  <button
                    class="secondary"
                    type="button"
                    (click)="loadSourcing(item)"
                    [disabled]="loading()"
                  >
                    Load supplier evidence
                  </button>
                }
              </article>
              <article class="research-card">
                <div class="research-heading">
                  <h3>Economics</h3>
                  <span class="muted">Assessment-bound</span>
                </div>
                @if (commercialOutput(); as commercial) {
                  <dl class="compact-facts">
                    <div>
                      <dt>Price evidence</dt>
                      <dd>{{ commercial.evidence_summary['prices'] ? 'Available' : 'Unknown' }}</dd>
                    </div>
                    <div>
                      <dt>Selling price</dt>
                      <dd>
                        {{ displayValue(commercial.economics['selling_price']) }}
                        {{ displayValue(commercial.economics['currency']) }}
                      </dd>
                    </div>
                    <div>
                      <dt>Landed cost</dt>
                      <dd>{{ displayValue(commercial.economics['landed_cost_per_unit']) }}</dd>
                    </div>
                    <div>
                      <dt>Contribution margin</dt>
                      <dd>
                        {{ displayValue(commercial.economics['contribution_margin_percent']) }}
                      </dd>
                    </div>
                    <div>
                      <dt>Gaps</dt>
                      <dd>{{ commercial.research_gaps.length }}</dd>
                    </div>
                  </dl>
                  <p class="muted">
                    No frontend profitability or landed-cost calculations are performed.
                  </p>
                } @else {
                  <p class="muted">Commercial evidence is not loaded or not available.</p>
                  <button
                    class="secondary"
                    type="button"
                    (click)="loadCommercial(item)"
                    [disabled]="loading()"
                  >
                    Load economics
                  </button>
                }
              </article>
              <article class="research-card">
                <div class="research-heading">
                  <h3>Risk / completeness</h3>
                  <span class="muted">Separate from score</span>
                </div>
                @if (riskEvidence(); as synthesis) {
                  <dl class="compact-facts">
                    <div>
                      <dt>Readiness</dt>
                      <dd>{{ displayValue(synthesis.summary['assessment_readiness']) }}</dd>
                    </div>
                    <div>
                      <dt>Confidence</dt>
                      <dd>{{ displayValue(synthesis.summary['confidence']) }}</dd>
                    </div>
                    <div>
                      <dt>Material risks</dt>
                      <dd>{{ displayValue(synthesis.summary['risk_count']) }}</dd>
                    </div>
                    <div>
                      <dt>Research gaps</dt>
                      <dd>{{ synthesis.research_gaps.length }}</dd>
                    </div>
                  </dl>
                } @else {
                  <p class="muted">Risk and evidence synthesis is not loaded.</p>
                  <button
                    class="secondary"
                    type="button"
                    (click)="loadRiskEvidence(item)"
                    [disabled]="loading()"
                  >
                    Load risk evidence
                  </button>
                }
              </article>
            </div>
          </section>

          <section class="panel" aria-labelledby="evidence-title">
            <div class="section-heading">
              <div>
                <p class="eyebrow">Inspect support</p>
                <h2 id="evidence-title">Evidence</h2>
              </div>
              <span class="muted">Observed, derived and technical states remain authoritative</span>
            </div>
            @if (evidenceCards().length) {
              <div class="evidence-grid">
                @for (card of evidenceCards(); track card.title) {
                  <app-evidence-card
                    [title]="card.title"
                    [classification]="card.classification"
                    [summary]="card.summary"
                    [source]="card.source"
                    [observedAt]="card.observedAt"
                    [details]="card.details"
                  />
                }
              </div>
            } @else {
              <p class="muted">No projection evidence has been loaded for this opportunity yet.</p>
            }
          </section>

          @if (researchGaps().length || contradictions().length) {
            <section class="panel" aria-labelledby="unknowns-title">
              <div class="section-heading">
                <div>
                  <p class="eyebrow">Human review</p>
                  <h2 id="unknowns-title">What we still do not know</h2>
                </div>
                <span class="muted">Returned gaps and contradictions only</span>
              </div>
              @if (researchGaps().length) {
                <div class="callout warning">
                  <h3>Research gaps</h3>
                  <ul>
                    @for (gap of researchGaps(); track gap) {
                      <li>{{ gap }}</li>
                    }
                  </ul>
                </div>
              }
              @if (contradictions().length) {
                <div class="callout danger">
                  <h3>Conflicting evidence</h3>
                  <ul>
                    @for (item of contradictions(); track item) {
                      <li>{{ item }}</li>
                    }
                  </ul>
                  <button class="secondary" type="button" (click)="focusEvidence()">
                    Review evidence
                  </button>
                </div>
              }
            </section>
          }

          <section class="panel" aria-labelledby="actions-title">
            <div class="section-heading">
              <div>
                <p class="eyebrow">Supported workflows</p>
                <h2 id="actions-title">Continue research</h2>
              </div>
              <span class="muted">No autonomous launch or procurement actions</span>
            </div>
            <div class="action-grid">
              @if (item.current_assessment_id) {
                <button
                  class="secondary"
                  type="button"
                  (click)="calculateTrendProjection(item)"
                  [disabled]="loading()"
                >
                  Refresh Trend projection
                </button>
                <button
                  class="secondary"
                  type="button"
                  (click)="calculateCompetition(item)"
                  [disabled]="loading()"
                >
                  Refresh Competition projection
                </button>
                <button
                  class="secondary"
                  type="button"
                  (click)="calculateReviewProjection(item)"
                  [disabled]="loading()"
                >
                  Refresh Customer projection
                </button>
                <button
                  class="secondary"
                  type="button"
                  (click)="calculateScore(item)"
                  [disabled]="loading()"
                >
                  Calculate Winning Product assessment
                </button>
                <button
                  class="secondary"
                  type="button"
                  (click)="calculateDemand(item)"
                  [disabled]="loading()"
                >
                  Calculate demand intelligence
                </button>
                <button
                  class="secondary"
                  type="button"
                  (click)="calculateCommercial(item)"
                  [disabled]="loading()"
                >
                  Calculate economics
                </button>
                <button
                  class="secondary"
                  type="button"
                  (click)="calculateRiskEvidence(item)"
                  [disabled]="loading()"
                >
                  Synthesize risk evidence
                </button>
                <button
                  class="secondary"
                  type="button"
                  (click)="calculateSourcing(item)"
                  [disabled]="loading()"
                >
                  Assess sourcing feasibility
                </button>
              } @else {
                <p class="muted">
                  Create a constraint and assessment before running assessment-bound workflows.
                </p>
              }
              <a class="primary action-link" routerLink="/intelligence/business-agent"
                >Ask VAYUJIT</a
              >
            </div>
          </section>

          <section class="panel" aria-labelledby="history-title">
            <div class="section-heading">
              <div>
                <p class="eyebrow">Versioned assessment</p>
                <h2 id="history-title">History</h2>
              </div>
              <span class="muted">No new history model or request fan-out</span>
            </div>
            @if (scoreHistory().length) {
              <ul class="history-list">
                @for (entry of scoreHistory(); track entry.id) {
                  <li>
                    <span>{{ entry.created_at | date: 'medium' }}</span
                    ><strong>{{ entry.overall_score ?? 'Unavailable' }}</strong
                    ><span>{{ entry.classification }}</span
                    ><span>{{ entry.eligibility }}</span>
                  </li>
                }
              </ul>
            } @else {
              <p class="muted">No immutable score history is loaded for this opportunity.</p>
            }
            @if (item.current_assessment_id) {
              <button
                class="secondary"
                type="button"
                (click)="loadHistory(item)"
                [disabled]="loading()"
              >
                Load score history
              </button>
            }
          </section>

          <section class="panel" aria-labelledby="decision-title">
            <div class="section-heading">
              <div>
                <p class="eyebrow">Human decision</p>
                <h2 id="decision-title">Record a governed next action</h2>
              </div>
              <span class="muted">The UI does not create a product verdict</span>
            </div>
            @if (score(); as result) {
              <p class="muted">
                Available actions are persisted through the existing decision endpoint.
              </p>
              <div class="action-grid">
                <button
                  class="secondary"
                  type="button"
                  (click)="recordDecision(item, 'research_more')"
                  [disabled]="loading()"
                >
                  Request more research</button
                ><button
                  class="secondary"
                  type="button"
                  (click)="recordDecision(item, 'watch')"
                  [disabled]="loading()"
                >
                  Watch</button
                ><button
                  class="primary"
                  type="button"
                  (click)="recordDecision(item, 'shortlist')"
                  [disabled]="loading() || result.eligibility === 'BLOCKED'"
                >
                  Shortlist for human review
                </button>
              </div>
            } @else {
              <p class="muted">
                Load the authoritative assessment before recording a score-bound decision.
              </p>
            }
            @if (decisionMessage()) {
              <p class="callout" role="status">{{ decisionMessage() }}</p>
            }
          </section>
        }
      }
    </main>
  `,
  styleUrl: './product-opportunity-workspace.css',
})
export class ProductOpportunityWorkspaceComponent implements OnInit {
  private readonly service = inject(ProductOpportunityService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly opportunities = signal<ProductOpportunity[]>([]);
  readonly detail = signal<OpportunityDetail | null>(null);
  readonly intelligenceOutputs = signal<IntelligenceOutput[]>([]);
  readonly competitionProjection = signal<CompetitionProjection | null>(null);
  readonly trendProjection = signal<TrendWinningProductProjection | null>(null);
  readonly commercialOutput = signal<CommercialOutput | null>(null);
  readonly sourcingFeasibility = signal<SourcingFeasibilityOutput | null>(null);
  readonly riskEvidence = signal<RiskEvidenceSynthesisOutput | null>(null);
  readonly score = signal<ProductOpportunityScore | null>(null);
  readonly reviewProjection = signal<ReviewWinningProductProjection | null>(null);
  readonly scoreHistory = signal<ProductOpportunityScoreHistory[]>([]);
  readonly comparison = signal<ProductOpportunityComparison | null>(null);
  readonly decisionMessage = signal('');
  readonly handoffMessage = signal('');
  readonly loading = signal(false);
  readonly error = signal('');
  readonly listBreadcrumbs: BreadcrumbItem[] = [
    { label: 'Dashboard', url: '/dashboard' },
    { label: 'Intelligence', url: '/intelligence' },
    { label: 'Product opportunities' },
  ];
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
      this.detail.set(await this.service.get(id));
      this.resetResearchState();
    } catch {
      this.error.set('The product opportunity could not be loaded.');
    } finally {
      this.loading.set(false);
    }
  }

  private resetResearchState(): void {
    this.intelligenceOutputs.set([]);
    this.competitionProjection.set(null);
    this.trendProjection.set(null);
    this.commercialOutput.set(null);
    this.sourcingFeasibility.set(null);
    this.riskEvidence.set(null);
    this.score.set(null);
    this.reviewProjection.set(null);
    this.scoreHistory.set([]);
    this.comparison.set(null);
    this.decisionMessage.set('');
    this.handoffMessage.set('');
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
  async retryLoad(): Promise<void> {
    const id = this.route.snapshot.paramMap.get('opportunityId');
    if (id) await this.loadDetail(id);
    else await this.load();
  }

  backToList(): void {
    this.detail.set(null);
    void this.router.navigate(['/intelligence/product-opportunities']);
    void this.load();
  }

  focusCreate(): void {
    document
      .getElementById('create-opportunity')
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  focusEvidence(): void {
    document
      .getElementById('evidence-title')
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  openBusinessAgent(): void {
    void this.router.navigate(['/intelligence/business-agent']);
  }

  detailBreadcrumbs(item: OpportunityDetail): BreadcrumbItem[] {
    return [
      { label: 'Dashboard', url: '/dashboard' },
      { label: 'Intelligence', url: '/intelligence' },
      { label: 'Product opportunities', url: '/intelligence/product-opportunities' },
      { label: item.name },
    ];
  }

  statusLabel(value: string): string {
    return value.replaceAll('_', ' ');
  }

  statusTone(value: string): StatusTone {
    const normalized = value.toLowerCase();
    if (
      ['completed', 'available', 'eligible', 'ready', 'current', 'low', 'passed'].some((item) =>
        normalized.includes(item),
      )
    )
      return 'success';
    if (
      ['blocked', 'high', 'failed', 'rejected', 'error', 'stale'].some((item) =>
        normalized.includes(item),
      )
    )
      return 'danger';
    if (
      ['partial', 'moderate', 'warning', 'required', 'insufficient', 'unknown'].some((item) =>
        normalized.includes(item),
      )
    )
      return 'warning';
    if (
      ['researching', 'started', 'active', 'pending', 'in_progress'].some((item) =>
        normalized.includes(item),
      )
    )
      return 'info';
    return 'neutral';
  }

  displayValue(value: unknown): string {
    if (value === null || value === undefined || value === '') return 'UNKNOWN';
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean')
      return String(value);
    try {
      return JSON.stringify(value);
    } catch {
      return 'Unavailable';
    }
  }

  async loadScore(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    await this.readSection(
      'score',
      () => this.service.getScore(item.id, item.current_assessment_id!),
      (value) => this.score.set(value),
    );
  }

  async loadTrend(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    await this.readSection(
      'Trend evidence',
      () => this.service.getTrendProjection(item.id, item.current_assessment_id!),
      (value) => this.trendProjection.set(value),
    );
  }

  async loadCompetition(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    await this.readSection(
      'competition evidence',
      () => this.service.getCompetitionProjection(item.id, item.current_assessment_id!),
      (value) => this.competitionProjection.set(value),
    );
  }

  async loadReview(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    await this.readSection(
      'customer evidence',
      () => this.service.getReviewProjection(item.id, item.current_assessment_id!),
      (value) => this.reviewProjection.set(value),
    );
  }

  async loadSourcing(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    await this.readSection(
      'supplier evidence',
      () => this.service.getSourcingFeasibility(item.id, item.current_assessment_id!),
      (value) => this.sourcingFeasibility.set(value),
    );
  }

  async loadCommercial(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    await this.readSection(
      'economics',
      () => this.service.getCommercial(item.id, item.current_assessment_id!),
      (value) => this.commercialOutput.set(value),
    );
  }

  async loadRiskEvidence(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    await this.readSection(
      'risk evidence',
      () => this.service.getRiskEvidenceSynthesis(item.id, item.current_assessment_id!),
      (value) => this.riskEvidence.set(value),
    );
  }

  async loadHistory(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    await this.readSection(
      'score history',
      () => this.service.getScoreHistory(item.id),
      (value) => this.scoreHistory.set(value),
    );
  }

  private async readSection<T>(
    label: string,
    request: () => Promise<T>,
    apply: (value: T) => void,
  ): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      apply(await request());
    } catch (error: unknown) {
      const status = (error as { status?: number })?.status;
      if (status !== 404) this.error.set(`${label} is unavailable.`);
    } finally {
      this.loading.set(false);
    }
  }

  evidenceCards(): Array<{
    title: string;
    classification: string;
    summary: string;
    source: string;
    observedAt: string;
    details: EvidenceDetail[];
  }> {
    const cards: Array<{
      title: string;
      classification: string;
      summary: string;
      source: string;
      observedAt: string;
      details: EvidenceDetail[];
    }> = [];
    const trend = this.trendProjection();
    if (trend)
      cards.push({
        title: 'Trend projection',
        classification: trend.source_state || 'UNKNOWN',
        summary: `${trend.signal_summaries.length} signal summary(ies), ${trend.momentum_summaries.length} momentum summary(ies).`,
        source: 'Trend ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ Winning Product projection',
        observedAt: trend.created_at,
        details: this.trendDetails(trend),
      });
    const competition = this.competitionProjection();
    if (competition)
      cards.push({
        title: 'Competition projection',
        classification: competition.source_state || 'UNKNOWN',
        summary: `${this.displayValue(competition.projection.cohort?.authoritative_count)} authoritative competitor record(s).`,
        source: 'Competitor Intelligence projection',
        observedAt: '',
        details: [
          { label: 'Freshness', value: competition.freshness_state },
          { label: 'Contradictions', value: competition.contradiction_state },
          { label: 'Research gaps', value: competition.research_gaps.length },
        ],
      });
    const review = this.reviewProjection();
    if (review)
      cards.push({
        title: 'Customer-feedback projection',
        classification: review.source_state || 'UNKNOWN',
        summary: `${this.displayValue(review.cohort['review_count'])} review(s) in the returned cohort.`,
        source: 'Review Intelligence projection',
        observedAt: review.created_at,
        details: [
          { label: 'Readiness', value: review.readiness },
          { label: 'Freshness', value: this.displayValue(review.freshness['state']) },
          { label: 'Contradictions', value: review.contradictions.length },
        ],
      });
    const supplier = this.sourcingFeasibility();
    if (supplier)
      cards.push({
        title: 'Supplier feasibility projection',
        classification: supplier.summary['feasibility_state'] || 'UNKNOWN',
        summary: `${this.displayValue(supplier.summary['supplier_availability']?.matched)} matched supplier candidate(s).`,
        source: 'Supplier and sourcing feasibility projection',
        observedAt: supplier.created_at,
        details: [
          { label: 'Confidence', value: supplier.summary['confidence'] },
          { label: 'Scenario availability', value: supplier.summary['scenario_availability'] },
          { label: 'Research gaps', value: supplier.research_gaps.length },
        ],
      });
    return cards;
  }

  trendDetails(trend: TrendWinningProductProjection): EvidenceDetail[] {
    return [
      { label: 'Readiness', value: trend.readiness },
      { label: 'Confidence', value: this.displayValue(trend.evidence_confidence['state']) },
      { label: 'Freshness', value: this.displayValue(trend.freshness['state']) },
      { label: 'Contradictions', value: trend.contradictions.length },
      { label: 'Research gaps', value: trend.research_gaps.length },
    ];
  }

  researchGaps(): string[] {
    const values: unknown[] = [];
    const trend = this.trendProjection();
    if (trend) values.push(...trend.research_gaps);
    const competition = this.competitionProjection();
    if (competition) values.push(...competition.research_gaps);
    const review = this.reviewProjection();
    if (review) values.push(...review.research_gaps);
    const supplier = this.sourcingFeasibility();
    if (supplier) values.push(...supplier.research_gaps);
    const commercial = this.commercialOutput();
    if (commercial) values.push(...commercial.research_gaps);
    const risk = this.riskEvidence();
    if (risk) values.push(...risk.research_gaps);
    return this.uniqueDisplayValues(values);
  }

  contradictions(): string[] {
    const values: unknown[] = [];
    const trend = this.trendProjection();
    if (trend) values.push(...trend.contradictions);
    const review = this.reviewProjection();
    if (review) values.push(...review.contradictions);
    return this.uniqueDisplayValues(values);
  }

  private uniqueDisplayValues(values: unknown[]): string[] {
    return [
      ...new Set(
        values.map((value) => this.displayValue(value)).filter((value) => value !== 'UNKNOWN'),
      ),
    ];
  }
  async calculateTrendProjection(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    this.loading.set(true);
    this.error.set('');
    try {
      this.trendProjection.set(
        await this.service.calculateTrendProjection(item.id, item.current_assessment_id),
      );
    } catch {
      this.error.set('Trend evidence projection could not be calculated.');
    } finally {
      this.loading.set(false);
    }
  }

  async calculateReviewProjection(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) return;
    this.loading.set(true);
    this.error.set('');
    try {
      this.reviewProjection.set(
        await this.service.calculateReviewProjection(item.id, item.current_assessment_id),
      );
    } catch {
      this.error.set('Review Intelligence projection could not be calculated.');
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
      this.competitionProjection.set(
        await this.service.getCompetitionProjection(item.id, item.current_assessment_id),
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
