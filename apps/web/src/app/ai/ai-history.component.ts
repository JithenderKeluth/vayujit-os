import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { AIArtifactStatus, AIGenerationStatus, PaginatedAIHistory } from '@vayujit/shared';
import { AIService } from './ai.service';

@Component({
  selector: 'app-ai-history',
  imports: [FormsModule, RouterLink],
  template: ` <section class="ai-page">
    <header class="ai-header">
      <h1>AI generation history</h1>
      <a class="ai-button" routerLink="/ai/generate">Generate</a>
    </header>
    <form class="ai-card ai-filters" (ngSubmit)="load(1)">
      <select name="requestStatus" [(ngModel)]="requestStatus">
        <option value="">All request statuses</option>
        @for (status of requestStatuses; track status) {
          <option [value]="status">{{ status }}</option>
        }
      </select>
      <select name="artifactStatus" [(ngModel)]="artifactStatus">
        <option value="">All review statuses</option>
        @for (status of artifactStatuses; track status) {
          <option [value]="status">{{ status }}</option>
        }
      </select>
      <input name="dateFrom" type="date" [(ngModel)]="dateFrom" /><input
        name="dateTo"
        type="date"
        [(ngModel)]="dateTo"
      />
      <button>Filter</button>
    </form>
    @if (error()) {
      <p class="ai-error">{{ error() }}</p>
    }
    <article class="ai-card">
      <table class="ai-table">
        <thead>
          <tr>
            <th>Created</th>
            <th>Brand / product</th>
            <th>Generation</th>
            <th>Artifact</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (item of result()?.items ?? []; track item.generation_id) {
            <tr>
              <td>{{ item.created_at.slice(0, 10) }}</td>
              <td>
                {{ item.brand_name }}<br /><strong>{{ item.product_name }}</strong>
              </td>
              <td>{{ item.request_status }}</td>
              <td>
                {{ item.artifact_status ?? '—' }}
                @if (item.version_number) {
                  · v{{ item.version_number }}
                }
              </td>
              <td>
                @if (item.artifact_id) {
                  <a [routerLink]="['/ai/artifacts', item.artifact_id]">Open</a>
                }
              </td>
            </tr>
          } @empty {
            <tr>
              <td colspan="5">No matching generations.</td>
            </tr>
          }
        </tbody>
      </table>
      <div class="ai-actions">
        <button class="ai-secondary" [disabled]="page() <= 1" (click)="load(page() - 1)">
          Previous
        </button>
        <span>Page {{ page() }} of {{ result()?.pages || 1 }}</span>
        <button
          class="ai-secondary"
          [disabled]="page() >= (result()?.pages || 1)"
          (click)="load(page() + 1)"
        >
          Next
        </button>
      </div>
    </article>
  </section>`,
  styleUrl: './ai.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AIHistoryComponent implements OnInit {
  private readonly ai = inject(AIService);
  readonly result = signal<PaginatedAIHistory | null>(null);
  readonly page = signal(1);
  readonly error = signal('');
  readonly requestStatuses: AIGenerationStatus[] = [
    'completed',
    'failed',
    'pending',
    'running',
    'cancelled',
  ];
  readonly artifactStatuses: AIArtifactStatus[] = [
    'pending_review',
    'approved',
    'rejected',
    'superseded',
  ];
  requestStatus: AIGenerationStatus | '' = '';
  artifactStatus: AIArtifactStatus | '' = '';
  dateFrom = '';
  dateTo = '';
  ngOnInit(): void {
    void this.load(1);
  }
  async load(page: number): Promise<void> {
    this.error.set('');
    try {
      this.result.set(
        await this.ai.history({
          page,
          requestStatus: this.requestStatus,
          artifactStatus: this.artifactStatus,
          dateFrom: this.dateFrom ? `${this.dateFrom}T00:00:00Z` : undefined,
          dateTo: this.dateTo ? `${this.dateTo}T23:59:59Z` : undefined,
        }),
      );
      this.page.set(page);
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    }
  }
}
