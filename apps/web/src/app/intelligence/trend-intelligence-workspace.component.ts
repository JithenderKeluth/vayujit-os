import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  TrendAnalysis,
  TrendAnalysisSeries,
  TrendContext,
  TrendIngestion,
  TrendIntelligenceService,
  TrendObservation,
  TrendSnapshot,
} from './trend-intelligence.service';

@Component({
  selector: 'app-trend-intelligence-workspace',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="workspace" aria-labelledby="trend-title">
      <p><a routerLink="/intelligence">Back to Intelligence</a></p>
      <h1 id="trend-title">Trend Intelligence</h1>
      <p>Evidence-first observations with immutable, owner-scoped snapshots.</p>
      <form (ngSubmit)="create()">
        <label>Context name <input name="name" [(ngModel)]="name" required /></label>
        <label
          >Subject type
          <select name="subjectType" [(ngModel)]="subjectType">
            <option>PRODUCT</option>
            <option>BRAND</option>
            <option>CATEGORY</option>
            <option>KEYWORD</option>
            <option>CUSTOM</option>
          </select></label
        >
        <label>Subject key <input name="subjectKey" [(ngModel)]="subjectKey" required /></label>
        <button type="submit">Create context</button>
      </form>
      @if (error()) {
        <p role="alert">{{ error() }}</p>
      }
      @if (contexts().length) {
        <section aria-labelledby="context-heading">
          <h2 id="context-heading">Contexts</h2>
          @for (context of contexts(); track context.id) {
            <button
              type="button"
              (click)="select(context)"
              [attr.aria-pressed]="selected()?.id === context.id"
            >
              {{ context.name }} - {{ context.status }}
            </button>
          }
        </section>
      }
      @if (selected()) {
        <section aria-labelledby="ingestion-heading">
          <h2 id="ingestion-heading">Local fixture ingestion</h2>
          <p>
            Provider input is normalized into evidence observations; live mode fails closed until
            configured.
          </p>
          <form (ngSubmit)="ingestFixture()">
            <label>Source ID <input name="sourceId" [(ngModel)]="sourceId" required /></label
            ><label
              >Signal <input name="fixtureSignal" [(ngModel)]="fixtureSignal" required /></label
            ><label>Value <input name="fixtureValue" [(ngModel)]="fixtureValue" required /></label
            ><button type="submit">Ingest local fixture</button>
          </form>
          @if (ingestions().length) {
            <ul>
              @for (batch of ingestions(); track batch.id) {
                <li>
                  {{ batch.status }} - accepted {{ batch.accepted_count }}, rejected
                  {{ batch.rejected_count }}, duplicates {{ batch.duplicate_count }}
                </li>
              }
            </ul>
          }
        </section>
        <section aria-labelledby="observation-heading">
          <h2 id="observation-heading">Evidence observations</h2>
          <p>Observations: {{ observations().length }} - Snapshots: {{ snapshots().length }}</p>
          @if (observations().length) {
            <table>
              <thead>
                <tr>
                  <th>Observed</th>
                  <th>Measurement</th>
                  <th>Value</th>
                  <th>Freshness</th>
                </tr>
              </thead>
              <tbody>
                @for (item of observations(); track item.id) {
                  <tr>
                    <td>{{ item.observed_at | date: 'medium' }}</td>
                    <td>{{ item.measurement_type }}</td>
                    <td>{{ item.value_numeric ?? item.value_text ?? item.value_boolean }}</td>
                    <td>{{ item.freshness_state }}</td>
                  </tr>
                }
              </tbody>
            </table>
          }
          @if (!observations().length) {
            <p>No observations have been accepted yet.</p>
          }
        </section>
      }
      @if (selected()) {
        <section aria-labelledby="analysis-heading">
          <h2 id="analysis-heading">Observed time-series analysis</h2>
          <p>Descriptive history only; no forecast, demand, sales, or future inference.</p>
          <button type="button" (click)="analyzeSnapshot()">
            Analyze latest immutable snapshot
          </button>
          @if (analysis()) {
            <p>
              Readiness: {{ analysis()?.readiness }} � observations:
              {{ analysis()?.included_observation_count }} � freshness:
              {{ analysis()?.freshness_state }}
            </p>
            @if (analysis()?.limitations?.length) {
              <p>Limitations: {{ analysis()?.limitations?.join(', ') }}</p>
            }
            @if (series().length) {
              <table>
                <thead>
                  <tr>
                    <th>Signal / source</th>
                    <th>Window</th>
                    <th>Sample</th>
                    <th>Change</th>
                    <th>Direction</th>
                    <th>Persistence</th>
                    <th>Variability</th>
                    <th>Missing</th>
                  </tr>
                </thead>
                <tbody>
                  @for (item of series(); track item.id) {
                    <tr>
                      <td>{{ item.signal_definition_id }} / {{ item.source_id }}</td>
                      <td>
                        {{ item.time_start | date: 'short' }} � {{ item.time_end | date: 'short' }}
                      </td>
                      <td>{{ item.sample_size }}</td>
                      <td>
                        {{ item.change['absolute'] ?? '�' }} ({{
                          item.change['relative_percent'] ?? '�'
                        }}%)
                      </td>
                      <td>{{ item.direction }}</td>
                      <td>{{ item.persistence }}</td>
                      <td>{{ item.variability_state }}</td>
                      <td>{{ item.missing_period_count }}</td>
                    </tr>
                  }
                </tbody>
              </table>
            }
          }
        </section>
      }
    </main>
  `,
})
export class TrendIntelligenceWorkspaceComponent {
  private readonly service = inject(TrendIntelligenceService);
  readonly contexts = signal<TrendContext[]>([]);
  readonly selected = signal<TrendContext | null>(null);
  readonly observations = signal<TrendObservation[]>([]);
  readonly snapshots = signal<TrendSnapshot[]>([]);
  readonly ingestions = signal<TrendIngestion[]>([]);
  readonly analysis = signal<TrendAnalysis | null>(null);
  readonly series = signal<TrendAnalysisSeries[]>([]);
  readonly error = signal('');
  name = '';
  subjectType = 'CUSTOM';
  subjectKey = '';
  sourceId = '';
  fixtureSignal = 'CUSTOM_INDEX';
  fixtureValue = '1';
  constructor() {
    this.load();
  }
  load(): void {
    this.service.contexts().subscribe({
      next: (value) => this.contexts.set(value),
      error: () => this.error.set('Trend data is unavailable.'),
    });
  }
  create(): void {
    this.service
      .createContext({
        name: this.name,
        subject_type: this.subjectType,
        subject_key: this.subjectKey,
      })
      .subscribe({
        next: (value) => {
          this.name = '';
          this.subjectKey = '';
          this.contexts.update((items) => [value, ...items]);
          this.select(value);
        },
        error: () => this.error.set('The trend context could not be created.'),
      });
  }
  select(value: TrendContext): void {
    this.selected.set(value);
    this.service.ingestions(value.id).subscribe({
      next: (items) => this.ingestions.set(items),
      error: () => this.error.set('Ingestion history is unavailable.'),
    });
    this.service.observations(value.id).subscribe({
      next: (page) => this.observations.set(page.items),
      error: () => this.error.set('Observations are unavailable.'),
    });
    this.service.snapshots(value.id).subscribe({
      next: (items) => this.snapshots.set(items),
      error: () => this.error.set('Snapshots are unavailable.'),
    });
    this.service.analyses(value.id).subscribe({
      next: (page) => {
        const latest = page.items[0] ?? null;
        this.analysis.set(latest);
        if (latest) {
          this.service.series(value.id, latest.id).subscribe({
            next: (seriesPage) => this.series.set(seriesPage.items),
            error: () => this.error.set('Time-series results are unavailable.'),
          });
        } else {
          this.series.set([]);
        }
      },
      error: () => this.error.set('Trend analyses are unavailable.'),
    });
  }
  analyzeSnapshot(): void {
    const context = this.selected();
    if (!context) return;
    const create = (snapshotId: string) =>
      this.service.createAnalysis(context.id, { snapshot_id: snapshotId }).subscribe({
        next: (analysis) => {
          this.analysis.set(analysis);
          this.service.series(context.id, analysis.id).subscribe({
            next: (page) => this.series.set(page.items),
            error: () => this.error.set('Time-series results are unavailable.'),
          });
        },
        error: () => this.error.set('The observed time-series analysis could not be created.'),
      });
    const snapshot = this.snapshots()[0];
    if (snapshot) create(snapshot.id);
    else {
      this.service.createSnapshot(context.id).subscribe({
        next: (created) => {
          this.snapshots.update((items) => [created, ...items]);
          create(created.id);
        },
        error: () => this.error.set('An immutable snapshot is required before analysis.'),
      });
    }
  }
  ingestFixture(): void {
    const context = this.selected();
    if (!context) return;
    this.service
      .ingest(context.id, {
        source_id: this.sourceId,
        mode: 'LOCAL_FIXTURE',
        provider: 'LOCAL_FIXTURE',
        candidates: [
          {
            signal_key: this.fixtureSignal,
            measurement_type: 'INDEX',
            value_numeric: this.fixtureValue,
            observed_at: new Date().toISOString(),
          },
        ],
      })
      .subscribe({
        next: (batch) => this.ingestions.update((items) => [batch, ...items]),
        error: () => this.error.set('The local fixture could not be ingested.'),
      });
  }
}
