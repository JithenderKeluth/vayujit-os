import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { AIProviderSummary, PaginatedAIHistory } from '@vayujit/shared';
import { AIService } from './ai.service';

@Component({
  selector: 'app-ai-home',
  imports: [RouterLink],
  template: ` <section class="ai-page">
    <header class="ai-header">
      <div>
        <h1>AI Content Studio</h1>
        <p class="ai-muted">
          Generate structured product content and review every version before use.
        </p>
      </div>
      <a class="ai-button" routerLink="/ai/generate">Generate content</a>
    </header>
    @if (error()) {
      <p class="ai-error">{{ error() }}</p>
    }
    <div class="ai-grid">
      <article class="ai-card">
        <h2>Provider</h2>
        @if (provider()) {
          <p>
            <strong>{{ provider()!.name }}</strong>
          </p>
          <p class="ai-muted">
            Local deterministic mock · {{ provider()!.available ? 'Available' : 'Unavailable' }}
          </p>
        }
      </article>
      <article class="ai-card">
        <h2>Generation history</h2>
        <p>{{ recent()?.total ?? 0 }} requests</p>
        <a routerLink="/ai/history">View history</a>
        · <a routerLink="/ai/usage">View usage</a>
      </article>
      <article class="ai-card">
        <h2>Provider settings</h2>
        <a routerLink="/settings/ai/providers/openai-compatible"
          >Configure and validate real provider</a
        >
      </article>
    </div>
    <article class="ai-card">
      <h2>Recent requests</h2>
      @if (!recent()?.items?.length) {
        <p class="ai-muted">No content has been generated yet.</p>
      }
      @for (item of recent()?.items ?? []; track item.generation_id) {
        <p>
          <strong>{{ item.product_name }}</strong> · {{ item.request_status }}
          @if (item.artifact_id) {
            ·
            <a [routerLink]="['/ai/artifacts', item.artifact_id]"
              >Review v{{ item.version_number }}</a
            >
          }
        </p>
      }
    </article>
  </section>`,
  styleUrl: './ai.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AIHomeComponent implements OnInit {
  private readonly ai = inject(AIService);
  readonly provider = signal<AIProviderSummary | null>(null);
  readonly recent = signal<PaginatedAIHistory | null>(null);
  readonly error = signal('');
  ngOnInit(): void {
    void this.load();
  }
  private async load(): Promise<void> {
    try {
      const [providers, recent] = await Promise.all([
        this.ai.providers(),
        this.ai.history({ pageSize: 5 }),
      ]);
      this.provider.set(providers[0] ?? null);
      this.recent.set(recent);
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    }
  }
}
