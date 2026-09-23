import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import { EvidenceCardComponent } from '../shared/evidence-card.component';
import { RouterLink } from '@angular/router';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { StatusBadgeComponent } from '../shared/status-badge.component';
import type { BreadcrumbItem } from '../shared/ux-foundation.types';
import { SupplierJourneyNavComponent } from './supplier-journey-nav.component';
import { SupplierShortlistingService } from './supplier-shortlisting.service';

@Component({
  selector: 'app-supplier-shortlisting',
  standalone: true,
  imports: [
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
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main aria-labelledby="shortlisting-title">
      <app-breadcrumbs [items]="breadcrumbs" />
      <header>
        <p>Intelligence / Sourcing</p>
        <h1 id="shortlisting-title">Supplier Shortlisting</h1>
        <p>Explainable, deterministic recommendations for human review.</p>
      </header>
      <app-supplier-journey-nav current="shortlist" />
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
      <section aria-labelledby="context">
        <h2 id="context">Context</h2>
        <label for="context-id">Context ID</label
        ><input id="context-id" [(ngModel)]="contextId" placeholder="UUID" /><button
          type="button"
          (click)="evaluate()"
          [disabled]="loading() || !contextId"
        >
          Evaluate shortlist
        </button>
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
        </section>
      } @else if (!loading()) {
        <app-empty-state
          title="No shortlist evaluated"
          message="Enter a supplier intelligence context to review the authoritative shortlist."
        />
      }
      <section aria-labelledby="next-step">
        <h2 id="next-step">Continue verification</h2>
        <p>Review evidence gaps and contradictions before comparing sourcing scenarios.</p>
        <a routerLink="/intelligence/due-diligence">Open Supplier Verification</a>
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
  readonly metrics = signal<Record<string, unknown> | null>(null);
  readonly result = signal<Record<string, unknown> | null>(null);
  readonly error = signal('');
  readonly loading = signal(false);
  contextId = '';
  readonly breadcrumbs: BreadcrumbItem[] = [
    { label: 'Intelligence', url: '/intelligence' },
    { label: 'Supplier shortlisting' },
  ];
  constructor() {
    void this.load();
  }
  async load() {
    this.loading.set(true);
    try {
      this.metrics.set(await this.api.operations());
    } catch {
      this.error.set(
        'Supplier shortlisting data is unavailable. Check the authenticated API connection.',
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
    } catch {
      this.error.set('The shortlist could not be evaluated safely.');
    } finally {
      this.loading.set(false);
    }
  }
  shortlistStatus(): string {
    const status = this.result()?.['status'];
    return typeof status === 'string' && status.trim() ? status : 'Available for review';
  }
}
