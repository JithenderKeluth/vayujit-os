/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unsafe-assignment, @typescript-eslint/no-unsafe-member-access, @typescript-eslint/no-redundant-type-constituents */
import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

type Json = any;

@Component({
  selector: 'app-ads-optimization',
  standalone: true,
  imports: [CommonModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="optimization-shell" aria-labelledby="optimization-title">
      <header class="page-header">
        <div>
          <p class="eyebrow">Ads and Marketing Automation</p>
          <h1 id="optimization-title">Optimization intelligence</h1>
          <p>Deterministic, owner-scoped recommendations with explicit review gates.</p>
        </div>
        <a routerLink="/ads">Back to Ads workspace</a>
      </header>
      <nav class="tabs" aria-label="Optimization navigation">
        @for (tab of tabs; track tab.path) {
          <a [routerLink]="tab.path" [class.active]="section() === tab.key">{{ tab.label }}</a>
        }
      </nav>
      <p class="notice">
        Synthetic / Local Simulation: no live provider spend or remote mutation occurs here.
      </p>
      @if (error()) {
        <div class="alert" role="alert">{{ error() }}</div>
      }
      @if (loading()) {
        <p aria-live="polite">Loading optimization intelligence...</p>
      }
      @if (!loading()) {
        @if (section() === 'overview') {
          <section class="cards">
            @for (card of overviewCards(); track card.label) {
              <article>
                <span>{{ card.label }}</span
                ><strong>{{ card.value }}</strong>
              </article>
            }
          </section>
          <section class="panel">
            <h2>Review queue</h2>
            <p>
              Preview recommendations before any mutation. Confirmations create durable Ads jobs for
              the local worker.
            </p>
            <button (click)="evaluate()">Evaluate campaigns</button>
          </section>
        } @else if (section() === 'recommendations') {
          <section class="panel">
            <h2>Recommendations</h2>
            <button (click)="evaluate()">Evaluate campaigns</button>
            @if (!recommendations.length) {
              <p>No recommendations are available yet.</p>
            }
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Campaign</th>
                  <th>Severity</th>
                  <th>Confidence</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                @for (item of recommendations; track item.id) {
                  <tr>
                    <td>{{ item.type || item.recommendation_type }}</td>
                    <td>{{ item.campaign_id }}</td>
                    <td>{{ item.severity }}</td>
                    <td>{{ item.confidence }}</td>
                    <td><button (click)="preview(item)">Preview</button></td>
                  </tr>
                }
              </tbody>
            </table>
          </section>
        } @else if (section() === 'rules') {
          <section class="panel">
            <h2>Optimization rules</h2>
            @if (!rules.length) {
              <p>No rules configured.</p>
            }
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Provider</th>
                  <th>Mode</th>
                  <th>Version</th>
                  <th>Enabled</th>
                </tr>
              </thead>
              <tbody>
                @for (rule of rules; track rule.id) {
                  <tr>
                    <td>{{ rule.name }}</td>
                    <td>{{ rule.provider }}</td>
                    <td>{{ rule.mode }}</td>
                    <td>{{ rule.version }}</td>
                    <td>{{ rule.enabled ? 'Yes' : 'No' }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </section>
        } @else if (section() === 'anomalies') {
          <section class="panel">
            <h2>Anomalies and fatigue</h2>
            @if (!anomalies.length && !fatigue.length) {
              <p>No bounded anomaly or fatigue signals detected.</p>
            }
            @for (item of anomalies; track item.id) {
              <article>
                <strong>{{ item.anomaly_type }}</strong
                ><span>{{ item.severity }} · {{ item.status }}</span>
              </article>
            }
            @for (item of fatigue; track item.id) {
              <article>
                <strong>Creative fatigue: {{ item.fatigue_state }}</strong
                ><span>{{ item.creative_age_days }} days</span>
              </article>
            }
          </section>
        } @else if (section() === 'experiments') {
          <section class="panel">
            <h2>Experiments</h2>
            <p>
              Experiments require two or more variants, 100% allocation, a primary metric, and
              deterministic winner evidence.
            </p>
          </section>
        } @else if (section() === 'comparison') {
          <section class="panel">
            <h2>Cross-provider comparison</h2>
            <p>
              Results are normalized by provider, currency, objective, attribution window, and
              metric availability.
            </p>
            <pre>{{ comparison | json }}</pre>
          </section>
        } @else {
          <section class="panel">
            <h2>Optimization history</h2>
            @if (!history.length) {
              <p>No optimization decisions or executions yet.</p>
            }
            @for (item of history; track item.id) {
              <article>
                <strong>{{ item.action || item.recommendation_type }}</strong
                ><span>{{ item.status || item.decision_status }}</span>
              </article>
            }
          </section>
        }
      }
      @if (previewItem()) {
        <div class="modal-backdrop">
          <section class="modal" role="dialog" aria-modal="true" aria-labelledby="preview-title">
            <h2 id="preview-title">Preview optimization</h2>
            <pre>{{ previewItem() | json }}</pre>
            <p>
              Preview is non-mutating. Confirmation is required and stale fingerprints are rejected.
            </p>
            <button (click)="closePreview()">Close</button>
          </section>
        </div>
      }
    </main>
  `,
  styles: [
    `
      :host {
        display: block;
        color: #102a43;
      }
      .optimization-shell {
        max-width: 1200px;
        margin: 0 auto;
        padding: 2rem;
      }
      .page-header {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
      }
      .eyebrow {
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #5b7185;
      }
      .tabs {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin: 1.5rem 0;
      }
      .tabs a {
        padding: 0.65rem 0.9rem;
        border: 1px solid #a8c3d2;
        border-radius: 999px;
        color: #155e75;
        text-decoration: none;
      }
      .tabs a.active {
        background: #155e75;
        color: white;
      }
      .notice,
      .alert {
        padding: 0.8rem 1rem;
        margin: 1rem 0;
        border-radius: 0.4rem;
      }
      .notice {
        background: #eef6f8;
      }
      .alert {
        background: #fff0f0;
        color: #991b1b;
      }
      .cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 1rem;
      }
      .cards article,
      .panel {
        background: white;
        border: 1px solid #d5e1e8;
        border-radius: 0.75rem;
        padding: 1.2rem;
        margin: 1rem 0;
      }
      .cards article {
        display: grid;
        gap: 0.5rem;
      }
      .cards strong {
        font-size: 2rem;
      }
      button {
        background: #155e75;
        color: white;
        border: 0;
        border-radius: 0.4rem;
        padding: 0.6rem 1rem;
        cursor: pointer;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 1rem;
      }
      th,
      td {
        padding: 0.7rem;
        text-align: left;
        border-bottom: 1px solid #e1e9ee;
      }
      pre {
        white-space: pre-wrap;
        background: #f6f9fa;
        padding: 1rem;
        border-radius: 0.4rem;
      }
      .modal-backdrop {
        position: fixed;
        inset: 0;
        background: #102a4366;
        display: grid;
        place-items: center;
        padding: 1rem;
      }
      .modal {
        background: white;
        max-width: 700px;
        max-height: 85vh;
        overflow: auto;
        padding: 1.5rem;
        border-radius: 0.8rem;
      }
      article {
        display: flex;
        gap: 1rem;
        padding: 0.8rem 0;
        border-bottom: 1px solid #e1e9ee;
      }
    `,
  ],
})
export class AdsOptimizationComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly section = signal('overview');
  readonly previewItem = signal<Json | null>(null);
  recommendations: Json[] = [];
  rules: Json[] = [];
  anomalies: Json[] = [];
  fatigue: Json[] = [];
  history: Json[] = [];
  comparison: Json = {};
  overview: Json = {};
  readonly tabs = [
    { key: 'overview', label: 'Overview', path: '/ads/optimization' },
    { key: 'recommendations', label: 'Recommendations', path: '/ads/recommendations' },
    { key: 'rules', label: 'Rules', path: '/ads/optimization-rules' },
    { key: 'anomalies', label: 'Anomalies & fatigue', path: '/ads/anomalies' },
    { key: 'experiments', label: 'Experiments', path: '/ads/experiments' },
    { key: 'history', label: 'History', path: '/ads/optimization-history' },
    { key: 'comparison', label: 'Comparison', path: '/ads/comparison' },
  ];
  ngOnInit(): void {
    this.route.url.subscribe((segments) => {
      const value = segments.at(-1)?.path;
      this.section.set(
        value === 'recommendations'
          ? 'recommendations'
          : value === 'optimization-rules'
            ? 'rules'
            : value === 'anomalies'
              ? 'anomalies'
              : value === 'experiments'
                ? 'experiments'
                : value === 'optimization-history'
                  ? 'history'
                  : value === 'comparison'
                    ? 'comparison'
                    : 'overview',
      );
      void this.refresh();
    });
  }
  overviewCards() {
    return [
      {
        label: 'Open recommendations',
        value: this.overview.open_recommendations ?? this.recommendations.length,
      },
      {
        label: 'Enabled rules',
        value: this.overview.enabled_rules ?? this.rules.filter((item) => item.enabled).length,
      },
      { label: 'Anomalies', value: this.anomalies.length },
      { label: 'Fatigue signals', value: this.fatigue.length },
    ];
  }
  async refresh(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const [overview, recommendations, rules, anomalies, fatigue, history, comparison] =
        await Promise.all([
          firstValueFrom(this.http.get<Json>('/api/v1/ads/optimization/overview')),
          firstValueFrom(this.http.get<Json[]>('/api/v1/ads/recommendations')),
          firstValueFrom(this.http.get<Json[]>('/api/v1/ads/optimization-rules')),
          firstValueFrom(this.http.get<Json[]>('/api/v1/ads/anomalies')),
          firstValueFrom(this.http.get<Json[]>('/api/v1/ads/creative-fatigue')),
          firstValueFrom(this.http.get<Json[]>('/api/v1/ads/optimization-history')),
          firstValueFrom(this.http.get<Json>('/api/v1/ads/comparison')),
        ]);
      this.overview = overview;
      this.recommendations = recommendations;
      this.rules = rules;
      this.anomalies = anomalies;
      this.fatigue = fatigue;
      this.history = history;
      this.comparison = comparison;
    } catch {
      this.error.set('Optimization data is unavailable. Check the authenticated API connection.');
    } finally {
      this.loading.set(false);
    }
  }
  async evaluate() {
    try {
      await firstValueFrom(this.http.post<Json>('/api/v1/ads/optimization/evaluate', {}));
      await this.refresh();
    } catch {
      this.error.set('Evaluation could not be completed safely.');
    }
  }
  async preview(item: Json) {
    try {
      this.previewItem.set(
        await firstValueFrom(
          this.http.post<Json>(`/api/v1/ads/recommendations/${item.id}/preview`, {}),
        ),
      );
    } catch {
      this.error.set('This recommendation is stale or unavailable; refresh and preview again.');
    }
  }
  closePreview() {
    this.previewItem.set(null);
  }
}
