import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { AIUsageHistoryItem, AIUsageSummary } from '@vayujit/shared';
import { AIService } from './ai.service';

@Component({
  selector: 'app-ai-usage',
  imports: [FormsModule, RouterLink],
  template: `<section class="ai-page">
    <header class="ai-header">
      <h1>AI usage</h1>
      <a routerLink="/ai">Back</a>
    </header>
    @if (error()) {
      <p class="ai-error" role="alert">{{ error() }}</p>
    }
    @if (usage(); as value) {
      <div class="ai-grid">
        <article class="ai-card">
          <h2>Requests</h2>
          <strong>{{ value.requests }}</strong>
        </article>
        <article class="ai-card">
          <h2>Successful / failed</h2>
          <strong>{{ value.successful_generations }} / {{ value.failed_generations }}</strong>
        </article>
        <article class="ai-card">
          <h2>Retries</h2>
          <strong>{{ value.retries }}</strong>
        </article>
        <article class="ai-card">
          <h2>Tokens</h2>
          <strong>{{ value.total_tokens }}</strong>
          <p>{{ value.input_tokens }} input · {{ value.output_tokens }} output</p>
        </article>
        <article class="ai-card">
          <h2>Estimated cost</h2>
          <strong>{{
            value.estimated_cost
              ? value.cost_currency + ' ' + value.estimated_cost
              : 'Cost unavailable'
          }}</strong>
          <p>Estimates appear only when operator-maintained pricing is configured.</p>
        </article>
      </div>
      <article class="ai-card">
        <h2>Usage history</h2>
        <label
          >Provider
          <select name="provider" [(ngModel)]="provider" (ngModelChange)="load()">
            <option value="">All providers</option>
            <option value="openai_compatible">OpenAI-compatible</option>
            <option value="deterministic_mock_v1">Deterministic mock</option>
          </select>
        </label>
        <button class="secondary" type="button" (click)="export()">Export last 31 days</button>
        @if (!history().length) {
          <p>No usage records match this filter.</p>
        }
        @for (item of history(); track item.generation_id) {
          <p>
            <strong>{{ item.product_name }}</strong> · {{ item.provider_key }} ·
            {{ item.model || 'No model' }} · {{ item.total_tokens ?? 'Usage unavailable' }} tokens ·
            {{
              item.estimated_cost
                ? item.cost_currency + ' ' + item.estimated_cost
                : 'Cost unavailable'
            }}
          </p>
        }
      </article>
    } @else {
      <p role="status">Loading bounded usage summary…</p>
    }
  </section>`,
  styleUrl: './ai.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AIUsageComponent implements OnInit {
  private readonly api = inject(AIService);
  readonly usage = signal<AIUsageSummary | null>(null);
  readonly error = signal('');
  readonly history = signal<AIUsageHistoryItem[]>([]);
  readonly studio = signal<Record<string, unknown> | null>(null);
  provider = '';
  ngOnInit(): void {
    void this.load();
  }
  async load(): Promise<void> {
    try {
      const [usage, history, studio] = await Promise.all([
        this.api.usage(),
        this.api.usageHistory(this.provider),
        this.api.studioUsage(this.provider ? { provider: this.provider } : {}),
      ]);
      this.usage.set(usage);
      this.history.set(history.items);
      this.studio.set(studio);
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    }
  }
  async export(): Promise<void> {
    try {
      const blob = await this.api.usageExport();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'ai-usage.csv';
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    }
  }
}
