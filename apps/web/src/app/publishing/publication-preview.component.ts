import { Component, input } from '@angular/core';
import type {
  AIArtifactDetails,
  ProductSummary,
  PublishingDestinationSummary,
} from '@vayujit/shared';

@Component({
  selector: 'app-publication-preview',
  template: `@if (artifact() && product() && destination()) {
    <article class="pub-card pub-preview" aria-labelledby="preview-title">
      <h2 id="preview-title">Publication preview</h2>
      <p class="pub-error">
        <strong>Local mock only:</strong> this action records a deterministic example publication
        and contacts no external service.
      </p>
      <dl>
        <div>
          <dt>Brand / Product</dt>
          <dd>{{ artifact()!.brand_name }} / {{ product()!.name }}</dd>
        </div>
        <div>
          <dt>SKU / price</dt>
          <dd>
            {{ product()!.sku || '—' }} /
            {{
              product()!.price_amount && product()!.price_currency
                ? product()!.price_amount + ' ' + product()!.price_currency
                : '—'
            }}
          </dd>
        </div>
        <div>
          <dt>Artifact / destination</dt>
          <dd>Version {{ artifact()!.version_number }} / {{ destination()!.name }}</dd>
        </div>
        <div>
          <dt>Generated title</dt>
          <dd>{{ artifact()!.content.product_title }}</dd>
        </div>
        <div>
          <dt>Short description</dt>
          <dd>{{ artifact()!.content.short_description }}</dd>
        </div>
      </dl>
      <details>
        <summary>Full generated content</summary>
        <h3>Long description</h3>
        <p>{{ artifact()!.content.long_description }}</p>
        <h3>Key features</h3>
        <ul>
          @for (feature of artifact()!.content.key_features; track feature) {
            <li>{{ feature }}</li>
          }
        </ul>
        <h3>SEO</h3>
        <p>
          <strong>{{ artifact()!.content.seo_title }}</strong
          ><br />{{ artifact()!.content.seo_description }}
        </p>
        <h3>Social caption</h3>
        <p>{{ artifact()!.content.social_caption }}</p>
        <div class="pub-tags">
          @for (keyword of artifact()!.content.keywords; track keyword) {
            <span>{{ keyword }}</span>
          }
        </div>
      </details>
    </article>
  }`,
  styleUrl: './publishing.css',
})
export class PublicationPreviewComponent {
  readonly artifact = input.required<AIArtifactDetails | null>();
  readonly product = input.required<ProductSummary | null>();
  readonly destination = input.required<PublishingDestinationSummary | null>();
}
