import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

type ProductMediaItem = {
  media_id: string;
  image_output_id: string | null;
  source_type: string;
  operation: string | null;
  status: string;
  channel: string | null;
  width: number;
  height: number;
  mime: string | null;
  approval: string;
  marketplace_usage: Array<{ listing_id: string; position: number; status: string }>;
  campaign_usage: Array<{ activity_id: string; campaign_id: string; status: string }>;
  generated_at: string | null;
  readiness: Record<string, unknown>;
};

@Component({
  selector: 'app-product-media',
  imports: [DatePipe, RouterLink],
  template: `
    <section class="media-page" aria-labelledby="product-media-title">
      <header class="media-header">
        <div>
          <p class="eyebrow">Product Media</p>
          <h1 id="product-media-title">Image workspace</h1>
          <p>Review original assets and immutable AI versions.</p>
        </div>
        <a routerLink="../" class="button">Back to product</a>
      </header>
      @if (error()) {
        <p class="state error" role="alert">{{ error() }}</p>
      }
      @if (loading()) {
        <p class="state" role="status">Loading media�</p>
      }
      @for (group of groups(); track group.id) {
        <section class="media-group" [attr.aria-labelledby]="group.id">
          <h2 [id]="group.id">
            {{ group.label }} <span class="count">{{ group.items.length }}</span>
          </h2>
          @if (!group.items.length) {
            <p class="empty">No media in this section.</p>
          }
          <div class="media-grid">
            @for (item of group.items; track item.media_id) {
              <article class="media-card">
                <div class="preview" aria-hidden="true">
                  {{ item.source_type === 'original_uploaded' ? 'Original' : 'AI' }}
                </div>
                <div class="media-card-body">
                  <h3>{{ item.operation || 'Uploaded asset' }}</h3>
                  <p>
                    <strong>{{ item.source_type }}</strong> � {{ item.status }} �
                    {{ item.channel || 'canonical' }}
                  </p>
                  <p>{{ item.width }}�{{ item.height }} � {{ item.mime || 'unknown type' }}</p>
                  @if (item.generated_at) {
                    <p>Generated {{ item.generated_at | date: 'medium' }}</p>
                  }
                  <p>Approval: {{ item.approval }} � Readiness: {{ readiness(item) }}</p>
                  <p>
                    Marketplace use: {{ item.marketplace_usage.length }} � Campaign use:
                    {{ item.campaign_usage.length }}
                  </p>
                  @if (item.image_output_id) {
                    <a class="button" [routerLink]="['/ai/images/assets', item.image_output_id]"
                      >Review</a
                    >
                  }
                </div>
              </article>
            }
          </div>
        </section>
      }
    </section>
  `,
  styles: [
    `
      .media-page {
        display: grid;
        gap: 1.5rem;
        max-width: 78rem;
        margin: 0 auto;
      }
      .media-header {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        flex-wrap: wrap;
      }
      .media-group {
        display: grid;
        gap: 1rem;
      }
      .media-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr));
        gap: 1rem;
      }
      .media-card {
        display: grid;
        grid-template-columns: 7rem 1fr;
        gap: 1rem;
        padding: 1rem;
        border: 1px solid #d9e3e1;
        border-radius: 0.75rem;
        background: #fff;
      }
      .preview {
        display: grid;
        place-items: center;
        min-height: 7rem;
        border-radius: 0.5rem;
        background: #e4ecea;
        font-weight: 700;
      }
      .media-card-body {
        display: grid;
        gap: 0.35rem;
        align-content: start;
      }
      .media-card-body h3,
      .media-card-body p {
        margin: 0;
      }
      .media-card-body p {
        color: #4f6661;
        font-size: 0.9rem;
      }
      .button {
        display: inline-block;
        width: max-content;
        padding: 0.5rem 0.75rem;
        border: 1px solid #8fa7a2;
        border-radius: 0.4rem;
        color: #173531;
        text-decoration: none;
      }
      .state {
        padding: 2rem;
        background: #fff;
        border-radius: 0.75rem;
        text-align: center;
      }
      .error {
        color: #9b2525;
      }
      .empty {
        padding: 1rem;
        background: #fff;
        border-radius: 0.5rem;
      }
      @media (max-width: 640px) {
        .media-card {
          grid-template-columns: 1fr;
        }
        .preview {
          min-height: 5rem;
        }
      }
    `,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProductMediaComponent {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  private readonly productId = this.route.snapshot.paramMap.get('id')!;
  readonly loading = signal(true);
  readonly error = signal('');
  readonly items = signal<ProductMediaItem[]>([]);
  constructor() {
    void this.load();
  }
  readonly groups = () => {
    const items = this.items();
    const generated = items.filter((i) => i.source_type !== 'original_uploaded');
    const originals = items.filter((i) => i.source_type === 'original_uploaded');
    return [
      { id: 'original-assets', label: 'Original Assets', items: originals },
      { id: 'ai-generated', label: 'AI Generated', items: generated },
      {
        id: 'pending-review',
        label: 'Pending Review',
        items: generated.filter((i) => i.status === 'needs_review' || i.status === 'succeeded'),
      },
      {
        id: 'approved-images',
        label: 'Approved AI Images',
        items: generated.filter((i) => i.status === 'approved'),
      },
      {
        id: 'rejected-images',
        label: 'Rejected',
        items: generated.filter((i) => i.status === 'rejected'),
      },
      {
        id: 'marketplace-usage',
        label: 'Marketplace Usage',
        items: items.filter((i) => i.marketplace_usage.length > 0),
      },
      {
        id: 'campaign-usage',
        label: 'Campaign Usage',
        items: items.filter((i) => i.campaign_usage.length > 0),
      },
    ];
  };
  readiness(item: ProductMediaItem): string {
    const value = item.readiness['ready'];
    return value === true ? 'ready' : value === false ? 'blocked' : 'not evaluated';
  }
  private async load(): Promise<void> {
    try {
      this.items.set(
        await firstValueFrom(
          this.http.get<ProductMediaItem[]>(
            `${environment.apiUrl}/ai/images/products/${this.productId}/media`,
            { withCredentials: true },
          ),
        ),
      );
    } catch {
      this.error.set('Product media is unavailable. Check the API connection and try again.');
    } finally {
      this.loading.set(false);
    }
  }
}
