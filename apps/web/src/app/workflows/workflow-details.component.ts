import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import type { WorkflowDetails } from '@vayujit/shared';
import { WorkflowService } from './workflow.service';
import { WorkflowTimelineComponent } from './workflow-timeline.component';

@Component({
  selector: 'app-workflow-details',
  imports: [RouterLink, WorkflowTimelineComponent],
  template: `<section class="wf-page">
    <header class="wf-header">
      <div>
        <a routerLink="/workflows">← Workflows</a>
        <h1>Workflow {{ id.slice(0, 8) }}</h1>
        @if (workflow(); as item) {
          <p class="wf-muted">{{ item.template_name }} v{{ item.template_version }}</p>
        }
      </div>
      <button class="secondary" [disabled]="busy()" (click)="load()">Refresh</button>
    </header>
    @if (loading()) {
      <p role="status">Loading Workflow…</p>
    }
    @if (error()) {
      <p class="wf-error" role="alert">{{ error() }}</p>
    }
    @if (workflow(); as item) {
      <article class="wf-card">
        <h2>Current state</h2>
        <p>
          <span class="wf-status" [class]="item.status">{{ item.status }}</span> ·
          {{ item.current_step_key || 'Finished' }}
        </p>
        <dl class="wf-details">
          <div>
            <dt>Brand</dt>
            <dd>
              <a [routerLink]="['/brands', item.brand_id]">{{ item.brand_name }}</a>
            </dd>
          </div>
          <div>
            <dt>Product</dt>
            <dd>
              <a [routerLink]="['/products', item.product_id]">{{ item.product_name }}</a>
            </dd>
          </div>
          <div>
            <dt>Destination</dt>
            <dd>
              <a [routerLink]="['/publishing/destinations', item.destination_id]">{{
                item.destination_name
              }}</a>
            </dd>
          </div>
          <div>
            <dt>Started</dt>
            <dd>{{ item.started_at || 'Not started' }}</dd>
          </div>
          <div>
            <dt>Updated</dt>
            <dd>{{ item.updated_at }}</dd>
          </div>
          <div>
            <dt>Retryable</dt>
            <dd>{{ item.retryable ? 'Yes' : 'No' }}</dd>
          </div>
        </dl>
        @if (item.error_code) {
          <p class="wf-error">
            <strong>{{ item.error_code }}</strong
            >: {{ item.safe_error_message }}
          </p>
        }
        <div class="wf-actions">
          @if (item.status === 'draft') {
            <button [disabled]="busy()" (click)="perform('start')">Start</button>
          }
          @if (item.status === 'waiting_for_approval' && item.artifact_id) {
            <a
              class="wf-button"
              [routerLink]="['/ai/artifacts', item.artifact_id]"
              [queryParams]="{ workflow: item.id }"
              >Review Artifact</a
            >
            <button class="secondary" [disabled]="busy()" (click)="perform('continue')">
              Continue after review
            </button>
          }
          @if (item.status === 'failed' && item.retryable) {
            <button [disabled]="busy()" (click)="perform('retry')">Retry failed step</button>
          }
          @if (canCancel(item)) {
            <button class="danger" [disabled]="busy()" (click)="cancel()">Cancel Workflow</button>
          }
        </div>
      </article>
      @if (item.status === 'waiting_for_approval') {
        <article class="wf-card">
          <h2>Human approval required</h2>
          <p>
            This Workflow is durably paused. Review the generated Artifact, then continue it.
            Refreshing or restarting the app does not lose this state.
          </p>
        </article>
      }
      <article class="wf-card">
        <h2>Step attempts</h2>
        <app-workflow-timeline [steps]="item.steps" />
      </article>
    }
  </section>`,
  styleUrl: './workflow.css',
})
export class WorkflowDetailsComponent implements OnInit {
  private readonly api = inject(WorkflowService);
  private readonly route = inject(ActivatedRoute);
  readonly workflow = signal<WorkflowDetails | null>(null);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly id = this.route.snapshot.paramMap.get('id') ?? '';
  ngOnInit(): void {
    void this.load();
  }
  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      this.workflow.set(await this.api.get(this.id));
    } catch (error) {
      this.error.set(WorkflowService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
  canCancel(item: WorkflowDetails): boolean {
    return ['draft', 'waiting_for_approval', 'failed'].includes(item.status);
  }
  async perform(action: 'start' | 'continue' | 'retry'): Promise<void> {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    try {
      this.workflow.set(await this.api[action](this.id));
    } catch (error) {
      this.error.set(WorkflowService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
  async cancel(): Promise<void> {
    if (!confirm('Cancel this Workflow? Existing Artifacts and execution history are preserved.'))
      return;
    this.busy.set(true);
    this.error.set('');
    try {
      this.workflow.set(await this.api.cancel(this.id));
    } catch (error) {
      this.error.set(WorkflowService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
}
