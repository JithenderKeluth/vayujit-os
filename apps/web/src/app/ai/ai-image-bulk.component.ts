import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AIService } from './ai.service';
import { ProductService } from '../products/product.service';
import type { AIImageBulkPreview } from '@vayujit/shared';

type BulkProduct = { id: string; name: string };
type BulkStatus = {
  id: string;
  status: string;
  total_outputs: number;
  counts: Record<string, number>;
  progress_percentage: number;
  outputs: Array<{
    id: string;
    product_name: string;
    channel: string;
    operation: string;
    status: string;
    media_id?: string | null;
    image_output_id?: string | null;
    retry_eligible: boolean;
    safe_error_message?: string | null;
  }>;
};

@Component({
  selector: 'app-ai-image-bulk',
  imports: [FormsModule, RouterLink],
  template: `
    <section class="ai-page">
      <header class="ai-header">
        <div>
          <h1>Bulk image generation</h1>
          <p class="ai-muted">
            AI Studio ? Images ? Bulk. Queue bounded, reviewable variants without running a provider
            request in the browser.
          </p>
        </div>
        <a class="ai-button" routerLink="/ai/images">Single image</a>
      </header>
      @if (error()) {
        <p class="ai-error" role="alert">{{ error() }}</p>
      }
      <article class="ai-card bulk-wizard">
        <h2>New bulk generation</h2>
        <p class="ai-muted">
          Select Products, source strategy, operation, channels, dimensions, and review the plan
          before queueing.
        </p>
        <fieldset>
          <legend>1. Products</legend>
          @for (product of products(); track product.id) {
            <label class="bulk-option"
              ><input
                type="checkbox"
                [checked]="selected().has(product.id)"
                (change)="toggleProduct(product.id)"
              />
              {{ product.name }}</label
            >
          }
          @if (!products().length) {
            <p class="ai-muted">No Products available.</p>
          }
        </fieldset>
        <label
          >2. Source media strategy
          <select [(ngModel)]="sourceStrategy">
            <option value="selected">Selected source Media</option>
            <option value="primary_original">Primary original image</option>
            <option value="first_eligible_original">First eligible original image</option>
          </select>
        </label>
        <label
          >3. Image operation
          <select [(ngModel)]="operation">
            <option value="marketplace_main_image">Marketplace main image</option>
            <option value="marketplace_gallery_image">Marketplace gallery image</option>
            <option value="white_background">White background</option>
            <option value="resize">Resize</option>
            <option value="crop">Crop</option>
            <option value="thumbnail">Thumbnail</option>
            <option value="banner">Banner</option>
            <option value="promotional_creative">Promotional creative</option>
          </select>
        </label>
        <fieldset>
          <legend>4. Target channels</legend>
          @for (channel of channels; track channel) {
            <label class="bulk-option"
              ><input
                type="checkbox"
                [checked]="selectedChannels().has(channel)"
                (change)="toggleChannel(channel)"
              />
              {{ channel }}</label
            >
          }
        </fieldset>
        <div class="bulk-grid">
          <label>7. Width <input type="number" min="64" max="4096" [(ngModel)]="width" /></label>
          <label>Height <input type="number" min="64" max="4096" [(ngModel)]="height" /></label>
          <label
            >Outputs/Product <input type="number" min="1" max="8" [(ngModel)]="outputsPerProduct"
          /></label>
        </div>
        <div class="bulk-actions">
          <button class="ai-button" [disabled]="busy()" (click)="preview()">
            {{ busy() ? 'Working�' : 'Review plan' }}
          </button>
          <button class="ai-button" [disabled]="busy() || !previewData()" (click)="queue()">
            Queue bulk generation
          </button>
        </div>
      </article>
      @if (previewData(); as plan) {
        <article class="ai-card" aria-live="polite">
          <h2>10. Review plan</h2>
          <p>
            {{ plan.total_outputs }} outputs � {{ plan.estimated_provider_calls }} provider calls �
            cost {{ plan.estimated_cost }}
          </p>
          @if (plan.blockers.length) {
            <p class="ai-error">{{ plan.blockers.join(' ') }}</p>
          }
          @if (plan.warnings.length) {
            <p class="ai-muted">{{ plan.warnings.join(' ') }}</p>
          }
        </article>
      }
      @if (status(); as current) {
        <article class="ai-card" aria-live="polite">
          <h2>Bulk operation: {{ current.status }}</h2>
          <progress [value]="current.progress_percentage" max="100">
            {{ current.progress_percentage }}%
          </progress>
          <p>{{ current.progress_percentage }}% complete � {{ current.total_outputs }} outputs</p>
          <table class="bulk-table">
            <caption>
              Output review queue
            </caption>
            <thead>
              <tr>
                <th>Product</th>
                <th>Channel</th>
                <th>Operation</th>
                <th>State</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              @for (item of current.outputs; track item.id) {
                <tr>
                  <td>{{ item.product_name }}</td>
                  <td>{{ item.channel }}</td>
                  <td>{{ item.operation }}</td>
                  <td>{{ item.status }}</td>
                  <td>
                    @if (item.media_id) {
                      <a [routerLink]="['/ai/images/assets', item.image_output_id]">Review</a>
                    } @else if (item.retry_eligible) {
                      <button (click)="retry(item.id)">Retry</button>
                    } @else {
                      <span>�</span>
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
export class AIImageBulkComponent implements OnInit {
  private readonly productsApi = inject(ProductService);
  private readonly ai = inject(AIService);
  readonly products = signal<BulkProduct[]>([]);
  readonly selected = signal<Set<string>>(new Set());
  readonly selectedChannels = signal<Set<string>>(new Set(['amazon', 'flipkart', 'meesho']));
  readonly channels = ['amazon', 'flipkart', 'meesho'];
  operation = 'marketplace_main_image';
  sourceStrategy = 'selected';
  width = 1024;
  height = 1024;
  outputsPerProduct = 1;
  readonly busy = signal(false);
  readonly error = signal('');
  readonly previewData = signal<AIImageBulkPreview | null>(null);
  readonly status = signal<BulkStatus | null>(null);

  ngOnInit(): void {
    void this.loadProducts();
  }

  private async loadProducts(): Promise<void> {
    try {
      const response = await this.productsApi.list({ page: 1, pageSize: 50, status: 'active' });
      this.products.set(response.items.map((item) => ({ id: item.id, name: item.name })));
    } catch {
      this.error.set('Products could not be loaded.');
    }
  }

  toggleProduct(id: string): void {
    const next = new Set(this.selected());
    if (next.has(id)) next.delete(id);
    else next.add(id);
    this.selected.set(next);
  }
  toggleChannel(channel: string): void {
    const next = new Set(this.selectedChannels());
    if (next.has(channel)) next.delete(channel);
    else next.add(channel);
    this.selectedChannels.set(next);
  }

  private payload(): Record<string, unknown> {
    return {
      product_ids: [...this.selected()],
      channels: [...this.selectedChannels()],
      operation: this.operation,
      source_media_strategy: this.sourceStrategy,
      width: this.width,
      height: this.height,
      output_count_per_product: this.outputsPerProduct,
      idempotency_key: `image-ui:${[...this.selected()].join(',')}:${Date.now()}`,
    };
  }
  async preview(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      this.previewData.set(await this.ai.imageBulkPreview(this.payload()));
    } catch {
      this.error.set('The bulk image plan could not be prepared.');
    } finally {
      this.busy.set(false);
    }
  }
  async queue(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      const result = await this.ai.imageBulkCreate(this.payload());
      this.status.set(result);
    } catch {
      this.error.set('The bulk image operation could not be queued.');
    } finally {
      this.busy.set(false);
    }
  }
  async retry(id: string): Promise<void> {
    try {
      const current = this.status();
      if (!current) return;
      await this.ai.imageBulkRetry(current.id, [id]);
      this.status.set(await this.ai.imageBulkStatus(current.id));
    } catch {
      this.error.set('The selected output could not be retried.');
    }
  }
}
