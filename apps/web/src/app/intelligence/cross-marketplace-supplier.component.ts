import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import { EvidenceCardComponent } from '../shared/evidence-card.component';
import { PageHeaderComponent } from '../shared/page-header.component';
import {
  BlockedStateComponent,
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { StatusBadgeComponent } from '../shared/status-badge.component';
import type { BreadcrumbItem } from '../shared/ux-foundation.types';
import { intelligenceErrorMessage } from './intelligence-error';
import { SupplierJourneyNavComponent } from './supplier-journey-nav.component';
import { CommerceJourneyService } from '../commerce-journey.service';
import { CommerceJourneyContextComponent } from '../commerce-journey-context.component';

import {
  CrossMarketplaceService,
  CanonicalSupplier,
  CrossMarketplaceOperations,
} from './cross-marketplace.service';

@Component({
  selector: 'app-cross-marketplace-supplier',
  standalone: true,
  imports: [
    BlockedStateComponent,
    BreadcrumbsComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    EvidenceCardComponent,
    FormsModule,
    JsonPipe,
    LoadingStateComponent,
    PageHeaderComponent,
    RouterLink,
    StatusBadgeComponent,
    SupplierJourneyNavComponent,
    CommerceJourneyContextComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="workspace" aria-labelledby="supplier-intelligence-title">
      <app-breadcrumbs [items]="breadcrumbs" />
      <app-page-header
        class="page-header"
        eyebrow="Intelligence / Supplier Intelligence"
        title="Cross-marketplace Supplier Intelligence"
        description="One canonical, evidence-first view across independent sources."
      >
        <a page-header-actions routerLink="/intelligence">Back to Intelligence</a>
      </app-page-header>
      <app-supplier-journey-nav current="discover" />
      <app-commerce-journey-context />

      @if (productContext(); as context) {
        <section class="context-panel" aria-labelledby="research-context-title">
          <p class="eyebrow">Selected product</p>
          <h2 id="research-context-title">{{ context.product || 'Selected product' }}</h2>
          <dl class="context-grid">
            <div>
              <dt>Marketplace</dt>
              <dd>{{ context.marketplace || 'Unknown' }}</dd>
            </div>
            <div>
              <dt>Category</dt>
              <dd>{{ context.category || 'Unknown' }}</dd>
            </div>
            <div>
              <dt>Subcategory</dt>
              <dd>{{ context.subcategory || 'Not established' }}</dd>
            </div>
            <div>
              <dt>Market / region</dt>
              <dd>{{ context.market || context.region || 'Unknown' }}</dd>
            </div>
          </dl>
          <p class="context-source">
            Product context came from Product Research and is preserved as the authoritative scope
            for this supplier research.
          </p>
          @if (researchMode === 'LOCAL_FIXTURE') {
            <p class="fixture-boundary" role="note">Local demo data — not live market evidence.</p>
          }
          <form class="research-form" (submit)="$event.preventDefault(); startResearch()">
            <label
              >Research query <input name="research-query" [(ngModel)]="researchQuery"
            /></label>
            <label
              >Mode
              <select name="research-mode" [(ngModel)]="researchMode">
                <option value="LOCAL_FIXTURE">Local deterministic</option>
                <option value="LIVE_READ_ONLY">Live read-only (configured provider only)</option>
              </select>
            </label>
            <button type="submit" [disabled]="researchBusy() || !researchQuery.trim()">
              Start supplier research
            </button>
          </form>
          @if (research(); as state) {
            <p class="research-status" role="status">
              Supplier research: <strong>{{ state['status'] || 'UNKNOWN' }}</strong> ·
              {{ state['researched_count'] || 0 }} websites researched ·
              {{ state['candidate_count'] || 0 }} candidates found
            </p>
          }
        </section>
      } @else {
        <section class="context-panel" aria-labelledby="choose-product-title">
          <app-blocked-state
            title="Select a product before finding suppliers"
            reason="Supplier results stay blocked until a human-selected product provides an authoritative context."
          />
          <a class="primary-link" routerLink="/intelligence/product-opportunities"
            >Review product opportunities</a
          >
        </section>
      }
      <p class="boundary" role="note">
        Read-only consolidation. Supplier contact, RFQ dispatch, purchasing and payments are
        disabled. Claims remain source-attributed and require human review.
      </p>
      @if (error()) {
        <app-error-state
          title="Supplier discovery is unavailable"
          [message]="error()"
          retryLabel="Retry"
          (retry)="load()"
        />
      }
      @if (loading()) {
        <app-loading-state message="Loading supplier discovery..." />
      }

      <section class="metrics" aria-label="Supplier operations">
        <article>
          <span>Suppliers found</span
          ><strong>{{ operations()?.canonical_supplier_count ?? 0 }}</strong>
        </article>
        <article>
          <span>Multi-source</span
          ><strong>{{ operations()?.multi_source_supplier_count ?? 0 }}</strong>
        </article>
        <article>
          <span>Conflicts</span><strong>{{ operations()?.conflict_count ?? 0 }}</strong>
        </article>
        <article>
          <span>High risk</span><strong>{{ operations()?.high_risk_count ?? 0 }}</strong>
        </article>
        <article>
          <span>Pending review</span><strong>{{ operations()?.pending_review_count ?? 0 }}</strong>
        </article>
      </section>

      <nav class="tabs" aria-label="Supplier Intelligence sections">
        @for (tab of tabs; track tab) {
          <a
            [href]="'#' + tab.toLowerCase().replaceAll(' ', '-')"
            (click)="activateTab($event, tab)"
          >
            {{ tab }}
          </a>
        }
      </nav>

      <section id="overview" class="panel" aria-labelledby="overview-title">
        <h2 id="overview-title">Overview</h2>
        <p class="journey-summary">
          Find possible suppliers first, then compare evidence and continue to shortlist or verify.
          This read-only projection does not select a supplier.
        </p>
        <button type="button" (click)="reconcile()" [disabled]="loading()">
          Reconcile accepted evidence
        </button>
        <p>Provider coverage: {{ operations()?.provider_coverage?.join(', ') || 'None yet' }}</p>
        <p>
          <app-status-badge
            status="PROVIDER_MODE"
            [label]="'Provider mode: ' + providerMode()"
            tone="info"
          />
        </p>
        <p>
          External live readiness is separately configured; no provider is contacted by this view.
        </p>
      </section>

      <section id="suppliers" class="panel" aria-labelledby="suppliers-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Discovered suppliers</p>
            <h2 id="suppliers-title">
              Suppliers for {{ productContext()?.product || 'the selected product' }}
            </h2>
          </div>
          <button type="button" (click)="load()">Refresh</button>
        </div>
        @if (!productContext()) {
          <app-blocked-state
            title="Select a product before finding suppliers"
            reason="Supplier records are not shown as canonical results until they are attached to a selected product."
          />
          <a routerLink="/intelligence/product-opportunities">Review product opportunities</a>
          @if (unscopedSuppliers().length) {
            <details class="advanced-unscoped">
              <summary>Advanced: unscoped supplier records (not canonical journey results)</summary>
              @for (supplier of unscopedSuppliers(); track supplier.id) {
                <p>
                  <button type="button" (click)="select(supplier)">
                    Inspect {{ supplier.display_name }}
                  </button>
                </p>
              }
            </details>
          }
        } @else if (!suppliers().length && !loading()) {
          <app-empty-state
            title="No suppliers were found from the currently available sources"
            message="Research completed with gaps, or supplier research has not started for this product. Adjust the research terms or review the product before trying again."
          >
            <button type="button" (click)="startResearch()" [disabled]="researchBusy()">
              Research again
            </button>
          </app-empty-state>
        }
        <div class="supplier-cards" aria-live="polite">
          @for (supplier of suppliers(); track supplier.id) {
            <article class="supplier-card" [attr.aria-labelledby]="'supplier-' + supplier.id">
              <div class="supplier-card-heading">
                <div>
                  <h3 [id]="'supplier-' + supplier.id">{{ supplier.display_name }}</h3>
                  <p class="supplier-location">{{ supplierLocation(supplier) }}</p>
                </div>
                <span class="provenance-pill">{{ supplierProvenance(supplier) }}</span>
              </div>
              <dl class="supplier-facts">
                <div>
                  <dt>Product match</dt>
                  <dd>{{ supplierProductMatch(supplier) }}</dd>
                </div>
                <div>
                  <dt>Verification</dt>
                  <dd>{{ supplierVerification(supplier) }}</dd>
                </div>
                <div>
                  <dt>Evidence</dt>
                  <dd>{{ supplierEvidenceLabel(supplier) }}</dd>
                </div>
                <div>
                  <dt>Risk</dt>
                  <dd>{{ supplierRisk(supplier) }}</dd>
                </div>
                <div>
                  <dt>Commercial information</dt>
                  <dd>{{ commercialSummary(supplier) }}</dd>
                </div>
                <div>
                  <dt>Freshness</dt>
                  <dd>{{ supplierFreshness(supplier) }}</dd>
                </div>
              </dl>
              <p class="supplier-gap">
                <strong>Important gap:</strong> {{ supplierGap(supplier) }}
              </p>
              <div class="supplier-card-actions">
                <button type="button" (click)="select(supplier)">View supplier</button>
                <label class="compare-check">
                  <input
                    type="checkbox"
                    [checked]="isComparisonSelected(supplier.id)"
                    [disabled]="
                      !isComparisonSelected(supplier.id) && comparisonSelection().size >= 5
                    "
                    (change)="toggleComparison(supplier.id)"
                    [attr.aria-label]="'Select ' + supplier.display_name + ' for comparison'"
                  />
                  Compare this supplier
                </label>
                <a
                  routerLink="/intelligence/supplier-shortlisting"
                  [queryParams]="shortlistParams()"
                  >Shortlist suppliers</a
                >
              </div>
            </article>
          }
        </div>
        @if (productContext() && suppliers().length) {
          <section class="comparison-picker" aria-labelledby="comparison-picker-title">
            <h3 id="comparison-picker-title">Compare selected suppliers</h3>
            <p>
              Select 2–5 suppliers to compare evidence, commercial facts, risks, and verification
              gaps. Comparison is a trade-off view, not an automatic winner.
            </p>
            <button
              type="button"
              (click)="compare()"
              [disabled]="comparisonSelection().size < 2 || comparisonSelection().size > 5"
            >
              Compare selected ({{ comparisonSelection().size }})
            </button>
            @if (comparisonSelection().size >= 5) {
              <p class="muted" role="status">Comparison is limited to five suppliers.</p>
            }
          </section>
        }
      </section>

      @if (selected()) {
        <section id="supplier-detail" class="panel" aria-labelledby="detail-title">
          <p class="eyebrow">Supplier detail</p>
          <h2 id="detail-title">{{ selected()?.display_name }}</h2>
          <p class="detail-lede">
            Supplier information for
            <strong>{{ productContext()?.product || 'the selected product' }}</strong
            >. Review evidence and gaps before deciding what to do next.
          </p>
          <div class="detail-summary-grid">
            <article>
              <h3>Product match</h3>
              <p>{{ supplierProductMatch(selected()!) }}</p>
            </article>
            <article>
              <h3>Where VAYUJIT found them</h3>
              <p>{{ supplierProvenance(selected()!) }}</p>
            </article>
            <article>
              <h3>Verification readiness</h3>
              <p>{{ supplierVerification(selected()!) }}</p>
            </article>
            <article>
              <h3>Risk and important unknowns</h3>
              <p>{{ supplierRisk(selected()!) }} · {{ supplierGap(selected()!) }}</p>
            </article>
          </div>
          <section class="detail-section" aria-labelledby="commercial-title">
            <h3 id="commercial-title">Commercial information</h3>
            <p>{{ commercialSummary(selected()!) }}</p>
            <p class="muted">
              These are source-provided observations, not independently verified quotes.
            </p>
          </section>
          <p>
            <strong>Identity:</strong> {{ selected()?.identity?.state }} —
            {{ selected()?.identity?.rationale }}
          </p>
          <p><strong>Aliases:</strong> {{ selected()?.aliases?.join(', ') || 'None recorded' }}</p>
          <app-evidence-card
            title="Observed supplier facts"
            classification="OBSERVED"
            [summary]="supplierEvidenceSummary()"
            source="Authoritative supplier projection"
            [details]="supplierEvidenceDetails()"
          />
          <details class="advanced-details">
            <summary>Advanced technical details</summary>
            <p class="muted">
              Structured source payloads are available for audit; the summary above remains the
              decision-facing view.
            </p>
            <div class="grid">
              <article>
                <h3>Sources</h3>
                <details>
                  <summary>View source metadata</summary>
                  <pre>{{ selected()?.freshness?.sources | json }}</pre>
                </details>
              </article>
              <article>
                <h3>Commercial Intelligence</h3>
                <p>
                  Observed commercial fields are shown as returned; no comparison winner is
                  inferred.
                </p>
                <details>
                  <summary>View commercial fields</summary>
                  <pre>{{ selected()?.commercial | json }}</pre>
                </details>
              </article>
              <article>
                <h3>Verification / certifications</h3>
                <details>
                  <summary>View verification fields</summary>
                  <pre>{{
                    {
                      verification: selected()?.verification,
                      certifications: selected()?.certifications,
                    } | json
                  }}</pre>
                </details>
              </article>
              <article>
                <h3>Capabilities / facilities</h3>
                <details>
                  <summary>View capability fields</summary>
                  <pre>{{
                    { capabilities: selected()?.capabilities, facilities: selected()?.facilities }
                      | json
                  }}</pre>
                </details>
              </article>
              <article>
                <h3>Risk / contradictions</h3>
                <p>
                  Risk and contradictions remain authoritative review signals, not a purchase
                  verdict.
                </p>
                <details>
                  <summary>View risk and contradiction fields</summary>
                  <pre>{{
                    { risk: selected()?.risk, contradictions: selected()?.contradictions } | json
                  }}</pre>
                </details>
              </article>
              <article>
                <h3>Confidence explanation</h3>
                <details>
                  <summary>View confidence fields</summary>
                  <pre>{{ selected()?.confidence | json }}</pre>
                </details>
              </article>
            </div>
          </details>
          <div class="actions">
            <a
              class="primary-action"
              routerLink="/intelligence/supplier-shortlisting"
              [queryParams]="shortlistParams()"
              >Shortlist this supplier</a
            >
            @if (productContext()) {
              <a
                class="primary-action"
                routerLink="/intelligence/sourcing-economics"
                [queryParams]="economicsParams()"
                >Continue to sourcing economics</a
              >
            }
            <details class="advanced-actions">
              <summary>Advanced research controls</summary>
              <button type="button" (click)="rank()">Evaluate ranking</button>
              <button type="button" (click)="makeReport()">Generate report</button>
              <button type="button" (click)="handoff()">Prepare internal sourcing handoff</button>
            </details>
          </div>
        </section>
      }

      <section id="comparison" class="panel" aria-labelledby="comparison-title">
        <h2 id="comparison-title">Comparison</h2>
        <p>
          Compare selected suppliers in business terms. The result is a trade-off view, not a
          best-supplier or winner decision.
        </p>
        <p>
          Select 2-5 suppliers from the result cards above to compare their evidence and trade-offs.
        </p>
        @if (!productContext()) {
          <app-empty-state
            title="Select a product before comparing suppliers"
            message="Comparison is available only for suppliers attached to the selected product."
          />
        } @else {
          <p>Select suppliers from the result cards above, then choose Compare selected.</p>
          <button type="button" (click)="compare()" [disabled]="comparisonSelection().size < 2">
            Compare selected ({{ comparisonSelection().size }})
          </button>
        }
        @if (comparison()) {
          <div class="comparison-grid" role="table" aria-label="Supplier trade-offs">
            <div class="comparison-row comparison-header" role="row">
              <span role="columnheader">Dimension</span>
              @for (supplier of comparisonSuppliers(); track supplier['id']) {
                <span role="columnheader">{{
                  supplier['display_name'] || supplier['supplier'] || 'Supplier'
                }}</span>
              }
            </div>
            @for (dimension of supplierComparisonDimensions; track dimension.key) {
              <div class="comparison-row" role="row">
                <strong role="rowheader">{{ dimension.label }}</strong>
                @for (supplier of comparisonSuppliers(); track supplier['id']) {
                  <span role="cell">{{ comparisonValue(supplier, dimension.key) }}</span>
                }
              </div>
            }
          </div>
          <p class="comparison-note">
            No winner is selected automatically; review strengths, risks, gaps, and unknowns.
          </p>
        }
      </section>

      <section id="reports" class="panel" aria-labelledby="reports-title">
        <h2 id="reports-title">Reports and history</h2>
        <p>
          Reports are server-generated as JSON, Markdown, or escaped HTML. Raw provider payloads and
          secrets are excluded.
        </p>
        @if (reportValue()) {
          <details open>
            <summary>View server report</summary>
            <pre>{{ reportValue() | json }}</pre>
          </details>
        }
      </section>
    </main>
  `,
  styles: [
    `
      :host {
        display: block;
        padding: 2rem;
        color: #102a43;
      }
      .workspace {
        max-width: 1280px;
        margin: auto;
      }
      .page-header,
      .section-heading {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
      }
      .lede {
        color: #486581;
      }
      .boundary,
      .panel {
        background: #fff;
        border: 1px solid #d9e2ec;
        border-radius: 1rem;
        padding: 1.25rem;
        margin: 1rem 0;
      }
      .boundary {
        border-left: 4px solid #17617a;
      }
      .context-panel {
        background: #edf7f7;
        border: 1px solid #9cc8cf;
        border-left: 4px solid #147d8c;
        border-radius: 0.75rem;
        padding: 1.25rem;
        margin: 1rem 0;
      }
      .context-panel h2 {
        margin: 0.25rem 0;
      }
      .fixture-boundary {
        margin: 0.75rem 0;
        padding: 0.65rem 0.8rem;
        border-left: 3px solid #d49300;
        background: #fff8df;
      }
      .context-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
      }
      .context-grid dt {
        color: #486581;
        font-size: 0.9rem;
      }
      .context-grid dd {
        margin: 0.2rem 0 0;
        font-weight: 600;
      }
      .context-source,
      .muted {
        color: #486581;
      }
      .primary-link,
      .primary-action {
        display: inline-block;
        margin-top: 0.5rem;
        padding: 0.55rem 0.8rem;
        border-radius: 0.4rem;
        background: #17617a;
        color: #fff;
        text-decoration: none;
      }
      .research-form {
        display: grid;
        grid-template-columns: minmax(14rem, 2fr) minmax(12rem, 1fr) auto;
        gap: 0.75rem;
        align-items: end;
      }
      .research-form label {
        display: grid;
        gap: 0.3rem;
      }
      .research-status {
        margin-bottom: 0;
      }
      .card-actions {
        white-space: normal;
      }
      .card-actions a {
        display: inline-block;
        margin: 0.25rem;
      }
      .supplier-cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
        gap: 1rem;
      }
      .supplier-card {
        border: 1px solid #d9e2ec;
        border-radius: 0.75rem;
        padding: 1rem;
        min-width: 0;
      }
      .supplier-card-heading,
      .supplier-card-actions {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-start;
        justify-content: space-between;
        gap: 0.6rem;
      }
      .supplier-card h3 {
        margin: 0;
      }
      .supplier-location {
        margin: 0.25rem 0 0;
        color: #486581;
      }
      .provenance-pill {
        border: 1px solid #9cc8cf;
        border-radius: 999px;
        padding: 0.25rem 0.55rem;
        font-size: 0.8rem;
      }
      .supplier-facts,
      .detail-summary-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.75rem;
        margin: 1rem 0;
      }
      .supplier-facts div,
      .detail-summary-grid article {
        border: 1px solid #e2e8f0;
        border-radius: 0.5rem;
        padding: 0.65rem;
      }
      .supplier-facts dt {
        color: #486581;
        font-size: 0.85rem;
      }
      .supplier-facts dd {
        margin: 0.2rem 0 0;
      }
      .supplier-gap {
        margin-bottom: 0.75rem;
      }
      .compare-check {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
      }
      .compare-check input {
        width: auto;
        min-height: auto;
      }
      .comparison-picker {
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid #d9e2ec;
      }
      .detail-summary-grid h3 {
        margin: 0;
        font-size: 1rem;
      }
      .detail-summary-grid p {
        margin-bottom: 0;
      }
      .comparison-grid {
        overflow-x: auto;
        border: 1px solid #d9e2ec;
        border-radius: 0.5rem;
      }
      .comparison-row {
        display: grid;
        grid-template-columns: minmax(10rem, 1fr) repeat(auto-fit, minmax(12rem, 1fr));
        gap: 0.75rem;
        padding: 0.75rem;
        border-top: 1px solid #e2e8f0;
      }
      .comparison-row:first-child {
        border-top: 0;
      }
      .comparison-header {
        background: #edf7f7;
        font-weight: 700;
      }
      .comparison-note {
        color: #486581;
      }
      .advanced-actions {
        margin-top: 0.75rem;
      }
      .metrics {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 1rem;
      }
      .metrics article {
        background: #fff;
        border: 1px solid #d9e2ec;
        border-radius: 0.75rem;
        padding: 1rem;
      }
      .metrics span,
      .metrics strong {
        display: block;
      }
      .metrics strong {
        font-size: 1.8rem;
        margin-top: 0.5rem;
      }
      .tabs {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        padding: 1rem 0;
      }
      .tabs a {
        color: #17617a;
      }
      .table-wrap {
        overflow: auto;
      }
      .grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
      }
      .grid article {
        border: 1px solid #d9e2ec;
        border-radius: 0.5rem;
        padding: 0.75rem;
        min-width: 0;
      }
      pre {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        max-height: 18rem;
        overflow: auto;
      }
      button {
        min-height: 2.4rem;
        border: 0;
        border-radius: 0.4rem;
        padding: 0.4rem 0.8rem;
        background: #17617a;
        color: #fff;
        margin: 0.25rem;
      }
      .actions {
        margin-top: 1rem;
      }
      .error {
        background: #fff1f1;
        color: #a61b1b;
        padding: 1rem;
      }
      .empty {
        padding: 1rem;
        border: 1px dashed #9fb3c8;
      }
      input {
        min-height: 2.3rem;
        width: min(100%, 44rem);
        padding: 0.4rem;
      }
      @media (max-width: 800px) {
        .research-form {
          grid-template-columns: 1fr;
        }
        .context-grid {
          grid-template-columns: 1fr;
        }
        .metrics {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .grid {
          grid-template-columns: 1fr;
        }
        .supplier-facts,
        .detail-summary-grid {
          grid-template-columns: 1fr;
        }
      }
      @media (max-width: 420px) {
        :host {
          padding: 1rem;
        }
        .metrics {
          grid-template-columns: 1fr;
        }
        .page-header {
          display: block;
        }
      }
    `,
  ],
})
export class CrossMarketplaceSupplierComponent {
  private readonly service = inject(CrossMarketplaceService);
  private readonly route = inject(ActivatedRoute);
  private readonly journey = inject(CommerceJourneyService, { optional: true });
  readonly tabs = [
    'Overview',
    'Suppliers',
    'Supplier Detail',
    'Sources',
    'Commercial',
    'Verification',
    'Capabilities',
    'Facilities',
    'Certifications',
    'Risk',
    'Confidence',
    'Contradictions',
    'Ranking',
    'Comparison',
    'History',
    'Reports',
    'Product Fit',
    'Sourcing Handoff',
  ];
  readonly supplierComparisonDimensions = [
    { key: 'location', label: 'Location' },
    { key: 'product_match', label: 'Product relevance' },
    { key: 'evidence', label: 'Evidence coverage' },
    { key: 'verification', label: 'Verification' },
    { key: 'risk', label: 'Risk' },
    { key: 'confidence', label: 'Confidence' },
    { key: 'commercial', label: 'Commercial facts' },
    { key: 'freshness', label: 'Freshness / unknowns' },
  ];
  readonly suppliers = signal<CanonicalSupplier[]>([]);
  readonly selected = signal<CanonicalSupplier | null>(null);
  readonly operations = signal<CrossMarketplaceOperations | null>(null);
  readonly comparison = signal<unknown>(null);
  readonly reportValue = signal<unknown>(null);
  readonly loading = signal(false);
  readonly productContext = signal<{
    opportunityId: string;
    product: string;
    category: string;
    subcategory: string;
    marketplace: string;
    market: string;
    region: string;
    researchTerms: string;
  } | null>(null);
  readonly unscopedSuppliers = signal<CanonicalSupplier[]>([]);
  readonly comparisonSelection = signal<Set<string>>(new Set());
  readonly research = signal<Record<string, unknown> | null>(null);
  readonly researchBusy = signal(false);
  researchQuery = '';
  researchMode: 'LOCAL_FIXTURE' | 'LIVE_READ_ONLY' = 'LOCAL_FIXTURE';
  readonly error = signal('');
  comparisonIds = '';
  readonly breadcrumbs: BreadcrumbItem[] = [
    { label: 'Intelligence', url: '/intelligence' },
    { label: 'Supplier discovery' },
  ];

  constructor() {
    const params = this.route.snapshot.queryParamMap;
    const opportunityId = params.get('opportunity_id');
    if (opportunityId) {
      const context = {
        opportunityId,
        product: params.get('product') || params.get('name') || '',
        category: params.get('category') || '',
        subcategory: params.get('subcategory') || '',
        marketplace: params.get('marketplace') || '',
        market: params.get('market') || params.get('region') || '',
        region: params.get('region') || '',
        researchTerms: params.get('search_terms') || params.get('research_terms') || '',
      };
      this.productContext.set(context);
      this.researchQuery = context.product || context.category;
    }
    void this.loadActiveJourneyContext();
    void this.load();
  }

  private async loadActiveJourneyContext(): Promise<void> {
    if (!this.journey || this.productContext()) return;
    try {
      const active = await this.journey.active();
      const values = active?.context.values || {};
      const opportunityId = values['selected_product_opportunity_id'];
      if (typeof opportunityId !== 'string' || !opportunityId) return;
      const context = {
        opportunityId,
        product: typeof values['product_name'] === 'string' ? values['product_name'] : '',
        category: typeof values['category'] === 'string' ? values['category'] : '',
        subcategory: typeof values['subcategory'] === 'string' ? values['subcategory'] : '',
        marketplace: typeof values['marketplace'] === 'string' ? values['marketplace'] : '',
        market: typeof values['market'] === 'string' ? values['market'] : '',
        region: typeof values['region'] === 'string' ? values['region'] : '',
        researchTerms: typeof values['search_terms'] === 'string' ? values['search_terms'] : '',
      };
      this.productContext.set(context);
      this.researchQuery = context.product || context.category;
      await this.load();
    } catch {
      // The discovery list remains usable when the optional journey projection is unavailable.
    }
  }

  activateTab(event: Event, tab: string): void {
    event.preventDefault();
    const targetId = tab.toLowerCase().replaceAll(' ', '-');
    document.getElementById(targetId)?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  }

  isComparisonSelected(id: string): boolean {
    return this.comparisonSelection().has(id);
  }
  toggleComparison(id: string): void {
    const next = new Set(this.comparisonSelection());
    if (next.has(id)) next.delete(id);
    else if (next.size < 5) next.add(id);
    this.comparisonSelection.set(next);
  }
  economicsParams(): Record<string, string> {
    const context = this.productContext();
    const selected = this.selected();
    return context
      ? {
          opportunity_id: context.opportunityId,
          product: context.product,
          marketplace: context.marketplace,
          market: context.market || context.region,
          ...(selected ? { supplier_id: selected.id } : {}),
        }
      : {};
  }

  shortlistParams(): Record<string, string> {
    const context = this.productContext();
    if (!context) return {};
    const selected = [...this.comparisonSelection()];
    return {
      opportunity_id: context.opportunityId,
      product: context.product,
      category: context.category,
      marketplace: context.marketplace,
      ...(selected.length ? { supplier_ids: selected.join(',') } : {}),
    };
  }

  private async loadResearchResults(opportunityId: string): Promise<void> {
    try {
      const result = await this.service.researchResults(opportunityId);
      this.research.set((result['research'] as Record<string, unknown>) || null);
      const context = result['product_context'] as Record<string, unknown> | null;
      if (context) {
        this.productContext.set({
          opportunityId:
            typeof context['opportunity_id'] === 'string'
              ? context['opportunity_id']
              : opportunityId,
          product: typeof context['product'] === 'string' ? context['product'] : this.researchQuery,
          category: typeof context['category'] === 'string' ? context['category'] : '',
          subcategory: typeof context['subcategory'] === 'string' ? context['subcategory'] : '',
          marketplace: typeof context['marketplace'] === 'string' ? context['marketplace'] : '',
          market: typeof context['market'] === 'string' ? context['market'] : '',
          region: typeof context['region'] === 'string' ? context['region'] : '',
          researchTerms:
            typeof context['research_terms'] === 'string' ? context['research_terms'] : '',
        });
      }
      const scoped = result['suppliers'];
      if (Array.isArray(scoped)) this.suppliers.set(scoped as CanonicalSupplier[]);
      this.unscopedSuppliers.set([]);
      this.comparisonSelection.set(new Set());
    } catch {
      // The main discovery list remains usable when the optional journey projection is unavailable.
    }
  }

  async startResearch(): Promise<void> {
    const context = this.productContext();
    if (!context || !this.researchQuery.trim()) return;
    this.researchBusy.set(true);
    this.error.set('');
    try {
      const result = await this.service.research({
        product_query: this.researchQuery.trim(),
        product_opportunity_id: context.opportunityId,
        category: context.category,
        mode: this.researchMode,
        max_candidates: 10,
        idempotency_key: `gp4-${context.opportunityId}-${this.researchQuery.trim().toLowerCase()}`,
      });
      const summary = (result['result'] as Record<string, unknown>) || result;
      this.research.set(summary);
      await this.service.reconcile();
      await this.load();
      await this.loadResearchResults(context.opportunityId);
    } catch (error: unknown) {
      this.error.set(intelligenceErrorMessage(error, 'Supplier research could not be completed.'));
    } finally {
      this.researchBusy.set(false);
    }
  }
  async load(): Promise<void> {
    this.loading.set(true);
    try {
      const context = this.productContext();
      if (context) {
        const summary = await this.service.operations();
        await this.loadResearchResults(context.opportunityId);
        const scoped = this.suppliers();
        this.operations.set({
          ...summary,
          canonical_supplier_count: scoped.length,
          multi_source_supplier_count: scoped.filter(
            (row) => (row.source_diversity?.independent_source_count ?? 0) > 1,
          ).length,
          conflict_count: scoped.filter((row) => (row.contradictions?.length ?? 0) > 0).length,
          high_risk_count: scoped.filter((row) => row.risk?.level === 'HIGH').length,
          pending_review_count: scoped.filter((row) => row.identity_state !== 'CONFIRMED').length,
        });
      } else {
        this.suppliers.set([]);
        const [rows, summary] = await Promise.all([this.service.list(), this.service.operations()]);
        this.unscopedSuppliers.set(rows);
        this.operations.set(summary);
      }
      this.error.set('');
    } catch (error: unknown) {
      this.error.set(
        intelligenceErrorMessage(
          error,
          'Supplier Intelligence is unavailable. Check the authenticated API connection.',
        ),
      );
    } finally {
      this.loading.set(false);
    }
  }

  async reconcile(): Promise<void> {
    this.loading.set(true);
    try {
      await this.service.reconcile();
      await this.load();
    } catch (error: unknown) {
      this.error.set(
        intelligenceErrorMessage(error, 'Canonical reconciliation could not be completed.'),
      );
    } finally {
      this.loading.set(false);
    }
  }
  select(row: CanonicalSupplier): void {
    this.selected.set(row);
  }
  providerMode(): string {
    const mode = this.operations()?.['provider_mode'] ?? this.selected()?.['provider_mode'];
    return typeof mode === 'string' && mode.trim() ? mode : 'Not reported';
  }
  supplierLocation(row: CanonicalSupplier): string {
    const locations = Array.isArray(row['business_locations']) ? row['business_locations'] : [];
    return locations.length ? locations.join(', ') : 'Location not established';
  }
  supplierProvenance(row: CanonicalSupplier): string {
    const providers = row.source_diversity?.provider_classes || [];
    if (providers.length) return providers.join(', ');
    const mode = row['provider_mode'];
    return typeof mode === 'string' && mode ? mode : 'Source not reported';
  }
  supplierProductMatch(row: CanonicalSupplier): string {
    const matches = row['product_offering_matches'];
    if (Array.isArray(matches) && matches.length)
      return 'Evidence-supported product/category match';
    return this.productContext()?.category
      ? 'Category relevance is not established'
      : 'Product relevance unknown';
  }
  supplierVerification(row: CanonicalSupplier): string {
    const values = row.verification || [];
    if (!values.length) return 'Verification not started';
    const states = values.map((item) =>
      this.displayValue(item['verification_state'] ?? item['state'] ?? 'unknown'),
    );
    return states.every((value) => ['verified', 'confirmed'].includes(value.toLowerCase()))
      ? 'Verified with evidence'
      : 'Needs evidence or review';
  }
  supplierEvidenceLabel(row: CanonicalSupplier): string {
    const count = row.source_diversity?.independent_source_count ?? 0;
    return count ? `${count} independent source${count === 1 ? '' : 's'}` : 'Insufficient evidence';
  }
  supplierRisk(row: CanonicalSupplier): string {
    const level = row.risk?.level;
    return level && level !== 'UNKNOWN' ? `${level} risk` : 'Risk not established';
  }
  supplierFreshness(row: CanonicalSupplier): string {
    const value = row.freshness_status || row.freshness?.overall;
    return value ? String(value).replaceAll('_', ' ') : 'Freshness not established';
  }
  commercialSummary(row: CanonicalSupplier): string {
    const commercial = row.commercial || {};
    const price = (commercial['price'] as Record<string, unknown> | undefined)?.['minimum'];
    const currencyValues = (commercial['currency_safety'] as Record<string, unknown> | undefined)?.[
      'currencies'
    ];
    const currency = Array.isArray(currencyValues) ? currencyValues : [];
    const moq = (commercial['moq'] as Record<string, unknown> | undefined)?.['minimum'];
    const lead = (commercial['lead_time'] as Record<string, unknown> | undefined)?.['minimum'];
    const facts = [
      price != null
        ? `price ${this.displayValue(currency[0] || '')} ${this.displayValue(price)}`.trim()
        : '',
      moq != null ? `MOQ ${this.displayValue(moq)}` : '',
      lead != null ? `lead time ${this.displayValue(lead)} days` : '',
    ].filter(Boolean);
    return facts.length ? `${facts.join(' · ')} (source-provided)` : 'Commercial facts unknown';
  }
  supplierGap(row: CanonicalSupplier): string {
    if (row.contradictions?.length) return 'Contradictory evidence needs human review';
    if (!row.verification?.length) return 'Verification evidence is missing';
    if (!row.commercial || !Object.keys(row.commercial).length)
      return 'Commercial facts are unknown';
    return 'No additional material gap reported';
  }
  comparisonSuppliers(): Array<Record<string, unknown>> {
    const value = this.comparison() as Record<string, unknown> | null;
    return Array.isArray(value?.['suppliers'])
      ? (value['suppliers'] as Array<Record<string, unknown>>)
      : [];
  }
  comparisonValue(row: Record<string, unknown>, key: string): string {
    const supplier = row as CanonicalSupplier;
    if (key === 'location') return this.supplierLocation(supplier);
    if (key === 'product_match') return this.supplierProductMatch(supplier);
    if (key === 'evidence') return this.supplierEvidenceLabel(supplier);
    if (key === 'verification') return this.supplierVerification(supplier);
    if (key === 'risk') return this.supplierRisk(supplier);
    if (key === 'confidence')
      return supplier['confidence_score'] != null
        ? this.displayValue(supplier['confidence_score'])
        : 'Unknown';
    if (key === 'commercial') return this.commercialSummary(supplier);
    return this.supplierFreshness(supplier) + ' · ' + this.supplierGap(supplier);
  }
  private displayValue(value: unknown): string {
    return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
  }
  supplierEvidenceSummary(): string {
    const row = this.selected();
    if (!row) return 'No supplier selected.';
    return (
      row.display_name +
      ' is an observed supplier projection from ' +
      (row.source_diversity?.independent_source_count ?? 0) +
      ' independent source(s).'
    );
  }
  supplierEvidenceDetails() {
    const row = this.selected();
    return [
      { label: 'Confidence', value: row?.confidence_score },
      { label: 'Freshness', value: row?.freshness_status },
      { label: 'Identity state', value: row?.identity_state },
    ];
  }
  async compare(): Promise<void> {
    const selectedIds = [...this.comparisonSelection()];
    if (selectedIds.length < 2 || selectedIds.length > 5) {
      this.error.set('Select between 2 and 5 suppliers to compare.');
      return;
    }
    try {
      this.comparison.set(await this.service.compare(selectedIds));
      document.getElementById('comparison-title')?.focus?.();
    } catch (error: unknown) {
      this.error.set(
        intelligenceErrorMessage(error, 'Supplier comparison requires 2–5 valid canonical IDs.'),
      );
    }
  }
  async rank(): Promise<void> {
    const row = this.selected();
    if (!row) return;
    try {
      this.reportValue.set(await this.service.ranking(row.id));
    } catch (error: unknown) {
      this.error.set(intelligenceErrorMessage(error, 'Ranking evaluation could not be completed.'));
    }
  }
  async makeReport(): Promise<void> {
    const row = this.selected();
    if (!row) return;
    try {
      this.reportValue.set(await this.service.report(row.id));
    } catch (error: unknown) {
      this.error.set(intelligenceErrorMessage(error, 'Supplier report could not be generated.'));
    }
  }
  async handoff(): Promise<void> {
    const row = this.selected();
    if (!row || !window.confirm('Prepare a human-controlled sourcing handoff?')) return;
    try {
      this.reportValue.set(await this.service.handoff(row.id, true));
    } catch (error: unknown) {
      this.error.set(intelligenceErrorMessage(error, 'Sourcing handoff could not be prepared.'));
    }
  }
}
