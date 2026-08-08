import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { BrandSummary, OperationalItem, ProductSummary } from '@vayujit/shared';
import { BrandService } from '../brands/brand.service';
import { ProductService } from '../products/product.service';
import { OperationsService } from './operations.service';

@Component({
  selector: 'app-execution-history',
  imports: [FormsModule, RouterLink],
  template: `<section class="op-page">
    <header class="op-header">
      <div>
        <h1>Execution History</h1>
        <p class="op-muted">One safe timeline over immutable domain and audit records.</p>
      </div>
      <button (click)="export()">Export filtered CSV</button>
    </header>
    <form class="op-card op-filters" (ngSubmit)="load(1)">
      <label
        >Brand<select name="brand" [(ngModel)]="brandId">
          <option value="">All Brands</option>
          @for (x of brands(); track x.id) {
            <option [value]="x.id">{{ x.name }}</option>
          }
        </select></label
      ><label
        >Product<select name="product" [(ngModel)]="productId">
          <option value="">All Products</option>
          @for (x of products(); track x.id) {
            <option [value]="x.id">{{ x.name }}</option>
          }
        </select></label
      ><label
        >Category<select name="category" [(ngModel)]="category">
          <option value="">All</option>
          @for (x of categories; track x) {
            <option>{{ x }}</option>
          }
        </select></label
      ><label>From<input type="date" name="from" [(ngModel)]="from" /></label
      ><label>To<input type="date" name="to" [(ngModel)]="to" /></label
      ><label>Event<input name="event" maxlength="80" [(ngModel)]="eventName" /></label
      ><label
        >Correlation ID<input name="correlation" maxlength="64" [(ngModel)]="correlationId"
      /></label>
      <button>Apply</button
      ><button type="button" class="secondary" (click)="timeline.set(!timeline())">
        {{ timeline() ? 'List view' : 'Timeline view' }}
      </button>
    </form>
    @if (loading()) {
      <p role="status">Loading history…</p>
    }
    @if (error()) {
      <p class="op-error" role="alert">{{ error() }}</p>
    }
    @if (!loading() && !items().length) {
      <div class="op-empty">No activity matches these filters.</div>
    }
    <div [class]="timeline() ? 'wf-timeline' : ''">
      @for (item of items(); track item.id) {
        <article class="op-card">
          <div class="op-header">
            <div>
              <strong>{{ item.safe_summary }}</strong>
              <p class="op-muted">
                {{ item.timestamp }} · {{ item.category }} · {{ item.entity_type }}
                {{ item.entity_id.slice(0, 8) }}
              </p>
              @if (item.correlation_id) {
                <p class="op-muted">Correlation: {{ item.correlation_id }}</p>
              }
              @if (item.event_name === 'campaign.activity_rescheduled' && item.actor_id) {
                <p class="op-muted">Actor: {{ item.actor_id }}</p>
              }
              @if (item.event_name === 'campaign.activity_rescheduled') {
                <p>
                  Campaign Activity rescheduled
                  @if (item.original_scheduled_at_utc && item.new_scheduled_at_utc) {
                    - {{ item.original_scheduled_at_utc }} to {{ item.new_scheduled_at_utc }}
                  }
                </p>
                @if (item.reason) {
                  <p class="op-muted">Reason: {{ item.reason }}</p>
                }
              }
              @if (
                item.event_name === 'campaign.catch_up_created' ||
                item.event_name === 'campaign.catch_up_reused'
              ) {
                <p>
                  Campaign catch-up Activity
                  {{ item.event_name.endsWith('reused') ? 'reused' : 'created' }}.
                </p>
                @if (item.reason) {
                  <p class="op-muted">Reason: {{ item.reason }}</p>
                }
              }
            </div>
            <span class="op-status">{{ item.status || 'recorded' }}</span>
          </div>
          <p>{{ item.brand_name || 'No Brand' }} · {{ item.product_name || 'No Product' }}</p>
          @if (item.related_url) {
            <a [routerLink]="item.related_url">Open related record</a>
          }
        </article>
      }
    </div>
    <div class="op-actions">
      <button class="secondary" [disabled]="page() <= 1" (click)="load(page() - 1)">Previous</button
      ><span>Page {{ page() }} of {{ pages() || 1 }}</span
      ><button class="secondary" [disabled]="page() >= pages()" (click)="load(page() + 1)">
        Next
      </button>
    </div>
  </section>`,
  styleUrl: './operations.css',
})
export class ExecutionHistoryComponent implements OnInit {
  private readonly api = inject(OperationsService);
  private readonly brandApi = inject(BrandService);
  private readonly productApi = inject(ProductService);
  readonly items = signal<OperationalItem[]>([]);
  readonly brands = signal<BrandSummary[]>([]);
  readonly products = signal<ProductSummary[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly timeline = signal(false);
  readonly page = signal(1);
  readonly pages = signal(0);
  readonly categories = [
    'Product',
    'AI Generation',
    'Publishing',
    'Campaign',
    'Workflow',
    'System',
  ];
  brandId = '';
  productId = '';
  category = '';
  from = '';
  to = '';
  eventName = '';
  correlationId = '';
  ngOnInit() {
    void this.init();
  }
  async init() {
    const [b, p] = await Promise.all([
      this.brandApi.list({ includeArchived: true, pageSize: 100 }),
      this.productApi.list({ allBrands: true, includeArchived: true, pageSize: 100 }),
    ]);
    this.brands.set(b.items);
    this.products.set(p.items);
    await this.load(1);
  }
  filters() {
    return {
      brand_id: this.brandId,
      product_id: this.productId,
      category: this.category,
      event_name: this.eventName,
      correlation_id: this.correlationId,
      date_from: this.from ? `${this.from}T00:00:00Z` : undefined,
      date_to: this.to ? `${this.to}T23:59:59Z` : undefined,
    };
  }
  async load(page: number) {
    this.loading.set(true);
    this.error.set('');
    try {
      const x = await this.api.history({ ...this.filters(), page });
      this.items.set(x.items);
      this.page.set(x.page);
      this.pages.set(x.pages);
    } catch {
      this.error.set('Unable to load operational history.');
    } finally {
      this.loading.set(false);
    }
  }
  async export() {
    try {
      const blob = await this.api.exportHistory(this.filters());
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'vayujit-operations.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      this.error.set('Unable to export history.');
    }
  }
}
