import { PageHeaderComponent } from '../shared/page-header.component';
import { EmptyStateComponent, ErrorStateComponent } from '../shared/state-components';
import { TitleCasePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  MarketplaceAccount,
  MarketplaceCapability,
  MarketplaceImportJob,
  MarketplaceReconciliation,
  MarketplaceService,
} from './marketplace.service';

@Component({
  selector: 'app-marketplace-accounts',
  imports: [FormsModule, TitleCasePipe, PageHeaderComponent, EmptyStateComponent, ErrorStateComponent],
  template: `<section class="marketplace-page">
    <app-page-header
      eyebrow="Sell / marketplaces"
      title="Marketplace accounts"
      description="Credentials are write-only and never returned by the API."
    />
    <div class="marketplace-toolbar">
      <p class="marketplace-help">Use synthetic imports to review local evidence. External provider calls stay blocked.</p>
      <button type="button" (click)="load()" [disabled]="loading()">Refresh</button>
    </div>
    <section class="marketplace-callout" aria-labelledby="connectivity-heading">
      <h2 id="connectivity-heading">Read-only connectivity center</h2>
      <p>
        Amazon India and Flipkart imports are currently available in deterministic synthetic mode.
        Provider contracts and seller permissions are not verified here, and no external writes are
        possible. Review each import result before reconciling canonical records.
      </p>
    </section>
    <section class="marketplace-card" aria-labelledby="capabilities-heading">
      <h2 id="capabilities-heading">Provider capabilities</h2>
      @if (capabilities().length) {
        <div class="marketplace-capabilities">
          @for (capability of capabilities(); track capability.provider) {
            <article>
              <h3>{{ capability.provider | titlecase }}</h3>
              <p><strong>Synthetic mode:</strong> {{ capability.synthetic_fixture ? 'Available' : 'Unavailable' }}</p>
              <p><strong>Provider authorization:</strong> {{ capability.official_contract }}</p>
              <p><strong>Live read-only:</strong> {{ capability.live_read_only }} · <strong>Live write:</strong> {{ capability.live_write }}</p>
              <small>Operations: {{ capability.supported_operations.join(', ') }}</small>
            </article>
          }
        </div>
      } @else if (loading()) {
        <p role="status">Loading provider capabilities…</p>
      } @else {
        <p class="marketplace-empty">Provider capability information is unavailable. Refresh to retry.</p>
      }
    </section>
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
      <app-error-state
        title="Marketplace accounts are unavailable"
        [message]="error()"
        retryLabel="Retry"
        (retry)="load()"
      />
    }
    @if (loading()) {
      <p role="status" aria-live="polite">Loading marketplace accounts…</p>
    }
    @if (!accounts().length && !loading()) {
      <app-empty-state
        title="No marketplace accounts yet"
        message="Add a marketplace account when a channel is ready."
      />
    }
    <div class="marketplace-table" role="region" tabindex="0" aria-label="Marketplace accounts">
      <table>
        <thead>
          <tr>
            <th>Marketplace</th>
            <th>Name</th>
            <th>Validation</th>
            <th>Connection</th>
            <th>Transport</th>
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
              <td>
                <span class="marketplace-status">{{ account.connection_state || 'UNVERIFIED' }}</span>
                <small>{{ account.permission_state || 'UNVERIFIED' }}</small>
              </td>
              <td>{{ account.transport_mode || 'SYNTHETIC' }}</td>
              <td>{{ account.enabled ? 'Enabled' : 'Disabled' }}</td>
              <td>
                <button type="button" (click)="validate(account)">Validate</button
                ><button type="button" (click)="toggle(account)">
                  {{ account.enabled ? 'Disable' : 'Enable' }}
                </button>
                <div class="marketplace-actions" aria-label="Read-only imports">
                  @for (operation of operations; track operation) {
                    <button
                      type="button"
                      [attr.aria-label]="'Import ' + operation + ' for ' + account.display_name"
                      [disabled]="syncing() === account.id + ':' + operation"
                      (click)="runImport(account, operation)"
                    >
                      {{ syncing() === account.id + ':' + operation ? 'Importing…' : 'Import ' + operation }}
                    </button>
                  }
                </div>
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
    @for (account of accounts(); track account.id) {
      <section class="marketplace-card" [attr.aria-labelledby]="'sync-' + account.id" [attr.aria-label]="'Import history for ' + account.display_name + ' (' + account.id + ')'">
        <h2 [id]="'sync-' + account.id">{{ account.display_name }} import history</h2>
        @if (accountJobs(account.id).length) {
          <div class="marketplace-table" role="region" tabindex="0" [attr.aria-label]="'Scrollable import jobs for ' + account.display_name">
            <table>
              <caption>Durable read-only import jobs</caption>
              <thead><tr><th>Operation</th><th>Status</th><th>Records</th><th>Evidence</th><th>Completed</th></tr></thead>
              <tbody>
                @for (job of accountJobs(account.id); track job.id) {
                  <tr>
                    <td>{{ job.operation }}</td>
                    <td>{{ job.status }}</td>
                    <td>{{ job.records_imported }} imported · {{ job.records_reused }} reused</td>
                    <td>{{ job.mode }} · external writes {{ job.provenance_json['external_writes'] ? 'enabled' : 'off' }}</td>
                    <td>{{ job.completed_at || 'Not completed' }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
          @if (reconciliation(account.id); as summary) {
            <dl class="marketplace-stats" aria-label="Import and canonical record status">
              <div><dt>Catalog records</dt><dd>{{ summary.canonical_counts['listings'] || 0 }} <small>{{ summary.freshness['catalog'] || 'NOT_IMPORTED' }}</small></dd></div>
              <div><dt>Orders</dt><dd>{{ summary.canonical_counts['orders'] || 0 }} <small>{{ summary.freshness['orders'] || 'NOT_IMPORTED' }}</small></dd></div>
              <div><dt>Inventory rows</dt><dd>{{ summary.canonical_counts['inventory'] || 0 }} <small>{{ summary.freshness['inventory'] || 'NOT_IMPORTED' }}</small></dd></div>
              <div><dt>Settlements</dt><dd>{{ summary.canonical_counts['settlements'] || 0 }} <small>{{ summary.freshness['financial'] || 'NOT_IMPORTED' }}</small></dd></div>
            </dl>
            <p class="marketplace-callout">
              {{ summary.next_action }} Stale operations: {{ summary.stale_operations.join(', ') || 'none' }}.
              Canonical records are never overwritten automatically.
            </p>
            @if (summary.exceptions.length) {
              <div class="marketplace-error" role="alert">
                <strong>Import exceptions require HUMAN review.</strong>
                <ul>@for (exception of summary.exceptions; track exception) { <li>{{ exception }}</li> }</ul>
              </div>
            }
          }
        } @else {
          <p class="marketplace-empty">No imports yet. Start a synthetic read-only import from the account row.</p>
        }
      </section>
    }
    @if (message()) {
      <p class="marketplace-success" role="status" aria-live="polite">{{ message() }}</p>
    }
  </section>`,
  styleUrl: './marketplaces.css',
})
export class MarketplaceAccountsComponent {
  private readonly service = inject(MarketplaceService);
  readonly accounts = signal<MarketplaceAccount[]>([]);
  readonly capabilities = signal<MarketplaceCapability[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly message = signal('');
  readonly syncing = signal('');
  readonly operations = ['catalog', 'orders', 'inventory', 'financial'] as const;
  readonly jobs = signal<Record<string, MarketplaceImportJob[]>>({});
  readonly summaries = signal<Record<string, MarketplaceReconciliation>>({});
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
    this.loading.set(true);
    this.error.set('');
    try {
      const [capabilityResponse, accounts] = await Promise.all([
        this.service.capabilities(),
        this.service.accounts(),
      ]);
      this.capabilities.set(capabilityResponse.providers);
      this.accounts.set(accounts);
      const entries = await Promise.all(
        accounts.map(async (account) => {
          const [jobs, summary] = await Promise.all([
            this.service.importJobs(account.id),
            this.service.reconciliation(account.id),
          ]);
          return [account.id, jobs, summary] as const;
        }),
      );
      this.jobs.set(Object.fromEntries(entries.map(([id, jobs]) => [id, jobs])));
      this.summaries.set(Object.fromEntries(entries.map(([id, , summary]) => [id, summary])));
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    } finally {
      this.loading.set(false);
    }
  }
  accountJobs(accountId: string): MarketplaceImportJob[] {
    return this.jobs()[accountId] || [];
  }
  reconciliation(accountId: string): MarketplaceReconciliation | null {
    return this.summaries()[accountId] || null;
  }
  async runImport(
    account: MarketplaceAccount,
    operation: (typeof this.operations)[number],
  ): Promise<void> {
    const key = `${account.id}:${operation}`;
    this.syncing.set(key);
    this.message.set('');
    try {
      const job = await this.service.startImport(account.id, operation, `ui-${operation}-${Date.now()}`);
      this.jobs.update((value) => ({ ...value, [account.id]: [job, ...(value[account.id] || [])] }));
      this.message.set(`${operation} import completed in SYNTHETIC read-only mode.`);
      const summary = await this.service.reconciliation(account.id);
      this.summaries.update((value) => ({ ...value, [account.id]: summary }));
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    } finally {
      this.syncing.set('');
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
