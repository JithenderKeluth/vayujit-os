import { DatePipe, JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import {
  JsonMap,
  PortfolioAnalysis,
  PortfolioAssessment,
  PortfolioCalendarItem,
  PortfolioDimension,
  PortfolioMember,
  PortfolioOperations,
  PortfolioProductChannel,
  PortfolioRecommendation,
  PortfolioSimulation,
  SupplierPortfolio,
  SupplierPortfolioService,
} from './supplier-portfolio.service';

const SIMULATION_TYPES = [
  'SUPPLIER_UNAVAILABLE',
  'SUPPLIER_CAPACITY_REDUCTION',
  'COUNTRY_DISRUPTION',
  'REGION_DISRUPTION',
  'LEAD_TIME_INCREASE',
  'LANDED_COST_INCREASE',
  'FX_SHOCK',
  'MOQ_INCREASE',
  'AVAILABILITY_REDUCTION',
  'MULTI_SUPPLIER_DISRUPTION',
  'CUSTOM',
] as const;

const READINESS_STATES = [
  'READY',
  'CONDITIONALLY_READY',
  'RESEARCH_REQUIRED',
  'DUE_DILIGENCE_REQUIRED',
  'COMMERCIAL_VALIDATION_REQUIRED',
  'NOT_READY',
  'BLOCKED',
  'UNKNOWN',
] as const;

const DIMENSION_LABELS: Record<string, string> = {
  SUPPLIER_DIVERSITY: 'Supplier Diversity',
  GEOGRAPHIC_DIVERSITY: 'Geographic Diversity',
  QUALIFIED_ALTERNATIVE_COVERAGE: 'Qualified Alternative Coverage',
  VERIFIED_ALTERNATIVE_COVERAGE: 'Verified Alternative Coverage',
  COMMERCIAL_FLEXIBILITY: 'Commercial Flexibility',
  LEAD_TIME_RESILIENCE: 'Lead-Time Resilience',
  COST_RESILIENCE: 'Cost Resilience',
  CAPABILITY_REDUNDANCY: 'Capability Redundancy',
  EVIDENCE_CONFIDENCE: 'Evidence Confidence',
  FRESHNESS: 'Freshness',
  CONTRADICTION_RISK: 'Contradiction Risk',
  DUE_DILIGENCE_COVERAGE: 'Due Diligence Coverage',
};

const ACTIONS = [
  'ACKNOWLEDGE_RISK',
  'REQUEST_MORE_RESEARCH',
  'REQUEST_DUE_DILIGENCE',
  'CREATE_BACKUP_SCENARIO',
  'KEEP_UNDER_REVIEW',
  'ACCEPT_CONCENTRATION',
  'ARCHIVE_RECOMMENDATION',
] as const;

@Component({
  selector: 'app-supplier-portfolio-workspace',
  imports: [DatePipe, FormsModule, JsonPipe, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="portfolio-page" aria-labelledby="portfolio-title">
      <header class="page-header">
        <div>
          <p class="eyebrow">Supplier Portfolio &amp; Resilience Intelligence</p>
          <h1 id="portfolio-title">Supplier portfolios</h1>
          <p class="lede">
            Evidence-first decision support. No supplier messaging, purchasing, or allocation
            changes are performed here.
          </p>
        </div>
        <nav class="header-actions" aria-label="Portfolio navigation">
          <a routerLink="/intelligence" class="secondary-button">Back to Intelligence</a>
          <a routerLink="/operations" class="secondary-button">Operations</a>
        </nav>
      </header>

      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }
      @if (loading()) {
        <p class="loading" aria-live="polite">Loading supplier portfolios...</p>
      } @else if (!portfolioId()) {
        <section class="panel" aria-labelledby="portfolio-list-title">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">Owner-scoped portfolio contexts</p>
              <h2 id="portfolio-list-title">Portfolio list</h2>
            </div>
            <button type="button" (click)="loadList()" [disabled]="loading()">Refresh</button>
          </div>
          @if (!portfolios().length) {
            <div class="empty-state">
              <h3>No supplier portfolios yet</h3>
              <p>Create a portfolio through the API, then return here for analysis and review.</p>
            </div>
          } @else {
            <div class="table-wrap">
              <table>
                <caption class="sr-only">
                  Supplier portfolio summary
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Portfolio</th>
                    <th scope="col">Scope</th>
                    <th scope="col">Status</th>
                    <th scope="col">Current assessment</th>
                    <th scope="col">Last updated</th>
                    <th scope="col"><span class="sr-only">Open</span></th>
                  </tr>
                </thead>
                <tbody>
                  @for (portfolio of portfolios(); track portfolio.id) {
                    <tr>
                      <th scope="row">{{ portfolio.name }}</th>
                      <td>
                        {{ portfolio.scope_type
                        }}{{ portfolio.scope_reference ? '  -  ' + portfolio.scope_reference : '' }}
                      </td>
                      <td>
                        <span class="status-badge">{{ portfolio.status }}</span>
                      </td>
                      <td>
                        {{ portfolio.current_assessment_version_id ? 'Available' : 'Not assessed' }}
                      </td>
                      <td>{{ portfolio.updated_at | date: 'medium' }}</td>
                      <td>
                        <a [routerLink]="['/intelligence/supplier-portfolios', portfolio.id]"
                          >Open workspace</a
                        >
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          }
        </section>
      } @else {
        @if (detailLoading()) {
          <p class="loading" aria-live="polite">Loading portfolio analysis...</p>
        }
        @if (portfolio()) {
          <section class="portfolio-heading panel">
            <div>
              <p class="eyebrow">{{ portfolio()?.scope_type }}</p>
              <h2>{{ portfolio()?.name }}</h2>
              <p>{{ portfolio()?.description || 'No portfolio description provided.' }}</p>
            </div>
            <div class="heading-status">
              <span class="status-badge">{{ portfolio()?.status }}</span>
              @if (assessment()?.status === 'not_assessed') {
                <span class="warning-badge">Assessment required</span>
              }
            </div>
          </section>

          <nav class="workspace-tabs" aria-label="Supplier portfolio sections">
            @for (section of sections; track section.id) {
              <a [href]="'#' + section.id">{{ section.label }}</a>
            }
          </nav>

          <section id="overview" class="panel" aria-labelledby="overview-title">
            <h2 id="overview-title">Overview</h2>
            <p class="helper">
              Risk is known exposure. Resilience is the ability to withstand disruption. Confidence
              is the strength of evidence. These are intentionally separate signals.
            </p>
            <div class="metric-grid">
              <article class="metric">
                <span>Resilience</span><strong>{{ value(resilience()?.score) }}</strong
                ><small>{{ value(resilience()?.classification, 'Not calculated') }}</small>
              </article>
              <article class="metric">
                <span>Risk</span
                ><strong>{{
                  value(resilience()?.risk?.['classification'], 'Not calculated')
                }}</strong
                ><small>Known exposure</small>
              </article>
              <article class="metric">
                <span>Confidence</span
                ><strong>{{ value(resilience()?.confidence?.['value']) }}</strong
                ><small>{{
                  value(resilience()?.confidence?.['classification'], 'Not calculated')
                }}</small>
              </article>
              <article class="metric">
                <span>Evidence</span
                ><strong>{{ value(resilience()?.evidence_status, 'Unknown') }}</strong
                ><small>Authoritative backend result</small>
              </article>
              <article class="metric">
                <span>Suppliers</span><strong>{{ members().length }}</strong
                ><small>Versioned membership</small>
              </article>
              <article class="metric">
                <span>Critical dependencies</span
                ><strong>{{ count(dependencies()?.['findings']) }}</strong
                ><small>Review without color-only cues</small>
              </article>
              <article class="metric">
                <span>Alternates</span><strong>{{ count(alternates()?.['items']) }}</strong
                ><small>Product-specific readiness</small>
              </article>
              <article class="metric">
                <span>Open recommendations</span><strong>{{ openRecommendations() }}</strong
                ><small>Human review required</small>
              </article>
            </div>
            @if (resilience()?.evidence_status === 'INSUFFICIENT_EVIDENCE') {
              <div class="notice" role="status">
                <strong>Insufficient evidence.</strong> Some metrics cannot be calculated; the UI
                never substitutes fake zeros.
              </div>
            }
          </section>

          <section id="suppliers" class="panel" aria-labelledby="suppliers-title">
            <h2 id="suppliers-title">Suppliers &amp; exposure</h2>
            @if (!members().length) {
              <p class="empty-state">No supplier memberships are recorded.</p>
            } @else {
              <div class="table-wrap">
                <table>
                  <caption class="sr-only">
                    Supplier exposure
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Supplier</th>
                      <th scope="col">Allocation</th>
                      <th scope="col">Country / region</th>
                      <th scope="col">Risk</th>
                      <th scope="col">Evidence freshness</th>
                      <th scope="col">Alternate readiness</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (member of members(); track member.id) {
                      <tr>
                        <th scope="row">{{ member.supplier_id }}</th>
                        <td>{{ member.allocation_percent ?? 'Unknown' }}%</td>
                        <td>{{ member.country_region || 'Unknown' }}</td>
                        <td>{{ member.risk || 'Unknown' }}</td>
                        <td>{{ member.evidence_freshness }}</td>
                        <td>{{ member.alternate_source_status }}</td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            }
          </section>

          <section id="concentration" class="panel" aria-labelledby="concentration-title">
            <h2 id="concentration-title">Concentration</h2>
            <p class="helper">
              HHI describes concentration, not the whole supplier-risk decision. Lower HHI generally
              means a more distributed allocation.
            </p>
            <div class="metric-grid compact">
              <article class="metric">
                <span>Largest supplier share</span
                ><strong>{{ metric('largest_supplier_share') }}</strong>
              </article>
              <article class="metric">
                <span>Top-three share</span
                ><strong>{{ metric('top_three_supplier_share') }}</strong>
              </article>
              <article class="metric">
                <span>Supplier HHI</span><strong>{{ metric('supplier_hhi') }}</strong>
              </article>
              <article class="metric">
                <span>Country HHI</span><strong>{{ metric('country_hhi') }}</strong>
              </article>
              <article class="metric">
                <span>Region HHI</span><strong>{{ metric('region_hhi') }}</strong>
              </article>
              <article class="metric">
                <span>Source coverage</span
                ><strong>{{
                  value(concentration()?.['coverage_classification'], 'Unknown')
                }}</strong>
              </article>
            </div>
            @if (!concentration()) {
              <p class="empty-state">Concentration is not available until an assessment exists.</p>
            }
          </section>

          <section id="dependencies" class="panel" aria-labelledby="dependencies-title">
            <h2 id="dependencies-title">Dependencies</h2>
            @if (!count(dependencies()?.['findings'])) {
              <p class="empty-state">No dependency findings are available.</p>
            } @else {
              <div class="cards">
                @for (finding of list(dependencies()?.['findings']); track idOf(finding)) {
                  <article class="finding-card">
                    <h3>{{ text(finding, 'dependency_type') }}</h3>
                    <p class="severity">Severity: {{ text(finding, 'severity', 'UNKNOWN') }}</p>
                    <p>{{ text(finding, 'explanation', 'No explanation provided.') }}</p>
                    <p>
                      <strong>Affected:</strong>
                      {{
                        text(finding, 'affected_supplier_id') ||
                          text(finding, 'affected_product_id') ||
                          text(finding, 'affected_capability') ||
                          'Portfolio-level'
                      }}
                    </p>
                    <p>
                      <strong>Missing evidence:</strong> {{ join(finding, 'missing_evidence') }}
                    </p>
                  </article>
                }
              </div>
            }
          </section>

          <section id="alternates" class="panel" aria-labelledby="alternates-title">
            <h2 id="alternates-title">Alternate readiness</h2>
            <p class="helper">
              Readiness is product and requirement specific; it is not a global supplier label.
            </p>
            <div class="readiness-grid">
              @for (state of readinessStates; track state) {
                <span class="readiness-chip" [attr.data-state]="state"
                  >{{ state }} <small>{{ readinessCount(state) }}</small></span
                >
              }
            </div>
            <div class="cards">
              @for (item of list(alternates()?.['items']); track idOf(item)) {
                <article class="finding-card">
                  <h3>{{ text(item, 'readiness_state', 'UNKNOWN') }}</h3>
                  <p><strong>Product:</strong> {{ text(item, 'product_id', 'Not specified') }}</p>
                  <p>{{ text(item, 'reason', 'No reason provided.') }}</p>
                  <p>
                    <strong>Missing or stale evidence:</strong> {{ join(item, 'missing_evidence') }}
                  </p>
                </article>
              }
            </div>
          </section>

          <section id="resilience" class="panel" aria-labelledby="resilience-title">
            <h2 id="resilience-title">Resilience dimensions</h2>
            <div class="dimension-grid">
              @for (dimension of dimensions(); track dimension.dimension) {
                <article class="dimension-card">
                  <h3>{{ dimensionLabel(dimension.dimension) }}</h3>
                  <strong>{{ value(dimension.score, 'Not calculated') }}</strong
                  ><span>{{ dimension.classification }} - {{ dimension.evidence_status }}</span>
                  <p>{{ dimension.explanation }}</p>
                  <p class="muted">Limitations: {{ joinValue(dimension.limitations) }}</p>
                </article>
              }
            </div>
          </section>

          <section id="recommendations" class="panel" aria-labelledby="recommendations-title">
            <h2 id="recommendations-title">Recommendations</h2>
            @if (!recommendations().length) {
              <p class="empty-state">No recommendations are available.</p>
            } @else {
              <div class="cards">
                @for (recommendation of recommendations(); track recommendation.id) {
                  <article class="recommendation-card">
                    <div class="card-heading">
                      <h3>{{ recommendation.recommendation_type }}</h3>
                      <span class="priority-badge">{{ recommendation.priority }}</span>
                    </div>
                    <p>{{ recommendation.reason }}</p>
                    <p><strong>Status:</strong> {{ recommendation.status }}</p>
                    <p>
                      <strong>Evidence gaps:</strong>
                      {{ joinValue(recommendation.missing_evidence) }}
                    </p>
                    <div class="action-row">
                      @for (action of actionsFor(recommendation); track action) {
                        <button type="button" (click)="openAction(action, recommendation)">
                          {{ actionLabel(action) }}
                        </button>
                      }
                    </div>
                  </article>
                }
              </div>
            }
          </section>

          <section id="simulations" class="panel" aria-labelledby="simulations-title">
            <h2 id="simulations-title">Disruption simulations</h2>
            <p class="helper">
              All outcomes below are hypothetical projections based on bounded assumptions, never
              observed facts.
            </p>
            <form
              class="form-grid"
              (submit)="$event.preventDefault(); createSimulation()"
              aria-label="Create bounded simulation"
            >
              <label
                >Simulation type
                <select name="simulation-type" [(ngModel)]="simulationType">
                  <option value="" disabled>Select a type</option>
                  @for (type of simulationTypes; track type) {
                    <option [value]="type">{{ type }}</option>
                  }
                </select></label
              >
              <label
                >Supplier ID (where applicable)<input
                  name="simulation-supplier"
                  [(ngModel)]="simulationSupplierId"
                  placeholder="UUID"
              /></label>
              <label
                >Reduction / increase %<input
                  name="simulation-percent"
                  type="number"
                  min="0"
                  max="100"
                  [(ngModel)]="simulationPercent"
              /></label>
              <label
                >Increase days (lead time)<input
                  name="simulation-days"
                  type="number"
                  min="0"
                  max="365"
                  [(ngModel)]="simulationDays"
              /></label>
              <label
                >Country / region<input name="simulation-geo" [(ngModel)]="simulationGeography"
              /></label>
              <button type="submit" [disabled]="simulationBusy() || !simulationType">
                {{ simulationBusy() ? 'Creating...' : 'Create simulation' }}
              </button>
            </form>
            @if (simulationError()) {
              <p class="error" role="alert">{{ simulationError() }}</p>
            }
            @if (!simulations().length) {
              <p class="empty-state">No simulations yet.</p>
            } @else {
              <div class="cards">
                @for (simulation of simulations(); track simulation.id) {
                  <article class="simulation-card">
                    <div class="card-heading">
                      <h3>{{ simulation.simulation_type }}</h3>
                      <span class="status-badge">{{ simulation.status }}</span>
                    </div>
                    @if (simulation.staleness === 'BASELINE_STALE') {
                      <p class="warning" role="alert">
                        Baseline stale: this historical simulation was not silently rerun.
                      </p>
                    }
                    <p>
                      <strong>Assumptions:</strong> <code>{{ simulation.assumptions | json }}</code>
                    </p>
                    <div class="result-columns">
                      <div>
                        <h4>BASELINE</h4>
                        <pre>{{ simulation.result['baseline'] | json }}</pre>
                      </div>
                      <div>
                        <h4>SIMULATED</h4>
                        <pre>{{ simulation.result['simulated'] | json }}</pre>
                      </div>
                      <div>
                        <h4>DELTA</h4>
                        <pre>{{ simulation.result['delta'] | json }}</pre>
                      </div>
                    </div>
                    <p><strong>Provenance:</strong> SIMULATION ASSUMPTION / SIMULATED RESULT</p>
                  </article>
                }
              </div>
            }
          </section>

          <section id="history" class="panel" aria-labelledby="history-title">
            <h2 id="history-title">Assessment history</h2>
            @if (!history().length) {
              <p class="empty-state">No historical assessments are available.</p>
            } @else {
              <div class="table-wrap">
                <table>
                  <caption class="sr-only">
                    Immutable portfolio assessment history
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Version</th>
                      <th scope="col">Created</th>
                      <th scope="col">Status</th>
                      <th scope="col">Lineage</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (item of history(); track item.id) {
                      <tr>
                        <th scope="row">v{{ item.version }}</th>
                        <td>{{ item.created_at | date: 'medium' }}</td>
                        <td>{{ item.status }}</td>
                        <td>{{ item.id }}</td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            }
          </section>

          <section id="operations" class="panel" aria-labelledby="operations-title">
            <h2 id="operations-title">Operational state</h2>
            <div class="metric-grid compact">
              <article class="metric">
                <span>Stale portfolios</span
                ><strong>{{ operations()?.stale_assessments ?? 0 }}</strong>
              </article>
              <article class="metric">
                <span>Failed simulations</span
                ><strong>{{ operations()?.failed_simulations ?? 0 }}</strong>
              </article>
              <article class="metric">
                <span>Research requests</span
                ><strong>{{ operations()?.research_requests ?? 0 }}</strong>
              </article>
              <article class="metric">
                <span>DD requests</span
                ><strong>{{ operations()?.due_diligence_requests ?? 0 }}</strong>
              </article>
              <article class="metric">
                <span>System Doctor</span><strong>{{ doctorStatus() }}</strong>
              </article>
            </div>
            <p>
              <a routerLink="/operations">Open Operations Control Center</a> -
              <a routerLink="/operations/recovery">Open Recovery Center</a>
            </p>
          </section>

          <section id="report" class="panel report-panel" aria-labelledby="report-title">
            <div class="panel-heading">
              <div>
                <h2 id="report-title">Report view</h2>
                <p class="helper">
                  A print-friendly view of authoritative portfolio data and its methodology
                  boundary.
                </p>
              </div>
              <button type="button" (click)="printReport()">Print report</button>
            </div>
            <div class="report-grid">
              <div>
                <h3>Executive Summary</h3>
                <p>
                  {{ portfolio()?.name }} is {{ portfolio()?.status }} with resilience
                  {{ value(resilience()?.classification, 'not calculated') }}, risk
                  {{ value(resilience()?.risk?.['classification'], 'not calculated') }}, and
                  confidence
                  {{ value(resilience()?.confidence?.['classification'], 'not calculated') }}.
                </p>
              </div>
              <div>
                <h3>Methodology / versions</h3>
                <p>
                  Backend calculation versions remain authoritative. UI labels facts as FACT,
                  VERIFIED, DERIVED, SIMULATION, HUMAN DECISION, RECOMMENDATION, or MISSING
                  EVIDENCE.
                </p>
              </div>
              <div>
                <h3>Limitations</h3>
                <p>
                  No supplier contact, RFQ, order, purchase, payment, or autonomous allocation
                  change is possible from this workspace.
                </p>
              </div>
            </div>
          </section>
        }
      }

      @if (actionDialogOpen()) {
        <div class="dialog-backdrop" role="presentation">
          <section
            class="action-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="action-title"
          >
            <h2 id="action-title">{{ actionLabel(pendingAction()) }}</h2>
            <p>{{ actionDescription(pendingAction()) }}</p>
            <label
              >Rationale
              <textarea
                [(ngModel)]="actionRationale"
                rows="4"
                required
                aria-describedby="action-help"
              ></textarea>
            </label>
            <p id="action-help" class="helper">
              This records a human decision only. It cannot contact a supplier or change allocation.
            </p>
            @if (actionError()) {
              <p class="error" role="alert">{{ actionError() }}</p>
            }
            <div class="action-row">
              <button
                type="button"
                (click)="submitAction()"
                [disabled]="actionBusy() || !actionRationale.trim()"
              >
                {{ actionBusy() ? 'Submitting...' : 'Confirm action' }}</button
              ><button type="button" class="secondary-button" (click)="closeAction()">
                Cancel
              </button>
            </div>
          </section>
        </div>
      }
    </main>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .portfolio-page {
        max-width: 1440px;
        margin: 0 auto;
        padding: 2rem clamp(1rem, 3vw, 3rem) 5rem;
        color: #092536;
      }
      .page-header,
      .panel-heading,
      .portfolio-heading,
      .card-heading {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
      }
      .page-header {
        margin-bottom: 2rem;
      }
      .header-actions,
      .action-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.65rem;
        align-items: center;
      }
      h1 {
        font-size: clamp(2.25rem, 5vw, 4.1rem);
        margin: 0.2rem 0 0.75rem;
      }
      h2 {
        font-size: clamp(1.55rem, 3vw, 2.35rem);
        margin-top: 0;
      }
      h3 {
        margin-top: 0;
      }
      .eyebrow {
        color: #17647c;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }
      .lede,
      .helper {
        color: #4c6c7e;
        max-width: 72rem;
      }
      .panel {
        background: #fff;
        border: 1px solid #c9d9df;
        border-radius: 1rem;
        margin: 1.2rem 0;
        padding: clamp(1rem, 2.5vw, 2rem);
        box-shadow: 0 8px 24px #0b31420d;
      }
      .workspace-tabs {
        display: flex;
        gap: 0.55rem;
        flex-wrap: wrap;
        margin: 1.5rem 0;
        position: sticky;
        top: 0;
        z-index: 2;
        background: #f2f7f8;
        padding: 0.75rem 0;
      }
      .workspace-tabs a,
      .secondary-button {
        border: 1px solid #88adba;
        border-radius: 999px;
        padding: 0.6rem 0.85rem;
        color: #07536b;
        background: #fff;
        text-decoration: none;
      }
      .workspace-tabs a:focus-visible,
      a:focus-visible,
      button:focus-visible,
      input:focus-visible,
      select:focus-visible,
      textarea:focus-visible {
        outline: 3px solid #f2a900;
        outline-offset: 2px;
      }
      button {
        border: 0;
        border-radius: 0.6rem;
        padding: 0.7rem 1rem;
        color: #fff;
        background: #126179;
        cursor: pointer;
        font: inherit;
      }
      button:disabled {
        cursor: not-allowed;
        opacity: 0.55;
      }
      .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 0.8rem;
      }
      .metric {
        border: 1px solid #d2e0e4;
        border-radius: 0.8rem;
        padding: 1rem;
        min-height: 6rem;
        background: #fbfdfd;
      }
      .metric span,
      .metric small {
        display: block;
        color: #4c6c7e;
      }
      .metric strong {
        display: block;
        font-size: 1.65rem;
        margin: 0.35rem 0;
        overflow-wrap: anywhere;
      }
      .compact .metric {
        min-height: 4.5rem;
      }
      .table-wrap {
        overflow-x: auto;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        min-width: 660px;
      }
      th,
      td {
        border-bottom: 1px solid #d8e4e7;
        padding: 0.8rem 0.6rem;
        text-align: left;
        vertical-align: top;
      }
      thead th {
        color: #3b5f70;
        font-size: 0.86rem;
      }
      .cards,
      .dimension-grid,
      .report-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
        gap: 0.9rem;
      }
      .finding-card,
      .recommendation-card,
      .simulation-card,
      .dimension-card {
        border: 1px solid #d2e0e4;
        border-radius: 0.8rem;
        padding: 1rem;
        background: #fbfdfd;
      }
      .dimension-card strong {
        font-size: 1.45rem;
        display: block;
      }
      .dimension-card span {
        color: #17647c;
        font-size: 0.9rem;
      }
      .severity,
      .warning,
      .error {
        color: #9d2020;
        font-weight: 600;
      }
      .priority-badge,
      .status-badge,
      .warning-badge,
      .readiness-chip {
        display: inline-block;
        border-radius: 999px;
        padding: 0.25rem 0.55rem;
        font-size: 0.82rem;
        font-weight: 700;
      }
      .priority-badge {
        background: #fff0cf;
        color: #6e4700;
      }
      .status-badge {
        background: #e0f0f3;
        color: #07536b;
      }
      .warning-badge {
        background: #fff0cf;
        color: #6e4700;
      }
      .readiness-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-bottom: 1rem;
      }
      .readiness-chip {
        background: #e8eef0;
        color: #294d5b;
      }
      .readiness-chip[data-state='READY'] {
        background: #d9f1e1;
        color: #14582c;
      }
      .readiness-chip[data-state='BLOCKED'],
      .readiness-chip[data-state='NOT_READY'] {
        background: #ffe1e1;
        color: #791c1c;
      }
      .form-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
        gap: 1rem;
        align-items: end;
        margin: 1rem 0;
      }
      label {
        display: grid;
        gap: 0.35rem;
        font-weight: 600;
      }
      input,
      select,
      textarea {
        width: 100%;
        box-sizing: border-box;
        border: 1px solid #9bb8c1;
        border-radius: 0.45rem;
        padding: 0.65rem;
        font: inherit;
        color: #092536;
        background: #fff;
      }
      .notice {
        border-left: 4px solid #c78600;
        background: #fff8e8;
        padding: 0.85rem 1rem;
        margin-top: 1rem;
      }
      .empty-state {
        border: 1px dashed #9bb8c1;
        border-radius: 0.7rem;
        padding: 1.2rem;
        color: #4c6c7e;
      }
      .loading {
        color: #17647c;
        font-weight: 700;
      }
      .muted {
        color: #607d89;
        font-size: 0.9rem;
      }
      .result-columns {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.75rem;
      }
      pre {
        overflow: auto;
        white-space: pre-wrap;
        word-break: break-word;
        background: #eef4f5;
        padding: 0.7rem;
        border-radius: 0.4rem;
        max-height: 15rem;
      }
      code {
        overflow-wrap: anywhere;
      }
      .dialog-backdrop {
        position: fixed;
        inset: 0;
        z-index: 10;
        display: grid;
        place-items: center;
        padding: 1rem;
        background: #06202c99;
      }
      .action-dialog {
        width: min(34rem, 100%);
        background: #fff;
        border-radius: 0.9rem;
        padding: 1.4rem;
        box-shadow: 0 20px 60px #0005;
      }
      .sr-only {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
      }
      @media (max-width: 720px) {
        .page-header,
        .portfolio-heading {
          flex-direction: column;
        }
        .header-actions {
          width: 100%;
        }
        .result-columns {
          grid-template-columns: 1fr;
        }
        .workspace-tabs {
          position: static;
        }
        .panel {
          border-radius: 0.65rem;
        }
      }
      @media print {
        .workspace-tabs,
        .header-actions,
        button,
        .action-row,
        form {
          display: none !important;
        }
        .panel {
          box-shadow: none;
          break-inside: avoid;
        }
        .portfolio-page {
          padding: 0;
        }
      }
    `,
  ],
})
export class SupplierPortfolioWorkspaceComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly service = inject(SupplierPortfolioService);

  readonly portfolios = signal<SupplierPortfolio[]>([]);
  readonly portfolio = signal<SupplierPortfolio | null>(null);
  readonly members = signal<PortfolioMember[]>([]);
  readonly assessment = signal<PortfolioAssessment | { status: 'not_assessed' } | null>(null);
  readonly history = signal<PortfolioAssessment[]>([]);
  readonly concentration = signal<JsonMap | null>(null);
  readonly dependencies = signal<JsonMap | null>(null);
  readonly alternates = signal<JsonMap | null>(null);
  readonly resilience = signal<PortfolioAnalysis | null>(null);
  readonly simulations = signal<PortfolioSimulation[]>([]);
  readonly channel = signal<PortfolioProductChannel | null>(null);
  readonly events = signal<JsonMap[]>([]);
  readonly calendar = signal<PortfolioCalendarItem[]>([]);
  readonly operations = signal<PortfolioOperations | null>(null);
  readonly doctor = signal<{ status: string } | null>(null);
  readonly loading = signal(true);
  readonly detailLoading = signal(false);
  readonly error = signal('');
  readonly simulationError = signal('');
  readonly simulationBusy = signal(false);
  readonly actionDialogOpen = signal(false);
  readonly actionBusy = signal(false);
  readonly actionError = signal('');
  readonly pendingAction = signal<string>('');
  readonly pendingRecommendation = signal<PortfolioRecommendation | null>(null);
  readonly portfolioId = signal<string | null>(null);
  actionRationale = '';
  simulationType = '';
  simulationSupplierId = '';
  simulationPercent: number | null = null;
  simulationDays: number | null = null;
  simulationGeography = '';
  readonly simulationTypes = SIMULATION_TYPES;
  readonly readinessStates = READINESS_STATES;
  readonly sections = [
    { id: 'overview', label: 'Overview' },
    { id: 'suppliers', label: 'Suppliers' },
    { id: 'concentration', label: 'Concentration' },
    { id: 'dependencies', label: 'Dependencies' },
    { id: 'alternates', label: 'Alternates' },
    { id: 'resilience', label: 'Resilience' },
    { id: 'recommendations', label: 'Recommendations' },
    { id: 'simulations', label: 'Simulations' },
    { id: 'history', label: 'History' },
    { id: 'operations', label: 'Operations' },
    { id: 'report', label: 'Report' },
  ];

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('portfolioId');
    this.portfolioId.set(id);
    if (id) this.loadDetail(id);
    else this.loadList();
  }

  loadList(): void {
    this.loading.set(true);
    this.error.set('');
    this.service
      .list()
      .then((rows) => this.portfolios.set(rows))
      .catch(() => {
        this.error.set(
          'Supplier portfolio data is unavailable. Check the authenticated API connection and try again.',
        );
        this.portfolios.set([]);
      })
      .finally(() => this.loading.set(false));
  }

  loadDetail(id: string): void {
    this.loading.set(false);
    this.detailLoading.set(true);
    this.error.set('');
    const requests = [
      this.service.detail(id),
      this.service.members(id),
      this.service.assessment(id),
      this.service.history(id),
      this.service.concentration(id),
      this.service.dependencies(id),
      this.service.alternates(id),
      this.service.resilience(id),
      this.service.simulations(id),
      this.service.productChannel(id),
      this.service.events(id),
      this.service.calendar(),
      this.service.operations(),
      this.service.doctor(),
    ] as const;
    Promise.allSettled(requests)
      .then((results) => {
        const [
          detail,
          members,
          assessment,
          history,
          concentration,
          dependencies,
          alternates,
          resilience,
          simulations,
          channel,
          events,
          calendar,
          operations,
          doctor,
        ] = results;
        if (detail.status === 'fulfilled') this.portfolio.set(detail.value);
        else {
          this.error.set(
            'This supplier portfolio could not be loaded. It may not exist or you may not have access.',
          );
          return;
        }
        this.setIfFulfilled(members, this.members);
        this.setIfFulfilled(assessment, this.assessment);
        this.setIfFulfilled(history, this.history);
        this.setIfFulfilled(concentration, this.concentration);
        this.setIfFulfilled(dependencies, this.dependencies);
        this.setIfFulfilled(alternates, this.alternates);
        this.setIfFulfilled(resilience, this.resilience);
        this.setIfFulfilled(simulations, this.simulations);
        this.setIfFulfilled(channel, this.channel);
        this.setIfFulfilled(events, this.events);
        this.setIfFulfilled(calendar, this.calendar);
        this.setIfFulfilled(operations, this.operations);
        this.setIfFulfilled(doctor, this.doctor);
      })
      .catch(() => this.error.set('Portfolio analysis is unavailable. Try again.'))
      .finally(() => this.detailLoading.set(false));
  }

  private setIfFulfilled<T>(
    result: PromiseSettledResult<T>,
    target: { set(value: T): void },
  ): void {
    if (result.status === 'fulfilled') target.set(result.value);
  }

  dimensions(): PortfolioDimension[] {
    return this.resilience()?.dimensions ?? [];
  }

  recommendations(): PortfolioRecommendation[] {
    return this.resilience()?.recommendations ?? [];
  }

  openRecommendations(): number {
    return this.recommendations().filter((row) => row.status === 'OPEN').length;
  }

  list(value: unknown): JsonMap[] {
    return Array.isArray(value)
      ? value.filter((item): item is JsonMap => typeof item === 'object' && item !== null)
      : [];
  }

  count(value: unknown): number {
    return Array.isArray(value) ? value.length : 0;
  }

  idOf(value: JsonMap): string {
    return this.display(value['id'] ?? value['supplier_id'] ?? value);
  }

  text(value: JsonMap, key: string, fallback = ''): string {
    const result = value[key];
    return result === null || result === undefined || result === ''
      ? fallback
      : this.display(result);
  }

  value(value: unknown, fallback = 'Unknown'): string {
    return value === null || value === undefined || value === '' ? fallback : this.display(value);
  }

  metric(key: string): string {
    return this.value(this.concentration()?.[key]);
  }

  join(value: JsonMap, key: string): string {
    return this.joinValue(value[key]);
  }

  joinValue(value: unknown): string {
    return Array.isArray(value)
      ? value.map((item) => this.display(item)).join(', ') || 'None recorded'
      : this.value(value, 'None recorded');
  }

  private display(value: unknown): string {
    if (typeof value === 'string') return value;
    if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
      return String(value);
    }
    if (value === null || value === undefined) return '';
    try {
      return JSON.stringify(value) ?? '';
    } catch {
      return '';
    }
  }

  dimensionLabel(key: string): string {
    return DIMENSION_LABELS[key] ?? key.replaceAll('_', ' ');
  }

  readinessCount(state: string): number {
    return this.list(this.alternates()?.['items']).filter(
      (item) => String(item['readiness_state']) === state,
    ).length;
  }

  actionsFor(recommendation: PortfolioRecommendation): string[] {
    return recommendation.status === 'ARCHIVED'
      ? []
      : ACTIONS.filter(
          (action) =>
            action !== 'REQUEST_MORE_RESEARCH' || recommendation.missing_evidence.length > 0,
        );
  }

  actionLabel(action: string): string {
    return action
      .replaceAll('_', ' ')
      .toLowerCase()
      .replace(/^./, (char) => char.toUpperCase());
  }

  actionDescription(action: string): string {
    if (action === 'ACCEPT_CONCENTRATION')
      return 'This records acceptance of the current concentration. It does not remove dependencies, lower risk, increase resilience, or alter sourcing allocation.';
    if (action === 'CREATE_BACKUP_SCENARIO')
      return 'This creates an internal sourcing scenario request for evaluation. It does not place an order or change supplier allocation.';
    return 'This records a human-controlled portfolio decision and preserves the current assessment lineage.';
  }

  openAction(action: string, recommendation: PortfolioRecommendation): void {
    this.pendingAction.set(action);
    this.pendingRecommendation.set(recommendation);
    this.actionRationale = '';
    this.actionError.set('');
    this.actionDialogOpen.set(true);
  }

  closeAction(): void {
    if (!this.actionBusy()) this.actionDialogOpen.set(false);
  }

  submitAction(): void {
    const id = this.portfolioId();
    if (!id || !this.actionRationale.trim()) return;
    this.actionBusy.set(true);
    this.actionError.set('');
    const recommendation = this.pendingRecommendation();
    this.service
      .action(id, {
        action: this.pendingAction(),
        recommendation_id: recommendation?.id,
        supplier_id: recommendation?.affected_supplier_id ?? this.members()[0]?.supplier_id,
        assessment_version_id: this.portfolio()?.current_assessment_version_id,
        rationale: this.actionRationale.trim(),
        idempotency_key: `portfolio-ui-${this.pendingAction().toLowerCase()}-${Date.now()}`,
      })
      .then(() => {
        this.actionDialogOpen.set(false);
        this.loadDetail(id);
      })
      .catch(() =>
        this.actionError.set(
          'The portfolio action could not be completed. No external action was taken.',
        ),
      )
      .finally(() => this.actionBusy.set(false));
  }

  createSimulation(): void {
    const id = this.portfolioId();
    if (!id || !this.simulationType) return;
    this.simulationBusy.set(true);
    this.simulationError.set('');
    const assumptions: JsonMap = {};
    if (this.simulationSupplierId.trim())
      assumptions['supplier_ids'] = [this.simulationSupplierId.trim()];
    if (this.simulationPercent !== null) {
      assumptions['capacity_reduction_percent'] = this.simulationPercent;
      assumptions['availability_reduction_percent'] = this.simulationPercent;
      assumptions['increase_percent'] = this.simulationPercent;
      assumptions['moq_increase_percent'] = this.simulationPercent;
    }
    if (this.simulationDays !== null) assumptions['increase_days'] = this.simulationDays;
    if (this.simulationGeography.trim()) {
      assumptions['country'] = this.simulationGeography.trim();
      assumptions['region'] = this.simulationGeography.trim();
    }
    this.service
      .createSimulation(id, {
        simulation_type: this.simulationType,
        assumptions,
        idempotency_key: `portfolio-ui-simulation-${Date.now()}`,
      })
      .then(() => this.loadDetail(id))
      .catch(() =>
        this.simulationError.set(
          'Simulation could not be created. Check the bounded assumptions and try again.',
        ),
      )
      .finally(() => this.simulationBusy.set(false));
  }

  doctorStatus(): string {
    return this.doctor()?.status ?? 'Unknown';
  }

  printReport(): void {
    window.print();
  }
}
