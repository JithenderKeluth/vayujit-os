import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { PageHeaderComponent } from '../shared/page-header.component';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import {
  ChannelSkuMapping,
  InventoryAdjustment,
  InventoryItem,
  InventoryMovement,
  MarketplaceAccount,
  MarketplaceService,
  ReconciliationSummary,
} from './marketplace.service';

@Component({
  selector: 'app-unified-inventory',
  imports: [
    DatePipe,
    PageHeaderComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    FormsModule,
    RouterLink,
  ],
  template: `
    <section class="marketplace-page" aria-label="Unified inventory">
      <app-page-header
        eyebrow="Sell · operations"
        title="Unified inventory"
        description="Canonical stock, reservations, damaged units, and available-to-promise by location."
        ><a
          page-header-actions
          routerLink="/marketplaces/inventory/opening"
          [queryParams]="{ sku: skuFilter || null, low_stock: lowStockOnly || null }"
          >Add opening stock</a
        ></app-page-header
      >
      <div class="marketplace-callout" role="note">
        <strong>One source of truth.</strong> Marketplace balances are projections. Use a
        human-reviewed adjustment for receipts, damage, or reconciliation; this workspace never
        writes to a channel.
      </div>
      @if (error()) {
        <app-error-state
          title="Inventory is unavailable"
          [message]="error()"
          retryLabel="Retry"
          (retry)="load()"
        />
      }
      @if (summary(); as value) {
        <dl class="marketplace-stats" aria-label="Inventory summary">
          <div>
            <dt>Items</dt>
            <dd>{{ value.inventory_items }}</dd>
          </div>
          <div>
            <dt>Low stock</dt>
            <dd>{{ value.low_stock_items }}</dd>
          </div>
          <div>
            <dt>Out of stock</dt>
            <dd>{{ value.out_of_stock_items }}</dd>
          </div>
          <div>
            <dt>Active reservations</dt>
            <dd>{{ value.active_reservations }}</dd>
          </div>
        </dl>
      }
      <div class="marketplace-form" role="group" aria-label="Inventory filters">
        <label>SKU search <input [(ngModel)]="skuFilter" (keyup.enter)="load()" /></label
        ><label class="checkbox-label"
          ><input type="checkbox" [(ngModel)]="lowStockOnly" (change)="load()" /> Low stock
          only</label
        ><button type="button" (click)="load()">Refresh</button>
      </div>
      @if (loading()) {
        <app-loading-state message="Loading canonical inventory..." />
      }
      @if (!loading() && !error() && !items().length) {
        @if (skuFilter.trim() || lowStockOnly) {
          <app-empty-state
            title="No matching inventory"
            message="Change the SKU search or clear Low stock only to see other balances."
          />
        } @else {
          <app-empty-state
            title="No canonical inventory yet"
            message="Count the physical units you own, then use Add opening stock. Later receipts and corrections use Adjust stock."
          />
        }
      }
      @if (items().length) {
        <div class="marketplace-table" tabindex="0">
          <table>
            <caption>
              Canonical inventory balances
            </caption>
            <thead>
              <tr>
                <th scope="col">SKU</th>
                <th scope="col">Location</th>
                <th scope="col">On hand</th>
                <th scope="col">Reserved</th>
                <th scope="col">Damaged</th>
                <th scope="col">Available to promise</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              @for (item of items(); track item.id) {
                <tr>
                  <th scope="row">{{ item.internal_sku }}</th>
                  <td>{{ item.location_code }}</td>
                  <td>{{ item.on_hand_quantity }} {{ item.unit }}</td>
                  <td>{{ item.reserved_quantity }}</td>
                  <td>{{ item.damaged_quantity }}</td>
                  <td>
                    <strong>{{ item.available_to_promise }}</strong>
                  </td>
                  <td class="marketplace-actions">
                    <button type="button" (click)="selectItem(item)">
                      {{
                        selectedItem()?.id === item.id ? 'Close adjustment' : 'Adjust stock'
                      }}</button
                    ><button type="button" (click)="toggleLedger(item)">
                      {{ ledgerItem()?.id === item.id ? 'Hide ledger' : 'View ledger' }}</button
                    ><button type="button" (click)="toggleMapping(item)">
                      {{ mappingItem()?.id === item.id ? 'Hide mapping' : 'Map channel SKU' }}
                    </button>
                  </td>
                </tr>
                @if (selectedItem()?.id === item.id) {
                  <tr>
                    <td colspan="7">
                      <form
                        class="marketplace-form"
                        (ngSubmit)="adjust()"
                        aria-label="Human stock adjustment"
                      >
                        <span
                          ><strong>Human review required.</strong> Current version
                          {{ item.version }}; available {{ item.available_to_promise }}.</span
                        ><label
                          >Delta
                          <input type="number" name="delta" [(ngModel)]="delta" required /></label
                        ><label>Reason <input name="reason" [(ngModel)]="reason" required /></label
                        ><button type="submit" [disabled]="saving()">
                          {{ saving() ? 'Saving...' : 'Record adjustment' }}
                        </button>
                        @if (formError()) {
                          <span class="marketplace-error" role="alert">{{ formError() }}</span>
                        }
                      </form>
                    </td>
                  </tr>
                }
                @if (ledgerItem()?.id === item.id) {
                  <tr>
                    <td colspan="7">
                      <section class="marketplace-card" aria-label="Inventory movement ledger">
                        <h2>Movement ledger for {{ item.internal_sku }}</h2>
                        @if (ledgerLoading()) {
                          <app-loading-state message="Loading movement ledger..." />
                        }
                        @if (!ledgerLoading() && !ledger().length) {
                          <p>No movements recorded yet.</p>
                        }
                        @if (ledger().length) {
                          <div class="marketplace-table" tabindex="0">
                            <table>
                              <caption>
                                Append-only movements
                              </caption>
                              <thead>
                                <tr>
                                  <th scope="col">When</th>
                                  <th scope="col">Type</th>
                                  <th scope="col">Quantity</th>
                                  <th scope="col">Balance</th>
                                  <th scope="col">Reason</th>
                                </tr>
                              </thead>
                              <tbody>
                                @for (movement of ledger(); track movement.id) {
                                  <tr>
                                    <td>{{ movement.created_at | date: 'medium' }}</td>
                                    <td>{{ movement.movement_type }}</td>
                                    <td>{{ movement.quantity }}</td>
                                    <td>
                                      {{ movement.after_on_hand }} on hand /
                                      {{ movement.after_reserved }} reserved
                                    </td>
                                    <td>{{ movement.reason }}</td>
                                  </tr>
                                }
                              </tbody>
                            </table>
                          </div>
                        }
                        @if (ledgerError()) {
                          <p class="marketplace-error" role="alert">{{ ledgerError() }}</p>
                        }
                      </section>
                    </td>
                  </tr>
                }
                @if (mappingItem()?.id === item.id) {
                  <tr>
                    <td colspan="7">
                      <form
                        class="marketplace-card"
                        (ngSubmit)="mapSku()"
                        aria-label="Map channel SKU"
                      >
                        <h3>Map a channel SKU for {{ item.internal_sku }}</h3>
                        <p>Mapping is owner-scoped and does not contact a marketplace.</p>
                        <div class="workspace-grid-form">
                          <label
                            >Marketplace account<select
                              name="account"
                              [(ngModel)]="mappingAccountId"
                              required
                            >
                              <option value="">Select an account</option>
                              @for (account of accounts(); track account.id) {
                                <option [value]="account.id">
                                  {{ account.marketplace }} · {{ account.display_name }}
                                </option>
                              }
                            </select></label
                          ><label
                            >External SKU<input
                              name="externalSku"
                              [(ngModel)]="externalSku"
                              required
                              maxlength="160"
                          /></label>
                        </div>
                        <div class="marketplace-actions">
                          <button
                            type="submit"
                            [disabled]="mappingSaving() || !mappingAccountId || !externalSku.trim()"
                          >
                            {{ mappingSaving() ? 'Saving...' : 'Save mapping' }}</button
                          ><button type="button" (click)="mappingItem.set(null)">Cancel</button>
                        </div>
                        @if (mappingError()) {
                          <p class="marketplace-error" role="alert">{{ mappingError() }}</p>
                        }
                        @if (mappingSuccess()) {
                          <p class="marketplace-success" role="status">{{ mappingSuccess() }}</p>
                        }
                      </form>
                    </td>
                  </tr>
                }
              }
            </tbody>
          </table>
        </div>
      }
      @if (summary()?.next_actions?.length) {
        <div class="marketplace-approval" role="note" aria-label="Next actions">
          <strong>Next actions</strong>
          <ul>
            @for (action of summary()!.next_actions; track action) {
              <li>{{ action }}</li>
            }
          </ul>
        </div>
      }
    </section>
  `,
  styleUrl: './marketplaces.css',
  styles: '.marketplace-table caption { text-align: left; }',
})
export class UnifiedInventoryComponent {
  private readonly service = inject(MarketplaceService);
  private readonly route = inject(ActivatedRoute);
  readonly items = signal<InventoryItem[]>([]);
  readonly summary = signal<ReconciliationSummary | null>(null);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly formError = signal('');
  readonly selectedItem = signal<InventoryItem | null>(null);
  readonly accounts = signal<MarketplaceAccount[]>([]);
  readonly mappings = signal<ChannelSkuMapping[]>([]);
  readonly ledgerItem = signal<InventoryItem | null>(null);
  readonly mappingItem = signal<InventoryItem | null>(null);
  readonly ledger = signal<InventoryMovement[]>([]);
  readonly ledgerLoading = signal(false);
  readonly ledgerError = signal('');
  readonly mappingSaving = signal(false);
  readonly mappingError = signal('');
  readonly mappingSuccess = signal('');
  skuFilter = this.route.snapshot.queryParamMap.get('sku') || '';
  lowStockOnly = this.route.snapshot.queryParamMap.get('low_stock') === 'true';
  delta = 0;
  reason = '';
  mappingAccountId = '';
  externalSku = '';

