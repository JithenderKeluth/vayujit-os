import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import type { BreadcrumbItem } from '../shared/ux-foundation.types';

interface EconomicContextView {
  id: string;
  status: string;
  base_currency: string | null;
  target_quantity: number | string | null;
  quantity_unit: string | null;
}

interface EconomicSnapshotView {
  id: string;
  version: number;
  fingerprint: string;
  completeness: string;
}

interface EconomicBreakdownView {
  id: string;
  category: string;
  inclusion_status: string;
  original_amount: number | string | null;
  included_amount: number | string | null;
  currency: string | null;
  basis: string | null;
  provenance: string;
  freshness: string;
  evidence_ref: string | null;
  exclusion_reason: string | null;
}

interface EconomicCalculationView {
  id: string;
  calculation_version: string;
  policy_version: string;
  status: string;
  currency: string | null;
  target_quantity: number | string | null;
  total_included_cost: number | string;
  per_unit_cost: number | string | null;
  breakdown: EconomicBreakdownView[];
  missing_inputs: string[];
  warnings: string[];
  assumptions: Array<{ source_id: string; reason: string | null }>;
  stale_inputs: Array<{ source_id: string; category: string }>;
  explanation: { included_total_label?: string; reporting_currency?: string };
}

interface ContextCreateResponse {
  context: EconomicContextView;
}

interface SnapshotCreateResponse {
  snapshot: EconomicSnapshotView;
}

interface CalculationResponse {
  calculation: EconomicCalculationView;
  breakdown: EconomicBreakdownView[];
}

interface EconomicContextDraft {
  idempotency_key: string;
  base_currency: string;
  target_quantity: number | null;
  quantity_unit: string;
  origin_country: string;
  destination_country: string;
}
interface EconomicScenarioView {
  id: string;
  name: string;
  description: string;
  status: string;
  baseline_calculation_id: string;
  overrides: Record<string, string | number | null>;
}

interface EconomicScenarioResultView {
  id: string;
  comparability: string;
  baseline: { total: string | null; per_unit: string | null };
  scenario: { total: string | null; per_unit: string | null };
  delta: { absolute: string | null; percentage: string | null; per_unit: string | null };
  changed_inputs: Array<{
    field: string;
    before: string | null;
    after: string | null;
    provenance: string;
  }>;
  warnings: string[];
}

interface EconomicSensitivityView {
  id: string;
  dimension: string;
  points: Array<{
    value: string;
    status: string;
    scenario_total: string | null;
    per_unit_cost: string | null;
    comparability: string;
    provenance: string;
  }>;
}

