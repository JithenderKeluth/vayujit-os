import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import {
  MarketplaceAccount,
  MarketplaceAnalytics,
  MarketplaceInventory,
  MarketplaceListing,
  MarketplaceOrder,
  MarketplaceService,
  MarketplaceSettlement,
} from './marketplace.service';

interface MarketplaceOverviewRow {
  marketplace: string;
  accounts: number;
  activeListings: number;
  processingListings: number;
  attentionListings: number;
  orders: number;
  grossSales: string;
  refunds: string;
  fees: string;
  contribution: string;
  profitAvailable: boolean;
  lowStock: number;
  failures: number;
  currency: string | null;
}

@Component({
  selector: 'app-marketplace-home',
  imports: [RouterLink],
  template: `
    <section class="marketplace-page">
      <header>
        <h1>Marketplace overview</h1>
        <p>
          Shared operations for every registered marketplace channel. Currency totals are never
          converted implicitly.
        </p>
      </header>
      @if (error()) {
        <p class="marketplace-error" role="alert">{{ error() }}</p>
      }
      <div class="marketplace-grid">
        <a routerLink="/marketplaces/accounts"
          ><h2>Accounts</h2>
          <p>Connected accounts and validation status.</p></a
        >
        <a routerLink="/marketplaces/listings"
          ><h2>Listings</h2>
          <p>Active, processing, and attention-required listings.</p></a
        >
        <a routerLink="/marketplaces/inventory"
          ><h2>Inventory</h2>
          <p>Explicit per-channel stock and synchronization.</p></a
        >
        <a routerLink="/marketplaces/orders"
          ><h2>Orders</h2>
          <p>Normalized buyer-safe order lifecycle.</p></a
        >
        <a routerLink="/marketplaces/settlements"
          ><h2>Settlements</h2>
          <p>Normalized gross, refunds, fees, and net.</p></a
        >
        <a routerLink="/marketplaces/analytics"
          ><h2>Profitability</h2>
          <p>Contribution with explicit cost availability.</p></a
        >
      </div>
      <section class="marketplace-card">
        <h2>Channel health</h2>
        <div class="marketplace-table">
          <table>
            <caption>
              Marketplace operational overview
            </caption>
            <thead>
              <tr>
                <th>Marketplace</th>
                <th>Accounts</th>
                <th>Listings</th>
                <th>Attention</th>
                <th>Orders</th>
                <th>Gross</th>
                <th>Refunds</th>
                <th>Fees</th>
                <th>Contribution</th>
                <th>Profit</th>
                <th>Low stock</th>
                <th>Failures</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              @for (row of rows(); track row.marketplace) {
                <tr>
                  <td>{{ row.marketplace }}</td>
                  <td>{{ row.accounts }}</td>
                  <td>{{ row.activeListings }} active / {{ row.processingListings }} processing</td>
                  <td>{{ row.attentionListings }}</td>
                  <td>{{ row.orders }}</td>
                  <td>{{ row.grossSales }} {{ row.currency || '' }}</td>
                  <td>{{ row.refunds }}</td>
                  <td>{{ row.fees }}</td>
                  <td>{{ row.contribution }}</td>
                  <td>{{ row.profitAvailable ? 'Available' : 'Unavailable' }}</td>
                  <td>{{ row.lowStock }}</td>
                  <td>{{ row.failures }}</td>
                  <td><a [routerLink]="channelPath(row.marketplace)">Open channel</a></td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </section>
      @if (combined(); as total) {
        <section class="marketplace-card">
          <h2>Combined totals ({{ total.currency }})</h2>
          <dl class="marketplace-stats">
            <div>
              <dt>Gross sales</dt>
              <dd>{{ total.gross }}</dd>
            </div>
            <div>
              <dt>Refunds</dt>
              <dd>{{ total.refunds }}</dd>
            </div>
            <div>
              <dt>Fees</dt>
              <dd>{{ total.fees }}</dd>
            </div>
            <div>
              <dt>Contribution</dt>
              <dd>{{ total.contribution }}</dd>
            </div>
          </dl>
          <p class="marketplace-callout">
            Combined values are shown only because all channels reported the same currency.
          </p>
        </section>
      } @else {
        <p class="marketplace-callout">
          Combined totals are unavailable when channel currencies differ.
        </p>
      }
    </section>
  `,
  styleUrl: './marketplaces.css',
})
export class MarketplaceHomeComponent {
  private readonly service = inject(MarketplaceService);
  readonly rows = signal<MarketplaceOverviewRow[]>([]);
  readonly combined = signal<{
    currency: string;
    gross: string;
    refunds: string;
    fees: string;
    contribution: string;
  } | null>(null);
  readonly error = signal('');
  private readonly channelRegistry: Record<string, string> = {
    amazon: '/marketplaces/amazon',
    flipkart: '/marketplaces/flipkart',
    meesho: '/marketplaces/meesho',
  };

