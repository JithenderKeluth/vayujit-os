import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MarketplaceAccount, MarketplaceService } from './marketplace.service';

@Component({
  selector: 'app-marketplace-accounts',
  imports: [FormsModule],
  template: `<section class="marketplace-page">
    <header>
      <h1>Marketplace accounts</h1>
      <p>Credentials are write-only and never returned by the API.</p>
    </header>
    <form class="marketplace-form" (ngSubmit)="add()">
      <label
        >Marketplace<select name="marketplace" [(ngModel)]="draft.marketplace">
          <option>amazon</option>
          <option>flipkart</option>
          <option>meesho</option>
          <option>shopify</option>
        </select></label
      ><label>Display name<input name="display" [(ngModel)]="draft.display_name" required /></label
      ><label
        >Seller/account ID<input
          name="seller"
          [(ngModel)]="draft.seller_account_id"
          required /></label
      ><label
        >Credential<input
          type="password"
          name="credential"
          [(ngModel)]="draft.credentials.token"
          placeholder="Write only" /></label
      ><button type="submit">Add account</button>
    </form>
    @if (error()) {
      <p class="marketplace-error">{{ error() }}</p>
    }
    @if (!accounts().length && !loading()) {
      <p class="marketplace-empty">No marketplace accounts yet.</p>
    }
    <div class="marketplace-table">
      <table>
        <thead>
          <tr>
            <th>Marketplace</th>
            <th>Name</th>
            <th>Validation</th>
            <th>Enabled</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          @for (account of accounts(); track account.id) {
            <tr>
              <td>{{ account.marketplace }}</td>
              <td>{{ account.display_name }}</td>
              <td>{{ account.validation_status }}</td>
              <td>{{ account.enabled ? 'Enabled' : 'Disabled' }}</td>
              <td>
                <button type="button" (click)="validate(account)">Validate</button
                ><button type="button" (click)="toggle(account)">
                  {{ account.enabled ? 'Disable' : 'Enable' }}
                </button>
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  </section>`,
  styleUrl: './marketplaces.css',
})
export class MarketplaceAccountsComponent {
  private readonly service = inject(MarketplaceService);
  readonly accounts = signal<MarketplaceAccount[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly draft = {
    marketplace: 'amazon',
    display_name: '',
    seller_account_id: '',
    credentials: { token: '' },
  };
  constructor() {
    void this.load();
  }
  async load(): Promise<void> {
    try {
      this.accounts.set(await this.service.accounts());
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    } finally {
      this.loading.set(false);
    }
  }
  async add(): Promise<void> {
    try {
      await this.service.createAccount(this.draft);
      this.draft.display_name = '';
      this.draft.seller_account_id = '';
      this.draft.credentials.token = '';
      await this.load();
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    }
  }
  async validate(account: MarketplaceAccount): Promise<void> {
    try {
      const value = await this.service.validateAccount(account.id);
      this.accounts.update((items) => items.map((item) => (item.id === value.id ? value : item)));
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    }
  }
  async toggle(account: MarketplaceAccount): Promise<void> {
    try {
      const value = account.enabled
        ? await this.service.disableAccount(account.id)
        : await this.service.enableAccount(account.id);
      this.accounts.update((items) => items.map((item) => (item.id === value.id ? value : item)));
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    }
  }
}
