import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { BrandService } from '../brands/brand.service';
import type { BrandSummary } from '@vayujit/shared';
import { CampaignService } from './campaign.service';

@Component({
  selector: 'app-campaign-form',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <section class="page">
      <header class="page-header">
        <h1>Create Campaign</h1>
        <a routerLink="/campaigns">Cancel</a>
      </header>
      <form [formGroup]="form" (ngSubmit)="save()">
        <label
          >Brand<select formControlName="brand_id" required>
            <option value="">Select Brand</option>
            @for (brand of brands(); track brand.id) {
              <option [value]="brand.id">{{ brand.name }}</option>
            }
          </select></label
        >
        <label>Name<input formControlName="name" required maxlength="160" /></label>
        <label>Objective<textarea formControlName="objective" maxlength="500"></textarea></label>
        <label
          >Timezone<input formControlName="timezone_name" required aria-describedby="timezone-help"
        /></label>
        <small id="timezone-help">Use an IANA timezone such as Asia/Kolkata.</small>
        <label
          >Starts<input type="datetime-local" formControlName="local_start_at" required
        /></label>
        <label>Ends<input type="datetime-local" formControlName="local_end_at" required /></label>
        <label
          >Approval policy<select formControlName="approval_policy">
            <option value="approve_before_scheduling">Approve before scheduling</option>
            <option value="all_artifacts_preapproved">All Artifacts preapproved</option>
            <option value="approve_before_execution">Approve before execution</option>
            <option value="manual_campaign_release">Manual Campaign release</option>
          </select></label
        >
        <label
          >Time window<select formControlName="scheduling_policy">
            <option value="strict_window">Strict window</option>
            <option value="warn_outside_window">Warn outside window</option>
            <option value="allow_with_confirmation">Allow with confirmation</option>
          </select></label
        >
        @if (error()) {
          <p class="error" role="alert">{{ error() }}</p>
        }
        <button class="button primary" [disabled]="form.invalid || saving()">
          Create Campaign
        </button>
      </form>
    </section>
  `,
  styleUrl: './campaigns.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CampaignFormComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(CampaignService);
  private readonly brandApi = inject(BrandService);
  private readonly router = inject(Router);
  readonly brands = signal<BrandSummary[]>([]);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly form = this.fb.nonNullable.group({
    brand_id: ['', Validators.required],
    name: ['', Validators.required],
    objective: [''],
    timezone_name: ['UTC', Validators.required],
    local_start_at: ['', Validators.required],
    local_end_at: ['', Validators.required],
    approval_policy: ['approve_before_scheduling'],
    scheduling_policy: ['strict_window'],
    conflict_policy: ['block'],
  });
  constructor() {
    void this.loadBrands();
  }
  private async loadBrands(): Promise<void> {
    const result = await this.brandApi.list({ pageSize: 100 });
    this.brands.set(result.items);
  }
  async save(): Promise<void> {
    if (this.form.invalid) return;
    this.saving.set(true);
    this.error.set('');
    try {
      const campaign = await this.api.create(this.form.getRawValue());
      await this.router.navigate(['/campaigns', campaign.id]);
    } catch {
      this.error.set('Campaign could not be created. Review the form and dates.');
    } finally {
      this.saving.set(false);
    }
  }
}
