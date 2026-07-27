import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { BrandSummary, PaginatedBrandResponse } from '@vayujit/shared';
import { BrandService } from './brand.service';

@Component({
  selector: 'app-brand-list',
  imports: [DatePipe, ReactiveFormsModule, RouterLink],
  template: `
    <section class="page">
      <header class="page-header">
        <div>
          <p class="eyebrow">Brand Management</p>
          <h1>Brands</h1>
        </div>
        <a class="button primary" routerLink="/brands/new">Create brand</a>
      </header>
      <form class="filters" (submit)="apply($event)">
        <label>Search<input [formControl]="search" placeholder="Search by name" /></label>
        <label
          >Status
          <select [formControl]="status">
            <option value="">All active</option>
            <option value="active">Active</option>
            <option value="archived">Archived</option>
          </select>
        </label>
        <label class="checkbox"
          ><input type="checkbox" [formControl]="includeArchived" /> Include archived</label
        >
        <button class="button" type="submit">Apply</button>
      </form>
      @if (loading()) {
        <p class="state">Loading brands…</p>
      } @else if (error()) {
        <p class="state error" role="alert">{{ error() }}</p>
      } @else if (!result()?.items?.length) {
        <div class="state">
          <h2>No brands found</h2>
          <p>Create your first brand or change the filters.</p>
        </div>
      } @else {
        <div class="brand-grid">
          @for (brand of result()!.items; track brand.id) {
            <article class="card">
              <div class="card-title">
                <div>
                  <h2>
                    <a [routerLink]="['/brands', brand.id]">{{ brand.name }}</a>
                  </h2>
                  <p>{{ brand.tagline || 'No tagline yet' }}</p>
                </div>
                @if (brand.is_active_context) {
                  <span class="badge active-brand">Active context</span>
                }
                <span class="badge">{{ brand.status }}</span>
              </div>
              @if (brand.website_url) {
                <a [href]="brand.website_url" target="_blank" rel="noopener">{{
                  brand.website_url
                }}</a>
              }
              <dl>
                <div>
                  <dt>Created</dt>
                  <dd>{{ brand.created_at | date: 'mediumDate' }}</dd>
                </div>
                <div>
                  <dt>Updated</dt>
                  <dd>{{ brand.updated_at | date: 'mediumDate' }}</dd>
                </div>
              </dl>
              <div class="actions">
                <a class="button" [routerLink]="['/brands', brand.id]">View</a>
                <a class="button" [routerLink]="['/brands', brand.id, 'edit']">Edit</a>
                @if (brand.status === 'active' && !brand.is_active_context) {
                  <button class="button" (click)="activate(brand)">Activate</button>
                }
                @if (brand.status === 'active') {
                  <button class="button danger" (click)="archive(brand)">Archive</button>
                } @else {
                  <button class="button" (click)="restore(brand)">Restore</button>
                }
              </div>
            </article>
          }
        </div>
        <nav class="pagination" aria-label="Brand pages">
          <button
            class="button"
            [disabled]="result()!.page <= 1"
            (click)="load(result()!.page - 1)"
          >
            Previous
          </button>
          <span
            >Page {{ result()!.page }} of {{ result()!.pages || 1 }} ·
            {{ result()!.total }} brands</span
          >
          <button
            class="button"
            [disabled]="result()!.page >= result()!.pages"
            (click)="load(result()!.page + 1)"
          >
            Next
          </button>
        </nav>
      }
    </section>
  `,
  styleUrl: './brands.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BrandListComponent {
  private readonly brands = inject(BrandService);
  readonly search = new FormControl('', { nonNullable: true });
  readonly status = new FormControl<'' | 'active' | 'archived'>('', { nonNullable: true });
  readonly includeArchived = new FormControl(false, { nonNullable: true });
  readonly result = signal<PaginatedBrandResponse | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');

  constructor() {
    void this.load();
  }

  apply(event: Event): void {
    event.preventDefault();
    void this.load(1);
  }

  async load(page = 1): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      this.result.set(
        await this.brands.list({
          search: this.search.value.trim(),
          status: this.status.value,
          includeArchived: this.includeArchived.value,
          page,
        }),
      );
    } catch (error) {
      this.error.set(BrandService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }

  async activate(brand: BrandSummary): Promise<void> {
    try {
      await this.brands.activate(brand.id);
      await this.load(this.result()?.page);
    } catch (error) {
      this.error.set(BrandService.errorMessage(error));
    }
  }

  async archive(brand: BrandSummary): Promise<void> {
    if (!confirm(`Archive ${brand.name}? The brand will remain available for restoration.`)) return;
    try {
      await this.brands.archive(brand.id);
      await this.load(this.result()?.page);
    } catch (error) {
      this.error.set(BrandService.errorMessage(error));
    }
  }

  async restore(brand: BrandSummary): Promise<void> {
    try {
      await this.brands.restore(brand.id);
      await this.load(this.result()?.page);
    } catch (error) {
      this.error.set(BrandService.errorMessage(error));
    }
  }
}
