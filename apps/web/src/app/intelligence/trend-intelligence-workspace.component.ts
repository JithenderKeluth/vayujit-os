import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
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
