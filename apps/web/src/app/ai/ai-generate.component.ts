import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import type {
  AIModelSummary,
  AIProviderConfiguration,
  AIProviderSummary,
  AITemplateSummary,
  ProductSummary,
} from '@vayujit/shared';
import { ProductService } from '../products/product.service';
import { OperationsService } from '../operations/operations.service';
import { AIService } from './ai.service';

@Component({
  selector: 'app-ai-generate',
  imports: [FormsModule, RouterLink],
  template: ` <section class="ai-page">
    <header class="ai-header">
      <h1>Generate product content</h1>
      <a routerLink="/ai">Back</a>
    </header>
    <form class="ai-card ai-form" (ngSubmit)="submit()">
      <label
        >Product<select required name="product" [(ngModel)]="productId">
          <option value="">Select a product</option>
          @for (product of products(); track product.id) {
            <option [value]="product.id">
              {{ product.brand_name }} · {{ product.name }} ({{ product.status }})
            </option>
          }
        </select></label
      >
      <label
        >Template<select name="template" [(ngModel)]="templateId">
          @for (template of templates(); track template.id) {
            <option [value]="template.id">{{ template.name }} · v{{ template.version }}</option>
          }
        </select></label
      >
      <label
        >Provider<select
          name="provider"
          [(ngModel)]="providerKey"
          (ngModelChange)="providerChanged()"
        >
          @for (provider of providers(); track provider.key) {
            <option [value]="provider.key">{{ provider.name }}</option>
          }
        </select></label
      >
      @if (providerKey === 'openai_compatible') {
        <label
          >Model<input
            required
            maxlength="120"
            name="model"
            list="generation-models"
            [(ngModel)]="model"
        /></label>
        <datalist id="generation-models">
          @for (item of models(); track item.identifier) {
            <option [value]="item.identifier"></option>
          }
        </datalist>
        <label
          ><input type="checkbox" name="fallback" [(ngModel)]="allowFallback" /> Allow explicit
          fallback to deterministic mock</label
        >
        @if (!configuration()?.configured || configuration()?.validation_status !== 'valid') {
          <p class="ai-error">
            Real provider configuration is not validated.
            <a routerLink="/settings/ai/providers/openai-compatible">Open provider settings</a>.
          </p>
        }
      }
      <label
        >Additional instructions
        <textarea
          name="instructions"
          rows="5"
          maxlength="2000"
          [(ngModel)]="instructions"
          placeholder="Optional tone or emphasis"
        ></textarea>
      </label>
      @if (error()) {
        <p class="ai-error">{{ error() }}</p>
      }
      <div>
        <button [disabled]="busy() || !productId">
          {{ busy() ? 'Generating…' : 'Generate review draft' }}
        </button>
      </div>
      <aside class="ai-card">
        <h2>Generation summary</h2>
        <p>
          Provider: {{ providerKey }} · Model:
          {{
            providerKey === 'openai_compatible'
              ? model || 'Not selected'
              : 'mock-product-content-v1'
          }}
        </p>
        <p>
          Human approval remains mandatory. Cost is unavailable unless operator pricing exists.
          Product content and additional instructions are treated as untrusted data.
        </p>
      </aside>
    </form>
  </section>`,
  styleUrl: './ai.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AIGenerateComponent implements OnInit {
  private readonly ai = inject(AIService);
  private readonly productService = inject(ProductService);
  private readonly router = inject(Router);
  private readonly operations = inject(OperationsService);
  readonly products = signal<ProductSummary[]>([]);
  readonly templates = signal<AITemplateSummary[]>([]);
  readonly providers = signal<AIProviderSummary[]>([]);
  readonly models = signal<AIModelSummary[]>([]);
  readonly configuration = signal<AIProviderConfiguration | null>(null);
  readonly busy = signal(false);
  readonly error = signal('');
  productId = '';
  templateId = '';
  instructions = '';
  providerKey = 'deterministic_mock_v1';
  model = 'mock-product-content-v1';
  allowFallback = false;
  ngOnInit(): void {
    void this.load();
  }
  private async load(): Promise<void> {
    try {
      const [products, templates, settings, providers, configuration] = await Promise.all([
        this.productService.list({ allBrands: true, pageSize: 100 }),
        this.ai.templates(),
        this.operations.settings(),
        this.ai.providers(),
        this.ai.providerConfiguration(),
      ]);
      this.products.set(products.items.filter((product) => product.status !== 'archived'));
      this.templates.set(templates);
      this.providers.set(providers);
      this.configuration.set(configuration);
      if (configuration.enabled && configuration.validation_status === 'valid') {
        this.providerKey = 'openai_compatible';
        this.model = configuration.default_model;
        this.allowFallback = configuration.fallback_provider_key === 'deterministic_mock_v1';
        try {
          this.models.set(await this.ai.models());
        } catch {
          this.models.set([]);
        }
      }
      const preferred = settings.preferences.default_prompt_template_id;
      this.templateId = templates.some((template) => template.id === preferred)
        ? (preferred ?? '')
        : (templates.find((template) => template.is_default)?.id ?? templates[0]?.id ?? '');
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    }
  }
  async submit(): Promise<void> {
    if (!this.productId || this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    try {
      const result = await this.ai.generate({
        product_id: this.productId,
        prompt_template_id: this.templateId || null,
        additional_instructions: this.instructions || null,
        provider_key:
          this.providerKey === 'openai_compatible' ? 'openai_compatible' : 'deterministic_mock_v1',
        model: this.model || null,
        allow_fallback: this.allowFallback,
      });
      if (result.artifact_id) await this.router.navigate(['/ai/artifacts', result.artifact_id]);
      else
        this.error.set(
          result.safe_error_message ?? 'Generation did not produce a reviewable artifact.',
        );
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
  providerChanged(): void {
    if (this.providerKey === 'deterministic_mock_v1') {
      this.model = 'mock-product-content-v1';
      this.allowFallback = false;
    } else {
      this.model = this.configuration()?.default_model ?? '';
    }
  }
}
