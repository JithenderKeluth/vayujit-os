import { JsonPipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import { EvidenceCardComponent } from '../shared/evidence-card.component';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import type { BreadcrumbItem } from '../shared/ux-foundation.types';
import { SupplierJourneyNavComponent } from './supplier-journey-nav.component';
import type {
  SourcingComparison,
  SourcingContextSummary,
  SourcingScenarioDetail,
} from '@vayujit/shared';

interface Candidate {
  supplier_id: string;
  supplier: string;
}
interface AllocationInput {
  supplier_id: string;
  due_diligence_id: string;
  quantity: number;
  unit_price: string;
  currency: string;
  moq: number | null;
  lead_time_days: number | null;
  availability: string;
  incoterm: string;
  assumption_reason: string;
}

@Component({
  selector: 'app-sourcing-scenarios',
  standalone: true,
  imports: [
    BreadcrumbsComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    EvidenceCardComponent,
    FormsModule,
    JsonPipe,
    LoadingStateComponent,
    RouterLink,
    SupplierJourneyNavComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main>
      <app-breadcrumbs [items]="breadcrumbs" />
      <header>
        <h1>Sourcing Scenarios</h1>
        <p>
          Estimated costs and supplier mixes for human review. No supplier contact, orders, or
          payments.
        </p>
        <a routerLink="/intelligence/supplier-shortlisting">Supplier Shortlisting</a>
        <a routerLink="/intelligence/due-diligence">Due Diligence</a>
      </header>
      <app-supplier-journey-nav current="scenarios" />
      @if (error()) {
        <app-error-state
          title="Sourcing scenarios are unavailable"
          [message]="error()"
          retryLabel="Retry"
          (retry)="initialize()"
        />
      }
      @if (busy()) {
        <app-loading-state message="Loading sourcing evidence..." />
      }
      <section aria-labelledby="new-context">
        <h2 id="new-context">Start from a shortlist</h2>
        <form #contextForm="ngForm" (ngSubmit)="createContext()">
          <label
            >Shortlist context<select
              name="shortlist"
              [(ngModel)]="shortlistId"
              (ngModelChange)="loadShortlists()"
              required
            >
              <option value="">Select a shortlist</option>
              @for (s of shortlists(); track s.id) {
                <option [value]="s.id">{{ s.category || s.id }}</option>
              }
            </select></label
          >
          <label
            >Shortlist version<select name="version" [(ngModel)]="shortlistVersion" required>
              <option value="">Select current version</option>
              @for (v of shortlistVersions(); track v.id) {
                <option [value]="v.id">Version {{ v.version }}</option>
              }
            </select></label
          >
          <label
            >Currency<input name="currency" [(ngModel)]="currency" pattern="[A-Z]{3}" required
          /></label>
          <label>Market<input name="market" [(ngModel)]="market" maxlength="80" required /></label>
          <label
            >Channel<input name="channel" [(ngModel)]="channel" maxlength="80" required
          /></label>
          <label
            >Target units<input
              name="quantity"
              type="number"
              [(ngModel)]="quantity"
              min="1"
              step="1"
              required
          /></label>
          <label>Sale price<input name="sale" [(ngModel)]="salePrice" inputmode="decimal" /></label>
          <label
            >Capital limit<input name="capital" [(ngModel)]="capitalLimit" inputmode="decimal"
          /></label>
          <button [disabled]="busy() || contextForm.invalid">Create analysis context</button>
        </form>
      </section>
      <section aria-labelledby="contexts">
        <h2 id="contexts">Analysis contexts</h2>
        @for (c of contexts(); track c.id) {
          <button type="button" (click)="selectContext(c.id)" [disabled]="busy()">
            {{ c.settings.target_market }} / {{ c.settings.target_channel }} /
            {{ c.settings.target_quantity }} units ? {{ c.status }}
          </button>
        } @empty {
          <app-empty-state
            title="No sourcing scenarios"
            message="Create a sourcing analysis context from an authoritative shortlist to compare trade-offs."
          />
        }
      </section>
      @if (contextId()) {
        <section aria-labelledby="custom-scenario">
          <h2 id="custom-scenario">Custom supplier mix</h2>
          <p>
            Amounts are assumptions, not verified facts. Costs are total base-currency charges.
            Blank means unknown; enter 0 only when justified.
          </p>
          <form #scenarioForm="ngForm" (ngSubmit)="createScenario()">
            <label>Name<input name="name" [(ngModel)]="name" required maxlength="120" /></label>
            @for (a of allocations; track $index; let i = $index) {
              <fieldset>
                <legend>Allocation {{ i + 1 }}</legend>
                <label
                  >Supplier<select [name]="'supplier' + i" [(ngModel)]="a.supplier_id" required>
                    <option value="">Select candidate</option>
                    @for (c of candidates(); track c.supplier_id) {
                      <option [value]="c.supplier_id">{{ c.supplier }}</option>
                    }
                  </select></label
                >
                <label
                  >Due diligence<select
                    [name]="'due' + i"
                    [(ngModel)]="a.due_diligence_id"
                    required
                  >
                    <option value="">Select matching assessment</option>
                    @for (d of diligence(); track d.id) {
                      @if (d.supplier_id === a.supplier_id) {
                        <option [value]="d.id">{{ d.status }} ? {{ d.id }}</option>
                      }
                    }
                  </select></label
                >
                <label
                  >Units<input
                    [name]="'units' + i"
                    type="number"
                    [(ngModel)]="a.quantity"
                    min="1"
                    step="1"
                    required
                /></label>
                <label
                  >Unit price<input
                    [name]="'price' + i"
                    [(ngModel)]="a.unit_price"
                    inputmode="decimal"
                /></label>
                <label
                  >Currency<input
                    [name]="'curr' + i"
                    [(ngModel)]="a.currency"
                    pattern="[A-Z]{3}"
                    required
                /></label>
                <label
                  >MOQ<input [name]="'moq' + i" type="number" [(ngModel)]="a.moq" min="1" step="1"
                /></label>
                <label
                  >Production days<input
                    [name]="'lead' + i"
                    type="number"
                    [(ngModel)]="a.lead_time_days"
                    min="0"
                    step="1"
                /></label>
                <label
                  >Availability<select [name]="'availability' + i" [(ngModel)]="a.availability">
                    <option>UNKNOWN</option>
                    <option>AVAILABLE</option>
                    <option>UNAVAILABLE</option>
                  </select></label
                >
                <label
                  >Incoterm<select [name]="'term' + i" [(ngModel)]="a.incoterm">
                    <option value="">Unknown</option>
                    @for (t of terms; track t) {
                      <option>{{ t }}</option>
                    }
                  </select></label
                >
                <label
                  >Assumption source/reason<input
                    [name]="'reason' + i"
                    [(ngModel)]="a.assumption_reason"
                    minlength="3"
                    maxlength="500"
                    required
                /></label>
                <button
                  type="button"
                  (click)="removeAllocation(i)"
                  [disabled]="allocations.length === 1"
                >
                  Remove allocation
                </button>
              </fieldset>
            }
            <button type="button" (click)="addAllocation()" [disabled]="allocations.length >= 20">
              Add supplier allocation
            </button>
            <fieldset>
              <legend>Cost and logistics assumptions</legend>
              <label
                >Transport<select name="transport" [(ngModel)]="transport">
                  @for (t of transports; track t) {
                    <option>{{ t }}</option>
                  }
                </select></label
              >
              @for (key of costKeys; track key) {
                <label
                  >{{ label(key) }}<input [name]="key" [(ngModel)]="costs[key]" inputmode="decimal"
                /></label>
              }
              @for (key of feeKeys; track key) {
                <label
                  >{{ label(key) }}<input [name]="key" [(ngModel)]="fees[key]" inputmode="decimal"
                /></label>
              }
              @for (key of stageKeys; track key) {
                <label
                  >{{ label(key)
                  }}<input [name]="key" type="number" [(ngModel)]="stages[key]" min="0" step="1"
                /></label>
              }
            </fieldset>
            <button [disabled]="busy() || scenarioForm.invalid">Calculate custom scenario</button>
            <button
              type="button"
              (click)="generateScenarios()"
              [disabled]="busy() || scenarioForm.invalid"
            >
              Generate evidenced baselines
            </button>
          </form>
          @if (generation(); as result) {
            <p role="status">
              {{ result.generated.length }} evidenced baseline scenarios generated.
            </p>
            @for (item of result.generated; track item.id) {
              <button type="button" (click)="openScenario(item.id)">
                {{ item.name }} ? {{ item.labels.join(', ') || 'Human review required' }}
              </button>
            }
            <p>{{ result.explanation }}</p>
          }
        </section>
        <section aria-labelledby="comparison">
          <h2 id="comparison">Comparison</h2>
          <p>
            Compare scenarios as trade-offs. No frontend winner or best-scenario decision is
            created.
          </p>
          <app-evidence-card
            title="Scenario comparison"
            classification="DERIVED"
            summary="Scenario costs, lead times, risks, labels, and freshness are returned by the authoritative sourcing service."
            source="Sourcing scenario comparison projection"
          />
          <button type="button" (click)="recommend()" [disabled]="busy()">
            Recommend for human review
          </button>
          <table>
            <thead>
              <tr>
                <th>Scenario</th>
                <th>Landed cost</th>
                <th>Capital</th>
                <th>Margin %</th>
                <th>Days</th>
                <th>Risk</th>
                <th>Score</th>
                <th>Labels</th>
              </tr>
            </thead>
            <tbody>
              @for (s of comparison()?.scenarios || []; track s.id) {
                <tr>
                  <td>
                    <button type="button" (click)="openScenario(s.scenario_id)">
                      {{ s.name }} v{{ s.version }}
                    </button>
                  </td>
                  <td>{{ s.result.cost?.total_landed_cost ?? 'Unknown' }}</td>
                  <td>{{ s.result.capital.estimated_total_initial_cash ?? 'Unknown' }}</td>
                  <td>{{ s.result.margin?.contribution_margin_percent ?? 'Unknown' }}</td>
                  <td>{{ s.result.lead_time?.critical_path ?? 'Unknown' }}</td>
                  <td>{{ s.result.supplier_risk ?? 'Unknown' }}</td>
                  <td>{{ s.score ?? 'Insufficient evidence' }}</td>
                  <td>{{ s.labels.join(', ') }} / {{ s.freshness }}</td>
                </tr>
              }
            </tbody>
          </table>
        </section>
        <section>
          <h2>History and report</h2>
          <button type="button" (click)="loadHistory()">View immutable history</button>
          <button type="button" (click)="loadReport()">View report</button>
          @if (history()) {
            <pre>{{ history() | json }}</pre>
          }
        </section>
      }
      @if (selected(); as s) {
        <section aria-labelledby="detail">
          <h2 id="detail">{{ s.name }} ? version {{ s.version }}</h2>
          <p>{{ s.status }} / {{ s.freshness }}</p>
          <p>Missing: {{ s.result.missing_dimensions.join(', ') || 'None recorded' }}</p>
          <p>Warnings: {{ s.result.warnings.join(', ') }}</p>
          <details>
            <summary>Allocation, cost, capital, MOQ, lead time, FX, risk, and evidence</summary>
            <pre>{{ s.result | json }}</pre>
            <pre>{{ s.snapshot | json }}</pre>
          </details>
          <label
            >Decision/research reason<input [(ngModel)]="reason" minlength="3" maxlength="500"
          /></label>
          <label
            ><input type="checkbox" [(ngModel)]="confirmed" /> I reviewed this exact version.
            Internal planning only.</label
          >
          <button (click)="action('approve')" [disabled]="busy() || !canApprove()">
            Approve for internal sourcing
          </button>
          <button (click)="action('reject')" [disabled]="busy() || !confirmed || reason.length < 3">
            Reject
          </button>
          <button (click)="action('review')" [disabled]="busy() || !confirmed || reason.length < 3">
            Keep under review
          </button>
          <button
            (click)="action('archive')"
            [disabled]="busy() || !confirmed || reason.length < 3"
          >
            Archive
          </button>
          <button (click)="versionAction('recalculate')" [disabled]="busy() || reason.length < 3">
            Recalculate
          </button>
          <button (click)="versionAction('research')" [disabled]="busy() || reason.length < 3">
            Request more research
          </button>
          <button
            (click)="versionAction('handoffs')"
            [disabled]="
              busy() ||
              s.status !== 'APPROVED_FOR_INTERNAL_SOURCING' ||
              s.freshness !== 'CURRENT' ||
              reason.length < 3
            "
          >
            Create internal handoff
          </button>
          <h3>What-if (does not change supplier evidence)</h3>
          <label
            >Dimension<select [(ngModel)]="dimension">
              @for (d of dimensions; track d) {
                <option>{{ d }}</option>
              }
            </select></label
          >
          <label>Change %<input type="number" [(ngModel)]="change" min="-20" max="20" /></label>
          <button (click)="whatIf()" [disabled]="busy() || reason.length < 3">
            Calculate sensitivity
          </button>
          @if (sensitivityResult()) {
            <pre>{{ sensitivityResult() | json }}</pre>
          }
        </section>
      }
    </main>
  `,
  styles: [
    `
      main {
        max-width: 1200px;
        margin: auto;
        padding: 1rem;
      }
      section {
        background: white;
        padding: 1rem;
        border: 1px solid #cad5d8;
        border-radius: 0.8rem;
        margin-block: 1rem;
      }
      form,
      fieldset {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
      }
      label {
        display: grid;
        gap: 0.3rem;
      }
      input,
      select,
      button {
        padding: 0.5rem;
        max-width: 100%;
      }
      fieldset {
        width: 100%;
      }
      table {
        width: 100%;
        text-align: left;
        border-collapse: collapse;
      }
      td,
      th {
        padding: 0.5rem;
        border-bottom: 1px solid #cad5d8;
      }
      pre {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        max-height: 32rem;
        overflow: auto;
      }
      a,
      button {
        margin: 0.3rem;
      }
      [role='alert'] {
        color: #9e1919;
      }
    `,
  ],
})
export class SourcingScenariosComponent implements OnInit {
  private readonly http = inject(HttpClient);
  readonly base = '/api/v1/intelligence/sourcing-scenarios';
  readonly breadcrumbs: BreadcrumbItem[] = [
    { label: 'Intelligence', url: '/intelligence' },
    { label: 'Sourcing scenarios' },
  ];
  readonly busy = signal(false);
  readonly error = signal('');
  readonly contexts = signal<SourcingContextSummary[]>([]);
  readonly contextId = signal('');
  readonly shortlists = signal<{ id: string; category?: string }[]>([]);
  readonly shortlistVersions = signal<
    { id: string; version: number; shortlist: Candidate[]; review_required: Candidate[] }[]
  >([]);
  readonly candidates = signal<Candidate[]>([]);
  readonly diligence = signal<{ id: string; supplier_id: string; status: string }[]>([]);
  readonly comparison = signal<SourcingComparison | null>(null);
  readonly selected = signal<SourcingScenarioDetail | null>(null);
  readonly history = signal<unknown>(null);
  readonly sensitivityResult = signal<unknown>(null);
  readonly generation = signal<{
    generated: { id: string; name: string; labels: string[] }[];
    explanation: string;
  } | null>(null);
  readonly terms = ['EXW', 'FCA', 'FOB', 'CFR', 'CIF', 'DAP', 'DDP'];
  readonly transports = ['AIR', 'SEA', 'EXPRESS', 'LOCAL', 'CUSTOM'];
  readonly costKeys = [
    'tooling',
    'branding',
    'packaging',
    'inspection',
    'freight',
    'insurance',
    'duty',
    'tax',
    'brokerage',
    'local_transport',
    'warehouse_inbound',
    'payment_fx_fee',
    'other',
  ];
  readonly feeKeys = [
    'channel_fee_per_unit',
    'payment_fee_per_unit',
    'returns_per_unit',
    'advertising_per_unit',
    'working_capital_buffer',
  ];
  readonly stageKeys = ['logistics_days', 'customs_days', 'domestic_days'];
  readonly dimensions = [
    'purchase',
    'freight',
    'fx',
    'sale_price',
    'returns',
    'advertising',
    'lead_time',
  ];
  shortlistId = '';
  shortlistVersion = '';
  currency = 'INR';
  market = '';
  channel = '';
  quantity = 1;
  salePrice = '';
  capitalLimit = '';
  name = '';
  transport = 'LOCAL';
  reason = '';
  confirmed = false;
  dimension = 'purchase';
  change = 10;
  costs: Record<string, string> = {};
  fees: Record<string, string> = {};
  stages: Record<string, number | null> = {};
  allocations: AllocationInput[] = [];

  ngOnInit(): void {
    this.addAllocation();
    void this.initialize();
  }
  label(value: string): string {
    return value.replaceAll('_', ' ');
  }
  addAllocation(): void {
    this.allocations.push({
      supplier_id: '',
      due_diligence_id: '',
      quantity: 1,
      unit_price: '',
      currency: this.currency,
      moq: null,
      lead_time_days: null,
      availability: 'UNKNOWN',
      incoterm: '',
      assumption_reason: '',
    });
  }
  removeAllocation(i: number): void {
    this.allocations.splice(i, 1);
  }
  private async run(work: () => Promise<void>): Promise<void> {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await work();
    } catch {
      this.error.set(
        'Request could not be completed. Check required inputs, current lineage, authentication, and the API connection.',
      );
    } finally {
      this.busy.set(false);
    }
  }
  private get<T>(path: string): Promise<T> {
    return firstValueFrom(this.http.get<T>(path));
  }
  private post<T>(path: string, data: object): Promise<T> {
    return firstValueFrom(
      this.http.post<T>(path, { idempotency_key: crypto.randomUUID(), ...data }),
    );
  }
  async initialize(): Promise<void> {
    await this.run(async () => {
      this.contexts.set(await this.get<SourcingContextSummary[]>(this.base + '/contexts'));
      this.shortlists.set(await this.get('/api/v1/intelligence/supplier-shortlisting/contexts'));
      this.diligence.set(await this.get('/api/v1/intelligence/supplier-due-diligence/contexts'));
    });
  }
  async loadShortlists(): Promise<void> {
    this.shortlistVersion = '';
    await this.run(async () => {
      this.shortlistVersions.set(
        await this.get(
          '/api/v1/intelligence/supplier-shortlisting/contexts/' + this.shortlistId + '/shortlists',
        ),
      );
    });
  }
  async createContext(): Promise<void> {
    await this.run(async () => {
      const c = await this.post<{ id: string }>(this.base + '/contexts', {
        shortlist_version_id: this.shortlistVersion,
        base_currency: this.currency,
        target_market: this.market,
        target_channel: this.channel,
        target_quantity: this.quantity,
        target_sale_price: this.salePrice || null,
        capital_limit: this.capitalLimit || null,
      });
      this.contexts.set(await this.get(this.base + '/contexts'));
      await this.selectInternal(c.id);
    });
  }
  private async selectInternal(id: string): Promise<void> {
    this.contextId.set(id);
    this.selected.set(null);
    this.history.set(null);
    this.comparison.set(await this.get(this.base + '/contexts/' + id + '/comparison'));
    const contexts = await this.get<(SourcingContextSummary & { shortlist_version_id: string })[]>(
      this.base + '/contexts',
    );
    const selected = contexts.find((c) => c.id === id);
    let version = this.shortlistVersions().find((v) => v.id === selected?.shortlist_version_id);
    if (!version) {
      for (const shortlist of this.shortlists()) {
        const versions = await this.get<ReturnType<typeof this.shortlistVersions>>(
          '/api/v1/intelligence/supplier-shortlisting/contexts/' + shortlist.id + '/shortlists',
        );
        version = versions.find((v) => v.id === selected?.shortlist_version_id);
        if (version) break;
      }
    }
    this.candidates.set(version ? [...version.shortlist, ...version.review_required] : []);
  }
  async selectContext(id: string): Promise<void> {
    await this.run(() => this.selectInternal(id));
  }
  async createScenario(): Promise<void> {
    await this.run(async () => {
      await this.post(
        this.base + '/contexts/' + this.contextId() + '/scenarios',
        this.scenarioInput(),
      );
      this.comparison.set(
        await this.get(this.base + '/contexts/' + this.contextId() + '/comparison'),
      );
    });
  }
  private scenarioInput(): object {
    return {
      name: this.name,
      scenario_type: this.allocations.length > 1 ? 'MULTI_SUPPLIER' : 'SINGLE_SUPPLIER',
      allocations: this.allocations.map((a) => ({
        ...a,
        unit_price: a.unit_price || null,
        incoterm: a.incoterm || null,
      })),
      logistics_mode: this.transport,
      costs: Object.fromEntries(Object.entries(this.costs).filter(([, v]) => v !== '')),
      ...Object.fromEntries(this.feeKeys.map((k) => [k, this.fees[k] || null])),
      ...Object.fromEntries(this.stageKeys.map((k) => [k, this.stages[k] ?? null])),
    };
  }
  async generateScenarios(): Promise<void> {
    await this.run(async () => {
      this.generation.set(
        await this.post(this.base + '/contexts/' + this.contextId() + '/generate', {
          idempotency_key: crypto.randomUUID(),
          basis: { ...this.scenarioInput(), idempotency_key: crypto.randomUUID() },
        }),
      );
      this.comparison.set(
        await this.get(this.base + '/contexts/' + this.contextId() + '/comparison'),
      );
    });
  }
  async recommend(): Promise<void> {
    await this.run(async () => {
      this.history.set(
        await this.post(this.base + '/contexts/' + this.contextId() + '/recommendations', {}),
      );
    });
  }
  async openScenario(id: string): Promise<void> {
    await this.run(async () => {
      this.confirmed = false;
      this.selected.set(await this.get(this.base + '/scenarios/' + id));
    });
  }
  canApprove(): boolean {
    const s = this.selected();
    return (
      !!s &&
      this.confirmed &&
      this.reason.length >= 3 &&
      s.freshness === 'CURRENT' &&
      s.status !== 'ARCHIVED' &&
      s.result.status !== 'BLOCKED' &&
      s.result.missing_dimensions.length === 0
    );
  }
  async action(action: string): Promise<void> {
    await this.versionAction('decisions', { action, confirm: this.confirmed });
  }
  async versionAction(endpoint: string, extra: object = {}): Promise<void> {
    const s = this.selected();
    if (!s) return;
    await this.run(async () => {
      this.history.set(
        await this.post(this.base + '/scenarios/' + s.id + '/' + endpoint, {
          expected_version: s.version,
          reason: this.reason,
          ...extra,
        }),
      );
      this.selected.set(await this.get(this.base + '/scenarios/' + s.id));
      this.confirmed = false;
      this.comparison.set(
        await this.get(this.base + '/contexts/' + this.contextId() + '/comparison'),
      );
    });
  }
  async whatIf(): Promise<void> {
    const s = this.selected();
    if (!s) return;
    await this.run(async () => {
      this.sensitivityResult.set(
        await this.post(this.base + '/scenarios/' + s.id + '/sensitivity', {
          expected_version: s.version,
          reason: this.reason,
          dimension: this.dimension,
          change_percent: String(this.change),
        }),
      );
    });
  }
  async loadHistory(): Promise<void> {
    await this.run(async () => {
      this.history.set(await this.get(this.base + '/contexts/' + this.contextId() + '/history'));
    });
  }
  async loadReport(): Promise<void> {
    await this.run(async () => {
      this.history.set(await this.get(this.base + '/contexts/' + this.contextId() + '/report'));
    });
  }
}
