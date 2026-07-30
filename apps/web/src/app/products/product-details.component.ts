import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import type { ProductDetails } from '@vayujit/shared';
import { ProductService } from './product.service';

@Component({
  selector: 'app-product-details',
  imports: [DatePipe, RouterLink],
  template: `
    <section class="page narrow">
      @if (loading()) {
        <p class="state">Loading product…</p>
      } @else if (error()) {
        <p class="state error" role="alert">{{ error() }}</p>
      } @else if (product()) {
        <header class="page-header">
          <div>
            <p class="eyebrow">{{ product()!.brand_name }} · {{ product()!.product_type }}</p>
            <h1>{{ product()!.name }}</h1>
            <p>{{ product()!.short_description || 'No short description.' }}</p>
          </div>
          <div class="actions">
            <a class="button" routerLink="/products">Back</a>
            <a class="button primary" [routerLink]="['/products', product()!.id, 'edit']">Edit</a>
          </div>
        </header>
        <article class="card details">
          <div class="card-title">
            <span class="badge">{{ product()!.status }}</span>
            @if (product()!.is_featured) {
              <span class="badge featured">Featured</span>
            }
          </div>
          <dl>
            <div>
              <dt>SKU</dt>
              <dd>{{ product()!.sku || '—' }}</dd>
            </div>
            <div>
              <dt>Barcode</dt>
              <dd>{{ product()!.barcode || '—' }}</dd>
            </div>
            <div>
              <dt>Category</dt>
              <dd>{{ product()!.category || '—' }}</dd>
            </div>
            <div>
              <dt>Slug</dt>
              <dd>{{ product()!.slug }}</dd>
            </div>
          </dl>
          @if (product()!.tags.length) {
            <p class="tags">
              @for (tag of product()!.tags; track tag) {
                <span class="badge">{{ tag }}</span>
              }
            </p>
          }
          <section>
            <h2>Content</h2>
            <p class="description">{{ product()!.description || 'No description.' }}</p>
          </section>
          <section>
            <h2>Pricing</h2>
            <dl>
              <div>
                <dt>Price</dt>
                <dd>{{ money(product()!.price_amount, product()!.price_currency) }}</dd>
              </div>
              <div>
                <dt>Compare at</dt>
                <dd>{{ money(product()!.compare_at_price_amount, product()!.price_currency) }}</dd>
              </div>
              <div>
                <dt>Cost</dt>
                <dd>{{ money(product()!.cost_amount, product()!.price_currency) }}</dd>
              </div>
              <div>
                <dt>Tax code</dt>
                <dd>{{ product()!.tax_code || '—' }}</dd>
              </div>
            </dl>
          </section>
          <section>
            <h2>Inventory and shipping</h2>
            <dl>
              <div>
                <dt>Tracking</dt>
                <dd>{{ product()!.inventory_tracking_enabled ? 'Enabled' : 'Disabled' }}</dd>
              </div>
              <div>
                <dt>Quantity</dt>
                <dd>{{ product()!.inventory_quantity }}</dd>
              </div>
              <div>
                <dt>Low-stock threshold</dt>
                <dd>{{ product()!.low_stock_threshold }}</dd>
              </div>
              <div>
                <dt>Weight</dt>
                <dd>
                  {{
                    product()!.weight_value
                      ? product()!.weight_value + ' ' + product()!.weight_unit
                      : '—'
                  }}
                </dd>
              </div>
            </dl>
          </section>
          <dl>
            <div>
              <dt>Created</dt>
              <dd>{{ product()!.created_at | date: 'medium' }}</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{{ product()!.updated_at | date: 'medium' }}</dd>
            </div>
          </dl>
          <div class="actions">
            @if (product()!.status === 'draft') {
              <button class="button primary" (click)="activate()">Activate</button>
            }
            @if (product()!.status === 'active') {
              <button class="button" (click)="draft()">Move to draft</button>
            }
            @if (product()!.status !== 'archived') {
              <button class="button danger" (click)="archive()">Archive</button>
            } @else {
              <button class="button" (click)="restore()">Restore to draft</button>
            }
          </div>
        </article>
        <section class="card">
          <h2>Recent activity</h2>
          @if (!product()!.recent_audit_events.length) {
            <p>No activity recorded.</p>
          }
          @for (event of product()!.recent_audit_events; track event.occurred_at) {
            <p>
              <strong>{{ event.action }}</strong> · {{ event.occurred_at | date: 'medium' }}
            </p>
          }
        </section>
      }
    </section>
  `,
  styleUrl: './products.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProductDetailsComponent {
  private readonly products = inject(ProductService);
  private readonly route = inject(ActivatedRoute);
  private readonly id = this.route.snapshot.paramMap.get('id')!;
  readonly product = signal<ProductDetails | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');

  constructor() {
    void this.load();
  }

  money(amount: string | null, currency: string | null): string {
    return amount && currency ? `${currency} ${amount}` : '—';
  }

  private async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      this.product.set(await this.products.get(this.id));
    } catch (error) {
      this.error.set(ProductService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }

  async activate(): Promise<void> {
    await this.action(() => this.products.activate(this.id));
  }
  async draft(): Promise<void> {
    await this.action(() => this.products.moveToDraft(this.id));
  }
  async restore(): Promise<void> {
    await this.action(() => this.products.restore(this.id));
  }
  async archive(): Promise<void> {
    if (!confirm(`Archive ${this.product()?.name}?`)) return;
    await this.action(() => this.products.archive(this.id));
  }
  private async action(operation: () => Promise<unknown>): Promise<void> {
    try {
      await operation();
      await this.load();
    } catch (error) {
      this.error.set(ProductService.errorMessage(error));
    }
  }
}
