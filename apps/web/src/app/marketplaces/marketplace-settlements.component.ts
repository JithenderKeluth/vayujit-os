import { Component, inject, signal } from '@angular/core';
import { MarketplaceSettlement, MarketplaceService } from './marketplace.service';

@Component({
  selector: 'app-marketplace-settlements',
  imports: [],
  template: `<section class="marketplace-page">
    <header>
      <h1>Marketplace settlements</h1>
      <p>Immutable settlement snapshots expose gross, fees, refunds, withholding, and net.</p>
    </header>
    @if (error()) {
      <p class="marketplace-error">{{ error() }}</p>
    }
    @if (!items().length && !loading()) {
      <p class="marketplace-empty">No settlements imported yet.</p>
    }
    <div class="marketplace-table">
      <table>
        <thead>
          <tr>
            <th>Marketplace</th>
            <th>Period</th>
            <th>Gross</th>
            <th>Fees</th>
            <th>Refunds</th>
            <th>Net</th>
          </tr>
        </thead>
        <tbody>
          @for (item of items(); track item.id) {
            <tr>
              <td>{{ item.marketplace }}</td>
              <td>{{ item.period_start }} — {{ item.period_end }}</td>
              <td>{{ item.gross_amount }} {{ item.currency }}</td>
              <td>{{ item.fee_amount }}</td>
              <td>{{ item.refund_amount }}</td>
              <td>{{ item.net_amount }}</td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  </section>`,
  styleUrl: './marketplaces.css',
})
export class MarketplaceSettlementsComponent {
  private readonly service = inject(MarketplaceService);
  readonly items = signal<MarketplaceSettlement[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  constructor() {
    void this.load();
  }
  async load(): Promise<void> {
    try {
      this.items.set(await this.service.settlements());
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    } finally {
      this.loading.set(false);
    }
  }
}
