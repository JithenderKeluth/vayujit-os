import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import { CommerceJourneyNavComponent } from '../shared/commerce-journey-nav.component';
import { ErrorStateComponent, LoadingStateComponent } from '../shared/state-components';
import { StatusBadgeComponent } from '../shared/status-badge.component';
import type { BreadcrumbItem } from '../shared/ux-foundation.types';
import { PageHeaderComponent } from '../shared/page-header.component';
import { BusinessEntitySelectorsComponent } from '../shared/business-entity-selectors.component';

type ImageGeneration = {
  generation_id: string;
  status: string;
  outputs: Array<{ id: string; status: string; media_id?: string; operation: string }>;
};

@Component({
  selector: 'app-ai-image-studio',
  imports: [
    BreadcrumbsComponent,
    BusinessEntitySelectorsComponent,
    CommerceJourneyNavComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    PageHeaderComponent,
    RouterLink,
    StatusBadgeComponent,
  ],
  template: ` <section class="ai-page">
    <app-breadcrumbs [items]="breadcrumbs" />
    <app-page-header
      eyebrow="Create / images"
      title="AI image studio"
      description="Create safe, reviewable image variants from trusted product media."
    >
      <div page-header-actions class="actions">
        <a class="ai-button" routerLink="/ai/images/bulk">Bulk images</a>
        <a class="ai-button" routerLink="/ai/studio">Content studio</a>
        <a class="ai-button" routerLink="/media">Media library</a>
      </div>
    </app-page-header>
    <app-commerce-journey-nav current="images" />
    @if (error()) {
      <app-error-state title="Image generation is unavailable" [message]="error()" />
    }
    @if (busy()) {
      <app-loading-state message="Image request queued; waiting for the worker result..." />
    }
    <ol class="generation-steps" aria-label="Image generation steps">
      <li>1. Product</li>
      <li>2. Source Image</li>
      <li>3. Operation</li>
      <li>4. Target Channel</li>
      <li>5. Brand Style</li>
      <li>6. Preset</li>
      <li>7. Aspect Ratio / Dimensions</li>
      <li>8. Instructions</li>
      <li>9. Provider / Model</li>
      <li>10. Review Plan</li>
      <li>11. Queue</li>
    </ol>
    <article class="ai-card">
      <h2>Generate image</h2>
      <app-business-entity-selectors
        [showBrand]="true"
        [showMedia]="true"
        [productId]="productId()"
        [brandId]="brandId()"
        [mediaIds]="sourceMediaIds().split(',').map((value) => value.trim()).filter((value) => !!value)"
        (productIdChange)="productId.set($event)"
        (brandIdChange)="brandId.set($event)"
        (mediaIdsChange)="sourceMediaIds.set($event.join(', '))"
      />
      <label
        >Operation
        <select [value]="operation()" (change)="operation.set($any($event.target).value)">
          <option value="generate_product_image">Generate product image</option>
          <option value="white_background">White background</option>
          <option value="lifestyle_scene">Lifestyle scene</option>
          <option value="remove_background">Remove background</option>
          <option value="marketplace_main_image">Marketplace main image</option>
          <option value="thumbnail">Thumbnail</option>
        </select></label
      >
      <button
        class="ai-button"
        [disabled]="busy() || !brandId() || !productId()"
        (click)="generate()"
      >
        {{ busy() ? 'Queueing...' : 'Queue deterministic image' }}
      </button>
    </article>
    @if (generation()) {
      <article class="ai-card">
        <h2>Generation {{ generation()!.status }}</h2>
        <app-status-badge
          [status]="generation()!.status"
          [label]="generation()!.status"
          tone="info"
        />
        <p>
          {{ generation()!.outputs.length }} output(s) queued. Worker execution creates a separate
          Media asset.
        </p>
        @for (output of generation()!.outputs; track output.id) {
          <a class="ai-button" [routerLink]="['/ai/images/assets', output.id]">Review output</a>
        }
      </article>
    }
    <article class="ai-card">
      <h2>Safety and readiness</h2>
      <p class="ai-muted">
        Original Media is preserved. Generated outputs remain pending review until explicitly
        approved. Marketplace readiness uses deterministic local rules. Provider: Local Workflow
        Simulation (visual effects simulated; no live provider).
      </p>
    </article>
  </section>`,
  styleUrl: './ai.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AIImageStudioComponent {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/ai/images`;
  readonly brandId = signal('');
  readonly productId = signal('');
  readonly sourceMediaIds = signal('');
  readonly operation = signal('generate_product_image');
  readonly busy = signal(false);
  readonly error = signal('');
  readonly generation = signal<ImageGeneration | null>(null);
  readonly breadcrumbs: BreadcrumbItem[] = [
    { label: 'Products', url: '/products' },
    { label: 'Images' },
  ];

  async generate(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      const body = {
        brand_id: this.brandId(),
        product_id: this.productId(),
        source_media_ids: this.sourceMediaIds()
          .split(',')
          .map((value) => value.trim())
          .filter((value) => !!value),
        operation: this.operation(),
        channel: 'canonical',
        width: 1024,
        height: 1024,
        output_count: 1,
        provider: 'deterministic_mock_v1',
        model: 'image-deterministic-v1',
        idempotency_key: `image:${this.productId()}:${Date.now()}`,
      };
      this.generation.set(
        await firstValueFrom(
          this.http.post<ImageGeneration>(`${this.base}/generate`, body, { withCredentials: true }),
        ),
      );
    } catch {
      this.error.set(
        'The image request could not be queued safely. Check the selected Brand, Product, and media.',
      );
    } finally {
      this.busy.set(false);
    }
  }
}
