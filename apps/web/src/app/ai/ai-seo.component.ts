import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import type {
  AIKeywordSuggestion,
  AISEOAnalysisResponse,
  AISEODimension,
  AISEOFinding,
} from '@vayujit/shared';

import { AIService } from './ai.service';

@Component({
  selector: 'app-ai-seo',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <main class="ai-shell">
      <header class="ai-header">
        <div>
          <a routerLink="/ai/studio">AI Studio</a>
          <h1>SEO & content intelligence</h1>
          <p>Explainable website SEO and channel-specific marketplace search optimization.</p>
        </div>
        <a routerLink="/ai/studio/bulk">Bulk generation</a>
      </header>
      <nav class="seo-tabs" aria-label="SEO workspace">
        <button type="button" [class.active]="tab() === 'overview'" (click)="tab.set('overview')">
          Overview</button
        ><button type="button" [class.active]="tab() === 'website'" (click)="tab.set('website')">
          Website SEO</button
        ><button
          type="button"
          [class.active]="tab() === 'marketplace'"
          (click)="tab.set('marketplace')"
        >
          Marketplace Search</button
        ><button type="button" [class.active]="tab() === 'keywords'" (click)="tab.set('keywords')">
          Keywords</button
        ><button type="button" [class.active]="tab() === 'tags'" (click)="tab.set('tags')">
          Tags</button
        ><button type="button" [class.active]="tab() === 'history'" (click)="tab.set('history')">
          Analysis History
        </button>
      </nav>
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }
      @if (tab() === 'overview' || tab() === 'website' || tab() === 'marketplace') {
        <section class="card controls">
          <label>Product ID<input [(ngModel)]="productId" aria-label="Product ID" /></label
          ><label
            >Artifact ID (optional)<input
              [(ngModel)]="artifactId"
              aria-label="Artifact ID" /></label
          ><label
            >Locale<select [(ngModel)]="locale">
              <option>en-IN</option>
              <option>hi-IN</option>
              <option>te-IN</option>
            </select></label
          ><label
            >Channel<select [(ngModel)]="channel">
              <option value="canonical">Website / canonical</option>
              <option value="wordpress">WordPress</option>
              <option value="shopify">Shopify</option>
              <option value="amazon">Amazon</option>
              <option value="flipkart">Flipkart</option>
              <option value="meesho">Meesho</option>
            </select></label
          ><label>Primary keyword<input [(ngModel)]="primaryKeyword" /></label
          ><button type="button" (click)="analyze()" [disabled]="loading()">
            {{ loading() ? 'Analyzing…' : 'Analyze' }}
          </button>
        </section>
        @if (analysis(); as currentAnalysis) {
          <section class="card">
            <h2>
              {{
                currentAnalysis.seo_type === 'website'
                  ? 'Website SEO'
                  : 'Marketplace Search Optimization'
              }}
              · {{ currentAnalysis.channel }}
            </h2>
            <p class="score">Overall {{ currentAnalysis.overall_score }}/100</p>
            <p>
              Locale: {{ currentAnalysis.locale }} · Artifact version:
              {{ currentAnalysis.artifact_version || 'none' }} · Intent:
              {{ currentAnalysis.intent }}
            </p>
            <div class="dimensions">
              @for (item of dimensionEntries(); track item[0]) {
                <div>
                  <strong>{{ item[0] }}</strong
                  ><span>{{ item[1].score }}/100</span><small>{{ item[1].explanation }}</small>
                </div>
              }
            </div>
            <h3>Findings</h3>
            <ul>
              @for (finding of currentAnalysis.findings; track finding.code + finding.field) {
                <li>
                  <strong>{{ finding.severity }}</strong> · {{ finding.field }} —
                  {{ finding.explanation }}
                  @for (action of finding.actions ?? []; track action) {
                    @if (action === 'edit') {
                      <button type="button" (click)="recommendationAction(action, finding)">
                        Edit
                      </button>
                    }
                    @if (action === 'regenerate') {
                      <button type="button" (click)="recommendationAction(action, finding)">
                        Regenerate
                      </button>
                    }
                    @if (action === 'reanalyze') {
                      <button type="button" (click)="recommendationAction(action, finding)">
                        Re-analyze
                      </button>
                    }
                    @if (action === 'open_keywords') {
                      <button type="button" (click)="recommendationAction(action, finding)">
                        Open keywords
                      </button>
                    }
                  }
                </li>
              }
            </ul>
            <p>
              Search volume unavailable · Keyword difficulty unavailable · CPC unavailable · Ranking
              position unavailable
            </p>
          </section>
        }
      }
      @if (tab() === 'keywords') {
        <section class="card">
          <h2>Keyword Sets</h2>
          <label>Name<input [(ngModel)]="keywordName" /></label
          ><label
            >Locale<select [(ngModel)]="locale">
              <option>en-IN</option>
              <option>hi-IN</option>
              <option>te-IN</option>
            </select></label
          ><label
            >Paste keywords<textarea
              [(ngModel)]="keywordPaste"
              placeholder="One keyword per line"
            ></textarea></label
          ><button type="button" (click)="saveKeywords()">Save Keyword Set</button
          ><button type="button" (click)="suggestKeywords()">AI Suggestions</button>
          <ul>
            @for (item of suggestions(); track item.keyword) {
              <li>
                {{ item.keyword }} <small>{{ item.category }} · AI Suggested</small>
              </li>
            }
          </ul>
        </section>
      }
      @if (tab() === 'tags') {
        <section class="card">
          <h2>Tags</h2>
          <label>Tag set name<input [(ngModel)]="tagName" /></label
          ><label
            >Tags<textarea [(ngModel)]="tagPaste" placeholder="One tag per line"></textarea></label
          ><button type="button" (click)="saveTags()">Save tags</button>
          <p>Tags are metadata preparation only and do not mutate Product tags automatically.</p>
        </section>
      }
      @if (tab() === 'history') {
        <section class="card">
          <h2>Analysis History</h2>
          <button type="button" (click)="loadHistory()">Refresh history</button>
          <ul>
            @for (item of history(); track item.id) {
              <li>
                v{{ item.artifact_version || '—' }} · {{ item.channel }} ·
                {{ item.overall_score }}/100 · {{ item.status }} · {{ item.locale }}
              </li>
            }
          </ul>
        </section>
      }
    </main>
  `,
  styles: [
    `
      .ai-shell {
        padding: 2rem;
        max-width: 1200px;
        margin: auto;
      }
      .ai-header {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
      }
      .seo-tabs {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
        margin: 1.5rem 0;
      }
      .seo-tabs button.active {
        font-weight: 700;
        border-bottom: 3px solid #176b85;
      }
      .card {
        border: 1px solid #d6e0e5;
        border-radius: 12px;
        padding: 1.25rem;
        margin: 1rem 0;
        background: #fff;
      }
      .controls {
        display: flex;
        gap: 1rem;
        flex-wrap: wrap;
        align-items: end;
      }
      .controls label,
      .card label {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        min-width: 150px;
      }
      input,
      select,
      textarea {
        padding: 0.55rem;
        border: 1px solid #aabac4;
        border-radius: 6px;
      }
      textarea {
        min-height: 100px;
      }
      .dimensions {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 0.75rem;
      }
      .dimensions div {
        padding: 0.75rem;
        background: #f3f7f8;
        border-radius: 8px;
      }
      .dimensions span,
      .dimensions small {
        display: block;
      }
      .score {
        font-size: 1.6rem;
        font-weight: 700;
      }
      .error {
        color: #a32020;
      }
    `,
  ],
})
export class AISeoComponent {
  private readonly api = inject(AIService);
  private readonly router = inject(Router);
  readonly tab = signal('overview');
  readonly loading = signal(false);
  readonly error = signal('');
  readonly analysis = signal<AISEOAnalysisResponse | null>(null);
  readonly history = signal<AISEOAnalysisResponse[]>([]);
  readonly suggestions = signal<AIKeywordSuggestion[]>([]);
  productId = '';
  artifactId = '';
  locale = 'en-IN';
  channel = 'canonical';
  primaryKeyword = '';
  keywordName = '';
  keywordPaste = '';
  tagName = '';
  tagPaste = '';
  dimensionEntries(): Array<[string, AISEODimension]> {
    return Object.entries(this.analysis()?.dimensions ?? {});
  }
  async analyze() {
    this.loading.set(true);
    this.error.set('');
    try {
      this.analysis.set(
        await this.api.seoAnalyze({
          product_id: this.productId,
          artifact_id: this.artifactId || undefined,
          channel: this.channel,
          locale: this.locale,
          primary_keyword: this.primaryKeyword || undefined,
        }),
      );
    } catch {
      this.error.set('SEO analysis is unavailable. Check the API connection and selected IDs.');
    } finally {
      this.loading.set(false);
    }
  }
  async recommendationAction(action: string, finding: AISEOFinding): Promise<void> {
    const current = this.analysis();
    if (!current) return;
    if (action === 'edit' && current.artifact_id) {
      await this.router.navigate(['/ai/artifacts', current.artifact_id], {
        queryParams: { field: finding.field, recommendation: finding.code },
      });
      return;
    }
    if (action === 'open_keywords') {
      this.tab.set('keywords');
      return;
    }
    if (action === 'reanalyze') {
      try {
        this.analysis.set(await this.api.seoReanalyze(current.id));
      } catch {
        this.error.set('SEO re-analysis is unavailable.');
      }
      return;
    }
    if (action === 'regenerate' && current.artifact_id) {
      if (!window.confirm('Queue a new reviewed Artifact generation for this recommendation?')) {
        return;
      }
      try {
        await this.api.studioRegenerate(current.artifact_id);
        this.error.set('Regeneration queued for review.');
      } catch (error) {
        this.error.set(AIService.errorMessage(error));
      }
    }
  }
  async loadHistory() {
    try {
      this.history.set(await this.api.seoAnalyses());
    } catch {
      this.error.set('Analysis history is unavailable.');
    }
  }
  async saveKeywords() {
    const values = this.keywordPaste
      .split(/\r?\n/)
      .map((value) => value.trim())
      .filter(Boolean);
    try {
      await this.api.seoCreateKeywords({
        name: this.keywordName || 'Product keywords',
        locale: this.locale,
        primary: values.slice(0, 1),
        secondary: values.slice(1),
      });
      this.error.set('Keyword Set saved.');
    } catch {
      this.error.set('Keyword Set could not be saved.');
    }
  }
  async suggestKeywords() {
    try {
      this.suggestions.set(
        await this.api.seoKeywordSuggestions({
          product_id: this.productId,
          locale: this.locale,
          channel: this.channel,
        }),
      );
    } catch {
      this.error.set('Keyword suggestions are unavailable.');
    }
  }
  async saveTags() {
    const tags = this.tagPaste
      .split(/\r?\n/)
      .map((value) => value.trim().replace(/^#/, ''))
      .filter(Boolean);
    try {
      await this.api.seoCreateTags({
        name: this.tagName || 'Product tags',
        product_id: this.productId || undefined,
        locale: this.locale,
        tags,
      });
      this.error.set('Tags saved as metadata.');
    } catch {
      this.error.set('Tags could not be saved.');
    }
  }
}
