import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { environment } from '../../environments/environment';
import { BusinessEntitySelectorsComponent } from '../shared/business-entity-selectors.component';

type BulkChild = {
  id: string;
  video_type: string;
  target_channel: string;
  status: string;
  generation_id?: string;
  job_id?: string;
  output_id?: string;
  retryable?: boolean;
  retry_count?: number;
  failure_code?: string;
  safe_error_message?: string;
};
type BulkPlan = {
  total_outputs: number;
  provider: string;
  plan_fingerprint: string;
  blockers?: unknown[];
};
type BulkOperation = {
  id: string;
  status: string;
  completed_count: number;
  child_count: number;
  progress_percentage: number;
  children: BulkChild[];
};
function safeError(error: unknown): string {
  if (typeof error === 'object' && error && 'error' in error) {
    const value = (error as { error?: unknown }).error;
    if (
      typeof value === 'object' &&
      value &&
      'detail' in value &&
      typeof (value as { detail?: unknown }).detail === 'string'
    )
      return (value as { detail: string }).detail;
    if (typeof value === 'string') return value;
  }
  return 'Bulk Video request failed safely.';
}
@Component({
  standalone: true,
  imports: [BusinessEntitySelectorsComponent, CommonModule, FormsModule, RouterLink],
  selector: 'app-ai-video-bulk',
  template: `
    <section class="bulk-page">
      <a routerLink="/ai/video">← AI Video Studio</a>
      <h1>Bulk Video Studio</h1>
      <p>Plan multi-product Videos, review the exact fingerprint, then queue durable child jobs.</p>
      <section class="card">
        <h2>Reopen saved operation</h2>
        <label>Operation ID <input [(ngModel)]="operationId" /></label>
        <button type="button" (click)="openOperation()" [disabled]="busy() || !operationId">
          Open operation
        </button>
      </section>
      <section class="card">
        <h2>1. Plan</h2>
        <app-business-entity-selectors
          [multiProduct]="true"
          [productIds]="productIds.split(',').map((value) => value.trim()).filter((value) => !!value)"
          (productIdsChange)="productIds = $event.join(',')"
        />
        <label>Video types <input [(ngModel)]="videoTypes" aria-label="Video types" /></label>
        <label>Targets <input [(ngModel)]="targets" aria-label="Targets" /></label>
        <label>Duration <input type="number" min="1" max="60" [(ngModel)]="duration" /></label>
        <button type="button" (click)="previewPlan()" [disabled]="busy()">Preview plan</button>
      </section>
      @if (plan(); as value) {
        <section class="card">
          <h2>2. Review and confirm</h2>
          <p>
            <strong>{{ value.total_outputs }}</strong> child outputs - {{ value.provider }}
          </p>
          <p>
            Fingerprint: <code>{{ value.plan_fingerprint }}</code>
          </p>
          @if (value.blockers?.length) {
            <p class="error" role="alert">Resolve preview blockers before queueing.</p>
          }
          <button type="button" (click)="enqueue()" [disabled]="busy() || value.blockers?.length">
            Confirm and queue
          </button>
        </section>
      }
      @if (operation(); as item) {
        <section class="card" aria-live="polite">
          <h2>Operation {{ item.status }}</h2>
          <p class="identifier">Operation ID: {{ item.id }}</p>
          <p>
            {{ item.completed_count || 0 }} / {{ item.child_count }} complete -
            {{ item.progress_percentage }}%
          </p>
          <button type="button" (click)="refresh()" [disabled]="busy()">Refresh status</button>
          <button
            type="button"
            (click)="recover('retry-failed')"
            [disabled]="busy() || !hasRetryable()"
          >
            Retry failed children
          </button>
          <button type="button" (click)="recover('cancel')" [disabled]="busy() || !hasActive()">
            Cancel remaining children
          </button>
          <ul>
            @for (child of item.children; track child.id) {
              <li>
                {{ child.video_type }} - {{ child.target_channel }} - {{ child.status }}
                <p class="identifier">
                  Job: {{ child.job_id || 'UNKNOWN' }}; output: {{ child.output_id || 'UNKNOWN' }};
                  retries: {{ child.retry_count ?? 0 }}
                </p>
                @if (child.failure_code) {
                  <p>{{ child.failure_code }} — {{ child.safe_error_message }}</p>
                }
                @if (child.generation_id) {
                  <a routerLink="/ai/video" [queryParams]="{ generation: child.generation_id }"
                    >Review child Video job</a
                  >
                }
              </li>
            }
          </ul>
          <h3>Persisted recovery history</h3>
          <pre>{{ history() | json }}</pre>
        </section>
      }
      @if (error(); as message) {
        <p class="error" role="alert">{{ message }}</p>
      }
    </section>
  `,
  styles: [
    `
      .bulk-page {
        max-width: 1100px;
        margin: 0 auto;
        padding: 2rem;
        color: #102b35;
      }
      .card {
        border: 1px solid #c9d9dd;
        border-radius: 14px;
        padding: 1.25rem;
        margin: 1rem 0;
        background: #fff;
      }
      code {
        overflow-wrap: anywhere;
      }
      pre,
      .identifier {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }
      label {
        display: inline-flex;
        flex-direction: column;
        gap: 0.35rem;
        margin: 0.5rem 1rem 0.5rem 0;
        min-width: 220px;
      }
      input {
        padding: 0.65rem;
        border: 1px solid #9eb7bf;
        border-radius: 6px;
      }
      button {
        border: 0;
        border-radius: 7px;
        padding: 0.7rem 1rem;
        background: #155e75;
        color: #fff;
        cursor: pointer;
      }
      button:disabled {
        opacity: 0.55;
      }
      .error {
        color: #a21caf;
        background: #fff1f2;
        padding: 0.75rem;
      }
    `,
  ],
})
export class AIVideoBulkComponent {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  readonly busy = signal(false);
  readonly plan = signal<BulkPlan | null>(null);
  readonly operation = signal<BulkOperation | null>(null);
  readonly error = signal('');
  readonly history = signal<unknown[]>([]);
  operationId = '';
  constructor() {
    this.route.queryParamMap.subscribe((params) => {
      this.operationId = params.get('operation') || '';
      this.operation.set(null);
      this.history.set([]);
      if (this.operationId) this.refresh();
    });
  }
  openOperation(): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { operation: this.operationId },
    });
  }
  hasRetryable(): boolean {
    return !!this.operation()?.children.some((c) => c.status === 'failed' && c.retryable);
  }
  hasActive(): boolean {
    return !!this.operation()?.children.some((c) =>
      ['queued', 'generating', 'validating', 'retry_wait'].includes(c.status),
    );
  }
  recover(action: 'retry-failed' | 'cancel'): void {
    const item = this.operation();
    if (
      !item ||
      this.busy() ||
      (action === 'retry-failed' ? !this.hasRetryable() : !this.hasActive())
    )
      return;
    if (
      action === 'cancel' &&
      !window.confirm('Cancel unfinished children of this saved operation?')
    )
      return;
    this.busy.set(true);
    this.error.set('');
    this.http
      .post(`${environment.apiUrl}/ai/video/bulk/${item.id}/${action}`, {
        idempotency_key: `web-bulk-${action}-${item.id}`,
      })
      .subscribe({
        next: () => {
          this.busy.set(false);
          this.refresh();
        },
        error: (err) => {
          this.busy.set(false);
          this.error.set(safeError(err));
        },
      });
  }
  productIds = '';
  videoTypes = 'product_showcase';
  targets = 'youtube';
  duration = 10;

  private payload() {
    return {
      product_ids: this.productIds
        .split(',')
        .map((v) => v.trim())
        .filter(Boolean),
      video_types: this.videoTypes
        .split(',')
        .map((v) => v.trim())
        .filter(Boolean),
      targets: this.targets
        .split(',')
        .map((v) => v.trim())
        .filter(Boolean),
      duration_seconds: Number(this.duration),
      resolution: '320x240',
      idempotency_key: `web-bulk-${Date.now()}`,
    };
  }
  previewPlan(): void {
    this.busy.set(true);
    this.error.set('');
    this.http
      .post<BulkPlan>(`${environment.apiUrl}/ai/video/bulk/preview`, this.payload())
      .subscribe({
        next: (value) => {
          this.plan.set(value);
          this.busy.set(false);
        },
        error: (err) => {
          this.error.set(safeError(err));
          this.busy.set(false);
        },
      });
  }
  enqueue(): void {
    const value = this.plan();
    if (!value || value.blockers?.length || this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.http
      .post<BulkOperation>(`${environment.apiUrl}/ai/video/bulk`, {
        ...this.payload(),
        preview_fingerprint: value.plan_fingerprint,
        confirm: true,
      })
      .subscribe({
        next: (result) => {
          this.operation.set(result);
          this.operationId = result.id;
          this.openOperation();
          this.busy.set(false);
        },
        error: (err) => {
          this.error.set(safeError(err));
          this.busy.set(false);
        },
      });
  }
  refresh(): void {
    const id = this.operationId || this.operation()?.id;
    if (!id) return;
    this.error.set('');
    this.http.get<BulkOperation>(`${environment.apiUrl}/ai/video/bulk/${id}`).subscribe({
      next: (value) => {
        if (this.operationId === id) this.operation.set(value);
      },
      error: () => {
        if (this.operationId === id) {
          this.operation.set(null);
          this.error.set('Bulk Video status is unavailable for this owned operation.');
        }
      },
    });
    this.http.get<unknown[]>(`${environment.apiUrl}/ai/video/bulk/${id}/history`).subscribe({
      next: (value) => {
        if (this.operationId === id) this.history.set(value);
      },
      error: () => {
        if (this.operationId === id) this.error.set('Bulk Video history is unavailable.');
      },
    });
  }
}
