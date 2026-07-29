import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import type { PublishingExecutionDetails, PublishingReconciliationResult } from '@vayujit/shared';
import { AttemptTimelineComponent } from './attempt-timeline.component';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-execution-details',
  imports: [RouterLink, AttemptTimelineComponent],
  template: ` <section class="pub-page">
    <header class="pub-header">
      <div>
        <h1>Publishing execution</h1>
        <p class="pub-muted">Reference {{ item()?.id?.slice(0, 8) }}</p>
      </div>
      <a routerLink="/publishing/executions">Back to history</a>
    </header>
    @if (loading()) {
      <p role="status">Loading execution details…</p>
    }
    @if (error()) {
      <p class="pub-error" role="alert">{{ error() }}</p>
    }
    @if (item(); as value) {
      <article class="pub-card">
        <header class="pub-header">
          <h2>
            <span class="pub-status" [class]="value.status">{{ value.status }}</span>
          </h2>
          @if (value.retryable) {
            <button [disabled]="busy()" (click)="retry()">
              {{ busy() ? 'Retrying…' : 'Retry original snapshot' }}
            </button>
          }
          @if (value.connector_key === 'wordpress' && value.remote_entity_id) {
            <button [disabled]="busy()" (click)="reconcile()">Refresh remote state</button>
          }
        </header>
        @if (value.status === 'succeeded') {
          <p>
            <strong>Publication succeeded.</strong> The deterministic mock result is stored locally.
          </p>
        } @else if (value.retryable) {
          <p>
            <strong>Publication failed safely.</strong> Correct the destination condition and retry
            the same immutable snapshot.
          </p>
        } @else if (value.status === 'failed') {
          <p>
            <strong>Permanent failure.</strong> Edit the destination configuration and begin a new
            publication.
          </p>
        }
        <dl class="pub-preview">
          <div>
            <dt>Brand / Product</dt>
            <dd>
              {{ value.content_snapshot['brand_name'] }} /
              {{ value.content_snapshot['product_name'] }}
            </dd>
          </div>
          <div>
            <dt>Artifact / destination / connector</dt>
            <dd>
              v{{ value.content_snapshot['artifact_version'] }} /
              {{ value.request_snapshot['destination_name'] }} / Local mock
            </dd>
          </div>
          <div>
            <dt>Idempotency summary</dt>
            <dd>…{{ value.idempotency_key.slice(-8) }}</dd>
          </div>
          <div>
            <dt>Attempts</dt>
            <dd>{{ value.attempt_count }}</dd>
          </div>
          <div>
            <dt>Created / started</dt>
            <dd>{{ value.created_at }} / {{ value.started_at || '—' }}</dd>
          </div>
          <div>
            <dt>Completed / failed</dt>
            <dd>{{ value.completed_at || '—' }} / {{ value.failed_at || '—' }}</dd>
          </div>
          @if (value.external_reference) {
            <div>
              <dt>External mock reference</dt>
              <dd>{{ value.external_reference }}</dd>
            </div>
          }
          @if (value.connector_key === 'wordpress') {
            <div>
              <dt>Remote post</dt>
              <dd>
                {{ value.remote_entity_id || 'Unknown' }} · {{ value.remote_status || 'Unknown' }} ·
                {{ value.reconciliation_status }}
              </dd>
            </div>
          }
          @if (value.external_url) {
            <div>
              <dt>Display-only mock URL</dt>
              <dd class="pub-url">
                {{ value.external_url }}<br /><small
                  >.invalid URLs are reserved, non-routable examples and are intentionally not
                  clickable.</small
                >
              </dd>
            </div>
          }
          @if (value.result?.['checksum']) {
            <div>
              <dt>Checksum</dt>
              <dd>{{ value.result['checksum'] }}</dd>
            </div>
          }
          @if (value.error_code) {
            <div>
              <dt>Safe failure</dt>
              <dd>{{ value.error_code }}: {{ value.safe_error_message }}</dd>
            </div>
          }
        </dl>
        <div class="pub-actions">
          <a [routerLink]="['/products', value.product_id]">View Product</a
          ><a [routerLink]="['/ai/artifacts', value.artifact_id]">View source Artifact</a
          ><a [routerLink]="['/publishing/destinations', value.destination_id]">View destination</a>
          @if (value.remote_edit_url) {
            <a [href]="value.remote_edit_url" target="_blank" rel="noopener noreferrer"
              >Open remote post</a
            >
          }
          @if (value.connector_key === 'wordpress' && value.remote_entity_id) {
            <button [disabled]="busy()" (click)="moveToDraft()">Move remote post to draft</button>
          }
        </div>
      </article>
      @if (reconciliation(); as result) {
        <article class="pub-card">
          <h2>Remote drift comparison</h2>
          <p>
            <strong>{{ result.reconciliation_status }}</strong
            >. Remote changes are never overwritten automatically.
          </p>
          <div class="pub-table">
            <table>
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Expected</th>
                  <th>Remote</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                @for (difference of result.differences; track difference.field) {
                  <tr>
                    <th>{{ difference.field }}</th>
                    <td>{{ display(difference.expected) }}</td>
                    <td>{{ display(difference.remote) }}</td>
                    <td>{{ difference.status }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
          <div class="pub-actions">
            @if (result.reconciliation_status === 'changed_remotely') {
              <button [disabled]="busy()" (click)="keepRemote()">Keep remote changes</button>
              <button [disabled]="busy()" (click)="overwrite()">
                Update remote from approved Artifact
              </button>
            }
            <a
              [routerLink]="['/publishing/new']"
              [queryParams]="{ destination: value.destination_id }"
              >Create a new draft</a
            >
            <a routerLink="/settings/publishing/connectors/wordpress">Open destination settings</a>
          </div>
        </article>
      }
      <article class="pub-card">
        <h2>Content snapshot</h2>
        <p>
          <strong>{{ value.content_snapshot['product_title'] }}</strong>
        </p>
        <p>{{ value.content_snapshot['short_description'] }}</p>
        <details>
          <summary>Show complete immutable snapshot</summary>
          <p>{{ value.content_snapshot['long_description'] }}</p>
          <h3>Key features</h3>
          <ul>
            @for (feature of list(value.content_snapshot['key_features']); track feature) {
              <li>{{ feature }}</li>
            }
          </ul>
          <h3>SEO and social</h3>
          <p>{{ value.content_snapshot['seo_title'] }}</p>
          <p>{{ value.content_snapshot['seo_description'] }}</p>
          <p>{{ value.content_snapshot['social_caption'] }}</p>
        </details>
      </article>
      <article class="pub-card">
        <h2>Attempt timeline</h2>
        <app-attempt-timeline [attempts]="value.attempts" />
      </article>
    }
  </section>`,
  styleUrl: './publishing.css',
})
export class ExecutionDetailsComponent implements OnInit {
  private readonly api = inject(PublishingService);
  private readonly route = inject(ActivatedRoute);
  readonly item = signal<PublishingExecutionDetails | null>(null);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly reconciliation = signal<PublishingReconciliationResult | null>(null);
  private id = '';
  ngOnInit(): void {
    this.id = this.route.snapshot.paramMap.get('id') ?? '';
    void this.load();
  }
  list(value: unknown): string[] {
    return Array.isArray(value) ? value.map(String) : [];
  }
  private async load() {
    try {
      this.item.set(await this.api.execution(this.id));
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
  async retry() {
    if (this.busy() || !confirm('Retry this execution using its original immutable snapshot?'))
      return;
    this.busy.set(true);
    this.error.set('');
    try {
      this.item.set(await this.api.retry(this.id));
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
  display(value: unknown): string {
    if (value === null || value === undefined) return 'Unknown';
    if (typeof value === 'object') return JSON.stringify(value);
    if (typeof value === 'string') return value;
    if (typeof value === 'number' || typeof value === 'boolean') return `${value}`;
    return 'Unknown';
  }
  async reconcile() {
    await this.run(async () => {
      this.reconciliation.set(await this.api.reconcile(this.id));
      await this.load();
    });
  }
  async keepRemote() {
    await this.run(async () => {
      this.item.set(await this.api.keepRemote(this.id));
    });
  }
  async moveToDraft() {
    if (!confirm('Move the remote WordPress post to draft? It will not be deleted.')) return;
    await this.run(async () => {
      this.item.set(await this.api.moveToDraft(this.id));
    });
  }
  async overwrite() {
    if (!confirm('Overwrite reviewed remote changes using the approved immutable Artifact?'))
      return;
    const value = this.item();
    if (!value) return;
    await this.run(async () => {
      const result = await this.api.publish({
        artifact_id: value.artifact_id,
        destination_id: value.destination_id,
        idempotency_key: crypto.randomUUID(),
        action: 'update',
        featured_media_id: (value.request_snapshot['featured_media_id'] as string | null) ?? null,
      });
      this.item.set(result);
    });
  }
  private async run(operation: () => Promise<void>) {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await operation();
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
}
