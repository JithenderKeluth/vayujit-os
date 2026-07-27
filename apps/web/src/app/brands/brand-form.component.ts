import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { BrandService } from './brand.service';

@Component({
  selector: 'app-brand-form',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <section class="page narrow">
      <header class="page-header">
        <div>
          <p class="eyebrow">Brand Management</p>
          <h1>{{ editing() ? 'Edit brand' : 'Create brand' }}</h1>
        </div>
      </header>
      @if (loading()) {
        <p class="state">Loading brand…</p>
      } @else {
        <form class="brand-form card" [formGroup]="form" (ngSubmit)="save()">
          <label>Name *<input formControlName="name" maxlength="120" /></label>
          <label
            >Slug override<input
              formControlName="slug"
              maxlength="120"
              placeholder="generated-from-name"
          /></label>
          <label>Tagline<input formControlName="tagline" maxlength="240" /></label>
          <label
            >Description<textarea
              formControlName="description"
              maxlength="5000"
              rows="6"
            ></textarea>
          </label>
          <label
            >Website URL<input
              type="url"
              formControlName="website_url"
              placeholder="https://example.com"
          /></label>
          <div class="color-row">
            <label>Primary color<input type="color" formControlName="primary_color" /></label>
            <label>Secondary color<input type="color" formControlName="secondary_color" /></label>
          </div>
          @if (form.controls.name.touched && form.controls.name.invalid) {
            <p class="error">A brand name is required.</p>
          }
          @if (form.controls.slug.touched && form.controls.slug.invalid) {
            <p class="error">Use lowercase letters, numbers, and single hyphens.</p>
          }
          @if (form.controls.website_url.touched && form.controls.website_url.invalid) {
            <p class="error">Enter a valid HTTP or HTTPS URL.</p>
          }
          @if (error()) {
            <p class="error" role="alert">{{ error() }}</p>
          }
          <div class="actions">
            <a class="button" [routerLink]="cancelUrl()">Cancel</a
            ><button class="button primary" type="submit" [disabled]="form.invalid || saving()">
              {{ saving() ? 'Saving…' : 'Save brand' }}
            </button>
          </div>
        </form>
      }
    </section>
  `,
  styleUrl: './brands.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BrandFormComponent {
  private readonly fb = inject(FormBuilder);
  private readonly brands = inject(BrandService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly id = this.route.snapshot.paramMap.get('id');
  readonly editing = signal(Boolean(this.id));
  readonly loading = signal(Boolean(this.id));
  readonly saving = signal(false);
  readonly error = signal('');
  readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required, Validators.maxLength(120)]],
    slug: ['', [Validators.pattern(/^[a-z0-9]+(?:-[a-z0-9]+)*$/), Validators.maxLength(120)]],
    tagline: ['', Validators.maxLength(240)],
    description: ['', Validators.maxLength(5000)],
    website_url: ['', Validators.pattern(/^https?:\/\/.+/i)],
    primary_color: ['#28565c', Validators.pattern(/^#[0-9a-f]{6}$/i)],
    secondary_color: ['#c8dbd6', Validators.pattern(/^#[0-9a-f]{6}$/i)],
  });

  constructor() {
    if (this.id) void this.load(this.id);
  }
  cancelUrl(): string {
    return this.id ? `/brands/${this.id}` : '/brands';
  }

  private async load(id: string): Promise<void> {
    try {
      const brand = await this.brands.get(id);
      this.form.patchValue({
        name: brand.name,
        slug: brand.slug,
        tagline: brand.tagline ?? '',
        description: brand.description ?? '',
        website_url: brand.website_url ?? '',
        primary_color: brand.primary_color ?? '#28565c',
        secondary_color: brand.secondary_color ?? '#c8dbd6',
      });
    } catch (error) {
      this.error.set(BrandService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }

  async save(): Promise<void> {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    this.error.set('');
    const raw = this.form.getRawValue();
    const payload = {
      name: raw.name.trim(),
      slug: raw.slug.trim() || null,
      tagline: raw.tagline.trim() || null,
      description: raw.description.trim() || null,
      website_url: raw.website_url.trim() || null,
      primary_color: raw.primary_color,
      secondary_color: raw.secondary_color,
    };
    try {
      const brand = this.id
        ? await this.brands.update(this.id, payload)
        : await this.brands.create(payload);
      await this.router.navigate(['/brands', brand.id]);
    } catch (error) {
      this.error.set(BrandService.errorMessage(error));
    } finally {
      this.saving.set(false);
    }
  }
}
