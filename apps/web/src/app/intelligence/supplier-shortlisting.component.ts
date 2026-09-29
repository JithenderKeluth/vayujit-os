import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import { EvidenceCardComponent } from '../shared/evidence-card.component';
import { PageHeaderComponent } from '../shared/page-header.component';
import { ActivatedRoute, RouterLink } from '@angular/router';
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
import { SupplierShortlistingService } from './supplier-shortlisting.service';
import { CommerceJourneyContextComponent } from '../commerce-journey-context.component';
import { CommerceJourneyService } from '../commerce-journey.service';

@Component({
  selector: 'app-supplier-shortlisting',
  standalone: true,
  imports: [
    BlockedStateComponent,
    PageHeaderComponent,
    BreadcrumbsComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    EvidenceCardComponent,
    FormsModule,
    JsonPipe,
    LoadingStateComponent,
    RouterLink,
    StatusBadgeComponent,
    SupplierJourneyNavComponent,
    CommerceJourneyContextComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main aria-labelledby="shortlisting-title">
      <app-breadcrumbs [items]="breadcrumbs" />
      <app-page-header
        headingId="shortlisting-title"
        eyebrow="Intelligence / Sourcing"
        title="Supplier Shortlisting"
        description="Explainable, deterministic recommendations for human review."
      />
      <app-supplier-journey-nav current="shortlist" />
      <app-commerce-journey-context />
      @if (carriedContext(); as context) {
        <section class="product-context" aria-labelledby="shortlist-product-title">
          <p class="eyebrow">Selected product</p>
          <h2 id="shortlist-product-title">{{ context.product || 'Selected product' }}</h2>
          <p>
            {{ context.category || 'Category not established' }} ·
            {{ context.marketplace || 'Market not established' }}
          </p>
          <p class="muted">Shortlisting applies only to suppliers researched for this product.</p>
        </section>
      }
      <p class="boundary" role="note">
        INTERNAL HANDOFF ONLY - NO RFQ SENT - NO SUPPLIER CONTACT - NO PURCHASE - NO PAYMENT
      </p>
      @if (error()) {
        <app-error-state
          title="Shortlisting is unavailable"
          [message]="error()"
          retryLabel="Retry"
          (retry)="load()"
        />
      }
      @if (loading()) {
        <app-loading-state message="Loading shortlist evidence..." />
      }
      <section aria-labelledby="overview">
        <h2 id="overview">Shortlisting Overview</h2>
        <div class="metrics">
          <span
            >Active contexts <strong>{{ metrics()?.['active_contexts'] ?? 0 }}</strong></span
          ><span
            >Shortlists <strong>{{ metrics()?.['shortlist_count'] ?? 0 }}</strong></span
          ><span
            >Handoffs <strong>{{ metrics()?.['handoff_count'] ?? 0 }}</strong></span
          >
        </div>
      </section>
      @if (carriedContext(); as context) {
        <p class="context-note" role="status">
          Product context carried from Product Research. Marketplace:
          {{ context.marketplace || 'Unknown' }} · Category: {{ context.category || 'Unknown' }}
        </p>
      }
      <section aria-labelledby="context">
        <h2 id="context">Context</h2>
        @if (contextId) {
          <p class="context-note" role="status">
            The current supplier context is carried from the selected product. No ID entry is
            required for the guided journey.
          </p>
          <button type="button" (click)="evaluate()" [disabled]="loading()">
            Evaluate current shortlist
          </button>
        }
        <details>
          <summary>Advanced context evaluation</summary>
          <label for="context-id">Context ID</label
          ><input id="context-id" [(ngModel)]="contextId" placeholder="UUID" /><button
            type="button"
            (click)="evaluate()"
            [disabled]="loading() || !contextId"
          >
            Evaluate shortlist
          </button>
        </details>
      </section>
      @if (result()) {
        <section aria-labelledby="shortlist">
          <h2 id="shortlist">Shortlist</h2>
          <p>
            The shortlist is server-derived for human review. It is not an automatic supplier winner
            or purchase recommendation.
          </p>
          <app-status-badge
            status="SHORTLIST_RESULT"
            [label]="'Result: ' + shortlistStatus()"
            tone="info"
          />
          <app-evidence-card
            title="Shortlist evidence"
            classification="DERIVED"
            summary="Eligibility, scoring, evidence, risk, freshness, and contradiction gates were evaluated by the authoritative shortlisting service."
            source="Supplier shortlisting projection"
          />
          <details>
            <summary>View shortlist details</summary>
            <pre>{{ result() | json }}</pre>
          </details>
          <div class="shortlist-items">
            @for (item of shortlistItems(); track item['supplier_id']) {
              <article class="shortlist-item">
                <div>
                  <h3>{{ item['supplier'] || 'Supplier' }}</h3>
                  <p>{{ shortlistSummary(item) }}</p>
                  <p class="muted">{{ firstReason(item) }}</p>
                </div>
                @if (decisionFor(item['supplier_id'])) {
                  <span class="decision-state">Shortlisted for verification</span>
                } @else {
                  <button
                    type="button"
                    (click)="shortlistForVerification(item)"
                    [disabled]="loading()"
                  >
                    Shortlist for verification
                  </button>
                }
              </article>
            }
          </div>
        </section>
      } @else if (!loading()) {
        @if ((metrics()?.['context_count'] ?? 0) === 0) {
          <app-blocked-state
            title="Find suppliers before shortlisting"
            reason="Run supplier discovery first, then create a shortlist context from canonical supplier evidence."
          />
          <a routerLink="/intelligence/cross-marketplace">Find suppliers</a>
        } @else {
          <app-empty-state
            title="No shortlist evaluated"
            message="Enter a supplier intelligence context to review the authoritative shortlist."
          />
        }
      }
      <section aria-labelledby="next-step">
        <h2 id="next-step">Next step</h2>
        @if (decisions().size) {
          <p>Review evidence gaps and contradictions for the suppliers you shortlisted.</p>
          <a routerLink="/intelligence/due-diligence">Verify shortlisted suppliers</a>
        } @else {
          <p>Shortlist suppliers before starting verification.</p>
          <a routerLink="/intelligence/cross-marketplace#comparison">Compare suppliers</a>
        }
        <a routerLink="/intelligence/sourcing-scenarios">Compare sourcing scenarios</a>
      </section>
      <section aria-labelledby="safety">
        <h2 id="safety">Safety and readiness</h2>
        <p>
          Eligibility, scoring, evidence, risk, freshness, and contradiction gates are
          server-derived. Human approval is required before an internal sourcing handoff.
        </p>
      </section>
    </main>
  `,
  styles: [
    `
      main {
        padding: 2rem;
        max-width: 1200px;
        margin: auto;
      }
      header {
        margin-bottom: 2rem;
      }
      .boundary {
        padding: 1rem;
        background: #fff3cd;
      }
      .metrics {
        display: flex;
        gap: 2rem;
        flex-wrap: wrap;
      }
      section {
        margin: 1.5rem 0;
        padding: 1.25rem;
        border: 1px solid #ccd8de;
        border-radius: 8px;
      }
      input {
        margin: 0.5rem;
        padding: 0.5rem;
      }
      .product-context,
      .shortlist-item {
        border: 1px solid #c7d7df;
        border-radius: 0.75rem;
        padding: 1rem;
        margin: 1rem 0;
      }
      .shortlist-items {
        display: grid;
        gap: 0.75rem;
      }
      .shortlist-item {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: center;
      }
      .shortlist-item h3 {
        margin: 0;
      }
      .decision-state {
        color: #0f766e;
        font-weight: 700;
      }
      .muted {
        color: #486581;
      }
      @media (max-width: 640px) {
        .shortlist-item {
          display: block;
        }
      }
      button {
        padding: 0.6rem 1rem;
      }
      pre {
        white-space: pre-wrap;
        overflow: auto;
      }
    `,
  ],
})
export class SupplierShortlistingComponent {
  private readonly api = inject(SupplierShortlistingService);
  private readonly route = inject(ActivatedRoute);
  private readonly journey = inject(CommerceJourneyService, { optional: true });
  readonly metrics = signal<Record<string, unknown> | null>(null);
  readonly result = signal<Record<string, unknown> | null>(null);
  readonly decisions = signal<Map<string, Record<string, unknown>>>(new Map());
  readonly error = signal('');
  readonly loading = signal(false);
  readonly carriedContext = signal<{
    opportunityId: string;
    product: string;
    category: string;
    marketplace: string;
  } | null>(null);
  contextId = '';
  readonly breadcrumbs: BreadcrumbItem[] = [
    { label: 'Intelligence', url: '/intelligence' },
    { label: 'Supplier shortlisting' },
  ];
  constructor() {
    const params = this.route.snapshot.queryParamMap;
    const opportunityId = params.get('opportunity_id');
    if (opportunityId) {
      this.carriedContext.set({
        opportunityId,
        product: params.get('product') || '',
        category: params.get('category') || '',
        marketplace: params.get('marketplace') || '',
      });
      void this.prepareContext(opportunityId);
    } else {
      void this.prepareFromJourney();
    }
    void this.load();
  }

  private async prepareFromJourney(): Promise<void> {
    if (!this.journey) return;
    try {
      const active = await this.journey.active();
      const values = active?.context.values || {};
      const opportunityId = values['selected_product_opportunity_id'];
      if (typeof opportunityId !== 'string' || !opportunityId) return;
      this.carriedContext.set({
        opportunityId,
        product: typeof values['product_name'] === 'string' ? values['product_name'] : '',
        category: typeof values['category'] === 'string' ? values['category'] : '',
        marketplace: typeof values['marketplace'] === 'string' ? values['marketplace'] : '',
      });
      await this.prepareContext(opportunityId);
    } catch {
      // Manual/advanced context entry remains available when no product is selected.
    }
  }

  private async prepareContext(opportunityId: string): Promise<void> {
    try {
      const context = await this.api.createContext({
        opportunity_id: opportunityId,
        category: this.carriedContext()?.category || undefined,
        target_market: this.carriedContext()?.marketplace || undefined,
        risk_tolerance: 'medium',
        idempotency_key: `gp4-shortlist-${opportunityId}`,
      });
      this.contextId = typeof context['id'] === 'string' ? context['id'] : '';
    } catch (error: unknown) {
      this.error.set(
        intelligenceErrorMessage(error, 'The supplier shortlist context could not be prepared.'),
      );
    }
  }
  async load() {
    this.loading.set(true);
    this.error.set('');
    try {
      this.metrics.set(await this.api.operations());
    } catch (error: unknown) {
      this.error.set(
        intelligenceErrorMessage(
          error,
          'Supplier shortlisting data is unavailable. Check the authenticated API connection.',
        ),
      );
    } finally {
      this.loading.set(false);
    }
  }
  async evaluate() {
    this.loading.set(true);
    this.error.set('');
    try {
      this.result.set(
        await this.api.shortlist(this.contextId, {
          context_version: 1,
          top_n: 5,
          model_version: 'shortlisting-v1',
          idempotency_key: `ui-${Date.now()}`,
        }),
      );
    } catch (error: unknown) {
      this.error.set(
        intelligenceErrorMessage(error, 'The shortlist could not be evaluated safely.'),
      );
    } finally {
      this.loading.set(false);
    }
  }
  shortlistItems(): Array<Record<string, unknown>> {
    const value = this.result() || {};
    const items = [
      ...(Array.isArray(value['shortlist'])
        ? (value['shortlist'] as Array<Record<string, unknown>>)
        : []),
      ...(Array.isArray(value['review_required'])
        ? (value['review_required'] as Array<Record<string, unknown>>)
        : []),
    ];
    return items;
  }
  shortlistSummary(item: Record<string, unknown>): string {
    const score =
      item['score'] != null ? `Score ${this.displayValue(item['score'])}` : 'Score unavailable';
    const eligibility = this.displayValue(item['eligibility'] || 'REVIEW_REQUIRED').replaceAll(
      '_',
      ' ',
    );
    const recommendation = this.displayValue(
      item['recommendation'] || 'REVIEW_REQUIRED',
    ).replaceAll('_', ' ');
    return `${eligibility} · ${recommendation} · ${score}`;
  }
  firstReason(item: Record<string, unknown>): string {
    const reason = item['reason'];
    return Array.isArray(reason) && reason.length
      ? this.displayValue(reason[0])
      : 'Evidence and risk gates remain server-derived.';
  }
  decisionFor(id: unknown): Record<string, unknown> | null {
    return typeof id === 'string' ? this.decisions().get(id) || null : null;
  }
  async shortlistForVerification(item: Record<string, unknown>): Promise<void> {
    const supplierId = this.displayValue(item['supplier_id']);
    if (!this.contextId || !supplierId || !this.result()?.['id']) return;
    this.loading.set(true);
    this.error.set('');
    try {
      const decision = await this.api.decide(this.contextId, {
        shortlist_version_id: this.result()?.['id'],
        supplier_id: supplierId,
        decision: 'KEEP_UNDER_REVIEW',
        reason: 'Human selected this supplier for deeper verification.',
        evidence_ids: [],
        decision_key: `ui-shortlist-${this.contextId}-${supplierId}`,
      });
      const next = new Map(this.decisions());
      next.set(supplierId, decision);
      this.decisions.set(next);
    } catch (error: unknown) {
      this.error.set(
        intelligenceErrorMessage(error, 'The supplier could not be shortlisted safely.'),
      );
    } finally {
      this.loading.set(false);
    }
  }
  private displayValue(value: unknown): string {
    return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
  }
  shortlistStatus(): string {
    const status = this.result()?.['status'];
    return typeof status === 'string' && status.trim() ? status : 'Available for review';
  }
}
