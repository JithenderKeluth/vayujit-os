import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-marketplace-home',
  imports: [RouterLink],
  template: `<section class="marketplace-page">
    <header>
      <h1>Marketplace</h1>
      <p>Commerce operations for listings, inventory, orders, and settlements.</p>
    </header>
    <div class="marketplace-grid">
      <a routerLink="/marketplaces/overview"
        ><h2>Overview</h2>
        <p>Connected accounts and items needing attention.</p></a
      >
      <a routerLink="/marketplaces/accounts"
        ><h2>Accounts</h2>
        <p>Connect and validate marketplace accounts.</p></a
      >
      <a routerLink="/marketplaces/listings"
        ><h2>Listings</h2>
        <p>Map Products to normalized marketplace listings.</p></a
      >
      <a routerLink="/marketplaces/inventory"
        ><h2>Inventory</h2>
        <p>Review explicit inventory snapshots.</p></a
      >
      <a routerLink="/marketplaces/orders"
        ><h2>Orders</h2>
        <p>Masked buyer-safe order snapshots.</p></a
      >
      <a routerLink="/marketplaces/settlements"
        ><h2>Settlements</h2>
        <p>Gross sales, fees, refunds, and net amounts.</p></a
      >
      <a routerLink="/marketplaces/analytics"
        ><h2>Analytics</h2>
        <p>Commerce summary read models.</p></a
      >
    </div>
  </section>`,
  styleUrl: './marketplaces.css',
})
export class MarketplaceHomeComponent {}
