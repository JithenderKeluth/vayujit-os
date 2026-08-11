import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

type ImageGeneration = {
  generation_id: string;
  status: string;
  outputs: Array<{ id: string; status: string; media_id?: string; operation: string }>;
};

@Component({
  selector: 'app-ai-image-studio',
  imports: [RouterLink],
  template: ` <section class="ai-page">
    <header class="ai-header">
      <div>
        <h1>AI Image Studio</h1>
        <p class="ai-muted">Create safe, reviewable image variants from trusted Product media.</p>
      </div>
      <a class="ai-button" routerLink="/ai/images/bulk">Bulk images</a
      ><a class="ai-button" routerLink="/ai/studio">Content Studio</a
      ><a class="ai-button" routerLink="/media">Media library</a>
    </header>
    @if (error()) {
      <p class="ai-error">{{ error() }}</p>
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
      <label
        >Brand ID
        <input
          [value]="brandId()"
          (input)="brandId.set($any($event.target).value)"
          placeholder="Brand UUID"
      /></label>
      <label
        >Product ID
        <input
          [value]="productId()"
          (input)="productId.set($any($event.target).value)"
          placeholder="Product UUID"
      /></label>
      <label
        >Source Media IDs
        <input
          [value]="sourceMediaIds()"
          (input)="sourceMediaIds.set($any($event.target).value)"
          placeholder="Optional comma-separated UUIDs"
      /></label>
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
        {{ busy() ? 'Queueingâ€¦' : 'Queue deterministic image' }}
      </button>
    </article>
    @if (generation()) {
      <article class="ai-card">
        <h2>Generation {{ generation()!.status }}</h2>
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
          .filter(Boolean),
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
        'The image request could not be queued safely. Check Brand, Product, and Media IDs.',
      );
    } finally {
      this.busy.set(false);
    }
  }
}
