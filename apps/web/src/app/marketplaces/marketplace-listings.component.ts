import { Component, inject, signal } from '@angular/core';
import { MarketplaceListing, MarketplaceService } from './marketplace.service';

@Component({
  selector: 'app-marketplace-listings',
  imports: [],
  template: `<section class="marketplace-page">
    <header>
      <h1>Marketplace listings</h1>
      <p>Each listing keeps remote identity and drift separate from the Product source of truth.</p>
    </header>
    @if (error()) {
      <p class="marketplace-error">{{ error() }}</p>
    }
    @if (!items().length && !loading()) {
      <p class="marketplace-empty">No listings need attention.</p>
    }
    <div class="marketplace-table">
      <table>
        <thead>
          <tr>
            <th>Marketplace</th>
            <th>Title</th>
            <th>SKU</th>
            <th>Status</th>
            <th>Drift</th>
          </tr>
        </thead>
        <tbody>
          @for (item of items(); track item.id) {
            <tr>
              <td>{{ item.marketplace }}</td>
              <td>{{ item.title }}</td>
              <td>{{ item.marketplace_sku || '—' }}</td>
              <td>
                <span class="marketplace-status">{{ item.status }}</span>
              </td>
              <td>{{ item.drift_state }}</td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  </section>`,
  styleUrl: './marketplaces.css',
})
export class MarketplaceListingsComponent {
  private readonly service = inject(MarketplaceService);
  readonly items = signal<MarketplaceListing[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  constructor() {
    void this.load();
  }
  async load(): Promise<void> {
    try {
      this.items.set(await this.service.listings());
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    } finally {
      this.loading.set(false);
    }
  }
}
