import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { ApprovalQueueItem, BrandSummary, ProductSummary } from '@vayujit/shared';
import { BrandService } from '../brands/brand.service';
import { ProductService } from '../products/product.service';
import { OperationsService } from './operations.service';

@Component({
  selector: 'app-approvals',
  imports: [FormsModule, RouterLink],
  template: `<section class="op-page">
    <header>
      <h1>Approvals</h1>
      <p class="op-muted">Review generated content before it becomes eligible for Publishing.</p>
    </header>
    <nav class="op-tabs" aria-label="Approval status">
      @for (tab of tabs; track tab.value) {
        <a
          [class.active]="status === tab.value"
          href=""
          (click)="$event.preventDefault(); status = tab.value; load(1)"
          >{{ tab.label }}</a
        >
      }
    </nav>
    <form class="op-card op-filters" (ngSubmit)="load(1)">
      <label
        >Brand
        <select name="brand" [(ngModel)]="brandId">
          <option value="">All Brands</option>
          @for (x of brands(); track x.id) {
            <option [value]="x.id">{{ x.name }}</option>
          }
        </select></label
      ><label
        >Product
        <select name="product" [(ngModel)]="productId">
          <option value="">All Products</option>
          @for (x of products(); track x.id) {
            <option [value]="x.id">{{ x.name }}</option>
          }
        </select></label
      ><label>Search <input name="search" maxlength="120" [(ngModel)]="search" /></label
      ><button>Apply</button>
    </form>
    @if (loading()) {
      <p role="status">Loading approval queue…</p>
    }
    @if (error()) {
      <p class="op-error" role="alert">{{ error() }}</p>
    }
    @if (!loading() && !items().length) {
      <div class="op-empty">
        <h2>Nothing in this queue</h2>
        <p>Generate Product content or choose another status.</p>
      </div>
    }
    @if (items().length) {
      <table class="op-table">
        <thead>
          <tr>
            <th>Product</th>
            <th>Generated content</th>
            <th>Version</th>
            <th>Status</th>
            <th>Generated</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (item of items(); track item.id) {
            <tr>
              <td data-label="Product">
                <strong>{{ item.product_name }}</strong
                ><br />{{ item.brand_name }}
              </td>
              <td data-label="Generated content">
                <strong>{{ item.generated_title }}</strong
                ><br />{{ item.short_description }}
              </td>
              <td data-label="Version">
                v{{ item.version_number }}<br />{{ item.template_name }} v{{
                  item.template_version
                }}
              </td>
              <td data-label="Status">
                <span class="op-status">{{ item.status }}</span>
              </td>
              <td data-label="Generated">{{ item.generated_at }}</td>
              <td data-label="Action">
                <a
                  [routerLink]="['/approvals', item.id]"
                  [queryParams]="item.workflow_id ? { workflow: item.workflow_id } : null"
                  >Review</a
                >
              </td>
            </tr>
          }
        </tbody>
      </table>
    }
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
export class ApprovalsComponent implements OnInit {
  private readonly api = inject(OperationsService);
  private readonly brandApi = inject(BrandService);
  private readonly productApi = inject(ProductService);
  readonly items = signal<ApprovalQueueItem[]>([]);
  readonly brands = signal<BrandSummary[]>([]);
  readonly products = signal<ProductSummary[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly page = signal(1);
  readonly pages = signal(0);
  status = 'pending_review';
  brandId = '';
  productId = '';
  search = '';
  readonly tabs = [
    { label: 'Pending', value: 'pending_review' },
    { label: 'Approved', value: 'approved' },
    { label: 'Rejected', value: 'rejected' },
    { label: 'Superseded', value: 'superseded' },
    { label: 'All', value: '' },
  ];
  ngOnInit(): void {
    void this.init();
  }
  async init() {
    try {
      const [b, p] = await Promise.all([
        this.brandApi.list({ includeArchived: true, pageSize: 100 }),
        this.productApi.list({ allBrands: true, includeArchived: true, pageSize: 100 }),
      ]);
      this.brands.set(b.items);
      this.products.set(p.items);
      await this.load(1);
    } catch {
      this.error.set('Unable to load approval filters.');
      this.loading.set(false);
    }
  }
  async load(page: number) {
    this.loading.set(true);
    this.error.set('');
    try {
      const x = await this.api.approvals({
        status: this.status || undefined,
        brand_id: this.brandId,
        product_id: this.productId,
        search: this.search,
        page,
      });
      this.items.set(x.items);
      this.page.set(x.page);
      this.pages.set(x.pages);
    } catch {
      this.error.set('Unable to load approvals.');
    } finally {
      this.loading.set(false);
    }
  }
}
