import { Component, inject, signal } from '@angular/core';
import { MarketplaceOrder, MarketplaceService } from './marketplace.service';

@Component({
  selector: 'app-marketplace-orders',
  imports: [],
  template: `<section class="marketplace-page">
    <header>
      <h1>Marketplace orders</h1>
      <p>Buyer details are masked; normalized lifecycle status remains safe to reconcile.</p>
    </header>
    @if (error()) {
      <p class="marketplace-error">{{ error() }}</p>
    }
    @if (!items().length && !loading()) {
      <p class="marketplace-empty">No orders imported yet.</p>
    }
    <div class="marketplace-table">
      <table>
        <thead>
          <tr>
            <th>Marketplace</th>
            <th>Order</th>
            <th>Status</th>
            <th>Fulfilment</th>
            <th>Total</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          @for (item of items(); track item.id) {
            <tr>
              <td>{{ item.marketplace }}</td>
              <td>{{ item.remote_order_id }}</td>
              <td>{{ item.status }}</td>
              <td>{{ item.fulfilment_status }}</td>
              <td>{{ item.totals['total'] || '—' }}</td>
              <td>{{ item.ordered_at }}</td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  </section>`,
  styleUrl: './marketplaces.css',
})
export class MarketplaceOrdersComponent {
  private readonly service = inject(MarketplaceService);
  readonly items = signal<MarketplaceOrder[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  constructor() {
    void this.load();
  }
  async load(): Promise<void> {
    try {
      this.items.set(await this.service.orders());
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    } finally {
      this.loading.set(false);
    }
  }
}
