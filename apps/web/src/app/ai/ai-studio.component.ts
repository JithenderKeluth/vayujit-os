import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type {
  AIStudioArtifact,
  AIStudioChannel,
  AIStudioContentType,
  AIStudioGeneration,
} from '@vayujit/shared';
import { AIService } from './ai.service';

@Component({
  selector: 'app-ai-studio',
  imports: [RouterLink],
  template: ` <section class="ai-page">
    <header class="ai-header">
      <div>
        <h1>AI Product Content + SEO Studio</h1>
        <p class="ai-muted">Generate trusted, channel-specific content with versioned review.</p>
      </div>
      <a class="ai-button" routerLink="/ai/studio/seo">SEO & keywords</a
      ><a class="ai-button" routerLink="/ai/studio/bulk">Bulk generation</a>
      <a class="ai-button" routerLink="/ai">AI overview</a>
    </header>
    @if (error()) {
      <p class="ai-error">{{ error() }}</p>
    }
    <nav class="ai-tabs">
      <a href="#generate">Generate</a><a href="#artifacts">Artifacts</a><a href="#seo">SEO Studio</a
      ><a href="#brand-voice">Brand Voice</a><a href="#diagnostics">Diagnostics</a>
    </nav>
    <article class="ai-card" id="generate">
      <h2>Generate content</h2>
      <label
        >Product ID
        <input
          [value]="productId()"
          (input)="productId.set($any($event.target).value)"
          placeholder="Product UUID"
      /></label>
      <div class="ai-grid">
        <label
          >Channels
          <select multiple (change)="setChannels($event)">
            @for (channel of channels; track channel) {
              <option [value]="channel" [selected]="selectedChannels().includes(channel)">
                {{ channel }}
              </option>
            }
          </select></label
        ><label
          >Content types
          <select multiple (change)="setContentTypes($event)">
            @for (type of contentTypes; track type) {
              <option [value]="type" [selected]="selectedTypes().includes(type)">{{ type }}</option>
            }
          </select></label
        >
      </div>
      <label
        >Instructions
        <textarea
          [value]="instructions()"
          (input)="instructions.set($any($event.target).value)"
          maxlength="2000"
          placeholder="Optional safe guidance"
        ></textarea>
      </label>
      <button class="ai-button" [disabled]="busy() || !productId()" (click)="generate()">
        {{ busy() ? 'Generating�' : 'Generate deterministic draft' }}
      </button>
      @if (generation()) {
        <p class="ai-success">
          {{ generation()!.completed_outputs }} / {{ generation()!.total_outputs }} outputs
          completed. Context {{ generation()!.context_fingerprint.slice(0, 12) }}�
        </p>
      }
    </article>
    <article class="ai-card" id="artifacts">
      <h2>Latest artifacts</h2>
      <button class="ai-button" (click)="loadArtifacts()">Refresh artifacts</button>
      @if (!artifacts().length) {
        <p class="ai-muted">No Studio artifacts yet.</p>
      }
      @for (artifact of artifacts(); track artifact.id) {
        <p>
          <strong>{{ artifact.product_name }}</strong> � {{ artifact.channel }} �
          {{ artifact.content_type }} � v{{ artifact.version_number }} � {{ artifact.status }}
          <a [routerLink]="['/ai/artifacts', artifact.id]">Review</a>
        </p>
      }
    </article>
    <article class="ai-card" id="seo">
      <h2>SEO Studio</h2>
      <p class="ai-muted">
        Analyze keyword coverage and channel readiness from trusted Product and Brand context.
      </p>
      <button class="ai-button" [disabled]="!productId()" (click)="analyzeSeo()">
        Analyze SEO
      </button>
      @if (seoScore() !== null) {
        <p>
          SEO score: <strong>{{ seoScore() }}</strong
          >/100
        </p>
      }
    </article>
    <article class="ai-card" id="brand-voice">
      <h2>Brand Voice</h2>
      <p class="ai-muted">
        Versioned tone, terminology, preferred and prohibited phrase rules are applied to generation
        context.
      </p>
      <a routerLink="/ai/brand-voices">Manage Brand Voices</a> �
      <a routerLink="/ai/presets">Manage Presets</a> � <a routerLink="/ai/usage">View Usage</a> �
      <a routerLink="/settings/ai/providers">Provider settings</a>
    </article>
    <article class="ai-card" id="diagnostics">
      <h2>Diagnostics</h2>
      <p class="ai-muted">
        Local deterministic provider only; remote content calls are disabled by default.
      </p>
    </article>
  </section>`,
  styleUrl: './ai.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AIStudioComponent {
  private readonly ai = inject(AIService);
  readonly productId = signal('');
  readonly instructions = signal('');
  readonly busy = signal(false);
  readonly error = signal('');
  readonly generation = signal<AIStudioGeneration | null>(null);
  readonly artifacts = signal<AIStudioArtifact[]>([]);
  readonly seoScore = signal<number | null>(null);
  readonly channels: AIStudioChannel[] = ['amazon', 'flipkart', 'meesho', 'shopify', 'wordpress'];
  readonly contentTypes: AIStudioContentType[] = [
    'marketplace_listing',
    'product_title',
    'bullet_points',
    'product_description',
    'seo_metadata',
  ];
  readonly selectedChannels = signal<AIStudioChannel[]>(['amazon', 'flipkart', 'meesho']);
  readonly selectedTypes = signal<AIStudioContentType[]>(['marketplace_listing']);
  setChannels(event: Event): void {
    const target = event.target;
    if (target instanceof HTMLSelectElement) {
      this.selectedChannels.set(
        Array.from(target.selectedOptions, (option) => option.value as AIStudioChannel),
      );
    }
  }
  setContentTypes(event: Event): void {
    const target = event.target;
    if (target instanceof HTMLSelectElement) {
      this.selectedTypes.set(
        Array.from(target.selectedOptions, (option) => option.value as AIStudioContentType),
      );
    }
  }
  async generate(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      this.generation.set(
        await this.ai.studioGenerate({
          product_ids: [this.productId()],
          channels: this.selectedChannels(),
          content_types: this.selectedTypes(),
          user_instructions: this.instructions() || undefined,
          idempotency_key: `studio:${this.productId()}:${Date.now()}`,
        }),
      );
      await this.loadArtifacts();
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
  async loadArtifacts(): Promise<void> {
    try {
      this.artifacts.set(await this.ai.studioArtifacts({ product_id: this.productId() }));
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    }
  }
  async analyzeSeo(): Promise<void> {
    try {
      const result = await this.ai.studioSeo({
        product_id: this.productId(),
        channel: 'canonical',
      });
      this.seoScore.set(result.score);
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    }
  }
}
