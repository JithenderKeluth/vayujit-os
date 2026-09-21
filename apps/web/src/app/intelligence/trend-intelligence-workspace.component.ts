import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  TrendContext,
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
  readonly error = signal('');
  name = '';
  subjectType = 'CUSTOM';
  subjectKey = '';
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
    this.service.observations(value.id).subscribe({
      next: (page) => this.observations.set(page.items),
      error: () => this.error.set('Observations are unavailable.'),
    });
    this.service.snapshots(value.id).subscribe({
      next: (items) => this.snapshots.set(items),
      error: () => this.error.set('Snapshots are unavailable.'),
    });
  }
}