  constructor() {
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const [items, summary, accounts, mappings] = await Promise.all([
        this.service.canonicalInventory({
          sku: this.skuFilter || undefined,
          lowStock: this.lowStockOnly,
        }),
        this.service.reconciliationSummary(),
        this.service.accounts(),
        this.service.inventoryMappings(),
      ]);
      this.items.set(items);
      this.summary.set(summary);
      this.accounts.set(accounts);
      this.mappings.set(mappings);
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    } finally {
      this.loading.set(false);
    }
  }
  selectItem(item: InventoryItem): void {
    this.formError.set('');
    this.selectedItem.set(this.selectedItem()?.id === item.id ? null : item);
    this.delta = 0;
    this.reason = '';
  }
  async adjust(): Promise<void> {
    const item = this.selectedItem();
    if (!item || !this.delta || !this.reason.trim()) return;
    this.saving.set(true);
    this.formError.set('');
    const payload: InventoryAdjustment = {
      delta: Number(this.delta),
      reason: this.reason.trim(),
      expected_version: item.version,
      idempotency_key: `ui-adjust-${item.id}-${Date.now()}`,
    };
    try {
      await this.service.adjustInventory(item.id, payload);
      this.selectedItem.set(null);
      await this.load();
    } catch {
      this.formError.set(
        'The stock changed or the adjustment was rejected. Refresh and review the current balance.',
      );
    } finally {
      this.saving.set(false);
    }
  }
  async toggleLedger(item: InventoryItem): Promise<void> {
    this.ledgerError.set('');
    if (this.ledgerItem()?.id === item.id) {
      this.ledgerItem.set(null);
      return;
    }
    this.ledgerItem.set(item);
    this.ledgerLoading.set(true);
    try {
      this.ledger.set(await this.service.inventoryLedger(item.id));
    } catch {
      this.ledgerError.set('The movement ledger could not be loaded. Retry after refreshing.');
    } finally {
      this.ledgerLoading.set(false);
    }
  }
  toggleMapping(item: InventoryItem): void {
    this.mappingError.set('');
    this.mappingSuccess.set('');
    this.mappingItem.set(this.mappingItem()?.id === item.id ? null : item);
    this.mappingAccountId = '';
    this.externalSku = '';
  }
  async mapSku(): Promise<void> {
    const item = this.mappingItem();
    if (!item || !this.mappingAccountId || !this.externalSku.trim()) return;
    this.mappingSaving.set(true);
    this.mappingError.set('');
    this.mappingSuccess.set('');
    try {
      await this.service.createInventoryMapping({
        account_id: this.mappingAccountId,
        inventory_item_id: item.id,
        external_sku: this.externalSku.trim(),
        idempotency_key: `ui-map-${item.id}-${this.mappingAccountId}-${this.externalSku.trim()}`,
      });
      this.mappingSuccess.set(
        'Channel SKU mapped. Provider balances remain read-only projections.',
      );
      this.mappings.set(await this.service.inventoryMappings());
    } catch {
      this.mappingError.set(
        'The SKU mapping was rejected. Verify the account and external SKU, then retry.',
      );
    } finally {
      this.mappingSaving.set(false);
    }
  }
}
