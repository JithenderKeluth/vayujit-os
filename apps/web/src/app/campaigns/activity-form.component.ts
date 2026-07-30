import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import type { CampaignSelectorItem } from '@vayujit/shared';
import { CampaignService } from './campaign.service';

@Component({
  selector: 'app-campaign-activity-form',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <section class="page">
      <header class="page-header">
        <h1>Add Campaign activity</h1>
        <a [routerLink]="['/campaigns', campaignId]">Cancel</a>
      </header>
      <form [formGroup]="form" (ngSubmit)="save()">
        <label
          >Activity type<select formControlName="activity_type" required>
            <optgroup label="WordPress">
              <option value="wordpress_create_draft">Create draft</option>
              <option value="wordpress_publish">Publish</option>
              <option value="wordpress_update">Update</option>
              <option value="wordpress_move_to_draft">Move to draft</option>
            </optgroup>
            <optgroup label="Shopify">
              <option value="shopify_create_draft">Create draft</option>
              <option value="shopify_update_product">Update Product</option>
              <option value="shopify_activate_product">Activate Product</option>
              <option value="shopify_archive_product">Archive Product</option>
              <option value="shopify_reconcile">Reconcile</option>
            </optgroup>
            <optgroup label="Checkpoints">
              <option value="review_checkpoint">Review checkpoint</option>
              <option value="approval_checkpoint">Approval checkpoint</option>
            </optgroup>
          </select></label
        >
        <label>Name<input formControlName="name" required /></label>
        <label>Search Products<input type="search" (input)="searchProducts($event)" /></label>
        <label
          >Product<select formControlName="product_id" (change)="productChanged()">
            <option value="">Select Product</option>
            @for (item of products(); track item.id) {
              <option [value]="item.id" [disabled]="item.disabled">{{ item.label }}</option>
            }
          </select></label
        >
        <label
          >Search approved Artifacts<input type="search" (input)="searchArtifacts($event)"
        /></label>
        <label
          >Exact approved Artifact version<select formControlName="artifact_id">
            <option value="">Select exact version</option>
            @for (item of artifacts(); track item.id) {
              <option [value]="item.id" [disabled]="item.disabled">
                {{ item.label }} · {{ item.status }}
              </option>
            }
          </select></label
        >
        <label
          >Search destinations<input type="search" (input)="searchDestinations($event)"
        /></label>
        <label
          >Destination<select formControlName="destination_id">
            <option value="">Select destination</option>
            @for (item of destinations(); track item.id) {
              <option [value]="item.id" [disabled]="item.disabled">
                {{ item.label }} · {{ item.connector_key }}
              </option>
            }
          </select></label
        >
        <label>Sequence<input type="number" min="1" max="500" formControlName="sequence" /></label>
        <label>Date<input type="date" formControlName="scheduled_local_date" required /></label>
        <label>Time<input type="time" formControlName="scheduled_local_time" required /></label>
        <label
          >Timezone<input formControlName="timezone_name" placeholder="Campaign default"
        /></label>
        <label><input type="checkbox" formControlName="required" /> Required activity</label>
        <p>
          Publishing activities accept only exact approved Artifact versions and compatible
          destinations.
        </p>
        @if (error()) {
          <p class="error" role="alert">{{ error() }}</p>
        }
        <button class="button primary" [disabled]="form.invalid">Add activity</button>
      </form>
    </section>
  `,
  styleUrl: './campaigns.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ActivityFormComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(CampaignService);
  private readonly router = inject(Router);
  readonly campaignId = inject(ActivatedRoute).snapshot.paramMap.get('id')!;
  readonly error = signal('');
  readonly products = signal<CampaignSelectorItem[]>([]);
  readonly artifacts = signal<CampaignSelectorItem[]>([]);
  readonly destinations = signal<CampaignSelectorItem[]>([]);
  readonly form = this.fb.nonNullable.group({
    activity_type: ['wordpress_create_draft', Validators.required],
    name: ['', Validators.required],
    product_id: [''],
    artifact_id: [''],
    destination_id: [''],
    sequence: [1, Validators.required],
    scheduled_local_date: ['', Validators.required],
    scheduled_local_time: ['09:00', Validators.required],
    timezone_name: [''],
    required: [true],
    enabled: [true],
  });
  constructor() {
    void this.searchProducts();
    void this.searchDestinations();
  }
  async searchProducts(event?: Event): Promise<void> {
    const search = event ? (event.target as HTMLInputElement).value : '';
    this.products.set((await this.api.lookup('product', search)).items);
  }
  async productChanged(): Promise<void> {
    this.form.controls.artifact_id.setValue('');
    await this.searchArtifacts();
  }
  async searchArtifacts(event?: Event): Promise<void> {
    const search = event ? (event.target as HTMLInputElement).value : '';
    const productId = this.form.controls.product_id.value;
    this.artifacts.set(
      (await this.api.lookup('artifact', search, { productId: productId || undefined })).items,
    );
  }
  async searchDestinations(event?: Event): Promise<void> {
    const search = event ? (event.target as HTMLInputElement).value : '';
    const connectorKey = this.form.controls.activity_type.value.startsWith('wordpress')
      ? 'wordpress'
      : this.form.controls.activity_type.value.startsWith('shopify')
        ? 'shopify'
        : undefined;
    this.destinations.set((await this.api.lookup('destination', search, { connectorKey })).items);
  }
  async save(): Promise<void> {
    if (this.form.invalid) return;
    const raw = this.form.getRawValue();
    const checkpoint = raw.activity_type.endsWith('checkpoint');
    const data: Record<string, unknown> = { ...raw };
    if (checkpoint) {
      data['product_id'] = null;
      data['artifact_id'] = null;
      data['destination_id'] = null;
    }
    if (!raw.timezone_name) delete data['timezone_name'];
    try {
      await this.api.createActivity(this.campaignId, data);
      await this.router.navigate(['/campaigns', this.campaignId]);
    } catch {
      this.error.set(
        'Activity could not be added. Verify approval, ownership, connector, and timing.',
      );
    }
  }
}
