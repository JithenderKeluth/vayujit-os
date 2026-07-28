import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type {
  BrandSummary,
  ProductSummary,
  PublishingDestinationSummary,
  PublishingExecutionDetails,
} from '@vayujit/shared';
import { BrandService } from '../brands/brand.service';
import { ProductService } from '../products/product.service';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-execution-list',
  imports: [FormsModule, RouterLink],
  template: ` <section class="pub-page">
    <header class="pub-header">
      <div>
        <h1>Publishing execution history</h1>
        <p class="pub-muted">
          Newest first. Every result and retry remains attached to its immutable publication
          snapshot.
        </p>
      </div>
      <a class="pub-button" routerLink="/publishing/new">Publish content</a>
    </header>
    <form class="pub-card pub-filters" (ngSubmit)="load(1)">
      <label
        >Brand
        <select name="brand" [(ngModel)]="brandId">
          <option value="">All Brands</option>
          @for (item of brands(); track item.id) {
            <option [value]="item.id">{{ item.name }}</option>
          }
        </select></label
      ><label
        >Product
        <select name="product" [(ngModel)]="productId">
          <option value="">All Products</option>
          @for (item of products(); track item.id) {
            <option [value]="item.id">{{ item.name }}</option>
          }
        </select></label
      ><label
        >Destination
        <select name="destination" [(ngModel)]="destinationId">
          <option value="">All destinations</option>
          @for (item of destinations(); track item.id) {
            <option [value]="item.id">{{ item.name }}</option>
          }
        </select></label
      ><label
        >Status
        <select name="status" [(ngModel)]="status">
          <option value="">All statuses</option>
          <option value="succeeded">Succeeded</option>
          <option value="failed">Failed</option>
        </select></label
      ><label
        >Retryable
        <select name="retryable" [(ngModel)]="retryable">
          <option value="">Any</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select></label
      ><label>From <input type="date" name="from" [(ngModel)]="dateFrom" /></label
      ><label>To <input type="date" name="to" [(ngModel)]="dateTo" /></label>
      <details>
        <summary>Advanced</summary>
        <label>Artifact ID <input name="artifact" [(ngModel)]="artifactId" /></label>
      </details>
      <button>Apply</button><button type="button" class="secondary" (click)="reset()">Reset</button>
    </form>
    @if (loading()) {
      <p role="status">Loading execution history…</p>
    }
    @if (error()) {
      <p class="pub-error" role="alert">{{ error() }}</p>
    }
    @if (!loading() && !items().length) {
      <div class="pub-empty">
        <h2>No executions found</h2>
        <p>Publish approved content or reset the filters.</p>
      </div>
    }
    @if (items().length) {
      <table class="pub-table">
        <thead>
          <tr>
            <th>Reference</th>
            <th>Brand / Product</th>
            <th>Artifact / destination</th>
            <th>Status</th>
            <th>Attempts</th>
            <th>Time</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (item of items(); track item.id) {
            <tr>
              <td data-label="Reference">{{ item.id.slice(0, 8) }}</td>
              <td data-label="Brand / Product">
                {{ item.content_snapshot['brand_name'] }}<br /><strong>{{
                  item.content_snapshot['product_name']
                }}</strong>
              </td>
              <td data-label="Artifact / destination">
                v{{ item.content_snapshot['artifact_version'] }}<br />{{
                  item.request_snapshot['destination_name']
                }}
              </td>
              <td data-label="Status">
                <span class="pub-status" [class]="item.status">{{ item.status }}</span
                ><br />Retryable: {{ item.retryable ? 'Yes' : 'No' }}
              </td>
              <td data-label="Attempts">{{ item.attempt_count }}</td>
              <td data-label="Time">
                {{ item.completed_at || item.failed_at || item.created_at }}
              </td>
              <td data-label="Action">
                <a [routerLink]="['/publishing/executions', item.id]">View details</a>
              </td>
            </tr>
          }
        </tbody>
      </table>
    }
    <div class="pub-actions">
      <button class="secondary" [disabled]="page() <= 1" (click)="load(page() - 1)">Previous</button
      ><span>Page {{ page() }} of {{ pages() || 1 }}</span
      ><button class="secondary" [disabled]="page() >= pages()" (click)="load(page() + 1)">
        Next
      </button>
    </div>
  </section>`,
  styleUrl: './publishing.css',
})
export class ExecutionListComponent implements OnInit {
  private readonly api = inject(PublishingService);
  private readonly brandApi = inject(BrandService);
  private readonly productApi = inject(ProductService);
  readonly items = signal<PublishingExecutionDetails[]>([]);
  readonly brands = signal<BrandSummary[]>([]);
  readonly products = signal<ProductSummary[]>([]);
  readonly destinations = signal<PublishingDestinationSummary[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly page = signal(1);
  readonly pages = signal(0);
  brandId = '';
  productId = '';
  destinationId = '';
  status = '';
  retryable = '';
  dateFrom = '';
  dateTo = '';
  artifactId = '';
  ngOnInit(): void {
    void this.init();
  }
  private async init() {
    try {
      const [brands, products, destinations] = await Promise.all([
        this.brandApi.list({ includeArchived: true, pageSize: 100 }),
        this.productApi.list({ allBrands: true, includeArchived: true, pageSize: 100 }),
        this.api.destinations({ pageSize: 100 }),
      ]);
      this.brands.set(brands.items);
      this.products.set(products.items);
      this.destinations.set(destinations.items);
      await this.load(1);
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
      this.loading.set(false);
    }
  }
  async load(page: number) {
    this.loading.set(true);
    this.error.set('');
    try {
      const result = await this.api.executions({
        brandId: this.brandId,
        productId: this.productId,
        destinationId: this.destinationId,
        status: this.status,
        retryable: this.retryable === '' ? null : this.retryable === 'true',
        dateFrom: this.dateFrom ? `${this.dateFrom}T00:00:00Z` : undefined,
        dateTo: this.dateTo ? `${this.dateTo}T23:59:59Z` : undefined,
        artifactId: this.artifactId,
        page,
      });
      this.items.set(result.items);
      this.page.set(page);
      this.pages.set(result.pages);
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
  reset() {
    this.brandId =
      this.productId =
      this.destinationId =
      this.status =
      this.retryable =
      this.dateFrom =
      this.dateTo =
      this.artifactId =
        '';
    void this.load(1);
  }
}
