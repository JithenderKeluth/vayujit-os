import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { MarketplaceService, MarketplaceSettlement } from './marketplace.service';

@Component({
  selector: 'app-marketplace-settlements',
  imports: [FormsModule],
  template: `
    <section class="marketplace-page">
      <header>
        <h1>Marketplace settlements</h1>
        <p>
          Normalized settlement lines preserve gross, refunds, fees, withholding, adjustments, net,
          and currency.
        </p>
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
          >Currency<input [(ngModel)]="currencyFilter" placeholder="INR" maxlength="3" /></label
        ><label>From<input type="date" [(ngModel)]="dateFrom" /></label
        ><label>To<input type="date" [(ngModel)]="dateTo" /></label>
      </div>
      @if (!filteredItems().length && !loading()) {
        <p class="marketplace-empty">No settlements match the filters.</p>
      }
      <div class="marketplace-table">
        <table>
          <caption>
            Unified marketplace settlements
          </caption>
          <thead>
            <tr>
              <th>Marketplace</th>
              <th>Period</th>
              <th>Status</th>
              <th>Gross</th>
              <th>Refunds</th>
              <th>Fees</th>
              <th>Withholding</th>
              <th>Net</th>
              <th>Currency</th>
            </tr>
          </thead>
          <tbody>
            @for (item of filteredItems(); track item.id) {
              <tr>
                <td>{{ item.marketplace }}</td>
                <td>{{ item.period_start }} — {{ item.period_end }}</td>
                <td>{{ item.status || 'settled' }}</td>
                <td>{{ item.gross_amount }}</td>
                <td>{{ item.refund_amount }}</td>
                <td>{{ item.fee_amount }}</td>
                <td>{{ item.tax_withholding_amount }}</td>
                <td>{{ item.net_amount }}</td>
                <td>{{ item.currency }}</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    </section>
  `,
  styleUrl: './marketplaces.css',
})
export class MarketplaceSettlementsComponent {
  private readonly service = inject(MarketplaceService);
  readonly items = signal<MarketplaceSettlement[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  marketplaceFilter = '';
  statusFilter = '';
  currencyFilter = '';
  dateFrom = '';
  dateTo = '';
  readonly marketplaces = signal<string[]>([]);
  constructor() {
    void this.load();
  }
  filteredItems(): MarketplaceSettlement[] {
    return this.items().filter(
      (item) =>
        (!this.marketplaceFilter || item.marketplace === this.marketplaceFilter) &&
        (!this.statusFilter ||
          (item.status || 'settled').toLowerCase() === this.statusFilter.toLowerCase()) &&
        (!this.currencyFilter ||
          item.currency.toLowerCase() === this.currencyFilter.toLowerCase()) &&
        (!this.dateFrom || item.period_end >= this.dateFrom) &&
        (!this.dateTo || item.period_start <= this.dateTo),
    );
  }
  async load(): Promise<void> {
    try {
      const values = await this.service.settlements();
      this.items.set(values);
      this.marketplaces.set([...new Set(values.map((item) => item.marketplace))].sort());
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    } finally {
      this.loading.set(false);
    }
  }
}
