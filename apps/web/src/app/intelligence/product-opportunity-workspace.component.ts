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
import { CommerceJourneyContextComponent } from '../commerce-journey-context.component';
import { BusinessAgentService } from './business-agent.service';

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
  ProductResearchResponse,
  ResearchCandidate,
  ResearchResults,
  SourcingFeasibilityOutput,
  RiskEvidenceSynthesisOutput,
  SourcingEconomicsProjection,
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
    CommerceJourneyContextComponent,
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
      <app-commerce-journey-context />
      @if (!detail()) {
        @if (researchResults(); as results) {
          <section class="panel research-results" aria-labelledby="research-results-title">
            <div class="section-heading">
              <div>
                <p class="eyebrow">Research complete</p>
                <h2 id="research-results-title">Your product research results</h2>
                <p>
                  {{ results.summary.total }} meaningful products found for this goal.
                  @if (results.historical_opportunities) {
                    <span class="muted">
                      {{ results.historical_opportunities }} previous opportunities are kept in
                      history.
                    </span>
                  }
                </p>
                @if (results.goal_context; as goal) {
                  <div class="research-goal-context">
                    <strong>Current research goal</strong>
                    <p>{{ goal.summary }}</p>
                    @if (!goal.confirmed) {
                      <span class="muted">Goal context is not confirmed yet.</span>
                    }
                  </div>
                }
                <div class="research-summary-facts" aria-label="Research summary">
                  <div>
                    <strong>{{ results.summary.total }}</strong
                    ><span>Products found</span>
                  </div>
                  <div>
                    <strong>{{ results.summary.ready_for_comparison }}</strong
                    ><span>Ready to compare</span>
                  </div>
                  <div>
                    <strong>{{ results.summary.needs_more_research }}</strong
                    ><span>Need more research</span>
                  </div>
                  <div>
                    <strong>{{ results.summary.insufficient_evidence || 0 }}</strong
                    ><span>Insufficient evidence</span>
                  </div>
                </div>
              </div>
              <app-status-badge
                [status]="results.status"
                [label]="statusLabel(results.status)"
                [tone]="statusTone(results.status)"
              />
            </div>
            @if (isFixtureResults(results)) {
              <p class="trust-banner" role="note">
                Local demo data - not live market evidence. Product identities are useful for
                exploring the workflow; prices, demand, supplier availability, and market claims
                remain unverified until authoritative evidence is loaded.
              </p>
            }
            @if (results.candidates.length === 0) {
              <app-empty-state
                title="No meaningful product opportunities are available yet."
                message="Research has not produced a meaningful product identity for the current goal. Continue research or adjust the goal constraints."
                actionLabel="Ask VAYUJIT"
                (action)="openBusinessAgent()"
              />
            } @else {
              <div class="candidate-grid" aria-label="Product candidates">
                @for (candidate of orderedCandidates(results.candidates); track candidate.id) {
                  <article class="candidate-card" [class.selected]="isSelected(candidate.id)">
                    <div class="candidate-heading">
                      <div>
                        <p class="eyebrow">{{ candidate.category || 'Product opportunity' }}</p>
                        <h3>{{ candidate.name }}</h3>
                      </div>
                      <app-status-badge
                        [status]="candidate.candidate_state"
                        [label]="statusLabel(candidate.candidate_state)"
                        [tone]="statusTone(candidate.candidate_state)"
                      />
                    </div>
                    @if (candidateImage(candidate); as image) {
                      <img class="candidate-image" [src]="image" [alt]="candidate.name" />
                    } @else {
                      <div
                        class="product-image-placeholder"
                        role="img"
                        aria-label="Product image not available"
                      >
                        Product image not available
                      </div>
                    }
                    <p class="candidate-description">{{ candidateDescription(candidate) }}</p>
                    <p class="candidate-category">
                      {{ candidate.category || 'Category not established' }}
                      @if (candidate.subcategory) {
                        <span> → {{ candidate.subcategory }}</span>
                      }
                    </p>
                    <dl class="candidate-primary-facts">
                      <div>
                        <dt>Readiness</dt>
                        <dd>{{ readinessLabel(candidate) }}</dd>
                      </div>
                      <div>
                        <dt>Goal fit</dt>
                        <dd>{{ goalFitLabel(candidate) }}</dd>
                      </div>
                      <div>
                        <dt>Trust</dt>
                        <dd>{{ candidateTrustLabel(candidate) }}</dd>
                      </div>
                      <div>
                        <dt>Observed price</dt>
                        <dd>{{ observedPrice(candidate) }}</dd>
                      </div>
                    </dl>
                    <h4>Why this product surfaced</h4>
                    <ul>
                      @for (item of candidateReasons(candidate); track item) {
                        <li>{{ item }}</li>
                      }
                    </ul>
                    <p class="candidate-evidence-summary">
                      <strong>Evidence:</strong> {{ evidenceLabel(candidate) }}.
                      <span>{{ candidateEvidenceSummary(candidate) }}</span>
                    </p>
                    @if (candidate.risks.length) {
                      <p class="candidate-risk">
                        <strong>Risks:</strong> {{ candidate.risks.join('; ') }}
                      </p>
                    }
                    @if (candidate.data_gaps.length) {
                      <p class="candidate-gap">
                        <strong>Data gaps:</strong> {{ candidate.data_gaps.join('; ') }}
                      </p>
                    }
                    <div class="card-actions">
                      <button
                        type="button"
                        class="primary"
                        (click)="primaryCandidateAction(candidate)"
                      >
                        {{ primaryActionLabel(candidate) }}
                      </button>
                      @if (
                        candidate.assessment_id && candidate.candidate_state === 'READY_TO_COMPARE'
                      ) {
                        <button
                          type="button"
                          class="secondary"
                          [attr.aria-pressed]="isSelected(candidate.id)"
                          (click)="toggleCandidate(candidate)"
                        >
                          {{
                            isSelected(candidate.id)
                              ? 'Remove from comparison'
                              : 'Add to comparison'
                          }}
                        </button>
                        <span class="selection-hint"
                          >Select a product after comparison to unlock supplier research.</span
                        >
                      }
                      @if (canRetryResearch(candidate)) {
                        <button
                          type="button"
                          class="secondary"
                          (click)="retryMissingResearch(candidate)"
                        >
                          Research this product
                        </button>
                      }
                    </div>
                    <details class="evidence-details">
                      <summary>View evidence and sources</summary>
                      @if (candidate.evidence.length) {
                        <ul>
                          @for (evidence of candidate.evidence; track $index) {
                            <li>
                              <strong>{{ displayValue(evidence['dimension']) }}</strong
                              >: {{ displayValue(evidence['classification']) }} ·
                              {{ displayValue(evidence['source']) }} · freshness
                              {{ displayValue(evidence['freshness']) }}
                            </li>
                          }
                        </ul>
                      } @else {
                        <p>Insufficient evidence.</p>
                      }
                    </details>
                    <details class="technical-details">
                      <summary>Advanced technical details</summary>
                      <dl class="compact-facts">
                        <div>
                          <dt>Opportunity ID</dt>
                          <dd>{{ candidate.id }}</dd>
                        </div>
                        <div>
                          <dt>Research run</dt>
                          <dd>{{ candidate.research_run_id || 'Not linked' }}</dd>
                        </div>
                        <div>
                          <dt>Raw provenance</dt>
                          <dd>{{ profileText(candidate, 'candidate_source') }}</dd>
                        </div>
                        <div>
                          <dt>Raw evidence state</dt>
                          <dd>{{ candidate.evidence_state || 'UNKNOWN' }}</dd>
                        </div>
                      </dl>
                    </details>
                  </article>
                }
              </div>
              <div class="comparison-toolbar" aria-live="polite">
                <span>{{ selectedCandidateIds().length }} selected (choose 2–4)</span>
                <button
                  type="button"
                  class="primary"
                  (click)="compareSelectedCandidates()"
                  [disabled]="!canCompareCandidates()"
                >
                  Compare selected products
                </button>
              </div>
              @if (comparison(); as result) {
                <section class="comparison-panel" aria-labelledby="comparison-results-title">
                  <h3 id="comparison-results-title">Evidence-backed comparison</h3>
                  <p class="comparison-purpose">
                    Comparison explains trade-offs; it does not choose a winner. Supplier research
                    stays blocked until you make an explicit human selection.
                  </p>
                  <div class="comparison-matrix" role="table" aria-label="Product trade-offs">
                    <div class="comparison-matrix-row comparison-matrix-header" role="row">
                      <span role="columnheader">Dimension</span>
                      @for (candidate of comparedCandidates(); track candidate.id) {
                        <span role="columnheader">{{ candidate.name }}</span>
                      }
                    </div>
                    @for (dimension of comparisonDimensions; track dimension.key) {
                      <div class="comparison-matrix-row" role="row">
                        <strong role="rowheader">{{ dimension.label }}</strong>
                        @for (candidate of comparedCandidates(); track candidate.id) {
                          <span role="cell">{{
                            comparisonDimension(candidate, dimension.key)
                          }}</span>
                        }
                      </div>
                    }
                  </div>
                  <p>{{ result.comparability }} · {{ result.reason }}</p>
                  @for (candidate of comparedCandidates(); track candidate.id) {
                    <article class="tradeoff-card">
                      <h4>{{ candidate.name }}</h4>
                      <p>
                        <strong>Strengths:</strong>
                        {{
                          candidate.strengths.length ? candidate.strengths.join('; ') : 'UNKNOWN'
                        }}
                      </p>
                      <p>
                        <strong>Risks:</strong>
                        {{ candidate.risks.length ? candidate.risks.join('; ') : 'UNKNOWN' }}
                      </p>
                      <p>
                        <strong>Data gaps:</strong>
                        {{
                          candidate.data_gaps.length
                            ? candidate.data_gaps.join('; ')
                            : 'None returned'
                        }}
                      </p>
                      <p>
                        <strong>Validate next:</strong>
                        {{
                          candidate.next_validation.length
                            ? candidate.next_validation.join('; ')
                            : 'Review authoritative evidence.'
                        }}
                      </p>
                      <button
                        type="button"
                        class="primary"
                        [disabled]="!candidate.assessment_id || loading()"
                        (click)="investigateCandidate(candidate)"
                      >
                        Select this product for supplier research
                      </button>
                      @if (candidate.selected) {
                        <span class="human-selection">Selected by you · HUMAN</span
                        ><a
                          class="secondary action-link"
                          routerLink="/intelligence/cross-marketplace"
                          [queryParams]="{
                            opportunity_id: candidate.id,
                            name: candidate.name,
                            product: candidate.product_concept,
                            category: candidate.category,
                            marketplace: candidate.marketplace,
                          }"
                          >Find suppliers</a
                        >
                      }
                    </article>
                  }
                </section>
              }
              @if (selectionMessage()) {
                <p class="callout" role="status">{{ selectionMessage() }}</p>
              }
            }
          </section>
        }
      }

      @if (error()) {
        <app-error-state
          title="Product opportunity data is unavailable"
          [message]="error()"
          retryLabel="Retry"
          (retry)="retryLoad()"
        />
      }
      @if (loading()) {
        <app-loading-state message="Loading product opportunity data..." />
      }

      @if (!detail()) {
        @if (!researchResults()) {
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
                A score is not a verdict. Confidence, risk, readiness and eligibility remain
                separate authoritative states.
              </p>
            </div>
          </section>

          <section
            class="panel create-panel"
            id="create-opportunity"
            aria-labelledby="create-title"
          >
            <details>
              <summary id="create-title">Start a product opportunity</summary>
              <p class="muted">
                Create the existing Product Opportunity record; assessment remains a separate
                governed step.
              </p>
              <form (ngSubmit)="create()" class="create-form">
                <label
                  >Name
                  <input name="name" [(ngModel)]="name" required minlength="2" maxlength="200"
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
                <p class="eyebrow">Active goal</p>
                <h2 id="list-title">Current research</h2>
              </div>
              <span class="muted">{{ currentOpportunities().length }} active record(s)</span>
            </div>
            @if (currentOpportunities().length === 0 && !loading()) {
              <app-empty-state
                title="No product opportunities yet"
                message="VAYUJIT has not created meaningful product candidates for this research goal."
                actionLabel="Start Product Research"
                (action)="openBusinessAgent()"
              />
            } @else {
              <div class="opportunity-list">
                @for (item of currentOpportunities(); track item.id) {
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
                      {{ item.description || item.product_concept || 'Description not confirmed.' }}
                    </p>
                    <dl class="compact-facts">
                      <div>
                        <dt>Marketplace</dt>
                        <dd>{{ item.target_marketplace || 'Not confirmed' }}</dd>
                      </div>
                      <div>
                        <dt>Evidence</dt>
                        <dd>{{ evidenceStateLabel(item.evidence_state) }}</dd>
                      </div>
                      <div>
                        <dt>Updated</dt>
                        <dd>{{ item.updated_at | date: 'mediumDate' }}</dd>
                      </div>
                    </dl>
                    <div class="card-actions">
                      <button type="button" class="primary" (click)="select(item.id)">
                        View research
                      </button>
                    </div>
                  </article>
                }
              </div>
            }
          </section>
        }

        @if (historicalOpportunities().length) {
          <section class="panel history-panel" aria-labelledby="history-title">
            <div class="section-heading">
              <div>
                <p class="eyebrow">Secondary context</p>
                <h2 id="history-title">Previous research</h2>
              </div>
              <span class="muted">{{ historicalOpportunities().length }} earlier record(s)</span>
            </div>
            <details>
              <summary>View previous research</summary>
              <div class="opportunity-list">
                @for (item of historicalOpportunities(); track item.id) {
                  <article class="opportunity-card historical-card">
                    <p class="eyebrow">{{ item.category || 'Product opportunity' }}</p>
                    <h3>{{ item.name }}</h3>
                    <p class="card-description">
                      {{ item.description || item.product_concept || 'Description not confirmed.' }}
                    </p>
                    <button type="button" class="secondary" (click)="select(item.id)">
                      View historical research
                    </button>
                  </article>
                }
              </div>
            </details>
          </section>
        }

        @if (!researchResults() && canCompare()) {
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
                {{ result.comparability }} Not available {{ result.reason }}
              </p>
              @if (result.ranking?.length) {
                <ol class="ranking-list">
                  @for (entry of result.ranking; track entry.assessment_id) {
                    <li>
                      <strong>Rank {{ entry.rank }}</strong> - {{ entry.score ?? 'Unavailable' }} -
                      {{ entry.classification }} - confidence {{ entry.confidence }} - readiness
                      {{ entry.readiness }}
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
            <div class="product-summary-hero">
              @if (detailImage(); as image) {
                <img
                  class="detail-product-image product-summary-image"
                  [src]="image"
                  [alt]="item.name"
                />
              } @else {
                <div
                  class="product-image-placeholder product-summary-image"
                  role="img"
                  aria-label="Product image not available"
                >
                  Product image not available
                </div>
              }
              <div class="product-summary-copy">
                <p class="eyebrow">Product summary</p>
                <h2 id="context-title" tabindex="-1">{{ item.name }}</h2>
                <p>
                  {{
                    item.description ||
                      item.product_concept ||
                      'Product description not established.'
                  }}
                </p>
                <div class="summary-pills" aria-label="Product readiness and context">
                  <span>{{ item.category || 'Category not established' }}</span>
                  <span>{{ item.subcategory || 'Subcategory not established' }}</span>
                  <span>{{ detailReadinessLabel() }}</span>
                  <span>{{ detailTrustLabel() }}</span>
                </div>
              </div>
            </div>
            <div class="context-copy">
              <p class="eyebrow">Current product research context</p>
              <h3>Why VAYUJIT surfaced this product</h3>
              <p>{{ detailWhySummary() }}</p>
              <h3>How it relates to your goal</h3>
              <p>{{ detailGoalFitSummary() }}</p>
            </div>
            <div class="context-actions">
              @if (detailSelected(item)) {
                <p class="selected-product-confirmation" role="status">
                  Selected for supplier research: <strong>{{ item.name }}</strong>
                </p>
                <a
                  class="primary action-link"
                  routerLink="/intelligence/cross-marketplace"
                  [queryParams]="supplierHandoffParams(item)"
                  >Find suppliers</a
                >
              } @else {
                <button
                  class="primary"
                  type="button"
                  (click)="selectDetailForSupplier(item)"
                  [disabled]="loading() || !item.current_assessment_id"
                >
                  Select this product for supplier research
                </button>
              }
              <a class="secondary action-link" routerLink="/intelligence/business-agent"
                >Continue research with VAYUJIT</a
              >
              <button
                class="secondary"
                type="button"
                (click)="researchMarketEvidence(item.id)"
                [disabled]="loading()"
              >
                Research market evidence
              </button>
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
          @if (researchMessage()) {
            <p class="callout" role="status">{{ researchMessage() }}</p>
          }

          <section class="panel product-profile-panel" aria-labelledby="profile-title">
            <div class="section-heading">
              <div>
                <p class="eyebrow">Product intelligence</p>
                <h2 id="profile-title">What this product means</h2>
              </div>
              <span class="muted">Truthful evidence and explicit unknowns</span>
            </div>
            <div class="overview-grid">
              <div>
                <h3>Why VAYUJIT found this</h3>
                <ul>
                  @for (value of detailProfileList('why_this_surfaced'); track value) {
                    <li>{{ value }}</li>
                  }
                </ul>
              </div>
              <div>
                <h3>Use case / customer problem</h3>
                <p>{{ detailProfileValue('customer_problem') }}</p>
              </div>
              <div>
                <h3>Key characteristics</h3>
                <p>
                  {{
                    detailProfileList('key_characteristics').join('; ') || 'UNKNOWN / NOT AVAILABLE'
                  }}
                </p>
              </div>
              <div>
                <h3>Research keywords</h3>
                <p>
                  {{
                    detailProfileList('research_keywords').join(', ') || 'UNKNOWN / NOT AVAILABLE'
                  }}
                </p>
              </div>
              <div>
                <h3>Representative image</h3>
                @if (detailImage(); as image) {
                  <img class="detail-product-image" [src]="image" [alt]="item.name" />
                } @else {
                  <p>Not available yet. This neutral state is not product evidence.</p>
                }
              </div>
              <div>
                <h3>Observed price</h3>
                <p>{{ detailObservedPrice() }}</p>
              </div>
              <div>
                <h3>Evidence gaps</h3>
                <p>
                  {{
                    detailProfileList('missing_information').join('; ') || 'UNKNOWN / NOT AVAILABLE'
                  }}
                </p>
              </div>
            </div>
            @if (detailLiveResearch(); as live) {
              <div class="callout">
                <strong>Market research:</strong> {{ detailLiveStatus(live) }} ·
                {{ detailLiveCount(live, 'search_results') }} sources discovered.
                @if (detailLiveSources(live).length) {
                  <ul>
                    @for (source of detailLiveSources(live); track source.url) {
                      <li>
                        <a [href]="source.url" target="_blank" rel="noopener noreferrer">
                          {{ source.domain || source.url }}
                        </a>
                        · {{ source.evidence_classification || 'SEARCH_DISCOVERY_EVIDENCE' }}
                      </li>
                    }
                  </ul>
                }
              </div>
            }
            <div class="callout">
              <strong>Source:</strong> {{ detailProfileValue('candidate_source') }} ·
              <strong>Freshness:</strong> {{ detailProfileValue('freshness') }} · Marketplace
              prices, customer reviews, competitors, trends, and supplier facts remain UNKNOWN until
              authoritative evidence exists.
            </div>
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
                          >Raw input {{ dimension['raw_input'] ?? 'Unavailable' }} - Contribution
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
                  -
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
                  <a routerLink="/intelligence/cross-marketplace">View Suppliers</a>
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
                    ><a
                      class="secondary action-link"
                      routerLink="/intelligence/sourcing-economics"
                      [queryParams]="{ opportunity_id: item.id }"
                      >Review Economics &amp; Decision Brief</a
                    >
                  </div>
                  @if (sourcing.candidates.length) {
                    <h4>Candidate evidence</h4>
                    <ul class="candidate-list">
                      @for (candidate of sourcing.candidates; track $index) {
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
            @if (economicProjection(); as economics) {
              <article class="research-card economics-evidence">
                <div class="research-heading">
                  <h3>Sourcing economics</h3>
                  <span class="muted">Factual cost evidence / human review</span>
                </div>
                <dl class="compact-facts">
                  <div>
                    <dt>Readiness</dt>
                    <dd>{{ economics.readiness }}</dd>
                  </div>
                  <div>
                    <dt>Status</dt>
                    <dd>{{ economics.status }}</dd>
                  </div>
                  @if (economics.calculation; as calculation) {
                    <div>
                      <dt>Total included cost</dt>
                      <dd>
                        {{ displayValue(calculation['total_included_cost']) }}
                        {{ displayValue(calculation['reporting_currency']) }}
                      </dd>
                    </div>
                    <div>
                      <dt>Per unit cost</dt>
                      <dd>
                        {{ displayValue(calculation['per_unit_cost']) }}
                        {{ displayValue(calculation['reporting_currency']) }}
                      </dd>
                    </div>
                  }
                  <div>
                    <dt>Scenario comparisons</dt>
                    <dd>{{ economics.scenario_comparisons?.length ?? 0 }}</dd>
                  </div>
                  <div>
                    <dt>Research gaps</dt>
                    <dd>{{ economics.research_gaps.length }}</dd>
                  </div>
                </dl>
                @if (economics.research_gaps.length) {
                  <ul class="muted">
                    @for (gap of economics.research_gaps; track gap['code']) {
                      <li>{{ displayValue(gap['message']) }}</li>
                    }
                  </ul>
                }
                <p class="muted">
                  This evidence does not rank suppliers or products and is not a profitability or
                  forecast claim.
                </p>
              </article>
            } @else {
              <article class="research-card economics-evidence">
                <div class="research-heading">
                  <h3>Sourcing economics</h3>
                  <span class="muted">Optional</span>
                </div>
                <p class="muted">Load existing 13A–13F cost evidence for this opportunity.</p>
                <button
                  class="secondary"
                  type="button"
                  (click)="loadSourcingEconomics(item)"
                  [disabled]="loading()"
                >
                  Load sourcing economics
                </button>
              </article>
            }
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
                    @for (gap of researchGaps(); track $index) {
                      <li>{{ gap }}</li>
                    }
                  </ul>
                </div>
              }
              @if (contradictions().length) {
                <div class="callout danger">
                  <h3>Conflicting evidence</h3>
                  <ul>
                    @for (item of contradictions(); track $index) {
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
  private readonly businessAgentService = inject(BusinessAgentService, { optional: true });
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly opportunities = signal<ProductOpportunity[]>([]);
  readonly researchResults = signal<ResearchResults | null>(null);
  readonly selectedCandidateIds = signal<string[]>([]);
  readonly selectionMessage = signal('');
  readonly detail = signal<OpportunityDetail | null>(null);
  readonly intelligenceOutputs = signal<IntelligenceOutput[]>([]);
  readonly competitionProjection = signal<CompetitionProjection | null>(null);
  readonly trendProjection = signal<TrendWinningProductProjection | null>(null);
  readonly commercialOutput = signal<CommercialOutput | null>(null);
  readonly sourcingFeasibility = signal<SourcingFeasibilityOutput | null>(null);
  readonly riskEvidence = signal<RiskEvidenceSynthesisOutput | null>(null);
  readonly economicProjection = signal<SourcingEconomicsProjection | null>(null);
  readonly score = signal<ProductOpportunityScore | null>(null);
  readonly reviewProjection = signal<ReviewWinningProductProjection | null>(null);
  readonly scoreHistory = signal<ProductOpportunityScoreHistory[]>([]);
  readonly comparison = signal<ProductOpportunityComparison | null>(null);
  readonly decisionMessage = signal('');
  readonly handoffMessage = signal('');
  readonly researchMessage = signal('');
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
  readonly comparisonDimensions = [
    { key: 'category', label: 'Category' },
    { key: 'goal_fit', label: 'Goal fit' },
    { key: 'readiness', label: 'Research readiness' },
    { key: 'evidence', label: 'Evidence' },
    { key: 'price', label: 'Observed price' },
    { key: 'risk', label: 'Risk' },
    { key: 'competition', label: 'Competition evidence' },
    { key: 'reviews', label: 'Customer feedback' },
    { key: 'trend', label: 'Trend evidence' },
    { key: 'unknowns', label: 'Important unknowns' },
  ] as const;
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
    this.error.set('');
    try {
      const [opportunities, results] = await Promise.all([
        this.service.list(),
        this.service.getResearchResults(),
      ]);
      this.opportunities.set(opportunities);
      this.researchResults.set(results);
      this.selectedCandidateIds.set(
        results.selected_candidate_ids.filter((id) =>
          results.candidates.some((candidate) => candidate.id === id),
        ),
      );
    } catch {
      this.error.set('Product opportunity data is unavailable.');
    } finally {
      this.loading.set(false);
    }
  }

  isSelected(id: string): boolean {
    return this.selectedCandidateIds().includes(id);
  }

  orderedCandidates(candidates: ResearchCandidate[]): ResearchCandidate[] {
    const order: Record<string, number> = {
      READY_TO_COMPARE: 0,
      NEEDS_MORE_RESEARCH: 1,
      INSUFFICIENT_EVIDENCE: 2,
    };
    return [...candidates].sort(
      (left, right) => (order[left.candidate_state] ?? 9) - (order[right.candidate_state] ?? 9),
    );
  }

  currentOpportunities(): ProductOpportunity[] {
    const ids = new Set(this.researchResults()?.candidates.map((candidate) => candidate.id) ?? []);
    return this.opportunities().filter((item) => ids.has(item.id));
  }

  historicalOpportunities(): ProductOpportunity[] {
    const ids = new Set(this.researchResults()?.candidates.map((candidate) => candidate.id) ?? []);
    return this.opportunities().filter((item) => !ids.has(item.id));
  }

  primaryActionLabel(candidate: ResearchCandidate): string {
    if (candidate.candidate_state === 'INSUFFICIENT_EVIDENCE') {
      return 'View research gaps';
    }
    if (candidate.candidate_state === 'NEEDS_MORE_RESEARCH') {
      return 'Research this product';
    }
    return 'View product research';
  }

  primaryCandidateAction(candidate: ResearchCandidate): void {
    if (candidate.candidate_state === 'NEEDS_MORE_RESEARCH') {
      void this.researchMarketEvidence(candidate.id);
      return;
    }
    this.viewCandidate(candidate);
  }

  readinessLabel(candidate: ResearchCandidate): string {
    if (candidate.candidate_state === 'READY_TO_COMPARE') return 'Ready to compare';
    if (candidate.candidate_state === 'INSUFFICIENT_EVIDENCE') return 'Insufficient evidence';
    return 'Needs more research';
  }

  candidateDescription(candidate: ResearchCandidate): string {
    const detailed = this.profileText(candidate, 'detailed_description');
    return (
      candidate.description ||
      candidate.product_concept ||
      (detailed !== 'UNKNOWN / NOT AVAILABLE' ? detailed : 'Product description not established.')
    );
  }

  candidateReasons(candidate: ResearchCandidate): string[] {
    const reasons = candidate.why_this_surfaced.filter(
      (item) => item.trim() && item.toLowerCase() !== 'insufficient evidence',
    );
    return reasons.length ? reasons : ['Reason not established from current evidence.'];
  }

  goalFitLabel(candidate: ResearchCandidate): string {
    const values = this.profileList(candidate, 'goal_fit');
    return values.length ? 'Supported preferences matched' : 'Not established';
  }

  candidateTrustLabel(candidate: ResearchCandidate): string {
    const provenance = candidate.intelligence_profile?.['candidate_provenance'];
    if (provenance && typeof provenance === 'object') {
      const mode = this.valueText((provenance as Record<string, unknown>)['mode']);
      if (mode === 'LOCAL_DETERMINISTIC') return 'Local demo - not live evidence';
    }
    const source = this.profileText(candidate, 'candidate_source');
    if (source.toUpperCase().includes('FIXTURE')) return 'Local demo - not live evidence';
    const live = candidate.intelligence_profile?.['live_research'];
    if (live && typeof live === 'object') {
      const status = this.valueText((live as Record<string, unknown>)['status']);
      if (status) return this.statusLabel(status);
    }
    return 'Evidence state not established';
  }

  candidateEvidenceSummary(candidate: ResearchCandidate): string {
    const profile = candidate.intelligence_profile || {};
    const parts = [
      this.profileBusinessValue(candidate, 'trend_evidence') !== 'Not available yet' ? 'trend' : '',
      this.profileBusinessValue(candidate, 'competitor_evidence') !== 'Not available yet'
        ? 'competition'
        : '',
      this.profileBusinessValue(candidate, 'customer_evidence') !== 'Not available yet'
        ? 'customer feedback'
        : '',
    ].filter(Boolean);
    if (parts.length) return 'Available for ' + parts.join(', ') + '.';
    if (profile['live_research'])
      return 'Market evidence is available with the freshness shown in detail.';
    return 'Supporting market, competition, trend, and review evidence is not available yet.';
  }

  isFixtureResults(results: ResearchResults): boolean {
    return results.candidates.some((candidate) =>
      this.candidateTrustLabel(candidate).includes('Local demo'),
    );
  }

  evidenceStateLabel(value: string | null | undefined): string {
    const normalized = String(value || '').toLowerCase();
    if (normalized === 'available') return 'Available';
    if (normalized === 'partial') return 'Partial';
    if (normalized === 'insufficient_evidence') return 'Not enough evidence';
    if (normalized === 'unknown') return 'Not available yet';
    return value ? this.statusLabel(value) : 'Not available yet';
  }

  evidenceLabel(candidate: ResearchCandidate): string {
    return this.evidenceStateLabel(candidate.score?.evidence_state || candidate.evidence_state);
  }

  valueText(value: unknown): string {
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      return String(value);
    }
    return '';
  }

  marketEvidenceLabel(candidate: ResearchCandidate): string {
    const profile = candidate.intelligence_profile || {};
    const live = profile['live_research'];
    if (live && typeof live === 'object') {
      const status = this.valueText((live as Record<string, unknown>)['status']).toUpperCase();
      if (status === 'RESEARCHED_WITH_GAPS') return 'Available with gaps';
      if (status === 'COMPLETED') return 'Available';
    }
    return profile['marketplace_observations'] ? 'Available' : 'Not available yet';
  }

  profileBusinessValue(candidate: ResearchCandidate, key: string): string {
    const value = candidate.intelligence_profile?.[key];
    if (!value) return 'Not available yet';
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return value.length ? 'Available' : 'Not available yet';
    if (typeof value === 'object') {
      const record = value as Record<string, unknown>;
      const status = record['status'] || record['state'] || record['message'];
      return status ? this.statusLabel(this.valueText(status)) : 'Available';
    }
    return 'Available';
  }

  riskLabel(candidate: ResearchCandidate): string {
    const risk = candidate.score?.risk_level || candidate.intelligence_profile?.['risk'];
    if (typeof risk === 'string') return this.statusLabel(risk);
    if (risk && typeof risk === 'object') {
      const value =
        (risk as Record<string, unknown>)['level'] || (risk as Record<string, unknown>)['state'];
      if (value) return this.statusLabel(this.valueText(value));
    }
    return 'Not available yet';
  }

  observedPrice(candidate: ResearchCandidate): string {
    const live = candidate.intelligence_profile?.['live_research'];
    if (live && typeof live === 'object') {
      const approved = (live as Record<string, unknown>)['approved_fetches'];
      if (Array.isArray(approved)) {
        for (const entry of approved) {
          if (!entry || typeof entry !== 'object') continue;
          const extracted = (entry as Record<string, unknown>)['extracted'];
          if (!extracted || typeof extracted !== 'object') continue;
          const metadata = (extracted as Record<string, unknown>)['product_metadata'];
          if (!metadata || typeof metadata !== 'object') continue;
          const offers = (metadata as Record<string, unknown>)['offers'];
          if (!offers || typeof offers !== 'object') continue;
          const price = (offers as Record<string, unknown>)['price'];
          const currency = (offers as Record<string, unknown>)['priceCurrency'];
          if (price)
            return 'Observed price: ' + this.valueText(price) + ' ' + this.valueText(currency);
        }
      }
    }
    return 'Not available yet';
  }

  candidateImage(candidate: ResearchCandidate): string | null {
    const image = candidate.intelligence_profile?.['image'];
    if (image && typeof image === 'object') {
      const record = image as Record<string, unknown>;
      if (record['available'] === false) return null;
      if (typeof record['url'] === 'string' && record['url']) return record['url'];
    }
    if (typeof image === 'string' && image) return image;
    const live = candidate.intelligence_profile?.['live_research'];
    if (live && typeof live === 'object') {
      const approved = (live as Record<string, unknown>)['approved_fetches'];
      if (Array.isArray(approved)) {
        for (const entry of approved) {
          if (!entry || typeof entry !== 'object') continue;
          const extracted = (entry as Record<string, unknown>)['extracted'];
          const metadata =
            extracted && typeof extracted === 'object'
              ? (extracted as Record<string, unknown>)['product_metadata']
              : null;
          const value =
            metadata && typeof metadata === 'object'
              ? (metadata as Record<string, unknown>)['image']
              : null;
          if (typeof value === 'string' && value) return value;
        }
      }
    }
    return null;
  }

  detailImage(): string | null {
    const image = this.detail()?.intelligence_profile?.['image'];
    if (typeof image === 'string' && image) return image;
    if (image && typeof image === 'object') {
      const value = (image as Record<string, unknown>)['url'];
      return typeof value === 'string' && value ? value : null;
    }
    return null;
  }

  detailObservedPrice(): string {
    const profile = this.detail()?.intelligence_profile || {};
    const live = profile['live_research'];
    if (!live || typeof live !== 'object') return 'Not available yet';
    const approved = (live as Record<string, unknown>)['approved_fetches'];
    if (!Array.isArray(approved)) return 'Not available yet';
    for (const entry of approved) {
      if (!entry || typeof entry !== 'object') continue;
      const extracted = (entry as Record<string, unknown>)['extracted'];
      const metadata =
        extracted && typeof extracted === 'object'
          ? (extracted as Record<string, unknown>)['product_metadata']
          : null;
      const offers =
        metadata && typeof metadata === 'object'
          ? (metadata as Record<string, unknown>)['offers']
          : null;
      const price =
        offers && typeof offers === 'object' ? (offers as Record<string, unknown>)['price'] : null;
      const currency =
        offers && typeof offers === 'object'
          ? (offers as Record<string, unknown>)['priceCurrency']
          : null;
      if (price) return 'Observed price: ' + this.valueText(price) + ' ' + this.valueText(currency);
    }
    return 'Not available yet';
  }

  profileList(candidate: ResearchCandidate, key: string): string[] {
    const value = candidate.intelligence_profile?.[key];
    return Array.isArray(value)
      ? value.filter((item): item is string => typeof item === 'string')
      : [];
  }

  profileText(candidate: ResearchCandidate, key: string): string {
    const value = candidate.intelligence_profile?.[key];
    return typeof value === 'string' ? value : 'UNKNOWN / NOT AVAILABLE';
  }

  detailProfile(key: string): Record<string, unknown> {
    const value = this.detail()?.intelligence_profile;
    return value && typeof value[key] === 'object' && value[key] !== null
      ? (value[key] as Record<string, unknown>)
      : {};
  }

  detailProfileValue(key: string): string {
    const value = this.detail()?.intelligence_profile?.[key];
    return typeof value === 'string' ? value : 'UNKNOWN / NOT AVAILABLE';
  }

  detailLiveResearch(): Record<string, unknown> {
    const value = this.detail()?.intelligence_profile?.['live_research'];
    return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
  }

  detailLiveStatus(live: Record<string, unknown>): string {
    return typeof live['status'] === 'string' ? live['status'] : 'NOT_RESEARCHED';
  }

  detailLiveCount(live: Record<string, unknown>, key: string): number {
    const value = live[key];
    return Array.isArray(value) ? value.length : 0;
  }

  detailLiveSources(
    live: Record<string, unknown>,
  ): Array<{ url: string; domain: string; evidence_classification: string }> {
    const value = live['search_results'];
    if (!Array.isArray(value)) {
      return [];
    }
    return value.flatMap((item) => {
      if (!item || typeof item !== 'object') {
        return [];
      }
      const source = item as Record<string, unknown>;
      const url = typeof source['url'] === 'string' ? source['url'] : '';
      if (!url) {
        return [];
      }
      return [
        {
          url,
          domain: typeof source['domain'] === 'string' ? source['domain'] : '',
          evidence_classification:
            typeof source['evidence_classification'] === 'string'
              ? source['evidence_classification']
              : 'SEARCH_DISCOVERY_EVIDENCE',
        },
      ];
    });
  }

  detailProfileList(key: string): string[] {
    const value = this.detail()?.intelligence_profile?.[key];
    return Array.isArray(value)
      ? value.filter((item): item is string => typeof item === 'string')
      : [];
  }

  detailReadinessLabel(): string {
    const item = this.detail();
    if (!item) return 'Readiness not established';
    if (
      item.current_assessment_id &&
      String(item.evidence_state || '').toLowerCase() === 'available'
    ) {
      return 'Ready to compare';
    }
    if (item.current_assessment_id) return 'Needs more research';
    return 'Researching';
  }

  detailTrustLabel(): string {
    const item = this.detail();
    if (!item) return 'Trust not established';
    const source = this.detailProfileValue('candidate_source');
    if (source.toUpperCase().includes('FIXTURE')) return 'Local demo - not live evidence';
    const live = this.detailLiveResearch();
    if (Object.keys(live).length) return 'Live evidence with source freshness';
    return 'Evidence state not established';
  }

  detailWhySummary(): string {
    const reasons = this.detailProfileList('why_this_surfaced').filter(
      (item) => item.trim() && item.toLowerCase() !== 'insufficient evidence',
    );
    return reasons.length
      ? reasons.join(' ')
      : 'This product was surfaced by the current research workflow; the specific reason is not established yet.';
  }

  detailGoalFitSummary(): string {
    const fit = this.detailProfileList('goal_fit');
    return fit.length
      ? fit.join(' ')
      : 'Product characteristics may relate to the goal, but commercial and budget viability are not established.';
  }

  detailSelected(item: OpportunityDetail): boolean {
    return (
      this.researchResults()?.selected_candidate_ids.includes(item.id) ||
      Boolean(
        this.researchResults()?.candidates.find((candidate) => candidate.id === item.id)?.selected,
      )
    );
  }

  supplierHandoffParams(item: OpportunityDetail): Record<string, string> {
    const profile = item.intelligence_profile || {};
    const keywords = Array.isArray(profile['research_keywords'])
      ? profile['research_keywords'].filter((value): value is string => typeof value === 'string')
      : [];
    return {
      opportunity_id: item.id,
      name: item.name,
      product: item.product_concept || item.description,
      category: item.category,
      subcategory: item.subcategory || '',
      marketplace: item.target_marketplace,
      region: item.target_region,
      search_terms: keywords.join(', '),
    };
  }

  canCompareCandidates(): boolean {
    const count = this.selectedCandidateIds().length;
    return count >= 2 && count <= 4;
  }

  toggleCandidate(candidate: ResearchCandidate): void {
    if (!candidate.assessment_id) return;
    const selected = this.selectedCandidateIds();
    if (selected.includes(candidate.id)) {
      this.selectedCandidateIds.set(selected.filter((id) => id !== candidate.id));
      return;
    }
    if (selected.length >= 4) {
      this.selectionMessage.set(
        'Comparison is limited to four candidates. Remove one before adding another.',
      );
      return;
    }
    this.selectedCandidateIds.set([...selected, candidate.id]);
    this.selectionMessage.set('');
  }

  viewCandidate(candidate: ResearchCandidate): void {
    void this.select(candidate.id);
  }

  canRetryResearch(candidate: ResearchCandidate): boolean {
    return (
      Boolean(candidate.research_run_id) &&
      ['failed', 'blocked', 'partial', 'incomplete'].includes(
        candidate.research_state.toLowerCase(),
      )
    );
  }

  async researchMarketEvidence(opportunityId: string): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    this.researchMessage.set('');
    try {
      const result: ProductResearchResponse =
        await this.service.researchMarketEvidence(opportunityId);
      this.researchMessage.set(
        `Market research ${result.research_state.replaceAll('_', ' ').toLowerCase()}: ${result.result_count} source results; ${result.fetch_count} approved fetches.`,
      );
      if (this.detail()) {
        await this.loadDetail(opportunityId);
      }
      await this.load();
    } catch {
      this.error.set('Market research could not be started.');
    } finally {
      this.loading.set(false);
    }
  }

  async retryMissingResearch(candidate: ResearchCandidate): Promise<void> {
    if (
      !candidate.research_run_id ||
      !this.businessAgentService ||
      !this.canRetryResearch(candidate)
    )
      return;
    this.loading.set(true);
    this.error.set('');
    try {
      await this.businessAgentService.retry(candidate.research_run_id);
      this.selectionMessage.set(
        'Missing research retry requested. Successful research steps were preserved.',
      );
      await this.load();
    } catch {
      this.error.set('The missing research retry could not be started.');
    } finally {
      this.loading.set(false);
    }
  }

  comparedCandidates(): ResearchCandidate[] {
    const candidates = this.researchResults()?.candidates ?? [];
    return this.selectedCandidateIds()
      .map((id) => candidates.find((candidate) => candidate.id === id))
      .filter((candidate): candidate is ResearchCandidate => Boolean(candidate));
  }

  comparisonDimension(candidate: ResearchCandidate, key: string): string {
    switch (key) {
      case 'category':
        return candidate.category || 'Category not established';
      case 'goal_fit':
        return this.goalFitLabel(candidate);
      case 'readiness':
        return this.readinessLabel(candidate);
      case 'evidence':
        return this.evidenceLabel(candidate);
      case 'price':
        return this.observedPrice(candidate);
      case 'risk':
        return this.riskLabel(candidate);
      case 'competition':
        return this.profileBusinessValue(candidate, 'competitor_evidence');
      case 'reviews':
        return this.profileBusinessValue(candidate, 'customer_evidence');
      case 'trend':
        return this.profileBusinessValue(candidate, 'trend_evidence');
      case 'unknowns':
        return candidate.data_gaps.length ? candidate.data_gaps.join('; ') : 'No gaps returned';
      default:
        return 'Not available yet';
    }
  }

  supplierHandoffParamsFromCandidate(candidate: ResearchCandidate): Record<string, string> {
    const keywords = this.profileList(candidate, 'research_keywords');
    return {
      opportunity_id: candidate.id,
      name: candidate.name,
      product: candidate.product_concept || candidate.description,
      category: candidate.category,
      subcategory: candidate.subcategory || '',
      marketplace: candidate.marketplace,
      region: candidate.region,
      search_terms: keywords.join(', '),
    };
  }

  async compareSelectedCandidates(): Promise<void> {
    const candidates = this.comparedCandidates();
    const assessmentIds = candidates
      .map((candidate) => candidate.assessment_id)
      .filter((id): id is string => Boolean(id));
    if (assessmentIds.length < 2 || assessmentIds.length > 4) return;
    this.loading.set(true);
    this.error.set('');
    try {
      this.comparison.set(await this.service.rankScores(assessmentIds));
      document.getElementById('comparison-results-title')?.focus?.();
    } catch {
      this.error.set('Opportunity comparison is unavailable for these assessments.');
    } finally {
      this.loading.set(false);
    }
  }

  async investigateCandidate(candidate: ResearchCandidate): Promise<void> {
    if (!candidate.assessment_id) return;
    this.loading.set(true);
    this.error.set('');
    try {
      await this.service.decide(candidate.id, candidate.assessment_id, {
        action: 'shortlist',
        rationale:
          'Human selected this product for further investigation from the GP-3 comparison.',
      });
      this.selectionMessage.set(
        `${candidate.name} selected for further investigation. Provenance: HUMAN.`,
      );
      await this.load();
    } catch {
      this.error.set('The human product selection could not be recorded.');
    } finally {
      this.loading.set(false);
    }
  }

  async selectDetailForSupplier(item: OpportunityDetail): Promise<void> {
    if (!item.current_assessment_id) {
      this.selectionMessage.set(
        'This product needs an assessment before supplier research can begin.',
      );
      return;
    }
    this.loading.set(true);
    this.error.set('');
    try {
      await this.service.decide(item.id, item.current_assessment_id, {
        action: 'shortlist',
        rationale: 'Human selected this product for supplier research.',
      });
      this.selectionMessage.set(
        item.name +
          ' selected for supplier research. Supplier research remains read-only and human-controlled.',
      );
      await this.load();
      document.getElementById('context-title')?.focus?.();
    } catch {
      this.error.set('The human product selection could not be recorded.');
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
    this.economicProjection.set(null);
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
    return (
      this.currentOpportunities().filter((item) => Boolean(item.current_assessment_id)).length >= 2
    );
  }

  async compareOpportunities(): Promise<void> {
    const assessmentIds = this.currentOpportunities()
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

  async loadSourcingEconomics(item: OpportunityDetail): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      this.economicProjection.set(await this.service.getSourcingEconomics(item.id));
    } catch {
      this.error.set('Sourcing economics evidence is unavailable for this opportunity.');
    } finally {
      this.loading.set(false);
    }
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
        source: 'Trend - Winning Product projection',
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
