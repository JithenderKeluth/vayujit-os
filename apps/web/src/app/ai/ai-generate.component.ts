import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import type { AITemplateSummary, ProductSummary } from '@vayujit/shared';
import { ProductService } from '../products/product.service';
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
    </form>
  </section>`,
  styleUrl: './ai.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AIGenerateComponent implements OnInit {
  private readonly ai = inject(AIService);
  private readonly productService = inject(ProductService);
  private readonly router = inject(Router);
  readonly products = signal<ProductSummary[]>([]);
  readonly templates = signal<AITemplateSummary[]>([]);
  readonly busy = signal(false);
  readonly error = signal('');
  productId = '';
  templateId = '';
  instructions = '';
  ngOnInit(): void {
    void this.load();
  }
  private async load(): Promise<void> {
    try {
      const [products, templates] = await Promise.all([
        this.productService.list({ allBrands: true, pageSize: 100 }),
        this.ai.templates(),
      ]);
      this.products.set(products.items.filter((product) => product.status !== 'archived'));
      this.templates.set(templates);
      this.templateId =
        templates.find((template) => template.is_default)?.id ?? templates[0]?.id ?? '';
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
}
