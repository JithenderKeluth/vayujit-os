import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type {
  BrandSummary,
  ProductSummary,
  PublishingDestinationSummary,
  WorkflowDetails,
  WorkflowStatus,
} from '@vayujit/shared';
import { BrandService } from '../brands/brand.service';
import { ProductService } from '../products/product.service';
import { PublishingService } from '../publishing/publishing.service';
import { WorkflowService } from './workflow.service';

@Component({
  selector: 'app-workflow-list',
  imports: [FormsModule, RouterLink],
  template: `<section class="wf-page">
    <header class="wf-header">
      <div>
        <h1>Workflows</h1>
        <p class="wf-muted">
          Durable orchestration from AI generation through approval and local mock publishing.
        </p>
      </div>
      <a class="wf-button" routerLink="/workflows/new">Create Workflow</a>
    </header>
    @if (!activeBrand()) {
      <div class="wf-empty">
        <h2>No active Brand</h2>
        <p>Activate a Brand to create a Workflow. Historical Workflows remain available.</p>
        <a routerLink="/brands">Manage Brands</a>
      </div>
    }
    <div class="wf-grid">
      <article class="wf-card">
        <h2>Total</h2>
        <p class="wf-stat">{{ total() }}</p>
      </article>
      <article class="wf-card">
        <h2>Waiting approval</h2>
        <p class="wf-stat">{{ waiting() }}</p>
      </article>
      <article class="wf-card">
        <h2>Completed</h2>
        <p class="wf-stat">{{ completed() }}</p>
      </article>
      <article class="wf-card">
        <h2>Failed / retryable</h2>
        <p class="wf-stat">{{ failed() }} / {{ retryableCount() }}</p>
      </article>
    </div>
    <form class="wf-card wf-filters" (ngSubmit)="load(1)">
      <label
        >Brand
        <select name="brand" [(ngModel)]="brandId">
          <option value="">All Brands</option>
          @for (item of brands(); track item.id) {
            <option [value]="item.id">{{ item.name }}</option>
          }
        </select></label
      ><label
        >Product
        <select name="product" [(ngModel)]="productId">
          <option value="">All Products</option>
          @for (item of products(); track item.id) {
            <option [value]="item.id">{{ item.name }}</option>
          }
        </select></label
      ><label
        >Destination
        <select name="destination" [(ngModel)]="destinationId">
          <option value="">All destinations</option>
          @for (item of destinations(); track item.id) {
            <option [value]="item.id">{{ item.name }}</option>
          }
        </select></label
      ><label
        >Status
        <select name="status" [(ngModel)]="status">
          <option value="">All statuses</option>
          @for (value of statuses; track value) {
            <option [value]="value">{{ value }}</option>
          }
        </select></label
      ><label
        >Step
        <select name="step" [(ngModel)]="currentStep">
          <option value="">Any step</option>
          <option value="generate_content">Generate content</option>
          <option value="wait_for_approval">Human approval</option>
          <option value="publish_content">Publish</option>
        </select></label
      ><label
        >Retryable
        <select name="retryable" [(ngModel)]="retryable">
          <option value="">Any</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select></label
      ><label>From <input type="date" name="from" [(ngModel)]="dateFrom" /></label
      ><label>To <input type="date" name="to" [(ngModel)]="dateTo" /></label><button>Apply</button
      ><button type="button" class="secondary" (click)="reset()">Reset</button>
    </form>
    @if (loading()) {
      <p role="status">Loading Workflows…</p>
    }
    @if (error()) {
      <p class="wf-error" role="alert">{{ error() }}</p>
    }
    @if (!loading() && !items().length) {
      <div class="wf-empty">
        <h2>No Workflows found</h2>
        <p>Create one or reset the filters.</p>
      </div>
    }
    @if (items().length) {
      <table class="wf-table">
        <thead>
          <tr>
            <th>Reference</th>
            <th>Brand / Product</th>
            <th>Destination</th>
            <th>Status / step</th>
            <th>Template</th>
            <th>Updated</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (item of items(); track item.id) {
            <tr>
              <td data-label="Reference">{{ item.id.slice(0, 8) }}</td>
              <td data-label="Brand / Product">
                {{ item.brand_name }}<br /><strong>{{ item.product_name }}</strong>
              </td>
              <td data-label="Destination">{{ item.destination_name }}</td>
              <td data-label="Status / step">
                <span class="wf-status" [class]="item.status">{{ item.status }}</span
                ><br />{{ item.current_step_key || 'Finished' }}<br />Retryable:
                {{ item.retryable ? 'Yes' : 'No' }}
              </td>
              <td data-label="Template">{{ item.template_name }} v{{ item.template_version }}</td>
              <td data-label="Updated">{{ item.updated_at }}</td>
              <td data-label="Action"><a [routerLink]="['/workflows', item.id]">View</a></td>
            </tr>
          }
        </tbody>
      </table>
    }
    <div class="wf-actions">
      <button class="secondary" [disabled]="page() <= 1" (click)="load(page() - 1)">Previous</button
      ><span>Page {{ page() }} of {{ pages() || 1 }}</span
      ><button class="secondary" [disabled]="page() >= pages()" (click)="load(page() + 1)">
        Next
      </button>
    </div>
  </section>`,
  styleUrl: './workflow.css',
})
export class WorkflowListComponent implements OnInit {
  private readonly api = inject(WorkflowService);
  private readonly brandApi = inject(BrandService);
  private readonly productApi = inject(ProductService);
  private readonly publishing = inject(PublishingService);
  readonly activeBrand = this.brandApi.activeBrand;
  readonly items = signal<WorkflowDetails[]>([]);
  readonly brands = signal<BrandSummary[]>([]);
  readonly products = signal<ProductSummary[]>([]);
  readonly destinations = signal<PublishingDestinationSummary[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly total = signal(0);
  readonly waiting = signal(0);
  readonly completed = signal(0);
  readonly failed = signal(0);
  readonly retryableCount = signal(0);
  readonly page = signal(1);
  readonly pages = signal(0);
  readonly statuses: WorkflowStatus[] = [
    'draft',
    'running',
    'waiting_for_approval',
    'completed',
    'failed',
    'cancelled',
  ];
  brandId = '';
  productId = '';
  destinationId = '';
  status: WorkflowStatus | '' = '';
  currentStep = '';
  retryable = '';
  dateFrom = '';
  dateTo = '';
  ngOnInit(): void {
    void this.init();
  }
  private async init(): Promise<void> {
    try {
      const [active, brands, products, destinations, all, waiting, completed, failed, retryable] =
        await Promise.all([
          this.brandApi.loadActive(),
          this.brandApi.list({ includeArchived: true, pageSize: 100 }),
          this.productApi.list({ allBrands: true, includeArchived: true, pageSize: 100 }),
          this.publishing.destinations({ pageSize: 100 }),
          this.api.list({ pageSize: 20 }),
          this.api.list({ status: 'waiting_for_approval', pageSize: 1 }),
          this.api.list({ status: 'completed', pageSize: 1 }),
          this.api.list({ status: 'failed', pageSize: 1 }),
          this.api.list({ status: 'failed', retryable: true, pageSize: 1 }),
        ]);
      this.brands.set(brands.items);
      this.products.set(products.items);
      this.destinations.set(destinations.items);
      this.brandId = active?.id ?? '';
      this.items.set(all.items);
      this.total.set(all.total);
      this.waiting.set(waiting.total);
      this.completed.set(completed.total);
      this.failed.set(failed.total);
      this.retryableCount.set(retryable.total);
      this.pages.set(all.pages);
    } catch (error) {
      this.error.set(WorkflowService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
  async load(page: number): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const result = await this.api.list({
        brandId: this.brandId,
        productId: this.productId,
        destinationId: this.destinationId,
        status: this.status,
        currentStep: this.currentStep,
        retryable: this.retryable === '' ? null : this.retryable === 'true',
        dateFrom: this.dateFrom ? `${this.dateFrom}T00:00:00Z` : undefined,
        dateTo: this.dateTo ? `${this.dateTo}T23:59:59Z` : undefined,
        page,
      });
      this.items.set(result.items);
      this.page.set(page);
      this.pages.set(result.pages);
    } catch (error) {
      this.error.set(WorkflowService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
  reset(): void {
    this.brandId =
      this.productId =
      this.destinationId =
      this.status =
      this.currentStep =
      this.retryable =
      this.dateFrom =
      this.dateTo =
        '';
    void this.load(1);
  }
}
