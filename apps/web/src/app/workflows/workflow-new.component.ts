import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import type {
  BrandSummary,
  ProductSummary,
  PublishingDestinationSummary,
  WorkflowTemplateSummary,
} from '@vayujit/shared';
import { BrandService } from '../brands/brand.service';
import { ProductService } from '../products/product.service';
import { PublishingService } from '../publishing/publishing.service';
import { WorkflowService } from './workflow.service';

@Component({
  selector: 'app-workflow-new',
  imports: [FormsModule, RouterLink],
  template: `<section class="wf-page">
    <header>
      <h1>Create Product Content Workflow</h1>
      <p class="wf-muted">
        This approved system Workflow generates content, pauses durably for your review, then
        publishes through the local mock connector.
      </p>
    </header>
    @if (loading()) {
      <p role="status">Loading eligible Products, destinations, and templates…</p>
    }
    @if (error()) {
      <p class="wf-error" role="alert">{{ error() }}</p>
    }
    <form class="wf-card wf-form" (ngSubmit)="createAndStart()">
      <label
        >1. Brand
        <select required name="brand" [(ngModel)]="brandId" (ngModelChange)="brandChanged()">
          <option value="">Select Brand</option>
          @for (item of brands(); track item.id) {
            <option [value]="item.id">{{ item.name }}</option>
          }
        </select></label
      >
      <label
        >2. Active Product
        <select required name="product" [(ngModel)]="productId">
          <option value="">Select Product</option>
          @for (item of eligibleProducts(); track item.id) {
            <option [value]="item.id">{{ item.name }}</option>
          }
        </select></label
      >
      <label
        >3. Compatible destination
        <select required name="destination" [(ngModel)]="destinationId">
          <option value="">Select destination</option>
          @for (item of eligibleDestinations(); track item.id) {
            <option [value]="item.id">
              {{ item.name }} · {{ item.brand_name || 'All Brands' }}
            </option>
          }
        </select></label
      >
      <label
        >4. System Workflow template
        <select required name="template" [(ngModel)]="templateId">
          @for (item of templates(); track item.id) {
            <option [value]="item.id">{{ item.name }} v{{ item.version }}</option>
          }
        </select></label
      >
      <label
        >5. Optional AI instructions
        <textarea
          name="instructions"
          rows="4"
          maxlength="2000"
          [(ngModel)]="instructions"
        ></textarea
        ><span class="wf-muted"
          >These instructions are bounded input and are not shown in audit history.</span
        ></label
      >
      @if (brandId && !eligibleProducts().length) {
        <div class="wf-empty">
          <p>No active Product is eligible for this Brand.</p>
          <a routerLink="/products/new">Create Product</a>
        </div>
      }
      @if (brandId && !eligibleDestinations().length) {
        <div class="wf-empty">
          <p>No active compatible destination exists.</p>
          <a routerLink="/publishing/destinations/new">Create destination</a>
        </div>
      }
      <article>
        <h2>Three durable steps</h2>
        <ol>
          <li><strong>Generate content</strong> using the existing AI service.</li>
          <li><strong>Wait for human approval</strong> without losing state on refresh.</li>
          <li>
            <strong>Publish approved content</strong> through existing Publishing idempotency.
          </li>
        </ol>
      </article>
      <label
        ><input type="checkbox" name="confirmed" [(ngModel)]="confirmed" /> Create and immediately
        start this Workflow.</label
      >
      <div class="wf-actions">
        <button [disabled]="busy() || !valid()">
          {{ busy() ? 'Starting…' : 'Create and start' }}</button
        ><a class="wf-button secondary" routerLink="/workflows">Cancel</a>
      </div>
    </form>
  </section>`,
  styleUrl: './workflow.css',
})
export class WorkflowNewComponent implements OnInit {
  private readonly api = inject(WorkflowService);
  private readonly brandApi = inject(BrandService);
  private readonly productApi = inject(ProductService);
  private readonly publishing = inject(PublishingService);
  private readonly router = inject(Router);
  readonly brands = signal<BrandSummary[]>([]);
  readonly products = signal<ProductSummary[]>([]);
  readonly destinations = signal<PublishingDestinationSummary[]>([]);
  readonly templates = signal<WorkflowTemplateSummary[]>([]);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  brandId = '';
  productId = '';
  destinationId = '';
  templateId = '';
  instructions = '';
  confirmed = false;
  readonly eligibleProducts = computed(() =>
    this.products().filter((item) => item.brand_id === this.brandId && item.status === 'active'),
  );
  readonly eligibleDestinations = computed(() =>
    this.destinations().filter(
      (item) => item.status === 'active' && (!item.brand_id || item.brand_id === this.brandId),
    ),
  );
  readonly valid = computed(() =>
    Boolean(
      this.brandId && this.productId && this.destinationId && this.templateId && this.confirmed,
    ),
  );
  ngOnInit(): void {
    void this.load();
  }
  private async load(): Promise<void> {
    try {
      const [brands, active, products, destinations, templates] = await Promise.all([
        this.brandApi.list({ pageSize: 100 }),
        this.brandApi.loadActive(),
        this.productApi.list({ allBrands: true, pageSize: 100 }),
        this.publishing.destinations({ status: 'active', pageSize: 100 }),
        this.api.templates(),
      ]);
      this.brands.set(brands.items);
      this.products.set(products.items);
      this.destinations.set(destinations.items);
      this.templates.set(templates);
      this.brandId = active?.id ?? '';
      this.templateId = templates.find((item) => item.is_default)?.id ?? templates[0]?.id ?? '';
    } catch (error) {
      this.error.set(WorkflowService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
  brandChanged(): void {
    this.productId = '';
    this.destinationId = '';
    this.confirmed = false;
  }
  async createAndStart(): Promise<void> {
    if (!this.valid() || this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    try {
      const created = await this.api.create({
        product_id: this.productId,
        destination_id: this.destinationId,
        workflow_template_id: this.templateId,
        additional_instructions: this.instructions || null,
      });
      const started = await this.api.start(created.id);
      await this.router.navigate(['/workflows', started.id]);
    } catch (error) {
      this.error.set(WorkflowService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
}
