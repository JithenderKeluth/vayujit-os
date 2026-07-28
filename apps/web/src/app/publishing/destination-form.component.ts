import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import type { BrandSummary } from '@vayujit/shared';
import { environment } from '../../environments/environment';
import { BrandService } from '../brands/brand.service';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-destination-form',
  imports: [ReactiveFormsModule, RouterLink],
  template: ` <section class="pub-page">
    <header>
      <h1>{{ editing() ? 'Edit' : 'Create' }} publishing destination</h1>
      <p class="pub-muted">
        Configuration is restricted to safe local mock fields. No credentials or arbitrary JSON are
        stored.
      </p>
    </header>
    @if (loading()) {
      <p role="status">Loading destination form…</p>
    }
    @if (error()) {
      <p class="pub-error" role="alert">{{ error() }}</p>
    }
    <form class="pub-card pub-form" [formGroup]="form" (ngSubmit)="save()">
      <label
        >Destination name <input formControlName="name" maxlength="160" />
        @if (touchedInvalid('name')) {
          <span class="pub-error">Enter a destination name.</span>
        }</label
      ><label
        >Connector
        <select formControlName="connector_key">
          <option value="mock_publisher_v1">Deterministic local mock</option>
        </select></label
      ><label
        >Brand scope
        <select formControlName="brand_id">
          <option value="">All Brands</option>
          @for (brand of brands(); track brand.id) {
            <option [value]="brand.id">{{ brand.name }}</option>
          }
        </select></label
      ><label
        >Channel name <input formControlName="channel_name" maxlength="100" />
        @if (touchedInvalid('channel_name')) {
          <span class="pub-error">Enter a channel name.</span>
        }</label
      ><label
        >Publication prefix
        <input
          formControlName="publication_prefix"
          maxlength="20"
          aria-describedby="prefix-help"
        /><span id="prefix-help" class="pub-muted"
          >1–20 letters, numbers, hyphens, or underscores.</span
        >
        @if (touchedInvalid('publication_prefix')) {
          <span class="pub-error">Use only letters, numbers, hyphens, or underscores.</span>
        }
      </label>
      @if (development) {
        <details class="pub-dev">
          <summary>Development testing</summary>
          <p>
            These controls deliberately simulate connector failures and are hidden in production
            builds.
          </p>
          <label
            ><input type="checkbox" formControlName="simulate_failure" /> Simulate failure</label
          ><label
            >Failure type
            <select formControlName="failure_type">
              <option value="retryable">Retryable</option>
              <option value="non_retryable">Permanent</option>
            </select></label
          >
        </details>
      }
      <div class="pub-actions">
        <button [disabled]="busy() || form.invalid">
          {{ busy() ? 'Saving…' : 'Save destination' }}</button
        ><a class="pub-button secondary" routerLink="/publishing/destinations">Cancel</a>
      </div>
    </form>
  </section>`,
  styleUrl: './publishing.css',
})
export class DestinationFormComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(PublishingService);
  private readonly brandsApi = inject(BrandService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly brands = signal<BrandSummary[]>([]);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly editing = signal(false);
  readonly development = !environment.production;
  private id = '';
  readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required, Validators.maxLength(160)]],
    connector_key: ['mock_publisher_v1' as const, Validators.required],
    brand_id: [''],
    channel_name: ['', [Validators.required, Validators.maxLength(100)]],
    publication_prefix: ['PUB', [Validators.required, Validators.pattern(/^[A-Za-z0-9_-]{1,20}$/)]],
    simulate_failure: [false],
    failure_type: this.fb.nonNullable.control<'retryable' | 'non_retryable'>('non_retryable'),
  });
  ngOnInit(): void {
    void this.load();
  }
  touchedInvalid(name: keyof typeof this.form.controls) {
    const control = this.form.controls[name];
    return control.touched && control.invalid;
  }
  private async load() {
    try {
      const brands = await this.brandsApi.list({ includeArchived: false, pageSize: 100 });
      this.brands.set(brands.items);
      this.id = this.route.snapshot.paramMap.get('id') ?? '';
      this.editing.set(Boolean(this.id));
      if (this.id) {
        const item = await this.api.destination(this.id);
        this.form.patchValue({
          name: item.name,
          connector_key: 'mock_publisher_v1',
          brand_id: item.brand_id ?? '',
          channel_name: item.configuration.channel_name,
          publication_prefix: item.configuration.publication_prefix,
          simulate_failure: item.configuration.simulate_failure,
          failure_type: item.configuration.failure_type,
        });
      }
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
  async save() {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    const value = this.form.getRawValue();
    const data = {
      name: value.name,
      brand_id: value.brand_id || null,
      connector_key: 'mock_publisher_v1' as const,
      configuration: {
        channel_name: value.channel_name,
        publication_prefix: value.publication_prefix,
        simulate_failure: this.development ? value.simulate_failure : false,
        failure_type: this.development ? value.failure_type : ('non_retryable' as const),
      },
    };
    try {
      const item = this.editing()
        ? await this.api.updateDestination(this.id, data)
        : await this.api.createDestination(data);
      await this.router.navigate(['/publishing/destinations', item.id]);
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
}
