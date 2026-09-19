import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import {
  CompetitorContext,
  CompetitorEntity,
  CompetitorIntelligenceService,
  CompetitorProduct,
} from './competitor-intelligence.service';

@Component({
  selector: 'app-competitor-intelligence-workspace',
  standalone: true,
  imports: [DatePipe, FormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="workspace" aria-labelledby="competitor-title">
      <header class="page-header">
        <div>
          <p class="eyebrow">Intelligence / Competitors</p>
          <h1 id="competitor-title">Competitor intelligence</h1>
          <p class="lede">
            Owner-scoped factual observations and immutable snapshots. Matching and analytics remain
            deliberately out of scope for this foundation.
          </p>
        </div>
        <a routerLink="/intelligence">Back to Intelligence</a>
      </header>

      @if (error()) {
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
