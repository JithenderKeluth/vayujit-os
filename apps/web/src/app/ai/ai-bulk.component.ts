import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { JsonPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import type {
  AIStudioBulkPreview,
  AIStudioBulkRequest,
  AIStudioBulkStatus,
  AIStudioChannel,
  AIStudioContentType,
  ProductSummary,
} from '@vayujit/shared';
import { ProductService } from '../products/product.service';
import { AIService } from './ai.service';

@Component({
  selector: 'app-ai-bulk',
  imports: [FormsModule, RouterLink, JsonPipe],
  template: `
    <section class="ai-page">
      <header class="ai-header">
        <div>
          <h1>Bulk generation</h1>
          <p class="ai-muted">Queue durable Product × channel content jobs.</p>
        </div>
        <a routerLink="/ai/studio">AI Studio</a>
      </header>
      @if (error()) {
        <p class="ai-error" role="alert">{{ error() }}</p>
      }
      <article class="ai-card ai-form">
        <h2>New bulk generation</h2>
        <fieldset>
          <legend>1. Select Products ({{ selectedProductIds().length }})</legend>
          <input
            aria-label="Search products"
            [value]="search()"
            (input)="search.set($any($event.target).value)"
            placeholder="Search Products"
          />
          <div class="ai-checklist">
            @for (product of visibleProducts(); track product.id) {
              <label
                ><input
                  type="checkbox"
                  [checked]="selectedProductIds().includes(product.id)"
                  (change)="toggleProduct(product.id)"
                />
                {{ product.name }} <span class="ai-muted">{{ product.status }}</span></label
              >
            }
          </div>
        </fieldset>
        <fieldset>
          <legend>2. Channels</legend>
          <div class="ai-checklist">
            @for (channel of channels; track channel) {
              <label
                ><input
                  type="checkbox"
                  [checked]="selectedChannels().includes(channel)"
                  (change)="toggleChannel(channel)"
                />
                {{ channel }}</label
              >
            }
          </div>
        </fieldset>
        <fieldset>
          <legend>3. Content types</legend>
          <div class="ai-checklist">
            @for (contentType of contentTypes; track contentType) {
              <label
                ><input
                  type="checkbox"
                  [checked]="selectedContentTypes().includes(contentType)"
                  (change)="toggleContentType(contentType)"
                />
                {{ contentType }}</label
              >
            }
          </div>
        </fieldset>
        <div class="ai-grid">
          <label>Locale <input [(ngModel)]="locale" maxlength="16" /></label>
          <label
            >Instructions <textarea [(ngModel)]="instructions" maxlength="2000" rows="3"></textarea>
          </label>
        </div>
        <div class="ai-actions">
          <button [disabled]="busy()" (click)="previewPlan()">Review plan</button>
          @if (preview()) {
            <button [disabled]="busy() || !!preview()!.blockers.length" (click)="queue()">
              Queue {{ preview()!.total_outputs }} outputs
            </button>
          }
        </div>
      </article>
      @if (preview(); as plan) {
        <article class="ai-card" aria-live="polite">
          <h2>Plan review</h2>
          <p>
            {{ plan.product_count }} Products × {{ plan.channel_count }} channels ×
            {{ plan.content_type_count }} content types =
            <strong>{{ plan.total_outputs }} outputs</strong>
          </p>
          <p>
            Provider: {{ plan.provider_key }} · Model: {{ plan.model }} · Locale:
            {{ plan.locale }} · Estimated cost: {{ plan.estimated_cost }}
          </p>
          @for (warning of plan.warnings; track warning) {
            <p class="ai-muted">Warning: {{ warning }}</p>
          }
          @for (blocker of plan.blockers; track blocker) {
            <p class="ai-error">Blocked: {{ blocker }}</p>
          }
        </article>
      }
      <article class="ai-card">
        <h2>Bulk operations</h2>
        <button class="ai-secondary" (click)="loadHistory()">Refresh history</button>
        @for (item of history(); track item.id) {
          <div class="ai-bulk-operation">
            <div>
              <strong>{{ item.status }}</strong> · {{ item.total_outputs }} outputs ·
              {{ item.progress_percentage }}%
            </div>
            <small>{{ item.created_at }} · {{ item.locale }} · {{ item.model }}</small>
            <div class="ai-actions">
              <button class="ai-secondary" (click)="selectOperation(item)">Open details</button
              ><button
                class="ai-danger"
                [disabled]="item.status === 'completed' || item.status === 'cancelled'"
                (click)="cancel(item)"
              >
                Cancel remaining</button
              ><button [disabled]="!retryable(item)" (click)="retry(item)">Retry failed</button>
            </div>
          </div>
        }
        @if (!history().length) {
          <p class="ai-muted">No bulk operations yet.</p>
        }
      </article>
      @if (operation(); as current) {
        <article class="ai-card" aria-live="polite">
          <h2>Operation details</h2>
          <p>
            <strong>{{ current.status }}</strong> · {{ current.progress_percentage }}% ·
            {{ current.counts | json }}
          </p>
          <table class="ai-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Channel</th>
                <th>Type</th>
                <th>Status</th>
                <th>Version</th>
                <th>Attempts</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              @for (output of current.outputs; track output.id) {
                <tr>
                  <td>{{ output.product_name }}</td>
                  <td>{{ output.channel }}</td>
                  <td>{{ output.content_type }}</td>
                  <td>{{ output.status }}</td>
                  <td>{{ output.artifact_version ?? '—' }}</td>
                  <td>{{ output.attempt_count }}</td>
                  <td>
                    @if (output.artifact_id) {
                      <a [routerLink]="['/ai/artifacts', output.artifact_id]">Review</a>
                    }
                    @if (output.retry_eligible) {
                      <button (click)="retryOne(current, output.id)">Retry</button>
                    }
                    @if (
                      output.status === 'queued' ||
                      output.status === 'retry_wait' ||
                      output.status === 'generating' ||
                      output.status === 'validating'
                    ) {
                      <button class="ai-danger" (click)="cancelOne(current, output.id)">
                        Cancel
                      </button>
                    }
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </article>
      }
    </section>
  `,
  styleUrl: './ai.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AIBulkComponent implements OnInit, OnDestroy {
  private readonly ai = inject(AIService);
  private readonly products = inject(ProductService);
  private timer: ReturnType<typeof setInterval> | null = null;
  readonly productsList = signal<ProductSummary[]>([]);
  readonly visibleProducts = signal<ProductSummary[]>([]);
  readonly selectedProductIds = signal<string[]>([]);
  readonly selectedChannels = signal<AIStudioChannel[]>(['amazon', 'flipkart', 'meesho']);
  readonly selectedContentTypes = signal<AIStudioContentType[]>(['marketplace_listing']);
  readonly channels: AIStudioChannel[] = [
    'amazon',
    'flipkart',
    'meesho',
    'shopify',
    'wordpress',
    'canonical',
  ];
  readonly contentTypes: AIStudioContentType[] = [
    'marketplace_listing',
    'product_description',
    'product_title',
    'bullet_points',
    'seo_metadata',
  ];
  readonly search = signal('');
  readonly history = signal<AIStudioBulkStatus[]>([]);
  readonly operation = signal<AIStudioBulkStatus | null>(null);
  readonly preview = signal<AIStudioBulkPreview | null>(null);
  readonly busy = signal(false);
  readonly error = signal('');
  locale = 'en-IN';
  instructions = '';

  ngOnInit(): void {
    void this.loadProducts();
    void this.loadHistory();
  }
  ngOnDestroy(): void {
    if (this.timer) clearInterval(this.timer);
  }
  async loadProducts(): Promise<void> {
    try {
      const page = await this.products.list({ status: 'active', pageSize: 50 });
      this.productsList.set(page.items);
      this.filterProducts();
    } catch {
      this.error.set('Unable to load Products for bulk generation.');
    }
  }
  filterProducts(): void {
    const term = this.search().trim().toLowerCase();
    this.visibleProducts.set(
      this.productsList().filter((item) => !term || item.name.toLowerCase().includes(term)),
    );
  }
  toggleProduct(id: string): void {
    this.selectedProductIds.update((items) =>
      items.includes(id) ? items.filter((value) => value !== id) : [...items, id].slice(0, 50),
    );
  }
  toggleChannel(value: AIStudioChannel): void {
    this.selectedChannels.update((items) =>
      items.includes(value) ? items.filter((item) => item !== value) : [...items, value],
    );
  }
  toggleContentType(value: AIStudioContentType): void {
    this.selectedContentTypes.update((items) =>
      items.includes(value) ? items.filter((item) => item !== value) : [...items, value],
    );
  }
  request(): AIStudioBulkRequest {
    return {
      product_ids: this.selectedProductIds(),
      channels: this.selectedChannels(),
      content_types: this.selectedContentTypes(),
      locale: this.locale,
      user_instructions: this.instructions || undefined,
      idempotency_key: `bulk-ui-${Date.now()}`,
    };
  }
  async previewPlan(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      this.preview.set(await this.ai.studioBulkPreview(this.request()));
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
  async queue(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      const item = await this.ai.studioBulkCreate(this.request());
      this.selectOperation(item);
      await this.loadHistory();
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
  async loadHistory(): Promise<void> {
    try {
      this.history.set(await this.ai.studioBulkList());
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    }
  }
  selectOperation(item: AIStudioBulkStatus): void {
    this.operation.set(item);
    if (this.timer) clearInterval(this.timer);
    this.timer = setInterval(() => {
      void this.refreshOperation(item.id);
    }, 3000);
  }
  async refreshOperation(id: string): Promise<void> {
    try {
      this.operation.set(await this.ai.studioBulk(id));
    } catch {
      /* retain last durable snapshot */
    }
  }
  retryable(item: AIStudioBulkStatus): boolean {
    return item.outputs.some((output) => output.retry_eligible);
  }
  async retry(item: AIStudioBulkStatus): Promise<void> {
    await this.ai.studioBulkRetryFailed(item.id);
    await this.refreshOperation(item.id);
  }
  async cancel(item: AIStudioBulkStatus): Promise<void> {
    if (!window.confirm('Completed outputs will be kept. Cancel remaining work?')) return;
    await this.ai.studioBulkCancel(item.id);
    await this.refreshOperation(item.id);
  }
  async retryOne(item: AIStudioBulkStatus, id: string): Promise<void> {
    await this.ai.studioBulkRetryFailed(item.id, [id]);
    await this.refreshOperation(item.id);
  }
  async cancelOne(item: AIStudioBulkStatus, id: string): Promise<void> {
    await this.ai.studioBulkCancel(item.id, [id]);
    await this.refreshOperation(item.id);
  }
}