@Component({
  selector: 'app-sourcing-economics-workspace',
  imports: [BreadcrumbsComponent, CommonModule, FormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="economics-page" aria-labelledby="economics-title">
      <app-breadcrumbs [items]="breadcrumbs" />
      <header class="page-header">
        <div>
          <p class="eyebrow">Intelligence / Sourcing economics</p>
          <h1 id="economics-title">Sourcing economic inputs</h1>
          <p class="lede">
            Capture immutable inputs, calculate a reproducible known-cost subtotal, and inspect
            every included or excluded line.
          </p>
        </div>
        <a routerLink="/intelligence">Back to Intelligence</a>
      </header>
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }
      <section class="panel" aria-labelledby="context-title">
        <h2 id="context-title">Sourcing context</h2>
        <p>
          Currency, quantity, geography, and ownership remain explicit. No currency conversion is
          performed.
        </p>
        <p>UNKNOWN is unavailable; it is never displayed as zero.</p>
        <form (submit)="$event.preventDefault(); createContext()" class="form-grid">
          <label
            >Idempotency key <input name="key" required [(ngModel)]="draft.idempotency_key"
          /></label>
          <label
            >Base currency
            <input
              name="currency"
              maxlength="3"
              [(ngModel)]="draft.base_currency"
              placeholder="Optional ISO code"
          /></label>
          <label
            >Target quantity
            <input name="quantity" type="number" min="0.0001" [(ngModel)]="draft.target_quantity"
          /></label>
          <label
            >Quantity unit
            <input name="unit" [(ngModel)]="draft.quantity_unit" placeholder="unit, kg, carton"
          /></label>
          <label>Origin country <input name="origin" [(ngModel)]="draft.origin_country" /></label>
          <label
            >Destination country <input name="destination" [(ngModel)]="draft.destination_country"
          /></label>
          <button type="submit" [disabled]="busy()">Create context</button>
        </form>
      </section>
      @if (context()) {
        <section class="panel" aria-labelledby="inputs-title">
          <h2 id="inputs-title">Inputs and provenance</h2>
          <p>UNKNOWN is unavailable; it is never displayed as zero.</p>
          <dl class="input-list">
            <div>
              <dt>Context</dt>
              <dd>{{ context()?.status }}</dd>
            </div>
            <div>
              <dt>Base currency</dt>
              <dd>{{ context()?.base_currency || 'UNKNOWN' }}</dd>
            </div>
            <div>
              <dt>Target quantity</dt>
              <dd>
                {{ context()?.target_quantity ?? 'UNKNOWN' }} {{ context()?.quantity_unit || '' }}
              </dd>
            </div>
          </dl>
          <button type="button" (click)="freezeSnapshot()" [disabled]="busy()">
            Freeze immutable input snapshot
          </button>
          @if (snapshot()) {
            <p role="status">
              Snapshot {{ snapshot()?.version }} saved. Calculations always use this immutable
              snapshot.
            </p>
            <label class="fx-selector">
              FX snapshot ID (optional)
              <input
                name="fx_snapshot_id"
                [(ngModel)]="fxSnapshotId"
                placeholder="Explicit immutable FX snapshot UUID"
              />
            </label>
            <p class="hint">
              FX conversion uses only the explicit immutable snapshot above; no latest/live rate is
              selected.
            </p>
            <label class="fx-selector">
              Freight snapshot ID (optional)
              <input
                name="freight_snapshot_id"
                [(ngModel)]="freightSnapshotId"
                placeholder="Explicit immutable freight snapshot UUID"
              />
            </label>
            <p class="hint">
              Freight uses only an explicit immutable LOCAL_FIXTURE or manual snapshot. Unknown
              freight remains unknown; no live carrier quote is fetched.
            </p>
            <label class="fx-selector">
              Customs/tax snapshot ID (optional)
              <input
                name="customs_tax_snapshot_id"
                [(ngModel)]="customsTaxSnapshotId"
                placeholder="Explicit immutable customs/tax snapshot UUID"
              />
            </label>
            <p class="hint">
              Customs/tax inputs are bounded decision-support evidence, not legal, customs, tax, or
              regulatory determinations. Unknown and conflicting data stays visible; no official
              compliance is implied.
            </p>
            <button type="button" (click)="calculateSnapshot()" [disabled]="busy()">
              Calculate from snapshot
            </button>
          }
        </section>
      }
      @if (calculation()) {
        <section class="panel result-panel" aria-labelledby="result-title">
          <h2 id="result-title">{{ calculation()?.explanation?.included_total_label }}</h2>
          <p class="status" role="status">
            Status: <strong>{{ calculation()?.status }}</strong> Ã¯Â¿Â½ Version
            {{ calculation()?.calculation_version }} Ã¯Â¿Â½ Snapshot {{ snapshot()?.version }}
          </p>
          <dl class="input-list">
            <div>
              <dt>Currency</dt>
              <dd>{{ calculation()?.currency || 'UNKNOWN' }}</dd>
            </div>
            <div>
              <dt>Known-cost subtotal</dt>
              <dd>{{ calculation()?.total_included_cost }} {{ calculation()?.currency || '' }}</dd>
            </div>
            <div>
              <dt>Target quantity</dt>
              <dd>{{ calculation()?.target_quantity ?? 'UNKNOWN' }}</dd>
            </div>
            <div>
              <dt>Per-unit cost</dt>
              <dd>{{ calculation()?.per_unit_cost ?? 'UNKNOWN' }}</dd>
            </div>
          </dl>
          @if ((calculation()?.breakdown?.length ?? 0) > 0) {
            <h3>Cost breakdown and lineage</h3>
            <div class="breakdown-scroll">
              <table>
                <caption>
                  Included and excluded calculation inputs
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Category</th>
                    <th scope="col">Status</th>
                    <th scope="col">Amount</th>
                    <th scope="col">Basis</th>
                    <th scope="col">Provenance</th>
                    <th scope="col">Reason / evidence</th>
                  </tr>
                </thead>
                <tbody>
                  @for (line of calculation()?.breakdown; track line.id) {
                    <tr>
                      <th scope="row">{{ line.category }}</th>
                      <td>{{ line.inclusion_status }}</td>
                      <td>
                        {{ line.included_amount ?? line.original_amount ?? 'UNKNOWN' }}
                        {{ line.currency || '' }}
                      </td>
                      <td>{{ line.basis || 'UNKNOWN' }}</td>
                      <td>{{ line.provenance }} Ã¯Â¿Â½ {{ line.freshness }}</td>
                      <td>
                        {{
                          line.exclusion_reason ||
                            (line.evidence_ref ? 'Evidence linked' : 'No evidence reference')
                        }}
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          }
          @if ((calculation()?.assumptions?.length ?? 0) > 0) {
            <p>Includes {{ calculation()?.assumptions?.length }} assumed inputs.</p>
          }
          @if ((calculation()?.stale_inputs?.length ?? 0) > 0) {
            <p>Includes stale inputs. Review freshness before relying on this result.</p>
          }
          @if ((calculation()?.missing_inputs?.length ?? 0) > 0) {
            <h3>Missing / excluded inputs</h3>
            <ul>
              @for (item of calculation()?.missing_inputs; track item) {
                <li>{{ item }}</li>
              }
            </ul>
          }
          @if ((calculation()?.warnings?.length ?? 0) > 0) {
            <h3>Warnings</h3>
            <ul>
              @for (warning of calculation()?.warnings; track warning) {
                <li>{{ warning }}</li>
              }
            </ul>
          }
        </section>
      }
      @if (calculation()) {
        <section class="panel" aria-labelledby="scenario-title">
          <h2 id="scenario-title">Bounded what-if scenario</h2>
          <p>
            Compare one explicit landed-cost assumption against the immutable baseline. This is
            hypothetical decision support, not a forecast or recommendation.
          </p>
          <form (submit)="$event.preventDefault(); createEconomicScenario()" class="form-grid">
            <label
              >Scenario name
              <input name="scenarioName" required [(ngModel)]="scenarioName" /></label
            ><label
              >Product unit cost (optional)
              <input
                name="scenarioProductCost"
                type="number"
                min="0"
                step="0.00000001"
                [(ngModel)]="scenarioProductCost" /></label
            ><label
              >Reason <input name="scenarioReason" required [(ngModel)]="scenarioReason" /></label
            ><button type="submit" [disabled]="busy()">Create hypothetical scenario</button>
          </form>
          @if (scenario()) {
            <p role="status">Scenario {{ scenario()?.name }} is {{ scenario()?.status }}.</p>
            <button type="button" (click)="runEconomicScenario()" [disabled]="busy()">
              Run comparison</button
            ><label
              >One-variable product-cost points<input
                name="sensitivityPoints"
                [(ngModel)]="sensitivityPoints"
                placeholder="8, 10, 12" /></label
            ><button type="button" (click)="runEconomicSensitivity()" [disabled]="busy()">
              Run bounded sensitivity
            </button>
          }
          @if (scenarioResult(); as result) {
            <h3>Comparison result</h3>
            <p>
              Comparability: <strong>{{ result.comparability }}</strong>
            </p>
            <p>
              Baseline {{ result.baseline.total || 'UNKNOWN' }}; scenario
              {{ result.scenario.total || 'UNKNOWN' }}; delta
              {{ result.delta.absolute || 'UNKNOWN' }}
            </p>
          }
          @if (sensitivity(); as run) {
            <h3>Bounded sensitivity points</h3>
            <p>Dimension: {{ run.dimension }}. No trend or forecast is inferred.</p>
            <ul>
              @for (point of run.points; track point.value) {
                <li>
                  {{ point.value }} -> {{ point.scenario_total || 'UNKNOWN' }}; per unit
                  {{ point.per_unit_cost || 'UNKNOWN' }}; {{ point.status }} ({{
                    point.comparability
                  }})
                </li>
              }
            </ul>
          }
        </section>
      }
    </main>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .economics-page {
        max-width: 1100px;
        margin: 0 auto;
        padding: 2rem;
      }
      .page-header {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: start;
      }
      .panel {
        border: 1px solid #cbd8df;
        border-radius: 1rem;
        padding: 1.5rem;
        margin-top: 1.5rem;
        background: #fff;
      }
      .form-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
        gap: 1rem;
        align-items: end;
      }
      label {
        display: grid;
        gap: 0.35rem;
        font-weight: 600;
      }
      input,
      button {
        min-height: 2.75rem;
        padding: 0.5rem 0.7rem;
        border-radius: 0.45rem;
        border: 1px solid #78909c;
        font: inherit;
      }
      button {
        background: #155e75;
        color: #fff;
        cursor: pointer;
      }
      button:disabled {
        opacity: 0.6;
        cursor: not-allowed;
      }
      .error {
        color: #9f1239;
        background: #fff1f2;
        padding: 1rem;
      }
      .input-list {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 1rem;
      }
      .input-list div {
        padding: 1rem;
        border: 1px solid #d6e0e5;
        border-radius: 0.6rem;
      }
      dt {
        color: #475569;
      }
      dd {
        margin: 0.35rem 0 0;
        font-weight: 700;
      }
      .breakdown-scroll {
        overflow-x: auto;
      }
      table {
        width: 100%;
        min-width: 680px;
        border-collapse: collapse;
      }
      th,
      td {
        padding: 0.65rem;
        border-bottom: 1px solid #d6e0e5;
        text-align: left;
        vertical-align: top;
      }
      caption {
        text-align: left;
        font-weight: 700;
        padding: 0.65rem 0;
      }
      @media (max-width: 600px) {
        .economics-page {
          padding: 1rem;
        }
        .page-header {
          display: block;
        }
      }
    `,
  ],
})
export class SourcingEconomicsWorkspaceComponent {
  private readonly http = inject(HttpClient);
  readonly breadcrumbs: BreadcrumbItem[] = [
    { label: 'Intelligence', url: '/intelligence' },
    { label: 'Sourcing economics' },
  ];
  readonly busy = signal(false);
  readonly error = signal('');
  readonly context = signal<EconomicContextView | null>(null);
  readonly snapshot = signal<EconomicSnapshotView | null>(null);
  readonly calculation = signal<EconomicCalculationView | null>(null);
  readonly scenario = signal<EconomicScenarioView | null>(null);
  readonly scenarioResult = signal<EconomicScenarioResultView | null>(null);
  readonly sensitivity = signal<EconomicSensitivityView | null>(null);
  scenarioName = 'Explicit landed-cost what-if';
  scenarioProductCost = '';
  scenarioReason = 'Test one explicit unit-cost assumption.';
  sensitivityPoints = '8, 10, 12';
  fxSnapshotId = '';
  freightSnapshotId = '';
  customsTaxSnapshotId = '';
  draft: EconomicContextDraft = {
    idempotency_key: `economic-context-${Date.now()}`,
    base_currency: '',
    target_quantity: null,
    quantity_unit: '',
    origin_country: '',
    destination_country: '',
  };

  async createContext(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    this.snapshot.set(null);
    this.calculation.set(null);
    try {
      const response = await firstValueFrom(
        this.http.post<ContextCreateResponse>(
          `${environment.apiUrl}/intelligence/sourcing-economics/contexts`,
          this.draft,
        ),
      );
      this.context.set(response.context);
    } catch {
      this.error.set(
        'The economic context could not be saved. Check the authenticated API connection.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async freezeSnapshot(): Promise<void> {
    const row = this.context();
    if (!row) return;
    this.busy.set(true);
    this.error.set('');
    this.calculation.set(null);
    try {
      const response = await firstValueFrom(
        this.http.post<SnapshotCreateResponse>(
          `${environment.apiUrl}/intelligence/sourcing-economics/snapshots?context_id=${row.id}`,
          {},
        ),
      );
      this.snapshot.set(response.snapshot);
    } catch {
      this.error.set('The immutable input snapshot could not be created.');
    } finally {
      this.busy.set(false);
    }
  }

  async calculateSnapshot(): Promise<void> {
    const row = this.snapshot();
    if (!row) return;
    this.busy.set(true);
    this.error.set('');
    try {
      const payload = this.customsTaxSnapshotId
        ? {
            customs_tax_snapshot_id: this.customsTaxSnapshotId,
            ...(this.freightSnapshotId ? { freight_snapshot_id: this.freightSnapshotId } : {}),
            ...(this.fxSnapshotId ? { fx_snapshot_id: this.fxSnapshotId } : {}),
            calculation_version: 'landed-cost-v4',
            policy_version: 'known-cost-customs-tax-v1',
          }
        : this.freightSnapshotId
          ? {
              freight_snapshot_id: this.freightSnapshotId,
              ...(this.fxSnapshotId ? { fx_snapshot_id: this.fxSnapshotId } : {}),
              calculation_version: 'landed-cost-v3',
              policy_version: 'known-cost-freight-v1',
            }
          : this.fxSnapshotId
            ? {
                fx_snapshot_id: this.fxSnapshotId,
                calculation_version: 'landed-cost-v2',
                policy_version: 'known-cost-fx-v1',
              }
            : {};
      const response = await firstValueFrom(
        this.http.post<CalculationResponse>(
          `${environment.apiUrl}/intelligence/sourcing-economics/snapshots/${row.id}/calculate`,
          payload,
        ),
      );
      this.calculation.set({ ...response.calculation, breakdown: response.breakdown });
    } catch {
      this.error.set('The deterministic calculation could not be created from this snapshot.');
    } finally {
      this.busy.set(false);
    }
  }
  async createEconomicScenario(): Promise<void> {
    const context = this.context();
    const calculation = this.calculation();
    if (!context || !calculation) return;
    this.busy.set(true);
    this.error.set('');
    this.scenarioResult.set(null);
    this.sensitivity.set(null);
    const overrides: Record<string, string | number> = { reason: this.scenarioReason };
    if (this.scenarioProductCost.trim()) {
      overrides['product_unit_cost'] = this.scenarioProductCost.trim();
    }
    try {
      const response = await firstValueFrom(
        this.http.post<EconomicScenarioView>(
          environment.apiUrl + '/intelligence/sourcing-economics/scenarios/contexts/' + context.id,
          {
            idempotency_key: 'economic-scenario-' + Date.now(),
            name: this.scenarioName,
            description: 'Hypothetical comparison only; not a forecast or recommendation.',
            baseline_calculation_id: calculation.id,
            overrides,
          },
        ),
      );
      this.scenario.set(response);
    } catch {
      this.error.set('The hypothetical scenario could not be created.');
    } finally {
      this.busy.set(false);
    }
  }

  async runEconomicScenario(): Promise<void> {
    const scenario = this.scenario();
    if (!scenario) return;
    this.busy.set(true);
    this.error.set('');
    try {
      const response = await firstValueFrom(
        this.http.post<EconomicScenarioResultView>(
          environment.apiUrl + '/intelligence/sourcing-economics/scenarios/' + scenario.id + '/run',
          { idempotency_key: 'economic-scenario-run-' + Date.now() },
        ),
      );
      this.scenarioResult.set(response);
    } catch {
      this.error.set('The scenario comparison could not be completed.');
    } finally {
      this.busy.set(false);
    }
  }

  async runEconomicSensitivity(): Promise<void> {
    const scenario = this.scenario();
    if (!scenario) return;
    const values = this.sensitivityPoints
      .split(',')
      .map((value) => value.trim())
      .filter((value) => value.length > 0);
    if (values.length === 0) {
      this.error.set('Enter at least one product-cost sensitivity point.');
      return;
    }
    this.busy.set(true);
    this.error.set('');
    try {
      const response = await firstValueFrom(
        this.http.post<EconomicSensitivityView>(
          environment.apiUrl +
            '/intelligence/sourcing-economics/scenarios/' +
            scenario.id +
            '/sensitivity',
          {
            idempotency_key: 'economic-sensitivity-' + Date.now(),
            points: values.map((value) => ({ dimension: 'product_unit_cost', value })),
          },
        ),
      );
      this.sensitivity.set(response);
    } catch {
      this.error.set('The bounded sensitivity run could not be completed.');
    } finally {
      this.busy.set(false);
    }
  }
}