  constructor() {
    void this.load();
  }
  channelPath(marketplace: string): string {
    return this.channelRegistry[marketplace] || '/marketplaces';
  }
  async load(): Promise<void> {
    try {
      const [accounts, listings, inventory, orders, settlements, analytics] = await Promise.all([
        this.service.accounts(),
        this.service.listings(),
        this.service.inventory(),
        this.service.orders(),
        this.service.settlements(),
        this.service.analytics(),
      ]);
      const channels = new Set([
        ...accounts.map((item) => item.marketplace),
        ...listings.map((item) => item.marketplace),
        ...orders.map((item) => item.marketplace),
        ...settlements.map((item) => item.marketplace),
      ]);
      const rows = [...channels]
        .sort()
        .map((marketplace) =>
          this.toRow(marketplace, accounts, listings, inventory, orders, settlements, analytics),
        );
      this.rows.set(rows);
      const currencies = new Set(settlements.map((item) => item.currency).filter(Boolean));
      if (currencies.size === 1 && rows.length) {
        const currency = [...currencies][0];
        const number = (value: string) => Number(value || 0);
        this.combined.set({
          currency,
          gross: String(rows.reduce((sum, row) => sum + number(row.grossSales), 0)),
          refunds: String(rows.reduce((sum, row) => sum + number(row.refunds), 0)),
          fees: String(rows.reduce((sum, row) => sum + number(row.fees), 0)),
          contribution: String(rows.reduce((sum, row) => sum + number(row.contribution), 0)),
        });
      }
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    }
  }
  private toRow(
    marketplace: string,
    accounts: MarketplaceAccount[],
    listings: MarketplaceListing[],
    inventory: MarketplaceInventory[],
    orders: MarketplaceOrder[],
    settlements: MarketplaceSettlement[],
    analytics: MarketplaceAnalytics,
  ): MarketplaceOverviewRow {
    const ownListings = listings.filter((item) => item.marketplace === marketplace);
    const ownSettlements = settlements.filter((item) => item.marketplace === marketplace);
    const ownOrders = orders.filter((item) => item.marketplace === marketplace);
    const currency = ownSettlements[0]?.currency || null;
    const gross = ownSettlements.reduce((sum, item) => sum + Number(item.gross_amount || 0), 0);
    const refunds = ownSettlements.reduce((sum, item) => sum + Number(item.refund_amount || 0), 0);
    const fees = ownSettlements.reduce((sum, item) => sum + Number(item.fee_amount || 0), 0);
    return {
      marketplace,
      accounts: accounts.filter((item) => item.marketplace === marketplace).length,
      activeListings: ownListings.filter((item) => item.status === 'active').length,
      processingListings: ownListings.filter((item) =>
        ['submitting', 'processing'].includes(item.status),
      ).length,
      attentionListings: ownListings.filter(
        (item) => ['rejected', 'error'].includes(item.status) || item.drift_state !== 'none',
      ).length,
      orders: ownOrders.length,
      grossSales: String(gross),
      refunds: String(refunds),
      fees: String(fees),
      contribution: String(gross - refunds - fees),
      profitAvailable: analytics.profit_status === 'available',
      lowStock: inventory.filter(
        (item) => item.marketplace === marketplace && item.available_quantity <= 0,
      ).length,
      failures: ownListings.filter((item) => item.status === 'error' || item.status === 'rejected')
        .length,
      currency,
    };
  }
}
