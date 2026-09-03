import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import {
  CrossMarketplaceService,
  CanonicalSupplier,
  CrossMarketplaceOperations,
} from './cross-marketplace.service';

@Component({
  selector: 'app-cross-marketplace-supplier',
  standalone: true,
  imports: [FormsModule, JsonPipe, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="workspace" aria-labelledby="supplier-intelligence-title">
      <header class="page-header">
        <div>
          <p class="eyebrow">Intelligence / Supplier Intelligence</p>
          <h1 id="supplier-intelligence-title">Cross-marketplace Supplier Intelligence</h1>
          <p class="lede">One canonical, evidence-first view across independent sources.</p>
        </div>
        <a routerLink="/intelligence">Back to Intelligence</a>
      </header>

      <p class="boundary" role="note">
        Read-only consolidation. Supplier contact, RFQ dispatch, purchasing and payments are
        disabled. Claims remain source-attributed and require human review.
      </p>
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }
      @if (loading()) {
        <p role="status" aria-live="polite">Loading Supplier Intelligence...</p>
      }

      <section class="metrics" aria-label="Supplier operations">
        <article>
          <span>Canonical Suppliers</span
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
          <a [href]="'#' + tab.toLowerCase().replace(' ', '-')">{{ tab }}</a>
        }
      </nav>

      <section id="overview" class="panel" aria-labelledby="overview-title">
        <h2 id="overview-title">Overview</h2>
        <button type="button" (click)="reconcile()" [disabled]="loading()">
          Reconcile accepted evidence
        </button>
        <p>Provider coverage: {{ operations()?.provider_coverage?.join(', ') || 'None yet' }}</p>
        <p>
          External live readiness is separately configured; no provider is contacted by this view.
        </p>
      </section>

      <section id="suppliers" class="panel" aria-labelledby="suppliers-title">
        <div class="section-heading">
          <h2 id="suppliers-title">Suppliers</h2>
          <button type="button" (click)="load()">Refresh</button>
        </div>
        @if (!suppliers().length && !loading()) {
          <p class="empty">No canonical Suppliers yet.</p>
        }
        <div class="table-wrap">
          <table>
            <caption>
              Canonical owner-scoped Supplier projection
            </caption>
            <thead>
              <tr>
                <th scope="col">Supplier</th>
                <th scope="col">Sources</th>
                <th scope="col">Confidence</th>
                <th scope="col">Risk</th>
                <th scope="col">Freshness</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              @for (supplier of suppliers(); track supplier.id) {
                <tr>
                  <th scope="row">{{ supplier.display_name }}</th>
                  <td>{{ supplier.source_diversity?.independent_source_count ?? 0 }}</td>
                  <td>{{ supplier.confidence_score }}</td>
                  <td>{{ supplier.risk?.level || 'UNKNOWN' }}</td>
                  <td>{{ supplier.freshness_status }}</td>
                  <td><button type="button" (click)="select(supplier)">Inspect</button></td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </section>

      @if (selected()) {
        <section id="supplier-detail" class="panel" aria-labelledby="detail-title">
          <h2 id="detail-title">Supplier Detail: {{ selected()?.display_name }}</h2>
          <p>
            <strong>Identity:</strong> {{ selected()?.identity?.state }} —
            {{ selected()?.identity?.rationale }}
          </p>
          <p><strong>Aliases:</strong> {{ selected()?.aliases?.join(', ') || 'None recorded' }}</p>
          <div class="grid">
            <article>
              <h3>Sources</h3>
              <pre>{{ selected()?.freshness?.sources | json }}</pre>
            </article>
            <article>
              <h3>Commercial Intelligence</h3>
              <pre>{{ selected()?.commercial | json }}</pre>
            </article>
            <article>
              <h3>Verification / certifications</h3>
              <pre>{{
                {
                  verification: selected()?.verification,
                  certifications: selected()?.certifications,
                } | json
              }}</pre>
            </article>
            <article>
              <h3>Capabilities / facilities</h3>
              <pre>{{
                { capabilities: selected()?.capabilities, facilities: selected()?.facilities }
                  | json
              }}</pre>
            </article>
            <article>
              <h3>Risk / contradictions</h3>
              <pre>{{
                { risk: selected()?.risk, contradictions: selected()?.contradictions } | json
              }}</pre>
            </article>
            <article>
              <h3>Confidence explanation</h3>
              <pre>{{ selected()?.confidence | json }}</pre>
            </article>
          </div>
          <div class="actions">
            <button type="button" (click)="rank()">Evaluate ranking v1</button>
            <button type="button" (click)="makeReport()">Generate JSON report</button>
            <button type="button" (click)="handoff()">Prepare sourcing handoff</button>
          </div>
        </section>
      }

      <section id="comparison" class="panel" aria-labelledby="comparison-title">
        <h2 id="comparison-title">Comparison</h2>
        <p>Select canonical Supplier IDs separated by commas (2–5).</p>
        <input aria-label="Supplier IDs to compare" [(ngModel)]="comparisonIds" />
        <button type="button" (click)="compare()">Compare Suppliers</button>
        @if (comparison()) {
          <pre>{{ comparison() | json }}</pre>
        }
      </section>

      <section id="reports" class="panel" aria-labelledby="reports-title">
        <h2 id="reports-title">Reports and history</h2>
        <p>
          Reports are server-generated as JSON, Markdown, or escaped HTML. Raw provider payloads and
          secrets are excluded.
        </p>
        @if (reportValue()) {
          <pre>{{ reportValue() | json }}</pre>
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
        .metrics {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .grid {
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
  readonly suppliers = signal<CanonicalSupplier[]>([]);
  readonly selected = signal<CanonicalSupplier | null>(null);
  readonly operations = signal<CrossMarketplaceOperations | null>(null);
  readonly comparison = signal<unknown>(null);
  readonly reportValue = signal<unknown>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  comparisonIds = '';

  constructor() {
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    try {
      const [rows, summary] = await Promise.all([this.service.list(), this.service.operations()]);
      this.suppliers.set(rows);
      this.operations.set(summary);
      this.error.set('');
    } catch {
      this.error.set(
        'Supplier Intelligence is unavailable. Check the authenticated API connection.',
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
    } catch {
      this.error.set('Canonical reconciliation could not be completed.');
    } finally {
      this.loading.set(false);
    }
  }
  select(row: CanonicalSupplier): void {
    this.selected.set(row);
  }
  async compare(): Promise<void> {
    try {
      this.comparison.set(
        await this.service.compare(
          this.comparisonIds
            .split(',')
            .map((value) => value.trim())
            .filter(Boolean),
        ),
      );
    } catch {
      this.error.set('Supplier comparison requires 2–5 valid canonical IDs.');
    }
  }
  async rank(): Promise<void> {
    const row = this.selected();
    if (!row) return;
    try {
      this.reportValue.set(await this.service.ranking(row.id));
    } catch {
      this.error.set('Ranking evaluation could not be completed.');
    }
  }
  async makeReport(): Promise<void> {
    const row = this.selected();
    if (!row) return;
    try {
      this.reportValue.set(await this.service.report(row.id));
    } catch {
      this.error.set('Supplier report could not be generated.');
    }
  }
  async handoff(): Promise<void> {
    const row = this.selected();
    if (!row || !window.confirm('Prepare a human-controlled sourcing handoff?')) return;
    try {
      this.reportValue.set(await this.service.handoff(row.id, true));
    } catch {
      this.error.set('Sourcing handoff could not be prepared.');
    }
  }
}
