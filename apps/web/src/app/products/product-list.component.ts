import { CurrencyPipe, DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { BrandSummary, PaginatedProductResponse, ProductSummary } from '@vayujit/shared';
import { BrandService } from '../brands/brand.service';
import { ProductService } from './product.service';

@Component({
  selector: 'app-product-list',
  imports: [CurrencyPipe, DatePipe, ReactiveFormsModule, RouterLink],
  template: `
    <section class="page">
      <header class="page-header">
        <div>
          <p class="eyebrow">Product Management</p>
          <h1>Products</h1>
          <p>Context: {{ selectedBrandName() }}</p>
        </div>
        <a class="button primary" routerLink="/products/new">Create product</a>
      </header>
      <form class="filters" (submit)="apply($event)">
        <label
          >Brand<select [formControl]="brandFilter" (change)="brandChanged()">
            <option value="">Active brand</option>
            <option value="all">All owned brands</option>
            @for (brand of brands(); track brand.id) {
              <option [value]="brand.id">{{ brand.name }}</option>
            }
          </select></label
        >
        <label>Search<input [formControl]="search" placeholder="Name or SKU" /></label>
        <label
          >Status<select [formControl]="status">
            <option value="">Draft and active</option>
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="archived">Archived</option>
          </select></label
        >
        <label
          >Type<select [formControl]="productType">
            <option value="">All types</option>
            <option value="physical">Physical</option>
            <option value="digital">Digital</option>
            <option value="service">Service</option>
            <option value="affiliate">Affiliate</option>
          </select></label
        >
        <label>Category<input [formControl]="category" /></label>
        <label
          >Featured<select [formControl]="featured">
            <option value="">Any</option>
            <option value="true">Featured</option>
            <option value="false">Not featured</option>
          </select></label
        >
        <label
          >Sort<select [formControl]="sort">
            <option value="name">Name</option>
            <option value="updated_at">Updated</option>
            <option value="created_at">Created</option>
            <option value="price">Price</option>
            <option value="inventory_quantity">Inventory</option>
          </select></label
        >
        <label
          >Direction<select [formControl]="direction">
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select></label
        >
        <label class="checkbox"
          ><input type="checkbox" [formControl]="includeArchived" /> Include archived</label
        >
        <button class="button" type="submit">Apply</button>
      </form>
      @if (!activeBrand() && !explicitBrand()) {
        <div class="state">
          <h2>No active brand</h2>
          <p>Select an active brand from Brands, or choose an owned brand above.</p>
          <a class="button" routerLink="/brands">Manage brands</a>
        </div>
      } @else if (loading()) {
        <p class="state">Loading products…</p>
      } @else if (error()) {
        <p class="state error" role="alert">{{ error() }}</p>
      } @else if (!result()?.items?.length) {
        <div class="state">
          <h2>No products found</h2>
          <p>Create a product or change the filters.</p>
        </div>
      } @else {
        <div class="product-grid">
          @for (product of result()!.items; track product.id) {
            <article class="card">
              <div class="card-title">
                <div>
                  <h2>
                    <a [routerLink]="['/products', product.id]">{{ product.name }}</a>
                  </h2>
                  <p>{{ product.brand_name }} · {{ product.product_type }}</p>
                </div>
                <span class="badge">{{ product.status }}</span>
                @if (product.is_featured) {
                  <span class="badge featured">Featured</span>
                }
              </div>
              <dl>
                <div>
                  <dt>SKU</dt>
                  <dd>{{ product.sku || '—' }}</dd>
                </div>
                <div>
                  <dt>Category</dt>
                  <dd>{{ product.category || '—' }}</dd>
                </div>
                <div>
                  <dt>Price</dt>
                  <dd>
                    @if (product.price_amount && product.price_currency) {
                      {{ product.price_amount | currency: product.price_currency }}
                    } @else {
                      —
                    }
                  </dd>
                </div>
                @if (product.inventory_tracking_enabled) {
                  <div>
                    <dt>Inventory</dt>
                    <dd>{{ product.inventory_quantity }}</dd>
                  </div>
                }
                <div>
                  <dt>Updated</dt>
                  <dd>{{ product.updated_at | date: 'mediumDate' }}</dd>
                </div>
              </dl>
              <div class="actions">
                <a class="button" [routerLink]="['/products', product.id]">View</a>
                <a class="button" [routerLink]="['/products', product.id, 'edit']">Edit</a>
                @if (product.status === 'draft') {
                  <button class="button primary" (click)="activate(product)">Activate</button>
                }
                @if (product.status === 'active') {
                  <button class="button" (click)="draft(product)">Move to draft</button>
                }
                @if (product.status !== 'archived') {
                  <button class="button danger" (click)="archive(product)">Archive</button>
                } @else {
                  <button class="button" (click)="restore(product)">Restore</button>
                }
              </div>
            </article>
          }
        </div>
        <nav class="pagination" aria-label="Product pages">
          <button
            class="button"
            [disabled]="result()!.page <= 1"
            (click)="load(result()!.page - 1)"
          >
            Previous
          </button>
          <span
            >Page {{ result()!.page }} of {{ result()!.pages || 1 }} ·
            {{ result()!.total }} products</span
          >
          <button
            class="button"
            [disabled]="result()!.page >= result()!.pages"
            (click)="load(result()!.page + 1)"
          >
            Next
          </button>
        </nav>
      }
    </section>
  `,
  styleUrl: './products.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProductListComponent {
  private readonly products = inject(ProductService);
  private readonly brandService = inject(BrandService);
  readonly activeBrand = this.brandService.activeBrand;
  readonly brands = signal<BrandSummary[]>([]);
  readonly result = signal<PaginatedProductResponse | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly explicitBrand = signal(false);
  readonly brandFilter = new FormControl('', { nonNullable: true });
  readonly search = new FormControl('', { nonNullable: true });
  readonly status = new FormControl<'' | 'draft' | 'active' | 'archived'>('', {
    nonNullable: true,
  });
  readonly productType = new FormControl<'' | 'physical' | 'digital' | 'service' | 'affiliate'>(
    '',
    { nonNullable: true },
  );
  readonly category = new FormControl('', { nonNullable: true });
  readonly featured = new FormControl<'' | 'true' | 'false'>('', { nonNullable: true });
  readonly includeArchived = new FormControl(false, { nonNullable: true });
  readonly sort = new FormControl<
    'name' | 'created_at' | 'updated_at' | 'price' | 'inventory_quantity'
  >('name', { nonNullable: true });
  readonly direction = new FormControl<'asc' | 'desc'>('asc', { nonNullable: true });

  constructor() {
    void this.loadBrands();
    effect(() => {
      const active = this.activeBrand();
      if (!this.explicitBrand()) {
        this.brandFilter.setValue('');
        if (active) void this.load(1);
        else {
          this.result.set(null);
          this.loading.set(false);
        }
      }
    });
  }

  selectedBrandName(): string {
    if (this.brandFilter.value === 'all') return 'All owned brands';
    if (this.brandFilter.value) {
      return this.brands().find((brand) => brand.id === this.brandFilter.value)?.name ?? 'Selected';
    }
    return this.activeBrand()?.name ?? 'None';
  }

  brandChanged(): void {
    this.explicitBrand.set(Boolean(this.brandFilter.value));
    void this.load(1);
  }

  apply(event: Event): void {
    event.preventDefault();
    void this.load(1);
  }

  private async loadBrands(): Promise<void> {
    try {
      this.brands.set(
        (
          await this.brandService.list({
            includeArchived: false,
            pageSize: 100,
          })
        ).items,
      );
    } catch (error) {
      this.error.set(ProductService.errorMessage(error));
    }
  }

  async load(page = 1): Promise<void> {
    if (!this.activeBrand() && !this.brandFilter.value) {
      this.loading.set(false);
      return;
    }
    this.loading.set(true);
    this.error.set('');
    try {
      const brandValue = this.brandFilter.value;
      this.result.set(
        await this.products.list({
          brandId: brandValue && brandValue !== 'all' ? brandValue : undefined,
          allBrands: brandValue === 'all',
          search: this.search.value.trim(),
          status: this.status.value,
          productType: this.productType.value,
          category: this.category.value.trim(),
          featured: this.featured.value === '' ? null : this.featured.value === 'true',
          includeArchived: this.includeArchived.value,
          sortBy: this.sort.value,
          sortDirection: this.direction.value,
          page,
        }),
      );
    } catch (error) {
      this.error.set(ProductService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }

  async activate(product: ProductSummary): Promise<void> {
    await this.action(() => this.products.activate(product.id));
  }
  async draft(product: ProductSummary): Promise<void> {
    await this.action(() => this.products.moveToDraft(product.id));
  }
  async restore(product: ProductSummary): Promise<void> {
    await this.action(() => this.products.restore(product.id));
  }
  async archive(product: ProductSummary): Promise<void> {
    if (!confirm(`Archive ${product.name}? It will remain available for restoration.`)) return;
    await this.action(() => this.products.archive(product.id));
  }
  private async action(operation: () => Promise<unknown>): Promise<void> {
    try {
      await operation();
      await this.load(this.result()?.page);
    } catch (error) {
      this.error.set(ProductService.errorMessage(error));
    }
  }
}
