import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { PageHeaderComponent } from '../shared/page-header.component';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { MarketplaceService, ReconciliationSummary, UnifiedOrder } from './marketplace.service';

@Component({
  selector: 'app-unified-orders',
  imports: [DatePipe, PageHeaderComponent, EmptyStateComponent, ErrorStateComponent, LoadingStateComponent, FormsModule],
  template: `
    <section class="marketplace-page" aria-label="Unified orders">
      <app-page-header
        eyebrow="Sell · operations"
        title="Unified orders"
        description="One owner-scoped order timeline with reservation, shipment, cancellation, and return states."
      />
      <div class="marketplace-callout" role="note"><strong>Read-only provider boundary.</strong> Orders shown here are local projections. Fake-provider events are available only for certification and never contact a marketplace.</div>
      @if (error()) { <app-error-state title="Orders are unavailable" [message]="error()" retryLabel="Retry" (retry)="load()" /> }
      @if (summary(); as value) {
        <dl class="marketplace-stats" aria-label="Order reconciliation summary"><div><dt>Inventory items</dt><dd>{{ value.inventory_items }}</dd></div><div><dt>Active reservations</dt><dd>{{ value.active_reservations }}</dd></div><div><dt>Reservation failures</dt><dd>{{ value.reservation_failures }}</dd></div><div><dt>Stale provider events</dt><dd>{{ value.stale_provider_events }}</dd></div></dl>
      }
      <div class="marketplace-form" role="group" aria-label="Order filters"><label>Marketplace <input [(ngModel)]="marketplace" (keyup.enter)="load()" /></label><label>Status <input [(ngModel)]="status" (keyup.enter)="load()" /></label><button type="button" (click)="load()">Refresh</button></div>
      @if (loading()) { <app-loading-state message="Loading unified orders..." /> }
      @if (!loading() && !orders().length) { <app-empty-state title="No unified orders yet" message="Orders appear after an approved provider event is ingested and reconciled against canonical inventory." /> }
      @if (orders().length) {
        <div class="marketplace-table" tabindex="0"><table><caption>Owner-scoped unified order timeline</caption><thead><tr><th scope="col">Marketplace</th><th scope="col">Order</th><th scope="col">Items</th><th scope="col">Status</th><th scope="col">Reservation</th><th scope="col">Ordered</th><th scope="col">Source</th><th scope="col">Action</th></tr></thead><tbody>@for (order of orders(); track order.id) {<tr><td>{{ order.marketplace }}</td><th scope="row">{{ order.remote_order_id }}</th><td>{{ order.line_count }}</td><td>{{ order.status }} / {{ order.fulfilment_status }}</td><td>{{ order.reservation_state }}</td><td>{{ order.ordered_at | date:'medium' }}</td><td>{{ order.fake_provider ? 'Local fake provider' : 'Provider' }}</td><td><button type="button" (click)="inspect(order)">{{ selectedOrder()?.id === order.id ? 'Hide details' : 'View details' }}</button></td></tr>}</tbody></table></div>
      }
      @if (detailLoading()) { <app-loading-state message="Loading order details..." /> }
      @if (detailError()) { <p class="marketplace-error" role="alert">{{ detailError() }}</p> }
      @if (selectedOrder(); as order) { <section class="marketplace-card" aria-label="Order details"><h2>Order {{ order.remote_order_id }}</h2><dl class="marketplace-stats"><div><dt>Marketplace</dt><dd>{{ order.marketplace }}</dd></div><div><dt>Status</dt><dd>{{ order.status }}</dd></div><div><dt>Fulfilment</dt><dd>{{ order.fulfilment_status }}</dd></div><div><dt>Reservation</dt><dd>{{ order.reservation_state }}</dd></div><div><dt>Line count</dt><dd>{{ order.line_count }}</dd></div></dl><p class="marketplace-callout">Source: {{ order.fake_provider ? 'Local fake provider certification event' : 'Provider projection' }}. This view is read-only; channel acknowledgements are disabled.</p></section> }
      <div class="marketplace-approval" role="note"><strong>Next step</strong><p>Review unmapped or stale events before changing stock. Channel acknowledgements and fulfilment writes remain outside this workspace.</p></div>
    </section>
  `,
  styleUrl: './marketplaces.css',
})
export class UnifiedOrdersComponent {
  private readonly service = inject(MarketplaceService);
  readonly orders = signal<UnifiedOrder[]>([]);
  readonly summary = signal<ReconciliationSummary | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly selectedOrder = signal<UnifiedOrder | null>(null);
  readonly detailLoading = signal(false);
  readonly detailError = signal('');
  marketplace = '';
  status = '';

  constructor() { void this.load(); }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const [orders, summary] = await Promise.all([
        this.service.unifiedOrders({ marketplace: this.marketplace || undefined, status: this.status || undefined }),
        this.service.unifiedInsights(),
      ]);
      this.orders.set(orders);
      this.summary.set(summary);
    } catch { this.error.set(MarketplaceService.errorMessage()); }
    finally { this.loading.set(false); }
  }

  async inspect(order: UnifiedOrder): Promise<void> {
    this.detailError.set('');
    if (this.selectedOrder()?.id === order.id) { this.selectedOrder.set(null); return; }
    this.detailLoading.set(true);
    try { this.selectedOrder.set(await this.service.unifiedOrder(order.id)); }
    catch { this.detailError.set('Order details are unavailable. Refresh and try again.'); }
    finally { this.detailLoading.set(false); }
  }
}
