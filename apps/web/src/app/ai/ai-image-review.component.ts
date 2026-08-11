import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

type ImageDetail = {
  id: string;
  media_id: string | null;
  parent_media_id: string | null;
  source_media_ids: string[];
  brand_id: string;
  product_id: string;
  operation: string;
  channel: string;
  status: string;
  requested_width: number;
  requested_height: number;
  actual_width: number | null;
  actual_height: number | null;
  mime_type: string | null;
  size_bytes: number | null;
  checksum_sha256: string | null;
  provider: string;
  model: string;
  style_version: number | null;
  preset_version: number | null;
  approval_feedback: string | null;
  rejection_category: string | null;
  lineage: string[];
  readiness: { status: string; approved: boolean; blockers?: string[]; warnings?: string[] };
  asset_classification: string;
  content_artifact_id?: string | null;
  content_artifact_version?: number | null;
};

type Comparison = { mode: string };

@Component({
  selector: 'app-ai-image-review',
  imports: [RouterLink],
  template: `
    <section class="ai-page">
      <header class="ai-header">
        <div>
          <h1>Image review</h1>
          <p class="ai-muted">Review one immutable generated asset and its exact lineage.</p>
        </div>
        <a class="ai-button" routerLink="/ai/images">Back to Images</a>
      </header>
      @if (error()) {
        <p class="ai-error">{{ error() }}</p>
      }
      @if (detail(); as image) {
        <article class="ai-card review-grid">
          <div>
            <h2>Generated image</h2>
            <p>
              Status: <strong>{{ image.status }}</strong>
            </p>
            <p>Operation: {{ image.operation }} - Channel: {{ image.channel }}</p>
            <p>
              Dimensions: {{ image.actual_width || image.requested_width }} x
              {{ image.actual_height || image.requested_height }}
            </p>
            <p>
              MIME: {{ image.mime_type || 'pending' }} - Size: {{ image.size_bytes || 0 }} bytes
            </p>
            <p>
              Checksum: <code>{{ image.checksum_sha256 || 'pending' }}</code>
            </p>
          </div>
          <div>
            <h2>Lineage</h2>
            <p>Source Media: {{ image.parent_media_id || image.source_media_ids[0] || 'none' }}</p>
            <p>Versions: {{ image.lineage.length }}</p>
            <p>Provider/model: {{ image.provider }} / {{ image.model }}</p>
            <p>
              Style version: {{ image.style_version || 'none' }} - Preset version:
              {{ image.preset_version || 'none' }}
            </p>
            <p>Readiness: {{ image.readiness.status }}</p>
          </div>
        </article>
        <article class="ai-card actions">
          <button
            class="ai-button"
            [disabled]="busy() || image.status === 'approved'"
            (click)="approve()"
          >
            Approve exact output
          </button>
          <button
            class="ai-button"
            [disabled]="busy() || image.status === 'rejected'"
            (click)="reject()"
          >
            Reject with feedback
          </button>
          <button class="ai-button" [disabled]="busy()" (click)="regenerate()">Regenerate</button>
        </article>
        <article class="ai-card">
          <h2>Readiness and classification</h2>
          <p>Classification: {{ image.asset_classification }}</p>
          <p>Blockers: {{ image.readiness.blockers?.join(', ') || 'none' }}</p>
          <p>Warnings: {{ image.readiness.warnings?.join(', ') || 'none' }}</p>
        </article>
        <article class="ai-card">
          <h2>Comparison and history</h2>
          <button class="ai-button" (click)="compare()" [disabled]="busy()">
            Compare exact versions
          </button>
          <button class="ai-button" (click)="loadHistory()" [disabled]="busy()">
            Show history
          </button>
          @if (comparison(); as result) {
            <p>Comparison mode: {{ result.mode }}; deterministic facts only.</p>
          }
          @if (history().length) {
            <p>History events: {{ history().length }}</p>
          }
        </article>
      }
    </section>
  `,
  styleUrl: './ai.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AIImageReviewComponent {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  private readonly base = `${environment.apiUrl}/ai/images`;
  readonly detail = signal<ImageDetail | null>(null);
  readonly error = signal('');
  readonly busy = signal(false);
  readonly comparison = signal<Comparison | null>(null);
  readonly history = signal<Array<unknown>>([]);

  constructor() {
    void this.load();
  }

  private async load(): Promise<void> {
    const id = this.route.snapshot.paramMap.get('outputId');
    if (!id) {
      this.error.set('Image output identity is missing.');
      return;
    }
    try {
      this.detail.set(
        await firstValueFrom(
          this.http.get<ImageDetail>(`${this.base}/outputs/${id}`, { withCredentials: true }),
        ),
      );
    } catch {
      this.error.set('The image review details are unavailable.');
    }
  }

  private async decide(path: 'approve' | 'reject'): Promise<void> {
    const image = this.detail();
    if (!image) return;
    this.busy.set(true);
    try {
      this.detail.set(
        await firstValueFrom(
          this.http.post<ImageDetail>(
            `${this.base}/outputs/${image.id}/${path}`,
            {
              feedback: path === 'reject' ? 'Review feedback required.' : undefined,
              category: path === 'reject' ? 'image_quality' : undefined,
            },
            { withCredentials: true },
          ),
        ),
      );
    } catch {
      this.error.set('The image decision could not be saved safely.');
    } finally {
      this.busy.set(false);
    }
  }

  approve(): Promise<void> {
    return this.decide('approve');
  }
  reject(): Promise<void> {
    return this.decide('reject');
  }

  async compare(): Promise<void> {
    const image = this.detail();
    if (!image) return;
    try {
      this.comparison.set(
        await firstValueFrom(
          this.http.get<Comparison>(`${this.base}/outputs/${image.id}/compare`, {
            withCredentials: true,
          }),
        ),
      );
    } catch {
      this.error.set('Comparison is unavailable.');
    }
  }

  async loadHistory(): Promise<void> {
    const image = this.detail();
    if (!image) return;
    try {
      this.history.set(
        await firstValueFrom(
          this.http.get<Array<unknown>>(`${this.base}/outputs/${image.id}/history`, {
            withCredentials: true,
          }),
        ),
      );
    } catch {
      this.error.set('History is unavailable.');
    }
  }

  async regenerate(): Promise<void> {
    const image = this.detail();
    if (!image) return;
    this.busy.set(true);
    try {
      await firstValueFrom(
        this.http.post(
          `${this.base}/outputs/${image.id}/regenerate`,
          {
            reason: 'rejected_feedback',
            feedback: image.approval_feedback || 'Please review the generated image.',
            idempotency_key: `regen:${image.id}:${Date.now()}`,
          },
          { withCredentials: true },
        ),
      );
    } catch {
      this.error.set('The regeneration request could not be queued safely.');
    } finally {
      this.busy.set(false);
    }
  }
}
