import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import type { AIArtifactDetails } from '@vayujit/shared';
import { AIService } from './ai.service';

@Component({
  selector: 'app-ai-artifact',
  imports: [FormsModule, RouterLink],
  template: ` <section class="ai-page">
    <header class="ai-header">
      <div>
        <h1>Content review</h1>
        @if (artifact()) {
          <p class="ai-muted">
            {{ artifact()!.brand_name }} · {{ artifact()!.product_name }} · Version
            {{ artifact()!.version_number }}
          </p>
        }
      </div>
      <a routerLink="/ai/history">History</a>
    </header>
    @if (error()) {
      <p class="ai-error">{{ error() }}</p>
    }
    @if (artifact(); as item) {
      <article class="ai-card">
        <p class="ai-status">Status: {{ item.status }}</p>
        <h2>{{ item.content.product_title }}</h2>
        <p>
          <strong>{{ item.content.short_description }}</strong>
        </p>
        <p class="ai-content">{{ item.content.long_description }}</p>
        <h3>Key features</h3>
        <ul>
          @for (feature of item.content.key_features; track feature) {
            <li>{{ feature }}</li>
          }
        </ul>
        <h3>SEO</h3>
        <p>
          <strong>{{ item.content.seo_title }}</strong>
        </p>
        <p>{{ item.content.seo_description }}</p>
        <h3>Social caption</h3>
        <p>{{ item.content.social_caption }}</p>
        <div class="ai-keywords">
          @for (keyword of item.content.keywords; track keyword) {
            <span>{{ keyword }}</span>
          }
        </div>
        <p class="ai-muted">
          {{ item.content.generation_summary }} · {{ item.template_name }} v{{
            item.template_version
          }}
          · {{ item.provider_key }}
        </p>
      </article>
      @if (item.status === 'pending_review') {
        <article class="ai-card ai-form">
          <div class="ai-actions">
            <button [disabled]="busy()" (click)="approve()">Approve</button>
            <button class="ai-secondary" [disabled]="busy()" (click)="regenerate()">
              Regenerate
            </button>
          </div>
          <label>Rejection reason<textarea rows="3" [(ngModel)]="reason"></textarea></label>
          <div>
            <button class="ai-danger" [disabled]="busy() || !reason.trim()" (click)="reject()">
              Reject
            </button>
          </div>
        </article>
      }
      @if (item.rejection_reason) {
        <article class="ai-card">
          <strong>Rejection reason:</strong> {{ item.rejection_reason }}
        </article>
      }
    }
  </section>`,
  styleUrl: './ai.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AIArtifactComponent implements OnInit {
  private readonly ai = inject(AIService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly artifact = signal<AIArtifactDetails | null>(null);
  readonly busy = signal(false);
  readonly error = signal('');
  reason = '';
  ngOnInit(): void {
    void this.load();
  }
  async approve(): Promise<void> {
    await this.act(() => this.ai.approve(this.id));
  }
  async reject(): Promise<void> {
    await this.act(() => this.ai.reject(this.id, this.reason));
  }
  async regenerate(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      const result = await this.ai.regenerate(this.id);
      if (result.artifact_id) await this.router.navigate(['/ai/artifacts', result.artifact_id]);
      else this.error.set(result.safe_error_message ?? 'Regeneration failed.');
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
  private get id(): string {
    return this.route.snapshot.paramMap.get('id') ?? '';
  }
  private async load(): Promise<void> {
    try {
      this.artifact.set(await this.ai.artifact(this.id));
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    }
  }
  private async act(action: () => Promise<AIArtifactDetails>): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      this.artifact.set(await action());
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
}
