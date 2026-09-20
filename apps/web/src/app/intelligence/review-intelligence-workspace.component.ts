import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  ReviewAnalysis,
  ReviewAnalysisDetail,
  ReviewAnalysisItem,
  ReviewChangeComparisonDetail,
  ReviewContext,
  ReviewGapAnalysisDetail,
  ReviewIngestionBatch,
  ReviewIntelligenceService,
  ReviewRecord,
  ReviewSnapshot,
  ReviewStatistics,
} from './review-intelligence.service';

@Component({
  selector: 'app-review-intelligence-workspace',
  standalone: true,
  imports: [FormsModule, RouterLink, JsonPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="workspace" aria-labelledby="reviews-title">
      <header class="page-header">
        <div>
          <p class="eyebrow">Intelligence / Reviews</p>
          <h1 id="reviews-title">Review Intelligence</h1>
          <p class="lede">
            Customer-feedback evidence with provenance, freshness, and immutable snapshots.
          </p>
        </div>
        <a routerLink="/intelligence">Back to Intelligence</a>
      </header>
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }
      @if (loading()) {
        <p role="status" aria-live="polite">Loading review intelligence...</p>
      }
      <section class="panel">
        <h2>Review contexts</h2>
        <form (ngSubmit)="createContext()">
          <label>Name <input name="name" [(ngModel)]="contextName" required /></label
          ><label
            >Product ID
            <input name="product" [(ngModel)]="productId" placeholder="Optional UUID" /></label
          ><label>Marketplace <input name="marketplace" [(ngModel)]="marketplace" /></label
          ><label>Market <input name="market" [(ngModel)]="market" /></label
          ><button type="submit" [disabled]="loading() || !contextName.trim()">
            Create context
          </button>
        </form>
        @for (context of contexts(); track context.id) {
          <button class="list-item" type="button" (click)="selectContext(context)">
            <strong>{{ context.name }}</strong
            ><span
              >{{ context.marketplace || 'Unspecified' }} ? {{ context.status }} ? v{{
                context.version
              }}</span
            >
          </button>
        } @empty {
          <p>No review contexts yet.</p>
        }
      </section>
      @if (selectedContext(); as context) {
        <section class="panel">
          <h2>{{ context.name }}</h2>
          <p class="muted">
            Reviews remain customer-feedback evidence; they do not imply sales, demand, revenue, or
            market size.
          </p>
          <form (ngSubmit)="addReview()">
            <label
              >Rating
              <input
                name="rating"
                [(ngModel)]="rating"
                inputmode="decimal"
                placeholder="Optional" /></label
            ><label
              >Scale
              <input
                name="scale"
                [(ngModel)]="ratingScale"
                inputmode="decimal"
                placeholder="5 or 10" /></label
            ><label>Title <input name="title" [(ngModel)]="title" /></label
            ><label>Review body <textarea name="body" [(ngModel)]="body" rows="3"></textarea></label
            ><label
              >Provider review ID <input name="reviewId" [(ngModel)]="providerReviewId" /></label
            ><label>Provider <input name="provider" [(ngModel)]="provider" /></label
            ><button type="submit" [disabled]="loading()">Import local review</button>
          </form>
        </section>
        @if (statistics(); as stats) {
          <section class="summary-grid">
            <article>
              <span>Reviews</span><strong>{{ stats.review_count }}</strong>
            </article>
            <article>
              <span>Rated</span><strong>{{ stats.rated_review_count }}</strong>
            </article>
            <article>
              <span>Sources</span><strong>{{ sourceCount(stats) }}</strong>
            </article>
            <article>
              <span>Freshness</span
              ><strong>{{ stats.freshness_counts['STALE'] || 0 }} stale</strong>
            </article>
          </section>
        }
        <section class="panel">
          <h2>Deterministic ingestion</h2>
          <p class="muted">
            Local fixtures only. Live read-only providers fail closed until configured.
          </p>
          <form (ngSubmit)="ingestReviews()">
            <label
              >Provider <input name="ingestionProvider" [(ngModel)]="ingestionProvider"
            /></label>
            <label
              >Mode
              <select name="ingestionMode" [(ngModel)]="ingestionMode">
                <option value="LOCAL_FIXTURE">LOCAL_FIXTURE</option>
                <option value="DISABLED">DISABLED</option>
                <option value="LIVE_READ_ONLY">LIVE_READ_ONLY</option>
              </select></label
            >
            <label
              >Records JSON
              <textarea name="ingestionRecords" [(ngModel)]="ingestionRecords" rows="5"></textarea>
            </label>
            <button type="submit" [disabled]="loading()">Ingest fixture batch</button>
          </form>
          @for (batch of ingestionBatches(); track batch.id) {
            <p class="list-item">
              <strong>{{ batch.status }} � {{ batch.provider }}</strong
              ><span
                >{{ batch.accepted_count }} accepted � {{ batch.rejected_count }} rejected �
                {{ batch.duplicate_count }} duplicates</span
              >
            </p>
          } @empty {
            <p>No ingestion batches yet.</p>
          }
        </section>
        <section class="panel">
          <h2>Reviews</h2>
          @for (review of reviews(); track review.id) {
            <article class="list-item">
              <strong
                >{{ review.rating || 'Unrated'
                }}{{ review.rating_scale ? ' / ' + review.rating_scale : '' }} ?
                {{ review.title || 'Untitled review' }}</strong
              ><span
                >{{ review.provider }} ? {{ review.verified_purchase }} ?
                {{ review.freshness_status }} ? {{ review.evidence_state }}</span
              >
              <p>{{ review.body || 'No review body supplied.' }}</p>
            </article>
          } @empty {
            <p>No reviews imported yet.</p>
          }
        </section>
        <section class="panel">
          <h2>Deterministic analysis</h2>
          <p class="muted">
            Local rules classify review text with explicit evidence and limitations. No live AI
            provider is called.
          </p>
          <button type="button" (click)="runAnalysis()" [disabled]="loading()">
            Analyze current snapshot
          </button>
          @if (analysis(); as result) {
            <p role="status">
              {{ result.analysis.status }} · {{ result.analysis.included_records }} included ·
              {{ result.analysis.excluded_records }} excluded
            </p>
            <div class="list-item">
              <strong>Sentiment</strong><span>{{ sentimentLabel(result) }}</span>
            </div>
            @for (item of analysisItems(result, 'PAIN_POINT'); track item.id) {
              <div class="list-item">
                <strong>Pain point: {{ item.canonical_label }}</strong
                ><span
                  >{{ item.sentiment }} · {{ item.support_count }} supporting reviews ·
                  {{ item.confidence }} confidence</span
                >
              </div>
            }
            @for (item of analysisItems(result, 'PRAISED_ATTRIBUTE'); track item.id) {
              <div class="list-item">
                <strong>Praised: {{ item.canonical_label }}</strong
                ><span>{{ item.support_count }} supporting reviews</span>
              </div>
            }
          }
        </section>
        <section class="panel">
          <h2>Product gaps and opportunity signals</h2>
          <p class="muted">
            Review-derived signals only. These are hypotheses requiring explicit validation, not
            demand, revenue, or commercial scores.
          </p>
          <button type="button" (click)="deriveGapAnalysis()" [disabled]="loading() || !analysis()">
            Derive product gaps
          </button>
          @if (gapAnalysis(); as gaps) {
            <p role="status">
              {{ gaps.analysis.status }} · {{ gaps.product_gaps.length }} product gaps ·
              {{ gaps.opportunity_signals.length }} opportunity signals
            </p>
            @for (gap of gaps.product_gaps; track gap.id) {
              <article class="list-item">
                <strong>{{ gap.gap_type }}: {{ gap.canonical_label }}</strong>
                <span
                  >Review-derived signal · {{ gap.support_classification }} ·
                  {{ gap.evidence_strength }} evidence</span
                >
                <span
                  >Requires validation:
                  {{ gap.required_validations.join(', ') || 'None recorded' }}</span
                >
                <p>{{ gap.hypothesis }}</p>
              </article>
            }
            @for (signal of gaps.opportunity_signals; track signal.id) {
              <article class="list-item">
                <strong>{{ signal.signal_type }}: {{ signal.canonical_label }}</strong>
                <span>{{ signal.status }} · {{ signal.confidence }} confidence</span>
                <span
                  >Requires validation:
                  {{ signal.required_validations.join(', ') || 'None recorded' }}</span
                >
                <p>{{ signal.explanation }}</p>
              </article>
            }
          }
        </section>
        <section class="panel">
          <h2>Review evidence changed</h2>
          <p class="muted">
            Compare two immutable review analyses to surface evidence changes only. This does not
            infer market demand, sales, revenue, or commercial value.
          </p>
          <form (ngSubmit)="compareReviewEvidence()">
            <label
              >Baseline analysis
              <select name="baselineAnalysisId" [(ngModel)]="baselineAnalysisId">
                <option value="">Select baseline</option>
                @for (item of availableAnalyses(); track item.id) {
                  <option [value]="item.id">
                    v{{ item.snapshot_version }} · {{ item.status }}
                  </option>
                }
              </select>
            </label>
            <label
              >Current analysis
              <select name="currentAnalysisId" [(ngModel)]="currentAnalysisId">
                <option value="">Select current</option>
                @for (item of availableAnalyses(); track item.id) {
                  <option [value]="item.id">
                    v{{ item.snapshot_version }} · {{ item.status }}
                  </option>
                }
              </select>
            </label>
            <button
              type="submit"
              [disabled]="loading() || !baselineAnalysisId || !currentAnalysisId"
            >
              Compare review evidence
            </button>
          </form>
          @if (changeComparison(); as comparison) {
            <p role="status">
              {{ comparison.comparison.status }} · {{ comparison.events.length }} evidence changes ·
              {{ comparison.comparison.created_at }}
            </p>
            @for (event of comparison.events; track event.id) {
              <article class="list-item">
                <strong>{{ event.change_type }} · {{ event.subject_key }}</strong>
                <span
                  >{{ event.baseline_support }}/{{ event.baseline_cohort }} →
                  {{ event.current_support }}/{{ event.current_cohort }} · {{ event.materiality }} ·
                  {{ event.status }}</span
                >
                <span
                  >{{ event.confidence }} confidence · {{ event.freshness | json }} ·
                  {{ event.alert_eligibility }}</span
                >
                <span
                  >Limitations: {{ event.limitations.join(', ') || 'None recorded' }} · Research
                  gaps: {{ event.research_gaps.join(', ') || 'None recorded' }}</span
                >
                <p>{{ event.explanation }}</p>
              </article>
            } @empty {
              <p>No evidence changes were detected for this comparison.</p>
            }
          } @else {
            <p>No review evidence comparison selected.</p>
          }
        </section>
        <section class="panel">
          <h2>Snapshots</h2>
          <button type="button" (click)="createSnapshot()" [disabled]="loading()">
            Create immutable snapshot
          </button>
          @for (snapshot of snapshots(); track snapshot.id) {
            <p class="list-item">
              <strong>Snapshot v{{ snapshot.snapshot_version }}</strong
              ><span>{{ snapshot.review_count }} reviews ? {{ snapshot.input_fingerprint }}</span>
            </p>
          } @empty {
            <p>No snapshots yet.</p>
          }
        </section>
      }
      @if (doctor(); as value) {
        <section class="panel">
          <h2>Foundation integrity</h2>
          <p role="status">
            {{ value.status }} ? {{ value.counts['duplicate_fingerprints'] || 0 }} duplicate
            fingerprints
          </p>
        </section>
      }
    </main>
  `,
  styles: [
    `
      .workspace {
        max-width: 1100px;
        margin: 0 auto;
      }
      .page-header {
        display: flex;
        justify-content: space-between;
        gap: 2rem;
      }
      .panel {
        background: #fff;
        border: 1px solid #d3e0e2;
        border-radius: 1rem;
        padding: 1.5rem;
        margin: 1.25rem 0;
      }
      form {
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
        align-items: end;
      }
      label {
        display: grid;
        gap: 0.3rem;
        min-width: 10rem;
        flex: 1;
      }
      input,
      textarea {
        font: inherit;
        padding: 0.55rem;
        border: 1px solid #9bb5b8;
        border-radius: 0.35rem;
      }
      button {
        font: inherit;
        padding: 0.6rem 1rem;
        border: 0;
        border-radius: 0.4rem;
        background: #185b72;
        color: #fff;
        cursor: pointer;
      }
      .list-item {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        width: 100%;
        text-align: left;
        margin-top: 0.6rem;
        padding: 0.8rem;
        border: 1px solid #c7d8da;
        border-radius: 0.5rem;
        background: #f8fbfb;
        color: #123;
      }
      .summary-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
      }
      .summary-grid article {
        background: #fff;
        border: 1px solid #d3e0e2;
        border-radius: 0.75rem;
        padding: 1rem;
      }
      .summary-grid span {
        display: block;
        color: #52777d;
      }
      .summary-grid strong {
        font-size: 1.7rem;
      }
      @media (max-width: 700px) {
        .page-header {
          display: block;
        }
        .summary-grid {
          grid-template-columns: repeat(2, 1fr);
        }
      }
    `,
  ],
})
export class ReviewIntelligenceWorkspaceComponent implements OnInit {
  private readonly service = inject(ReviewIntelligenceService);
  readonly contexts = signal<ReviewContext[]>([]);
  readonly selectedContext = signal<ReviewContext | null>(null);
  readonly reviews = signal<ReviewRecord[]>([]);
  readonly ingestionBatches = signal<ReviewIngestionBatch[]>([]);
  readonly snapshots = signal<ReviewSnapshot[]>([]);
  readonly statistics = signal<ReviewStatistics | null>(null);
  readonly analysis = signal<ReviewAnalysisDetail | null>(null);
  readonly availableAnalyses = signal<ReviewAnalysis[]>([]);
  readonly changeComparison = signal<ReviewChangeComparisonDetail | null>(null);
  readonly gapAnalysis = signal<ReviewGapAnalysisDetail | null>(null);
  readonly doctor = signal<{ status: string; counts: Record<string, number> } | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  contextName = 'Product reviews';
  productId = '';
  marketplace = 'amazon';
  market = 'IN';
  rating = '';
  ratingScale = '5';
  title = '';
  body = '';
  providerReviewId = '';
  provider = 'manual';
  ingestionProvider = 'LOCAL_FIXTURE';
  ingestionMode = 'LOCAL_FIXTURE';
  baselineAnalysisId = '';
  currentAnalysisId = '';
  ingestionRecords =
    '[{"id":"fixture-1","rating":"5","rating_scale":"5","title":"Useful","body":"Local fixture review"}]';
  ngOnInit(): void {
    void this.refresh();
  }
  async refresh(): Promise<void> {
    await this.run(async () => {
      this.contexts.set(await this.service.contexts());
      this.doctor.set(await this.service.doctor());
      if (this.selectedContext()) await this.selectContext(this.selectedContext()!);
    }, 'Review data is unavailable. Check the authenticated API connection.');
  }
  async createContext(): Promise<void> {
    await this.run(async () => {
      await this.service.createContext({
        name: this.contextName.trim(),
        product_id: this.productId.trim() || null,
        marketplace: this.marketplace.trim(),
        market: this.market.trim(),
        status: 'ACTIVE',
        idempotency_key: `review-context-${this.contextName.trim()}-${this.market.trim()}`,
      });
      await this.refresh();
    }, 'The review context could not be created.');
  }
  async selectContext(context: ReviewContext): Promise<void> {
    this.selectedContext.set(context);
    const [page, stats, snapshots, batches, gapAnalysis, analyses, changeComparison] =
      await Promise.all([
        this.service.reviews(context.id),
        this.service.statistics(context.id),
        this.service.snapshots(context.id),
        this.service.ingestions(context.id),
        this.service.currentGapAnalysis(context.id),
        this.service.analyses(context.id),
        this.service.currentChangeComparison(context.id),
      ]);
    this.reviews.set(page.items);
    this.statistics.set(stats);
    this.snapshots.set(snapshots);
    this.ingestionBatches.set(batches);
    this.gapAnalysis.set(gapAnalysis);
    this.availableAnalyses.set(analyses);
    this.changeComparison.set(changeComparison);
    if (analyses.length >= 2 && !this.baselineAnalysisId && !this.currentAnalysisId) {
      this.baselineAnalysisId = analyses[analyses.length - 2].id;
      this.currentAnalysisId = analyses[analyses.length - 1].id;
    }
  }
  async ingestReviews(): Promise<void> {
    const context = this.selectedContext();
    if (!context) return;
    await this.run(async () => {
      const records = JSON.parse(this.ingestionRecords) as unknown;
      if (!Array.isArray(records)) throw new Error('records must be an array');
      await this.service.ingest(context.id, {
        provider: this.ingestionProvider.trim() || 'LOCAL_FIXTURE',
        mode: this.ingestionMode,
        records,
        idempotency_key: `review-ingestion-${Date.now()}`,
      });
      await this.selectContext(context);
    }, 'The review ingestion batch could not be completed.');
  }
  async addReview(): Promise<void> {
    const context = this.selectedContext();
    if (!context) return;
    await this.run(async () => {
      const payload: Record<string, unknown> = {
        provider: this.provider.trim() || 'manual',
        provider_review_id: this.providerReviewId.trim() || null,
        rating: this.rating.trim() ? this.rating.trim() : null,
        rating_scale: this.ratingScale.trim() ? this.ratingScale.trim() : null,
        title: this.title.trim() || null,
        body: this.body || null,
        source: {
          source_reference: `${this.provider || 'manual'}:${this.providerReviewId || 'local'}`,
          provider: this.provider.trim() || 'manual',
          source_type: 'manual',
        },
      };
      await this.service.createReview(context.id, payload);
      this.title = '';
      this.body = '';
      this.providerReviewId = '';
      await this.selectContext(context);
    }, 'The review could not be imported.');
  }
  async runAnalysis(): Promise<void> {
    const context = this.selectedContext();
    if (!context) return;
    await this.run(async () => {
      const result = await this.service.createAnalysis(context.id, { mode: 'LOCAL_FIXTURE' });
      this.analysis.set(result);
    }, 'The deterministic review analysis could not be completed.');
  }
  async compareReviewEvidence(): Promise<void> {
    const context = this.selectedContext();
    if (!context || !this.baselineAnalysisId || !this.currentAnalysisId) return;
    await this.run(async () => {
      this.changeComparison.set(
        await this.service.createChangeComparison(context.id, {
          baseline_analysis_id: this.baselineAnalysisId,
          current_analysis_id: this.currentAnalysisId,
        }),
      );
    }, 'The review evidence comparison could not be completed.');
  }
  async deriveGapAnalysis(): Promise<void> {
    const context = this.selectedContext();
    const analysis = this.analysis();
    if (!context || !analysis) return;
    await this.run(async () => {
      this.gapAnalysis.set(await this.service.createGapAnalysis(context.id, analysis.analysis.id));
    }, 'The product-gap analysis could not be completed.');
  }

  analysisItems(result: ReviewAnalysisDetail, type: string): ReviewAnalysisItem[] {
    return result.items.filter((item) => item.item_type === type);
  }
  sentimentLabel(result: ReviewAnalysisDetail): string {
    return (
      Object.entries(result.analysis.sentiment_distribution) as Array<[string, { count: number }]>
    )
      .map(([key, value]) => `${key}: ${value.count}`)
      .join(' · ');
  }
  async createSnapshot(): Promise<void> {
    const context = this.selectedContext();
    if (!context) return;
    await this.run(async () => {
      await this.service.createSnapshot(context.id);
      await this.selectContext(context);
    }, 'The review snapshot could not be created.');
  }
  sourceCount(stats: ReviewStatistics): number {
    return Object.keys(stats.source_counts).length;
  }
  private async run(action: () => Promise<void>, message: string): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      await action();
    } catch {
      this.error.set(message);
    } finally {
      this.loading.set(false);
    }
  }
}
