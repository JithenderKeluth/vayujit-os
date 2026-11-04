import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { SellerMoneyPipe } from '../intelligence/seller-financial-format';

import { PageHeaderComponent } from '../shared/page-header.component';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { MarketplaceService, ReconciliationSummary, UnifiedOrder } from './marketplace.service';

@Component({
  selector: 'app-unified-orders',
  imports: [
    DatePipe,
    PageHeaderComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    FormsModule,
    RouterLink,
    SellerMoneyPipe,
  ],
  template: `
    <section class="marketplace-page" aria-label="Unified orders">
      <app-page-header
        eyebrow="Sell · operations"
        title="Unified orders"
        description="One owner-scoped order timeline with reservation, shipment, cancellation, and return states."
      />
      <div class="marketplace-callout" role="note">
        <strong>Read-only provider boundary.</strong> Orders shown here are local projections.
        Fake-provider events are available only for certification and never contact a marketplace.
      </div>
      <p>
        No live synchronization is started here. Cancellation and return are recorded states, not
        requests to cancel, refund or restock.
        <a routerLink="/marketplaces/accounts">Review account prerequisites</a> ·
        <a routerLink="/marketplaces/inventory">Review inventory</a> ·
        <a routerLink="/marketplaces/financials">Review financial evidence</a>
      </p>
      @if (error()) {
        <app-error-state
          title="Orders are unavailable"
          [message]="error()"
          retryLabel="Retry"
          (retry)="load()"
        />
      }
      @if (summary(); as value) {
        <dl class="marketplace-stats" aria-label="Order reconciliation summary">
          <div>
            <dt>Inventory items</dt>
            <dd>{{ value.inventory_items }}</dd>
          </div>
          <div>
            <dt>Active reservations</dt>
            <dd>{{ value.active_reservations }}</dd>
          </div>
          <div>
            <dt>Reservation failures</dt>
            <dd>{{ value.reservation_failures }}</dd>
          </div>
          <div>
            <dt>Stale provider events</dt>
            <dd>{{ value.stale_provider_events }}</dd>
          </div>
        </dl>
      }
      <div class="marketplace-form" role="group" aria-label="Order filters">
        <label>Marketplace <input [(ngModel)]="marketplace" (keyup.enter)="load()" /></label
        ><label>Status <input [(ngModel)]="status" (keyup.enter)="load()" /></label
        ><button type="button" (click)="load()">Refresh</button>
      </div>
      @if (loading()) {
        <app-loading-state message="Loading unified orders..." />
      }
      @if (!loading() && !error() && !orders().length) {
        <app-empty-state
          title="No matching local orders"
          message="No orders match this filter. Live synchronization is not performed here; review authorized account and ingestion prerequisites. An unavailable read is not an empty business history."
        />
      }
      @if (orders().length) {
        <div class="marketplace-table" tabindex="0">
          <table>
            <caption>
              Owner-scoped unified order timeline
            </caption>
            <thead>
              <tr>
                <th scope="col">Marketplace</th>
                <th scope="col">Order</th>
                <th scope="col">Items</th>
                <th scope="col">Status</th>
                <th scope="col">Reservation</th>
                <th scope="col">Ordered</th>
                <th scope="col">Source</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              @for (order of orders(); track order.id) {
                <tr>
                  <td>{{ order.marketplace }}</td>
                  <th scope="row">{{ order.remote_order_id }}</th>
                  <td>{{ order.line_count }}</td>
                  <td>{{ order.status }} / {{ order.fulfilment_status }}</td>
                  <td>{{ order.reservation_state }}</td>
                  <td>{{ order.ordered_at | date: 'medium' }}</td>
                  <td>{{ sourceLabel(order) }}</td>
                  <td>
                    <button type="button" (click)="inspect(order)">
                      {{ selectedOrder()?.id === order.id ? 'Hide details' : 'View details' }}
                    </button>
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      }
      @if (detailLoading()) {
        <app-loading-state message="Loading order details..." />
      }
      @if (detailError()) {
        <p class="marketplace-error" role="alert">{{ detailError() }}</p>
      }
      @if (selectedOrder(); as order) {
        <section class="marketplace-card" aria-label="Order details">
          <h2>Order {{ order.remote_order_id }}</h2>
          <dl class="marketplace-stats">
            <div>
              <dt>Marketplace</dt>
              <dd>{{ order.marketplace }}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{{ order.status }}</dd>
            </div>
            <div>
              <dt>Fulfilment</dt>
              <dd>{{ order.fulfilment_status }}</dd>
            </div>
            <div>
              <dt>Reservation</dt>
              <dd>{{ order.reservation_state }}</dd>
            </div>
            <div>
              <dt>Line count</dt>
              <dd>{{ order.line_count }}</dd>
            </div>
          </dl>
          <p class="marketplace-callout">
            Source: {{ sourceLabel(order) }}. This view is read-only; channel acknowledgements are
            disabled.
          </p>
          @for (line of order.lines || []; track line.id) {
            <article class="marketplace-card">
              <h3>{{ line.title || line.marketplace_sku || 'Order line' }}</h3>
              <p>
                SKU {{ line.marketplace_sku || 'UNKNOWN' }} · Quantity {{ line.quantity }} · Stored
                unit price (rounded) {{ line.unit_price | sellerMoney: order.currency }} · Line
                total
                {{ line.total_price | sellerMoney: order.currency }}
              </p>
              <p>
                Stored unit prices are two-decimal projections. Recorded line totals may retain a
                different source rounding basis and must not be reconstructed from the rounded unit
                display. Review original order evidence before accounting or corrections.
              </p>
              @if (line.product_id) {
                <a [routerLink]="['/catalog', line.product_id]">Review this product</a> ·
                <a
                  routerLink="/marketplaces/inventory"
                  [queryParams]="{ product_id: line.product_id }"
                  >Review this product inventory</a
                >
              } @else {
                <p>
                  Product mapping UNKNOWN. Review the source mapping; no replacement product is
                  selected.
                </p>
              }
            </article>
          }
        </section>
      }
      <div class="marketplace-approval" role="note">
        <strong>Next step</strong>
        <p>
          Review unmapped or stale events before changing stock. Channel acknowledgements and
          fulfilment writes remain outside this workspace.
        </p>
      </div>
    </section>
  `,
  styleUrl: './marketplaces.css',
})
export class UnifiedOrdersComponent {
  private readonly service = inject(MarketplaceService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly orders = signal<UnifiedOrder[]>([]);
  readonly summary = signal<ReconciliationSummary | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly selectedOrder = signal<UnifiedOrder | null>(null);
  readonly detailLoading = signal(false);
  readonly detailError = signal('');
  marketplace = '';
  status = '';
  private requestVersion = 0;
  private detailVersion = 0;

  constructor() {
    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      const id = params.get('order_id');
      if (id) void this.openOrder(id);
      else {
        this.selectedOrder.set(null);
        this.detailVersion++;
        this.detailLoading.set(false);
      }
    });
    void this.load();
  }
  sourceLabel(order: UnifiedOrder): string {
    if (order.fake_provider) return 'Synthetic fixture — not a real marketplace transaction';
    return order.provenance_status === 'REPORTED'
      ? 'Reported source, not independently verified'
      : 'Provenance UNKNOWN';
  }

  async load(): Promise<void> {
    const version = ++this.requestVersion;
    this.loading.set(true);
    this.error.set('');
    this.orders.set([]);
    this.summary.set(null);
    try {
      const [orders, summary] = await Promise.all([
        this.service.unifiedOrders({
          marketplace: this.marketplace || undefined,
          status: this.status || undefined,
        }),
        this.service.unifiedInsights(),
      ]);
      if (version !== this.requestVersion) return;
      this.orders.set(orders);
      this.summary.set(summary);
    } catch {
      if (version === this.requestVersion) this.error.set(MarketplaceService.errorMessage());
    } finally {
      if (version === this.requestVersion) this.loading.set(false);
    }
  }

  async inspect(order: UnifiedOrder): Promise<void> {
    await this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { order_id: this.selectedOrder()?.id === order.id ? null : order.id },
      queryParamsHandling: 'merge',
    });
  }
  private async openOrder(id: string): Promise<void> {
    const version = ++this.detailVersion;
    this.detailError.set('');
    this.selectedOrder.set(null);
    if (!/^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(id)) {
      this.detailError.set('Invalid order identifier. No other order was substituted.');
      this.detailLoading.set(false);
      return;
    }
    this.detailLoading.set(true);
    try {
      const value = await this.service.unifiedOrder(id);
      if (version === this.detailVersion) this.selectedOrder.set(value);
    } catch {
      if (version === this.detailVersion)
        this.detailError.set('Order details are unavailable. Refresh and try again.');
    } finally {
      if (version === this.detailVersion) this.detailLoading.set(false);
    }
  }
}
