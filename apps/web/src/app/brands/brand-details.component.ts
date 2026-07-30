import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import type { BrandDetails } from '@vayujit/shared';
import { BrandService } from './brand.service';

@Component({
  selector: 'app-brand-details',
  imports: [DatePipe, RouterLink],
  template: `
    <section class="page narrow">
      @if (loading()) {
        <p class="state">Loading brand…</p>
      } @else if (error()) {
        <p class="state error" role="alert">{{ error() }}</p>
      } @else if (brand()) {
        <header class="page-header">
          <div>
            <p class="eyebrow">Brand details</p>
            <h1>{{ brand()!.name }}</h1>
            <p>{{ brand()!.tagline || 'No tagline yet' }}</p>
          </div>
          <div class="actions">
            <a class="button" routerLink="/brands">Back</a
            ><a class="button primary" [routerLink]="['/brands', brand()!.id, 'edit']">Edit</a>
          </div>
        </header>
        <article class="card details">
          <div class="card-title">
            <span class="badge">{{ brand()!.status }}</span>
            @if (brand()!.is_active_context) {
              <span class="badge active-brand">Active context</span>
            }
          </div>
          @if (brand()!.website_url) {
            <p>
              <strong>Website</strong><br /><a
                [href]="brand()!.website_url"
                target="_blank"
                rel="noopener"
                >{{ brand()!.website_url }}</a
              >
            </p>
          }
          <div class="swatches">
            @if (brand()!.primary_color) {
              <span [style.background]="brand()!.primary_color">{{ brand()!.primary_color }}</span>
            }
            @if (brand()!.secondary_color) {
              <span [style.background]="brand()!.secondary_color">{{
                brand()!.secondary_color
              }}</span>
            }
          </div>
          <p class="description">{{ brand()!.description || 'No description yet.' }}</p>
          <dl>
            <div>
              <dt>Slug</dt>
              <dd>{{ brand()!.slug }}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{{ brand()!.created_at | date: 'medium' }}</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{{ brand()!.updated_at | date: 'medium' }}</dd>
            </div>
          </dl>
          <div class="actions">
            @if (brand()!.status === 'active' && !brand()!.is_active_context) {
              <button class="button primary" (click)="activate()">Set active</button>
            }
            @if (brand()!.status === 'active') {
              <button class="button danger" (click)="archive()">Archive</button>
            } @else {
              <button class="button" (click)="restore()">Restore</button>
            }
          </div>
        </article>
        <section class="card">
          <h2>Recent activity</h2>
          @if (!brand()!.recent_audit_events.length) {
            <p>No activity recorded.</p>
          }
          @for (event of brand()!.recent_audit_events; track event.occurred_at) {
            <p>
              <strong>{{ event.action }}</strong> · {{ event.occurred_at | date: 'medium' }}
            </p>
          }
        </section>
      }
    </section>
  `,
  styleUrl: './brands.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BrandDetailsComponent {
  private readonly brands = inject(BrandService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly id = this.route.snapshot.paramMap.get('id')!;
  readonly brand = signal<BrandDetails | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  constructor() {
    void this.load();
  }
  private async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      this.brand.set(await this.brands.get(this.id));
    } catch (error) {
      this.error.set(BrandService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
  async activate(): Promise<void> {
    await this.action(() => this.brands.activate(this.id));
  }
  async restore(): Promise<void> {
    await this.action(() => this.brands.restore(this.id));
  }
  async archive(): Promise<void> {
    if (!confirm(`Archive ${this.brand()?.name}?`)) return;
    await this.action(() => this.brands.archive(this.id));
  }
  private async action(operation: () => Promise<unknown>): Promise<void> {
    try {
      await operation();
      await this.load();
    } catch (error) {
      this.error.set(BrandService.errorMessage(error));
    }
  }
}
