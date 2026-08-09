import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { MarketplaceOrder, MarketplaceService } from './marketplace.service';

@Component({
  selector: 'app-marketplace-orders',
  imports: [FormsModule],
  template: `
    <section class="marketplace-page">
      <header>
        <h1>Marketplace orders</h1>
        <p>Normalized order, payment, fulfilment, cancellation, return, and refund projections.</p>
      </header>
      @if (error()) {
        <p class="marketplace-error" role="alert">{{ error() }}</p>
      }
      <div class="workspace-grid-form">
        <label
          >Marketplace<select [(ngModel)]="marketplaceFilter">
            <option value="">All</option>
            @for (marketplace of marketplaces(); track marketplace) {
              <option [value]="marketplace">{{ marketplace }}</option>
            }
          </select></label
        ><label>Status<input [(ngModel)]="statusFilter" placeholder="Any status" /></label
        ><label
          >Fulfilment<input [(ngModel)]="fulfilmentFilter" placeholder="Any fulfilment" /></label
        ><label>From<input type="date" [(ngModel)]="dateFrom" /></label
        ><label>To<input type="date" [(ngModel)]="dateTo" /></label>
      </div>
      @if (!filteredItems().length && !loading()) {
        <p class="marketplace-empty">No orders match the filters.</p>
      }
      <div class="marketplace-table">
        <table>
          <caption>
            Unified marketplace orders
          </caption>
          <thead>
            <tr>
              <th>Marketplace</th>
              <th>Account/order</th>
              <th>Items/Product</th>
              <th>Status</th>
              <th>Fulfilment</th>
              <th>Total/tax/shipping</th>
              <th>Payment</th>
              <th>Cancellation/return/refund</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>
            @for (item of filteredItems(); track item.id) {
              <tr>
                <td>{{ item.marketplace }}</td>
                <td>{{ item.remote_order_id }}</td>
                <td>{{ item.buyer_summary.display_name }}</td>
                <td>{{ item.status }}</td>
                <td>{{ item.fulfilment_status }}</td>
                <td>{{ item.totals['total'] || '—' }} {{ item.totals['currency'] || '' }}</td>
                <td>{{ item.totals['payment_status'] || 'Unknown' }}</td>
                <td>
                  {{ item.totals['cancellation_status'] || '—' }} /
                  {{ item.totals['return_status'] || '—' }} /
                  {{ item.totals['refund_status'] || '—' }}
                </td>
                <td>{{ item.ordered_at }}</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    </section>
  `,
  styleUrl: './marketplaces.css',
})
export class MarketplaceOrdersComponent {
  private readonly service = inject(MarketplaceService);
  readonly items = signal<MarketplaceOrder[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  marketplaceFilter = '';
  statusFilter = '';
  fulfilmentFilter = '';
  dateFrom = '';
  dateTo = '';
  readonly marketplaces = signal<string[]>([]);
  constructor() {
    void this.load();
  }
  filteredItems(): MarketplaceOrder[] {
    return this.items().filter(
      (item) =>
        (!this.marketplaceFilter || item.marketplace === this.marketplaceFilter) &&
        (!this.statusFilter ||
          item.status.toLowerCase().includes(this.statusFilter.toLowerCase())) &&
        (!this.fulfilmentFilter ||
          item.fulfilment_status.toLowerCase().includes(this.fulfilmentFilter.toLowerCase())) &&
        (!this.dateFrom || item.ordered_at >= this.dateFrom) &&
        (!this.dateTo || item.ordered_at <= this.dateTo),
    );
  }
  async load(): Promise<void> {
    try {
      const values = await this.service.orders();
      this.items.set(values);
      this.marketplaces.set([...new Set(values.map((item) => item.marketplace))].sort());
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    } finally {
      this.loading.set(false);
    }
  }
}
