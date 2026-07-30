import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
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
        <label>Product ID<input formControlName="product_id" /></label>
        <label>Approved Artifact ID<input formControlName="artifact_id" /></label>
        <label>Destination ID<input formControlName="destination_id" /></label>
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
