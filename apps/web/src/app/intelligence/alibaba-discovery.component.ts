import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import {
  AlibabaDiscoveryRequestRecord,
  AlibabaDiscoveryResult,
  AlibabaPreflight,
  IntelligenceService,
} from './intelligence.service';

@Component({
  selector: 'app-alibaba-discovery',
  standalone: true,
  imports: [DatePipe, FormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="workspace" aria-labelledby="alibaba-title">
      <header class="page-header">
        <div>
          <p class="eyebrow">Intelligence / Supplier discovery</p>
          <h1 id="alibaba-title">Alibaba read-only discovery</h1>
          <p class="lede">
            Deterministic, owner-scoped supplier candidates with discovery-only evidence.
          </p>
        </div>
        <a routerLink="/intelligence">Back to Intelligence</a>
      </header>

      <section class="boundary" aria-labelledby="boundary-title">
        <h2 id="boundary-title">Provider boundary</h2>
        <p>
          Mode: <strong>{{ preflight()?.mode || 'DISABLED' }}</strong> · Readiness:
          <strong>{{ preflight()?.status || 'UNKNOWN' }}</strong> · Live validation:
          <strong>{{ preflight()?.live_validation || 'NOT_RUN' }}</strong>
        </p>
        <p class="muted">
          No contact, RFQ, order, payment, supplier modification, or raw provider payload is
          supported.
        </p>
        <p class="muted">Risk status: unverified claims require human review.</p>
      </section>

      @if (loading()) {
        <p role="status" aria-live="polite">Loading Alibaba discovery…</p>
      }
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }

      <section class="panel" aria-labelledby="discover-title">
        <div class="section-heading">
          <h2 id="discover-title">Run local discovery</h2>
          <span class="status-pill">DISCOVERY ONLY</span>
        </div>
        <form (submit)="discover($event)" aria-label="Alibaba discovery request">
          <label
            >Product or category query<input
              name="query"
              [(ngModel)]="query"
              required
              minlength="2"
              maxlength="240"
          /></label>
          <label
            >Country code<input
              name="country"
              [(ngModel)]="countryCode"
              maxlength="2"
              placeholder="CN"
          /></label>
          <label>Region<input name="region" [(ngModel)]="region" maxlength="120" /></label>
          <label
            >Result limit<input
              name="limit"
              type="number"
              [(ngModel)]="resultLimit"
              min="1"
              max="20"
          /></label>
          <button type="submit" [disabled]="loading() || query.trim().length < 2">
            Search suppliers
          </button>
        </form>
      </section>

      <section class="panel" aria-labelledby="history-title">
        <div class="section-heading">
          <h2 id="history-title">Discovery history</h2>
          <button type="button" (click)="load()" [disabled]="loading()">Refresh</button>
        </div>
        @if (!history().length && !loading()) {
          <p class="empty">No Alibaba discovery runs yet.</p>
        }
        @if (history().length) {
          <div class="table-wrap">
            <table>
              <caption>
                Owner-scoped discovery requests
              </caption>
              <thead>
                <tr>
                  <th scope="col">Query</th>
                  <th scope="col">Status</th>
                  <th scope="col">Results</th>
                  <th scope="col">Created</th>
                </tr>
              </thead>
              <tbody>
                @for (run of history(); track run.id) {
                  <tr>
                    <td>
                      <button class="text-button" type="button" (click)="select(run)">
                        {{ run.query }}
                      </button>
                    </td>
                    <td>{{ run.status }}</td>
                    <td>{{ run.result_count }}</td>
                    <td>{{ run.created_at | date: 'medium' }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>

      @if (selectedResults().length) {
        <section class="panel" aria-labelledby="results-title">
          <div class="section-heading">
            <h2 id="results-title">Normalized listings</h2>
            <span class="status-pill">DISCOVERY ONLY</span>
          </div>
          <div class="table-wrap">
            <table>
              <caption>
                Provider claims are not verified commercial truth
              </caption>
              <thead>
                <tr>
                  <th scope="col">Supplier</th>
                  <th scope="col">Listing</th>
                  <th scope="col">Location</th>
                  <th scope="col">Match</th>
                  <th scope="col">Claims</th>
                  <th scope="col">Evidence</th>
                </tr>
              </thead>
              <tbody>
                @for (row of selectedResults(); track row.id) {
                  <tr>
                    <td>{{ row.supplier_name }}</td>
                    <td>{{ row.listing_name }}</td>
                    <td>{{ row.location || 'Unknown' }}</td>
                    <td>{{ row.product_match }}</td>
                    <td>{{ claimText(row) }}</td>
                    <td>{{ row.evidence_id ? 'Discovery evidence' : 'None' }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        </section>
      }
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
        max-width: 1200px;
        margin: 0 auto;
      }
      .page-header,
      .section-heading {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
      }
      .lede,
      .muted {
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
      form {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 1rem;
        align-items: end;
      }
      label {
        display: grid;
        gap: 0.35rem;
        font-weight: 600;
      }
      input {
        min-height: 2.5rem;
        padding: 0.4rem 0.6rem;
        border: 1px solid #9fb3c8;
        border-radius: 0.4rem;
      }
      button {
        min-height: 2.5rem;
        border: 0;
        border-radius: 0.4rem;
        padding: 0.4rem 0.8rem;
        background: #17617a;
        color: white;
        cursor: pointer;
      }
      button:focus-visible,
      input:focus-visible,
      a:focus-visible {
        outline: 3px solid #0b6e99;
        outline-offset: 2px;
      }
      button:disabled {
        opacity: 0.55;
        cursor: not-allowed;
      }
      .status-pill {
        border: 1px solid #9fb3c8;
        border-radius: 99px;
        padding: 0.35rem 0.65rem;
        font-size: 0.8rem;
      }
      .error {
        color: #a61b1b;
      }
      .empty {
        color: #627d98;
      }
      .table-wrap {
        overflow-x: auto;
      }
      table {
        width: 100%;
        border-collapse: collapse;
      }
      th,
      td {
        text-align: left;
        padding: 0.65rem;
        border-bottom: 1px solid #d9e2ec;
        vertical-align: top;
      }
      caption {
        text-align: left;
        padding: 0.5rem 0;
        color: #486581;
      }
      .text-button {
        background: transparent;
        color: #0b6e99;
        padding: 0;
        min-height: auto;
        text-decoration: underline;
      }
      @media (max-width: 768px) {
        :host {
          padding: 1rem;
        }
        form {
          grid-template-columns: 1fr 1fr;
        }
        .page-header,
        .section-heading {
          flex-direction: column;
        }
      }
      @media (max-width: 390px) {
        form {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class AlibabaDiscoveryComponent {
  private readonly service = inject(IntelligenceService);
  readonly preflight = signal<AlibabaPreflight | null>(null);
  readonly history = signal<AlibabaDiscoveryRequestRecord[]>([]);
  readonly selectedResults = signal<AlibabaDiscoveryResult[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  query = '';
  countryCode = 'CN';
  region = '';
  resultLimit = 10;

  constructor() {
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const [preflight, history] = await Promise.all([
        this.service.alibabaPreflight(),
        this.service.alibabaHistory(),
      ]);
      this.preflight.set(preflight);
      this.history.set(history);
    } catch {
      this.error.set('Alibaba discovery is unavailable. Check the authenticated API connection.');
    } finally {
      this.loading.set(false);
    }
  }

  async discover(event: Event): Promise<void> {
    event.preventDefault();
    this.loading.set(true);
    this.error.set('');
    try {
      const response = await this.service.alibabaDiscover({
        query: this.query,
        country_code: this.countryCode || undefined,
        region: this.region || undefined,
        result_limit: this.resultLimit,
      });
      this.selectedResults.set(response.results);
      await this.load();
    } catch {
      this.error.set(
        'Discovery could not be completed. The provider may be disabled or not configured.',
      );
      this.loading.set(false);
    }
  }

  async select(run: AlibabaDiscoveryRequestRecord): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      this.selectedResults.set((await this.service.alibabaDetail(run.id)).results);
    } catch {
      this.error.set('The selected discovery run is unavailable.');
    } finally {
      this.loading.set(false);
    }
  }

  claimText(row: AlibabaDiscoveryResult): string {
    const parts = [
      row.price_claim != null && row.currency ? `${row.currency} ${row.price_claim}` : null,
      row.moq_claim != null ? `MOQ ${row.moq_claim} ${row.moq_unit || ''}` : null,
      row.lead_time_claim ? `Lead ${row.lead_time_claim}` : null,
      row.availability_claim,
    ].filter(Boolean);
    return parts.join(' · ') || 'Unknown';
  }
}
