import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

type Plan = {
  id: string;
  objective: string;
  target_channels: string[];
  budget_envelope: { total?: string; currency?: string };
  status: string;
  current_version: number;
  update_available?: boolean;
};

@Component({
  selector: 'app-marketing-plan',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <main class="marketing-shell" aria-labelledby="marketing-title">
      <header>
        <p class="eyebrow">Ads &amp; Marketing Automation</p>
        <h1 id="marketing-title">Cross-channel marketing plans</h1>
        <p class="lede">
          Coordinate approved content, marketplace Ads, social publishing, Campaigns, and Calendar
          from one version-pinned plan.
        </p>
      </header>
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }
      <section class="card" aria-labelledby="create-title">
        <h2 id="create-title">Plan readiness</h2>
        <p>
          Plans remain local, deterministic, and require explicit preview confirmation. Meesho Ads
          is not supported.
        </p>
        @if (capabilities(); as value) {
          <div class="capabilities">
            @for (channel of value.channels; track channel) {
              <span>{{ channel }}</span>
            }
            <span class="unsupported">meesho · unsupported</span>
          </div>
        }
      </section>
      <section class="card wizard-card" aria-labelledby="wizard-title">
        <div class="section-heading">
          <div>
            <h2 id="wizard-title">12-step Marketing Plan wizard</h2>
            <p>Preview and explicit confirmation keep provider mutations in the worker.</p>
          </div>
          <button type="button" (click)="wizardOpen.set(!wizardOpen())">
            {{ wizardOpen() ? 'Close wizard' : 'Create plan' }}
          </button>
        </div>
        @if (wizardOpen()) {
          <ol class="wizard-steps" aria-label="Marketing Plan steps">
            @for (step of steps; track step; let index = $index) {
              <li [class.active]="index === wizardStep()">
                <button type="button" (click)="wizardStep.set(index)">
                  {{ index + 1 }}. {{ step }}
                </button>
              </li>
            }
          </ol>
          <div class="wizard-panel">
            <h3>{{ steps[wizardStep()] }}</h3>
            @if (wizardStep() === 0) {
              <label
                >Brand ID <input [(ngModel)]="draft.brand_id" placeholder="Brand UUID"
              /></label>
              <label
                >Product ID <input [(ngModel)]="draft.product_id" placeholder="Product UUID"
              /></label>
            }
            @if (wizardStep() === 1) {
              <label
                >Objective
                <select [(ngModel)]="draft.objective">
                  <option value="sales">Sales</option>
                  <option value="traffic">Traffic</option>
                  <option value="awareness">Awareness</option>
                </select></label
              >
            }
            @if (wizardStep() === 2) {
              <label
                >Channels <input [(ngModel)]="draft.channels" aria-describedby="channel-help"
              /></label>
              <small id="channel-help">Comma-separated supported channels.</small>
            }
            @if (wizardStep() === 6) {
              <label>Total budget <input type="number" min="0" [(ngModel)]="draft.total" /></label>
              <label>Currency <input [(ngModel)]="draft.currency" maxlength="3" /></label>
            }
            @if (wizardStep() > 2 && wizardStep() !== 6) {
              <p class="step-hint">Review this step before continuing.</p>
            }
            <div class="wizard-actions">
              <button type="button" (click)="previousStep()" [disabled]="wizardStep() === 0">
                Back
              </button>
              @if (wizardStep() < steps.length - 1) {
                <button type="button" (click)="nextStep()">Next</button>
              } @else {
                <button type="button" (click)="submitWizard()" [disabled]="submitting()">
                  Preview and confirm
                </button>
              }
            </div>
            @if (wizardError()) {
              <p class="error" role="alert">{{ wizardError() }}</p>
            }
          </div>
        }
      </section>
      <section class="card" aria-labelledby="plans-title">
        <div class="section-heading">
          <h2 id="plans-title">Plans</h2>
          <button type="button" (click)="load()">Refresh</button>
        </div>
        @if (!plans().length) {
          <p class="empty">
            No marketing plans yet. Create one after validating channel readiness.
          </p>
        }
        @if (plans().length) {
          <div class="plan-list">
            @for (plan of plans(); track plan.id) {
              <article class="plan">
                <div>
                  <h3>{{ plan.objective | titlecase }}</h3>
                  <p>{{ plan.target_channels.join(' · ') }}</p>
                </div>
                <div class="plan-meta">
                  <strong>{{ plan.status | titlecase }}</strong
                  ><span>v{{ plan.current_version }}</span
                  ><span
                    >{{ plan.budget_envelope.total || '0' }}
                    {{ plan.budget_envelope.currency || 'INR' }}</span
                  >
                </div>
              </article>
            }
          </div>
        }
      </section>
    </main>
  `,
  styles: [
    `
      :host {
        display: block;
        min-height: 100%;
        color: #102b38;
      }
      .marketing-shell {
        max-width: 1180px;
        margin: 0 auto;
        padding: 48px 34px 72px;
      }
      header {
        margin-bottom: 28px;
      }
      .eyebrow {
        color: #176078;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }
      h1 {
        font-size: clamp(2rem, 4vw, 3.3rem);
        margin: 0.3rem 0 1rem;
      }
      .lede {
        color: #4d6c7b;
        font-size: 1.1rem;
        max-width: 760px;
      }
      .card {
        background: #fff;
        border: 1px solid #d5e1e4;
        border-radius: 16px;
        padding: 24px;
        margin-top: 20px;
        box-shadow: 0 8px 24px #1233;
      }
      .section-heading {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
      }
      button {
        border: 0;
        border-radius: 8px;
        background: #155b73;
        color: #fff;
        padding: 10px 16px;
        cursor: pointer;
      }
      .capabilities {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 18px;
      }
      .capabilities span {
        border: 1px solid #9ebec8;
        border-radius: 999px;
        padding: 7px 12px;
      }
      .capabilities .unsupported {
        color: #7d3131;
        border-color: #d99b9b;
      }
      .plan-list {
        display: grid;
        gap: 12px;
      }
      .plan {
        display: flex;
        justify-content: space-between;
        gap: 18px;
        border: 1px solid #d5e1e4;
        border-radius: 12px;
        padding: 16px;
      }
      .plan h3 {
        margin: 0 0 6px;
      }
      .plan p {
        margin: 0;
        color: #577481;
      }
      .plan-meta {
        display: flex;
        align-items: center;
        gap: 12px;
        color: #416474;
      }
      .error {
        color: #9b2424;
        background: #fff0f0;
        padding: 12px 16px;
        border-left: 4px solid #b82929;
      }
      .empty {
        color: #577481;
      }
      @media (max-width: 680px) {
        .marketing-shell {
          padding: 28px 18px 48px;
        }
        .plan {
          flex-direction: column;
        }
        .plan-meta {
          flex-wrap: wrap;
        }
      }
    `,
  ],
})
export class MarketingPlanComponent {
  private readonly http = inject(HttpClient);
  readonly plans = signal<Plan[]>([]);
  readonly capabilities = signal<{ channels: string[] } | null>(null);
  readonly error = signal('');
  readonly wizardOpen = signal(false);
  readonly wizardStep = signal(0);
  readonly wizardError = signal('');
  readonly submitting = signal(false);
  readonly steps = [
    'Product(s)',
    'Objective',
    'Channels',
    'Accounts/Listings',
    'Creative',
    'Audience/Targeting',
    'Budget Envelope',
    'Channel Allocation',
    'Schedule',
    'Automation/Guardrails',
    'Review',
    'Confirm',
  ];
  readonly draft = {
    brand_id: '',
    product_id: '',
    objective: 'sales',
    channels: 'social,campaign',
    total: '100',
    currency: 'INR',
  };

  constructor() {
    void this.load();
  }

  previousStep(): void {
    this.wizardStep.update((value) => Math.max(0, value - 1));
  }

  nextStep(): void {
    this.wizardError.set('');
    this.wizardStep.update((value) => Math.min(this.steps.length - 1, value + 1));
  }

  async submitWizard(): Promise<void> {
    this.submitting.set(true);
    this.wizardError.set('');
    const channels = this.draft.channels
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean);
    const payload = {
      brand_id: this.draft.brand_id,
      product_ids: [this.draft.product_id],
      objective: this.draft.objective,
      target_channels: channels,
      budget_envelope: {
        total: this.draft.total,
        currency: this.draft.currency.toUpperCase(),
        allocations: Object.fromEntries(channels.map((channel) => [channel, this.draft.total])),
      },
      strategy_mode: 'manual',
      automation_mode: 'manual',
      creative_mapping: {},
      targeting: {},
      schedule: { mode: 'immediate' },
      idempotency_key: 'web-marketing-plan-' + Date.now(),
    };
    try {
      const preview = await firstValueFrom(
        this.http.post<{ fingerprint: string }>('/api/v1/ads/marketing/plans/preview', {
          plan: payload,
          expected_version: 1,
        }),
      );
      await firstValueFrom(
        this.http.post('/api/v1/ads/marketing/plans/confirm', {
          plan: payload,
          expected_version: 1,
          preview_fingerprint: preview.fingerprint,
          confirm: true,
        }),
      );
      this.wizardOpen.set(false);
      this.wizardStep.set(0);
      await this.load();
    } catch {
      this.wizardError.set('The plan could not be confirmed. Review owner-scoped dependencies.');
    } finally {
      this.submitting.set(false);
    }
  }

  async load(): Promise<void> {
    this.error.set('');
    try {
      const [plans, capabilities] = await Promise.all([
        firstValueFrom(this.http.get<Plan[]>('/api/v1/ads/marketing/plans')),
        firstValueFrom(this.http.get<{ channels: string[] }>('/api/v1/ads/marketing/capabilities')),
      ]);
      this.plans.set(plans);
      this.capabilities.set(capabilities);
    } catch {
      this.error.set('Marketing Plan data is unavailable. Check the authenticated API connection.');
    }
  }
}
