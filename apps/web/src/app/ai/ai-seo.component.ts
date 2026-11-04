import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import { CommerceJourneyNavComponent } from '../shared/commerce-journey-nav.component';
import { ErrorStateComponent, LoadingStateComponent } from '../shared/state-components';
import type { BreadcrumbItem } from '../shared/ux-foundation.types';
import { PageHeaderComponent } from '../shared/page-header.component';
import { BusinessEntitySelectorsComponent } from '../shared/business-entity-selectors.component';

import type {
  AIKeywordSuggestion,
  AISEOAnalysisResponse,
  AISEODimension,
  AISEOFinding,
} from '@vayujit/shared';

import { AIService } from './ai.service';
type SavedSet = {
  id: string;
  name: string;
  product_id?: string | null;
  locale: string;
  version?: number;
  primary?: string[];
  secondary?: string[];
  tags?: string[];
};

@Component({
  selector: 'app-ai-seo',
  standalone: true,
  imports: [
    BreadcrumbsComponent,
    BusinessEntitySelectorsComponent,
    CommerceJourneyNavComponent,
    CommonModule,
    ErrorStateComponent,
    FormsModule,
    LoadingStateComponent,
    PageHeaderComponent,
    RouterLink,
  ],
  template: `
    <section class="ai-shell">
      <app-breadcrumbs [items]="breadcrumbs" />
      <app-page-header
        eyebrow="Create / SEO"
        title="SEO and content intelligence"
        description="Explainable website SEO and channel-specific marketplace search optimization."
      >
        <a page-header-actions routerLink="/ai/studio/bulk">Bulk generation</a>
      </app-page-header>
      <app-commerce-journey-nav current="seo" />
      <p class="ai-muted">
        SEO evidence describes keyword and content coverage only; it does not predict demand or
        guarantee ranking outcomes.
      </p>
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
        <app-error-state title="SEO analysis is unavailable" [message]="error()" />
      }
      @if (message()) {
        <p role="status">{{ message() }}</p>
      }
      @if (loading()) {
        <app-loading-state message="Loading saved SEO analysis..." />
      }
      @if (tab() === 'overview' || tab() === 'website' || tab() === 'marketplace') {
        <section class="card controls">
          <app-business-entity-selectors
            [showArtifact]="true"
            [productId]="productId"
            [artifactId]="artifactId"
            (productIdChange)="setProductContext($event)"
            (artifactIdChange)="artifactId = $event"
          />
          <label
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
          ><label
            >Saved keyword set<select [(ngModel)]="keywordSetId">
              <option value="">No saved set</option>
              @for (item of keywordSets(); track item.id) {
                <option [value]="item.id">{{ item.name }} — revision {{ item.version }}</option>
              }
            </select></label
          ><label>Primary keyword<input [(ngModel)]="primaryKeyword" /></label
          ><button type="button" (click)="analyze()" [disabled]="loading()">
            {{ loading() ? 'Analyzing...' : 'Analyze' }}
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
              - {{ currentAnalysis.channel }}
            </h2>
            <p class="score">Overall {{ currentAnalysis.overall_score }}/100</p>
            <p>
              Locale: {{ currentAnalysis.locale }} - Artifact version:
              {{ currentAnalysis.artifact_version || 'none' }} - Intent:
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
                  <strong>{{ finding.severity }}</strong> - {{ finding.field }} -
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
              Search volume unavailable - Keyword difficulty unavailable - CPC unavailable - Ranking
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
          ><button type="button" (click)="saveKeywords()" [disabled]="metadataBusy()">
            Save Keyword Set</button
          ><button type="button" (click)="suggestKeywords()">AI Suggestions</button>
          <ul>
            @for (item of suggestions(); track item.keyword) {
              <li>
                {{ item.keyword }} <small>{{ item.category }} - AI Suggested</small>
              </li>
            }
          </ul>
          <button type="button" (click)="loadSets()">Refresh saved metadata</button>
          <ul aria-label="Saved keyword sets">
            @for (item of keywordSets(); track item.id) {
              <li>
                {{ item.name }} — revision {{ item.version }}
                <button type="button" (click)="editSet('keywords', item)">
                  Edit {{ item.name }}
                </button>
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
          ><button type="button" (click)="saveTags()" [disabled]="metadataBusy()">Save tags</button>
          <p>Tags are metadata preparation only and do not mutate Product tags automatically.</p>
          <button type="button" (click)="loadSets()">Refresh saved metadata</button>
          <ul aria-label="Saved tag sets">
            @for (item of tagSets(); track item.id) {
              <li>
                {{ item.name }} — {{ item.tags?.join(', ') }}
                <button type="button" (click)="editSet('tags', item)">Edit {{ item.name }}</button>
              </li>
            }
          </ul>
        </section>
      }
      @if (tab() === 'history') {
        <section class="card">
          <h2>Analysis History</h2>
          <button type="button" (click)="loadHistory()">Refresh history</button>
          <ul>
            @for (item of history(); track item.id) {
              <li>
                v{{ item.artifact_version || '-' }} - {{ item.channel }} -
                {{ item.overall_score }}/100 - {{ item.status }} - {{ item.locale }}
                <button type="button" (click)="analysis.set(item); tab.set('overview')">
                  Open saved analysis
                </button>
                <button type="button" (click)="reanalyze(item)">Re-analyze saved snapshot</button>
                @if (item.artifact_id) {
                  <a [routerLink]="['/ai/artifacts', item.artifact_id]">Review analyzed artifact</a>
                }
              </li>
            }
          </ul>
        </section>
      }
    </section>
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
  private readonly route = inject(ActivatedRoute);
  readonly tab = signal('overview');
  readonly loading = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  readonly analysis = signal<AISEOAnalysisResponse | null>(null);
  readonly history = signal<AISEOAnalysisResponse[]>([]);
  readonly suggestions = signal<AIKeywordSuggestion[]>([]);
  readonly keywordSets = signal<SavedSet[]>([]);
  readonly metadataBusy = signal(false);
  readonly tagSets = signal<SavedSet[]>([]);
  private editingKeyword: Record<string, unknown> | null = null;
  private editingTag: Record<string, unknown> | null = null;
  constructor() {
    this.productId = this.route.snapshot.queryParamMap.get('product') || '';
    this.artifactId = this.route.snapshot.queryParamMap.get('artifact') || '';
    this.keywordSetId = this.route.snapshot.queryParamMap.get('keywords') || '';
    void this.loadSets();
  }
  async loadSets(): Promise<void> {
    const contextProduct = this.productId;
    try {
      const [keywords, tags] = await Promise.all([
        this.api.seoSets('keywords'),
        this.api.seoSets('tags'),
      ]);
      if (this.productId !== contextProduct) return;
      const scoped = (items: Record<string, unknown>[]) =>
        items.filter((i) => !this.productId || i['product_id'] === this.productId) as SavedSet[];
      this.keywordSets.set(scoped(keywords));
      this.tagSets.set(scoped(tags));
    } catch {
      this.error.set('Saved SEO metadata is unavailable. Retry the authenticated connection.');
    }
  }
  setProductContext(id: string): void {
    if (this.productId === id) return;
    this.productId = id;
    this.keywordSetId = '';
    this.editingKeyword = null;
    this.editingTag = null;
    this.analysis.set(null);
    this.history.set([]);
    this.keywordSets.set([]);
    this.tagSets.set([]);
    void this.loadSets();
  }
  editSet(kind: 'keywords' | 'tags', item: SavedSet): void {
    if (kind === 'keywords') {
      this.editingKeyword = { ...item };
      this.keywordName = item.name;
      this.keywordPaste = [...(item.primary || []), ...(item.secondary || [])].join('\n');
    } else {
      this.editingTag = { ...item };
      this.tagName = item.name;
      this.tagPaste = (item.tags || []).join('\n');
    }
    this.locale = item.locale;
  }
  async reanalyze(item: AISEOAnalysisResponse): Promise<void> {
    try {
      this.analysis.set(await this.api.seoReanalyze(item.id));
      this.tab.set('overview');
      await this.loadHistory();
    } catch {
      this.error.set('SEO re-analysis is unavailable.');
    }
  }
  productId = '';
  readonly breadcrumbs: BreadcrumbItem[] = [
    { label: 'Products', url: '/products' },
    { label: 'SEO' },
  ];
  artifactId = '';
  locale = 'en-IN';
  channel = 'canonical';
  primaryKeyword = '';
  keywordSetId = '';
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
          keyword_set_id: this.keywordSetId || undefined,
          channel: this.channel,
          locale: this.locale,
          primary_keyword: this.primaryKeyword || undefined,
        }),
      );
      await this.router.navigate([], {
        relativeTo: this.route,
        queryParams: {
          product: this.productId,
          artifact: this.artifactId || null,
          keywords: this.keywordSetId || null,
        },
      });
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
        this.message.set('Regeneration queued for review.');
      } catch (error) {
        this.error.set(AIService.errorMessage(error));
      }
    }
  }
  async loadHistory() {
    try {
      this.history.set(
        (await this.api.seoAnalyses()).filter(
          (a) => !this.productId || a.product_id === this.productId,
        ),
      );
    } catch {
      this.error.set('Analysis history is unavailable.');
    }
  }
  async saveKeywords() {
    if (this.metadataBusy()) return;
    this.metadataBusy.set(true);
    this.error.set('');
    this.message.set('');
    const values = this.keywordPaste
      .split(/\r?\n/)
      .map((value) => value.trim())
      .filter(Boolean);
    try {
      const data = {
        ...this.editingKeyword,
        name: this.keywordName || 'Product keywords',
        product_id: this.productId || undefined,
        locale: this.locale,
        primary: values.slice(0, 1),
        secondary: values.slice(1),
      };
      if (this.editingKeyword)
        await this.api.seoUpdateSet('keywords', String(this.editingKeyword['id']), data);
      else await this.api.seoCreateKeywords(data);
      this.editingKeyword = null;
      await this.loadSets();
      this.message.set('Keyword Set saved.');
    } catch {
      this.error.set('Keyword Set could not be saved.');
    } finally {
      this.metadataBusy.set(false);
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
    if (this.metadataBusy()) return;
    this.metadataBusy.set(true);
    this.error.set('');
    this.message.set('');
    const tags = this.tagPaste
      .split(/\r?\n/)
      .map((value) => value.trim().replace(/^#/, ''))
      .filter(Boolean);
    try {
      const data = {
        ...this.editingTag,
        name: this.tagName || 'Product tags',
        product_id: this.productId || undefined,
        locale: this.locale,
        tags,
      };
      if (this.editingTag) await this.api.seoUpdateSet('tags', String(this.editingTag['id']), data);
      else await this.api.seoCreateTags(data);
      this.editingTag = null;
      await this.loadSets();
      this.message.set('Tags saved as metadata.');
    } catch {
      this.error.set('Tags could not be saved.');
    } finally {
      this.metadataBusy.set(false);
    }
  }
}
