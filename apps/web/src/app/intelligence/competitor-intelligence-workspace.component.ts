import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import { EvidenceCardComponent } from '../shared/evidence-card.component';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { StatusBadgeComponent } from '../shared/status-badge.component';
import type { BreadcrumbItem, StatusTone } from '../shared/ux-foundation.types';

import {
  CompetitorChangeEvent,
  CompetitorCommercialAnalysis,
  CompetitorContext,
  CompetitorDiscoveryCandidate,
  CompetitorEntity,
  CompetitorIntelligenceService,
  CompetitorProduct,
} from './competitor-intelligence.service';

@Component({
  selector: 'app-competitor-intelligence-workspace',
  standalone: true,
  imports: [
    DatePipe,
    FormsModule,
    RouterLink,
    BreadcrumbsComponent,
    EvidenceCardComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    StatusBadgeComponent,
  ],
  styleUrl: './intelligence-workspace.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-breadcrumbs [items]="breadcrumbs" />
    @if (loading()) {
      <app-loading-state message="Loading observed competitor intelligence..." />
    }
    @if (!contexts().length && !loading() && !error()) {
      <app-empty-state
        title="No competitor research yet"
        message="Create a research context to review observed competitors and changes."
      />
    }
    <main class="workspace" aria-labelledby="competitor-title">
      <header class="page-header">
        <div>
          <p class="eyebrow">Intelligence / Competitors</p>
          <h1 id="competitor-title">Competitor intelligence</h1>
          <p class="lede">
            Deterministic, owner-scoped discovery with explainable matching and human review.
          </p>
        </div>
        <a routerLink="/intelligence">Back to Intelligence</a>
      </header>

      @if (error()) {
        <app-error-state
          title="Competitor data is unavailable"
          [message]="error()"
          retryLabel="Retry"
          (retry)="refresh()"
        />
        <p class="error" role="alert">{{ error() }}</p>
      }
      @if (loading()) {
        <p role="status" aria-live="polite">Loading competitor intelligence...</p>
      }

      <section class="panel" aria-labelledby="context-title">
        <h2 id="context-title">Research contexts</h2>
        <p class="muted">
          Contexts attach competitor evidence to a Product Opportunity, Product, or Brand.
        </p>
        <form (ngSubmit)="createContext()">
          <label
            >Product Opportunity ID
            <input name="subject" [(ngModel)]="subjectReference" required />
          </label>
          <label>Marketplace <input name="marketplace" [(ngModel)]="marketplace" /></label>
          <label>Market <input name="market" [(ngModel)]="market" /></label>
          <button type="submit" [disabled]="loading() || !subjectReference.trim()">
            Create context
          </button>
        </form>
        @for (context of contexts(); track context.id) {
          <button class="list-item" type="button" (click)="selectContext(context)">
            <strong>{{ context.marketplace || 'Unspecified marketplace' }}</strong>
            <span>{{ context.subject_type }} · {{ context.status }} · v{{ context.version }}</span>
          </button>
        } @empty {
          <p>No competitor contexts yet.</p>
        }
      </section>

      <section class="panel" aria-labelledby="entity-title">
        <h2 id="entity-title">Competitor entities</h2>
        <form (ngSubmit)="createEntity()">
          <label>Display name <input name="entityName" [(ngModel)]="entityName" required /></label>
          <label
            >Canonical name <input name="canonicalName" [(ngModel)]="canonicalName" required
          /></label>
          <label
            >Type
            <select name="entityType" [(ngModel)]="entityType">
              @for (value of entityTypes; track value) {
                <option [value]="value">{{ value }}</option>
              }
            </select>
          </label>
          <button
            type="submit"
            [disabled]="loading() || !entityName.trim() || !canonicalName.trim()"
          >
            Add entity
          </button>
        </form>
        @for (entity of entities(); track entity.id) {
          <p class="list-item">
            <strong>{{ entity.display_name }}</strong
            ><span>{{ entity.entity_type }} · {{ entity.evidence_state }}</span>
          </p>
        } @empty {
          <p>No competitor entities yet.</p>
        }
      </section>

      @if (selectedContext(); as context) {
        <app-evidence-card
          title="Observed competitor facts"
          classification="OBSERVED"
          summary="Competitor identity, availability, pricing, ratings, and review attributes remain source-backed observations."
          source="Competitor Intelligence"
        />
        <section class="panel" aria-labelledby="discovery-title">
          <h2 id="discovery-title">Discovery and identity review</h2>
          <p class="muted">
            LOCAL_FIXTURE is deterministic and read-only; live providers fail closed until
            configured.
          </p>
          <button type="button" (click)="discover(context)" [disabled]="loading()">
            Run local discovery
          </button>
          @for (candidate of discoveryCandidates(); track candidate.id) {
            <article class="list-item">
              <strong>{{ candidate.raw_title }}</strong>
              <span
                >{{ candidate.identity_state }} &middot; {{ candidate.match_level }} &middot;
                {{ candidate.evidence_state }}</span
              >
              <small>Signals: {{ candidate.supporting_signals.join(', ') || 'none' }}</small>
              <button
                type="button"
                (click)="resolveCandidate(candidate, 'confirm')"
                [disabled]="loading()"
              >
                Confirm
              </button>
              <button
                type="button"
                (click)="resolveCandidate(candidate, 'reject')"
                [disabled]="loading()"
              >
                Reject
              </button>
              <button
                type="button"
                (click)="resolveCandidate(candidate, 'ambiguous')"
                [disabled]="loading()"
              >
                Mark ambiguous
              </button>
            </article>
          } @empty {
            <p>No discovery candidates yet.</p>
          }
        </section>
        <section class="panel" aria-labelledby="commercial-title">
          <h2 id="commercial-title">Pricing, positioning, and assortment</h2>
          <p class="muted">
            Deterministic commercial analysis uses the confirmed evidence in this context. Currency
            mismatches remain non-comparable and research gaps stay visible.
          </p>
          <button type="button" (click)="runCommercialAnalysis(context)" [disabled]="loading()">
            Run commercial analysis
          </button>
          @if (commercialAnalysis(); as analysis) {
            <app-evidence-card
              title="Derived competitor analysis"
              classification="DERIVED"
              summary="Pricing, assortment, positioning, and concentration are derived from observed competitor evidence; they are not a market-attractiveness verdict."
              source="Competitor Intelligence"
            />
            <article class="list-item" aria-label="Commercial analysis summary">
              <strong
                >{{ analysis.status }} ·
                {{ analysis.pricing_analysis['currency'] || 'NOT_COMPARABLE' }}</strong
              >
              <span
                >Calculation {{ analysis.calculation_version }} ·
                {{ analysis.pricing_analysis['currency'] || 'Currency unknown' }}</span
              >
              <small
                >Pricing, concentration, ratings, assortment, positioning, and evidence coverage are
                versioned.</small
              >
            </article>
          } @else {
            <p>No commercial analysis has been run for this context.</p>
          }
        </section>
        <section class="panel" aria-labelledby="changes-title">
          <h2 id="changes-title">Competitive changes</h2>
          <p class="muted">
            Reproducible changes compare immutable commercial analyses. Materiality is not a
            business recommendation; unresolved evidence remains visible for review.
          </p>
          <button type="button" (click)="runChangeComparison(context)" [disabled]="loading()">
            Run change comparison
          </button>
          @if (changes().length) {
            <div role="region" aria-label="Competitive change timeline">
              @for (change of changes(); track change.id) {
                <article class="list-item">
                  <strong>{{ change.change_type }} · {{ change.materiality }}</strong>
                  <small
                    >Observed value: {{ change.old_value ?? 'Not available' }} →
                    {{ change.new_value ?? 'Not available' }}</small
                  >
                  <span
                    >{{ change.status }} · {{ change.alert_eligibility }} ·
                    {{ change.evidence_state }}</span
                  >
                  <small>
                    {{ change.observed_or_derived }} ·
                    {{
                      change.percentage_delta
                        ? change.percentage_delta + '%'
                        : 'No percentage delta'
                    }}
                    · {{ change.freshness_state }}
                  </small>
                </article>
              }
            </div>
          } @else {
            <p>No competitive changes have been compared for this context.</p>
          }
        </section>
        <section class="panel" aria-labelledby="product-title">
          <h2 id="product-title">Products in {{ context.marketplace || 'this context' }}</h2>
          <form (ngSubmit)="createProduct()">
            <label>Title <input name="productTitle" [(ngModel)]="productTitle" required /></label>
            <label>External ID <input name="externalId" [(ngModel)]="externalId" required /></label>
            <button
              type="submit"
              [disabled]="loading() || !productTitle.trim() || !externalId.trim()"
            >
              Add competitor product
            </button>
          </form>
          @for (product of products(); track product.id) {
            <article class="list-item">
              <strong>{{ product.title }}</strong>
              <span>{{ product.external_identifier }} · {{ product.identity_state }}</span>
              <small>Last observed {{ product.last_observed | date: 'medium' }}</small>
              <button type="button" (click)="confirmIdentity(product)" [disabled]="loading()">
                Mark confirmed
              </button>
            </article>
          } @empty {
            <p>No competitor products yet.</p>
          }
        </section>
      }

      @if (doctor(); as value) {
        <app-status-badge
          [status]="value.status"
          [label]="value.status"
          [tone]="statusTone(value.status)"
        />
        <section class="panel" aria-labelledby="doctor-title">
          <h2 id="doctor-title">Foundation integrity</h2>
          <p role="status">{{ value.status }} · owner-scoped lineage checks</p>
        </section>
      }
    </main>
  `,
})
export class CompetitorIntelligenceWorkspaceComponent implements OnInit {
  private readonly service = inject(CompetitorIntelligenceService);
  readonly contexts = signal<CompetitorContext[]>([]);
  readonly entities = signal<CompetitorEntity[]>([]);
  readonly products = signal<CompetitorProduct[]>([]);
  readonly discoveryCandidates = signal<CompetitorDiscoveryCandidate[]>([]);
  readonly commercialAnalysis = signal<CompetitorCommercialAnalysis | null>(null);
  readonly changes = signal<CompetitorChangeEvent[]>([]);
  private discoveryRequestId = '';
  readonly selectedContext = signal<CompetitorContext | null>(null);
  readonly doctor = signal<{ status: string } | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly entityTypes = ['UNKNOWN', 'BRAND', 'SELLER', 'MANUFACTURER', 'MERCHANT'];
  subjectReference = '';
  marketplace = 'amazon';
  market = 'IN';
  entityName = '';
  canonicalName = '';
  entityType = 'UNKNOWN';
  productTitle = '';
  externalId = '';

  ngOnInit(): void {
    void this.refresh();
  }

  async refresh(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const [contexts, entities, doctor] = await Promise.all([
        this.service.contexts(),
        this.service.entities(),
        this.service.doctor(),
      ]);
      this.contexts.set(contexts);
      this.entities.set(entities);
      this.doctor.set(doctor);
      if (this.selectedContext()) await this.loadProducts(this.selectedContext()!);
    } catch {
      this.error.set('Competitor data is unavailable. Check the authenticated API connection.');
    } finally {
      this.loading.set(false);
    }
  }

  async createContext(): Promise<void> {
    await this.run(async () => {
      await this.service.createContext({
        subject_type: 'PRODUCT_OPPORTUNITY',
        subject_reference: this.subjectReference.trim(),
        marketplace: this.marketplace.trim(),
        market: this.market.trim(),
        idempotency_key: `competitor-context-${this.subjectReference.trim()}-${this.market.trim()}`,
      });
      await this.refresh();
    }, 'The competitor context could not be created.');
  }

  async createEntity(): Promise<void> {
    await this.run(async () => {
      await this.service.createEntity({
        display_name: this.entityName.trim(),
        canonical_name: this.canonicalName.trim(),
        entity_type: this.entityType,
        idempotency_key: `competitor-entity-${this.canonicalName.trim().toLowerCase()}`,
      });
      this.entityName = '';
      this.canonicalName = '';
      await this.refresh();
    }, 'The competitor entity could not be created.');
  }

  async selectContext(context: CompetitorContext): Promise<void> {
    this.selectedContext.set(context);
    await this.loadProducts(context);
  }

  async discover(context: CompetitorContext): Promise<void> {
    await this.run(async () => {
      const request = await this.service.createDiscoveryRequest(context.id, {
        provider_mode: 'LOCAL_FIXTURE',
        maximum_candidates: 50,
        filters: { fixture_candidates: [] },
        idempotency_key: 'competitor-discovery-' + context.id,
      });
      this.discoveryRequestId = request.id;
      const result = await this.service.executeDiscovery(request.id);
      this.discoveryCandidates.set(result.candidates);
    }, 'Competitor discovery could not be completed.');
  }

  async resolveCandidate(
    candidate: CompetitorDiscoveryCandidate,
    state: 'confirm' | 'reject' | 'ambiguous',
  ): Promise<void> {
    await this.run(async () => {
      const updated = await this.service.resolveDiscoveryCandidate(candidate.id, state);
      this.discoveryCandidates.update((values) =>
        values.map((value) => (value.id === updated.id ? updated : value)),
      );
    }, 'The discovery candidate could not be resolved.');
  }

  async runChangeComparison(context: CompetitorContext): Promise<void> {
    await this.run(async () => {
      const result = await this.service.runChangeComparison(context.id, {
        idempotency_key: `competitor-change-${context.id}`,
      });
      this.changes.set(result.events);
    }, 'The competitive change comparison could not be completed.');
  }

  async runCommercialAnalysis(context: CompetitorContext): Promise<void> {
    await this.run(async () => {
      this.commercialAnalysis.set(
        await this.service.runCommercialAnalysis(context.id, {
          idempotency_key: `competitor-commercial-${context.id}`,
          confirmation: true,
        }),
      );
    }, 'The commercial analysis could not be completed.');
  }
  async createProduct(): Promise<void> {
    const context = this.selectedContext();
    if (!context) return;
    await this.run(async () => {
      await this.service.createProduct(context.id, {
        title: this.productTitle.trim(),
        external_identifier: this.externalId.trim(),
        marketplace: context.marketplace,
        idempotency_key: `competitor-product-${context.id}-${this.externalId.trim()}`,
      });
      this.productTitle = '';
      this.externalId = '';
      await this.loadProducts(context);
    }, 'The competitor product could not be created.');
  }

  async confirmIdentity(product: CompetitorProduct): Promise<void> {
    await this.run(async () => {
      await this.service.identity(product.id, 'CONFIRMED');
      const context = this.selectedContext();
      if (context) await this.loadProducts(context);
    }, 'The competitor identity could not be updated.');
  }

  private async loadProducts(context: CompetitorContext): Promise<void> {
    this.products.set(await this.service.products(context.id));
    try {
      this.changes.set((await this.service.currentChanges(context.id)).items);
    } catch {
      this.changes.set([]);
    }
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
  readonly breadcrumbs: BreadcrumbItem[] = [
    { label: 'Intelligence', url: '/intelligence' },
    { label: 'Competitors' },
  ];
  statusTone(status: string): StatusTone {
    const value = status.toUpperCase();
    if (['PASS', 'CONFIRMED', 'AVAILABLE', 'ACTIVE'].includes(value)) return 'success';
    if (['PARTIAL', 'STALE', 'AMBIGUOUS', 'PENDING'].includes(value)) return 'warning';
    if (['REJECTED', 'ERROR', 'UNAVAILABLE'].includes(value)) return 'danger';
    return 'info';
  }
}
