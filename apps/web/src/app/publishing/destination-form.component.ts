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
        Destinations contain publishing preferences only. WordPress credentials are configured
        separately and are never stored here.
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
          <option value="wordpress">WordPress</option>
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
      @if (form.controls.connector_key.value === 'wordpress') {
        <fieldset>
          <legend>WordPress mapping</legend>
          <label
            >Post status
            <select formControlName="post_status">
              <option value="draft">Draft</option>
              <option value="publish">Publish</option>
            </select></label
          >
          <label>Category IDs <input formControlName="category_ids" placeholder="1, 2" /></label>
          <label>Tag IDs <input formControlName="tag_ids" placeholder="3, 4" /></label>
          <label>Author ID <input formControlName="author_id" type="number" min="1" /></label>
          <a routerLink="/settings/publishing/connectors/wordpress"
            >Configure WordPress credentials</a
          >
        </fieldset>
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
    connector_key: this.fb.nonNullable.control<'mock_publisher_v1' | 'wordpress'>(
      'mock_publisher_v1',
      Validators.required,
    ),
    brand_id: [''],
    channel_name: ['', [Validators.required, Validators.maxLength(100)]],
    publication_prefix: ['PUB', [Validators.required, Validators.pattern(/^[A-Za-z0-9_-]{1,20}$/)]],
    simulate_failure: [false],
    failure_type: this.fb.nonNullable.control<'retryable' | 'non_retryable'>('non_retryable'),
    post_status: this.fb.nonNullable.control<'draft' | 'publish'>('draft'),
    category_ids: [''],
    tag_ids: [''],
    author_id: [''],
  });
  ngOnInit(): void {
    this.form.controls.connector_key.valueChanges.subscribe((key) => {
      const channel = this.form.controls.channel_name;
      const prefix = this.form.controls.publication_prefix;
      if (key === 'wordpress') {
        channel.clearValidators();
        prefix.clearValidators();
      } else {
        channel.setValidators([Validators.required, Validators.maxLength(100)]);
        prefix.setValidators([Validators.required, Validators.pattern(/^[A-Za-z0-9_-]{1,20}$/)]);
      }
      channel.updateValueAndValidity();
      prefix.updateValueAndValidity();
    });
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
        const configuration = item.configuration;
        this.form.patchValue({
          name: item.name,
          connector_key: item.connector_key === 'wordpress' ? 'wordpress' : 'mock_publisher_v1',
          brand_id: item.brand_id ?? '',
          ...('channel_name' in configuration
            ? {
                channel_name: configuration.channel_name,
                publication_prefix: configuration.publication_prefix,
                simulate_failure: configuration.simulate_failure,
                failure_type: configuration.failure_type,
              }
            : {
                post_status: configuration.post_status,
                category_ids: configuration.category_ids.join(', '),
                tag_ids: configuration.tag_ids.join(', '),
                author_id: configuration.author_id ? String(configuration.author_id) : '',
              }),
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
    const ids = (input: string) =>
      input
        .split(',')
        .map((part) => Number(part.trim()))
        .filter((part) => Number.isInteger(part) && part > 0);
    const data = {
      name: value.name,
      brand_id: value.brand_id || null,
      connector_key: value.connector_key,
      configuration:
        value.connector_key === 'wordpress'
          ? {
              post_status: value.post_status,
              category_ids: ids(value.category_ids),
              tag_ids: ids(value.tag_ids),
              author_id: value.author_id ? Number(value.author_id) : null,
              media_policy: 'fail' as const,
              update_existing_remote_post: true,
              content_mapping_version: 1 as const,
            }
          : {
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
