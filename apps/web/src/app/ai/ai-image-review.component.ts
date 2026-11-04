import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

type ImageDetail = {
  id: string;
  job_id: string;
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
            @if (image.media_id) {
              <img
                [src]="previewUrl(image.media_id)"
                alt="Generated output for exact-version HUMAN review"
                style="max-width:100%;height:auto"
              />
            } @else {
              <p>No processed image is available yet. Do not approve an unseen output.</p>
            }
            <p>
              Status: <strong>{{ image.status }}</strong>
            </p>
            <p>Operation: {{ image.operation }} - Channel: {{ image.channel }}</p>
            <p>
              Actual dimensions: {{ image.actual_width ?? 'UNKNOWN' }} x
              {{ image.actual_height ?? 'UNKNOWN' }}
            </p>
            <p>
              MIME: {{ image.mime_type || 'UNKNOWN' }} - Size:
              {{ image.size_bytes ?? 'UNKNOWN' }} bytes
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
            [disabled]="busy() || !image.media_id || image.status === 'approved'"
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
          <button class="ai-button" [disabled]="busy() || !image.media_id" (click)="regenerate()">
            Regenerate
          </button>
          <button class="ai-button" [disabled]="busy()" (click)="refreshOutput()">
            Refresh exact output
          </button>
          @if (recovery(); as state) {
            <p role="status">
              Job {{ image.job_id }}: {{ state.status }} — {{ state.safe_error_message }}
            </p>
            <button
              class="ai-button"
              [disabled]="busy() || state.status !== 'failed' || !state.retryable"
              (click)="retryOutput()"
            >
              Retry exact image job
            </button>
          }
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
  private readonly router = inject(Router);
  private readonly base = `${environment.apiUrl}/ai/images`;
  readonly detail = signal<ImageDetail | null>(null);
  readonly error = signal('');
  readonly busy = signal(false);
  readonly comparison = signal<Comparison | null>(null);
  readonly history = signal<Array<unknown>>([]);
  readonly recovery = signal<{
    status: string;
    retryable: boolean;
    safe_error_message: string | null;
  } | null>(null);
  refreshOutput(): void {
    void this.load();
  }
  async retryOutput(): Promise<void> {
    const image = this.detail(),
      recovery = this.recovery();
    if (!image?.job_id || this.busy() || recovery?.status !== 'failed' || !recovery.retryable)
      return;
    this.busy.set(true);
    try {
      await firstValueFrom(
        this.http.post(
          `${environment.apiUrl}/ai/studio/recovery/actions`,
          { action: 'retry_generation', job_id: image.job_id },
          { withCredentials: true },
        ),
      );
      await this.load();
    } catch {
      this.error.set('The exact image job retry was rejected safely. Refresh current status.');
    } finally {
      this.busy.set(false);
    }
  }
  previewUrl(id: string): string {
    return `${environment.apiUrl}/media/${encodeURIComponent(id)}/preview`;
  }

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
      const image = this.detail();
      this.recovery.set(null);
      if (image?.job_id && image.status === 'failed') {
        this.recovery.set(
          await firstValueFrom(
            this.http.post<{
              status: string;
              retryable: boolean;
              safe_error_message: string | null;
            }>(
              `${environment.apiUrl}/ai/studio/recovery/actions`,
              { action: 'review_failure', job_id: image.job_id },
              { withCredentials: true },
            ),
          ),
        );
      }
    } catch {
      this.error.set('The image review details are unavailable.');
    }
  }

  private async decide(path: 'approve' | 'reject'): Promise<void> {
    const image = this.detail();
    if (!image) return;
    this.busy.set(true);
    try {
      await firstValueFrom(
        this.http.post<unknown>(
          `${this.base}/outputs/${image.id}/${path}`,
          {
            feedback: path === 'reject' ? 'Review feedback required.' : undefined,
            category: path === 'reject' ? 'image_quality' : undefined,
          },
          { withCredentials: true },
        ),
      );
      // Decision responses are output summaries, not the rich review projection.
      // Reload the exact output instead of rendering missing lineage/readiness fields.
      await this.load();
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
      const result = await firstValueFrom(
        this.http.post<{ outputs: Array<{ id: string }> }>(
          `${this.base}/outputs/${image.id}/regenerate`,
          {
            reason: 'rejected_feedback',
            feedback: image.approval_feedback || 'Please review the generated image.',
            idempotency_key: `regen:${image.id}:${Date.now()}`,
          },
          { withCredentials: true },
        ),
      );
      const next = result.outputs[0];
      if (!next) throw new Error('No queued output identity');
      await this.router.navigate(['/ai/images/assets', next.id]);
      await this.load();
    } catch {
      this.error.set('The regeneration request could not be queued safely.');
    } finally {
      this.busy.set(false);
    }
  }
}
