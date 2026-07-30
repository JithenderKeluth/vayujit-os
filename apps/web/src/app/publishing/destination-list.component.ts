import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { BrandSummary, PublishingDestinationSummary } from '@vayujit/shared';
import { BrandService } from '../brands/brand.service';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-destination-list',
  imports: [FormsModule, RouterLink],
  template: ` <section class="pub-page">
    <header class="pub-header">
      <div>
        <h1>Publishing destinations</h1>
        <p class="pub-muted">
          Local targets describe where the mock connector should record a publication.
        </p>
      </div>
      <a class="pub-button" routerLink="/publishing/destinations/new">Create destination</a>
    </header>
    <form class="pub-card pub-filters" (ngSubmit)="load(1)">
      <label>Search <input name="search" [(ngModel)]="search" /></label
      ><label
        >Brand
        <select name="brand" [(ngModel)]="brandId">
          <option value="">All Brands</option>
          @for (brand of brands(); track brand.id) {
            <option [value]="brand.id">{{ brand.name }}</option>
          }
        </select></label
      ><label
        >Status
        <select name="status" [(ngModel)]="status">
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="disabled">Disabled</option>
        </select></label
      ><label
        >Connector
        <select name="connector" [(ngModel)]="connectorKey">
          <option value="">All connectors</option>
          <option value="mock_publisher_v1">Local mock</option>
        </select></label
      ><button>Apply filters</button>
    </form>
    @if (loading()) {
      <p role="status">Loading destinations…</p>
    }
    @if (error()) {
      <p class="pub-error" role="alert">{{ error() }}</p>
    }
    @if (!loading() && !items().length) {
      <div class="pub-empty">
        <h2>No destinations found</h2>
        <p>Create a local mock destination or adjust the filters.</p>
      </div>
    }
    @if (items().length) {
      <table class="pub-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Connector</th>
            <th>Brand scope</th>
            <th>Channel / prefix</th>
            <th>Status</th>
            <th>Updated</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          @for (item of items(); track item.id) {
            <tr [class.pub-disabled]="item.status === 'disabled'">
              <td data-label="Name">{{ item.name }}</td>
              <td data-label="Connector">Local mock</td>
              <td data-label="Brand scope">{{ item.brand_name || 'All Brands' }}</td>
              <td data-label="Channel / prefix">
                {{
                  item.connector_key === 'wordpress'
                    ? 'WordPress / ' + $any(item.configuration).post_status
                    : $any(item.configuration).channel_name +
                      ' / ' +
                      $any(item.configuration).publication_prefix
                }}
              </td>
              <td data-label="Status">
                <span class="pub-status" [class]="item.status">{{ item.status }}</span>
              </td>
              <td data-label="Updated">{{ item.updated_at.slice(0, 10) }}</td>
              <td data-label="Actions">
                <div class="pub-actions">
                  <a [routerLink]="['/publishing/destinations', item.id]">View</a
                  ><a [routerLink]="['/publishing/destinations', item.id, 'edit']">Edit</a>
                  @if (item.status === 'active') {
                    <button class="danger" (click)="disable(item)">Disable</button>
                  } @else {
                    <button (click)="enable(item)">Enable</button>
                  }
                </div>
              </td>
            </tr>
          }
        </tbody>
      </table>
    }
    <div class="pub-actions">
      <button class="secondary" [disabled]="page() <= 1" (click)="load(page() - 1)">Previous</button
      ><span>Page {{ page() }} of {{ pages() || 1 }}</span
      ><button class="secondary" [disabled]="page() >= pages()" (click)="load(page() + 1)">
        Next
      </button>
    </div>
  </section>`,
  styleUrl: './publishing.css',
})
export class DestinationListComponent implements OnInit {
  private readonly api = inject(PublishingService);
  private readonly brandApi = inject(BrandService);
  readonly items = signal<PublishingDestinationSummary[]>([]);
  readonly brands = signal<BrandSummary[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly page = signal(1);
  readonly pages = signal(0);
  search = '';
  brandId = '';
  status = '';
  connectorKey = '';
  ngOnInit(): void {
    void this.init();
  }
  private async init() {
    const [brands, active] = await Promise.all([
      this.brandApi.list({ includeArchived: false, pageSize: 100 }),
      this.brandApi.loadActive(),
    ]);
    this.brands.set(brands.items);
    this.brandId = active?.id ?? '';
    await this.load(1);
  }
  async load(page: number) {
    this.loading.set(true);
    this.error.set('');
    try {
      const result = await this.api.destinations({
        search: this.search,
        brandId: this.brandId,
        connectorKey: this.connectorKey,
        status: this.status,
        page,
      });
      this.items.set(result.items);
      this.page.set(page);
      this.pages.set(result.pages);
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
  async disable(item: PublishingDestinationSummary) {
    if (!confirm(`Disable ${item.name}? New publications will be blocked.`)) return;
    try {
      await this.api.destinationStatus(item.id, 'disable');
      await this.load(this.page());
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    }
  }
  async enable(item: PublishingDestinationSummary) {
    try {
      await this.api.destinationStatus(item.id, 'enable');
      await this.load(this.page());
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    }
  }
}
