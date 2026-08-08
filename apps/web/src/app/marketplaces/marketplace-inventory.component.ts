import { Component, inject, signal } from '@angular/core';
import { MarketplaceInventory, MarketplaceService } from './marketplace.service';

@Component({
  selector: 'app-marketplace-inventory',
  imports: [],
  template: `<section class="marketplace-page">
    <header>
      <h1>Marketplace inventory</h1>
      <p>
        Inventory writes are explicit; this view shows local and marketplace-reported quantities.
      </p>
    </header>
    @if (error()) {
      <p class="marketplace-error">{{ error() }}</p>
    }
    @if (!items().length && !loading()) {
      <p class="marketplace-empty">No inventory snapshots yet.</p>
    }
    <div class="marketplace-table">
      <table>
        <thead>
          <tr>
            <th>Product</th>
            <th>Available</th>
            <th>Remote</th>
            <th>Sync</th>
            <th>Last sync</th>
          </tr>
        </thead>
        <tbody>
          @for (item of items(); track item.id) {
            <tr>
              <td>{{ item.product_id }}</td>
              <td>{{ item.available_quantity }}</td>
              <td>{{ item.marketplace_reported_quantity ?? '—' }}</td>
              <td>{{ item.synchronization_status }}</td>
              <td>{{ item.last_synchronized_at || 'Never' }}</td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  </section>`,
  styleUrl: './marketplaces.css',
})
export class MarketplaceInventoryComponent {
  private readonly service = inject(MarketplaceService);
  readonly items = signal<MarketplaceInventory[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  constructor() {
    void this.load();
  }
  async load(): Promise<void> {
    try {
      this.items.set(await this.service.inventory());
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    } finally {
      this.loading.set(false);
    }
  }
}
