import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { MarketplaceInventory, MarketplaceService } from './marketplace.service';

@Component({
  selector: 'app-marketplace-inventory',
  imports: [FormsModule],
  template: `
    <section class="marketplace-page">
      <header>
        <h1>Marketplace inventory</h1>
        <p>Inventory writes are explicit; continuous synchronization is not enabled.</p>
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
        ><label><input type="checkbox" [(ngModel)]="lowStockOnly" /> Low stock only</label>
      </div>
      @if (!filteredItems().length && !loading()) {
        <p class="marketplace-empty">No inventory snapshots match the filters.</p>
      }
      <div class="marketplace-table">
        <table>
          <caption>
            Normalized inventory by marketplace
          </caption>
          <thead>
            <tr>
              <th>Product</th>
              <th>Marketplace</th>
              <th>SKU/listing</th>
              <th>Available</th>
              <th>Remote</th>
              <th>Sync</th>
              <th>Last sync</th>
            </tr>
          </thead>
          <tbody>
            @for (item of filteredItems(); track item.id) {
              <tr>
                <td>{{ item.product_id }}</td>
                <td>{{ item.marketplace || 'Unknown' }}</td>
                <td>{{ item.listing_id }}</td>
                <td>{{ item.available_quantity }}</td>
                <td>{{ item.marketplace_reported_quantity ?? '—' }}</td>
                <td>{{ item.synchronization_status }}</td>
                <td>{{ item.last_synchronized_at || 'Never' }}</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    </section>
  `,
  styleUrl: './marketplaces.css',
})
export class MarketplaceInventoryComponent {
  private readonly service = inject(MarketplaceService);
  readonly items = signal<MarketplaceInventory[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  marketplaceFilter = '';
  lowStockOnly = false;
  readonly marketplaces = signal<string[]>([]);
  constructor() {
    void this.load();
  }
  filteredItems(): MarketplaceInventory[] {
    return this.items().filter(
      (item) =>
        (!this.marketplaceFilter || item.marketplace === this.marketplaceFilter) &&
        (!this.lowStockOnly || item.available_quantity <= 0),
    );
  }
  async load(): Promise<void> {
    try {
      const values = await this.service.inventory();
      this.items.set(values);
      this.marketplaces.set(
        [
          ...new Set(
            values.map((item) => item.marketplace).filter((item): item is string => Boolean(item)),
          ),
        ].sort(),
      );
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    } finally {
      this.loading.set(false);
    }
  }
}
