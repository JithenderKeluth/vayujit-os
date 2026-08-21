/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unsafe-assignment, @typescript-eslint/no-unsafe-member-access, @typescript-eslint/no-unsafe-return, @typescript-eslint/no-unsafe-argument, @typescript-eslint/no-redundant-type-constituents */
import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnDestroy, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  ActivatedRoute,
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
} from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom, filter, Subscription } from 'rxjs';

type Json = any;
type Account = Json & {
  id: string;
  provider: 'meta' | 'google' | 'amazon' | 'flipkart';
  display_name: string;
  status: string;
  enabled: boolean;
  validated: boolean;
};
type Campaign = Json & {
  id: string;
  provider: string;
  name: string;
  state: string;
  objective: string;
  account_id: string;
  product_id?: string;
};
type Capability = Json & {
  objectives?: string[];
  bidding_strategies?: string[];
  creative_types?: string[];
};

@Component({
  selector: 'app-ads-workspace',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, RouterLinkActive],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="ads-shell" aria-labelledby="ads-title">
      <header class="ads-header">
        <div>
          <p class="eyebrow">Ads and Marketing Automation</p>
          <h1 id="ads-title">Operational Ads workspace</h1>
          <p class="lede">
            Owner-scoped social, search, and marketplace campaign operations with explicit review
            gates.
          </p>
        </div>
        <div class="header-actions">
          <span class="badge">LOCAL SYNTHETIC</span
          ><a class="button primary" routerLink="/ads/create">Create campaign</a>
        </div>
      </header>
      <nav class="ads-nav" aria-label="Ads workspace navigation">
        @for (item of navItems; track item.path) {
          <a
            [routerLink]="item.path"
            routerLinkActive="active"
            [routerLinkActiveOptions]="{ exact: item.path === '/ads' }"
            >{{ item.label }}</a
          >
        }
      </nav>
      @if (error()) {
        <div class="alert error" role="alert">{{ error() }}</div>
      }
      @if (notice()) {
        <div class="alert success" role="status">{{ notice() }}</div>
      }
      @if (loading()) {
        <p aria-live="polite" class="loading">Loading Ads workspace...</p>
      }
      @if (!loading()) {
        @switch (section()) {
          @case ('overview') {
            <ng-container *ngTemplateOutlet="overviewView" />
          }
          @case ('accounts') {
            <ng-container *ngTemplateOutlet="accountsView" />
          }
          @case ('campaigns') {
            <ng-container *ngTemplateOutlet="campaignsView" />
          }
          @case ('create') {
            <ng-container *ngTemplateOutlet="createView" />
          }
          @case ('detail') {
            <ng-container *ngTemplateOutlet="detailView" />
          }
          @case ('analytics') {
            <ng-container *ngTemplateOutlet="analyticsView" />
          }
          @case ('calendar') {
            <ng-container *ngTemplateOutlet="calendarView" />
          }
          @case ('recovery') {
            <ng-container *ngTemplateOutlet="recoveryView" />
          }
          @default {
            <ng-container *ngTemplateOutlet="settingsView" />
          }
        }
      }
    </main>
    <ng-template #overviewView
      ><section class="section-heading">
        <div>
          <h2>Overview</h2>
          <p>What needs attention today, with synthetic data clearly marked.</p>
        </div>
        <button class="button" (click)="refresh()">Refresh</button>
      </section>
      <section class="metric-grid">
        @for (metric of overviewMetrics(); track metric.label) {
          <article class="metric-card">
            <span>{{ metric.label }}</span
            ><strong>{{ metric.value }}</strong
            ><small>{{ metric.detail }}</small>
          </article>
        }
      </section>
      <div class="two-column">
        <section class="panel">
          <h3>Provider health</h3>
          @for (provider of ['meta', 'google', 'amazon', 'flipkart']; track provider) {
            <div class="health-row">
              <strong>{{ provider | titlecase }}</strong
              ><span class="status" [class.good]="providerHealth(provider) === 'Ready'">{{
                providerHealth(provider)
              }}</span
              ><small>Local fake connector only</small>
            </div>
          }
        </section>
        <section class="panel">
          <h3>Quick actions</h3>
          <div class="action-list">
            <a class="button" routerLink="/ads/accounts">Manage accounts</a
            ><a class="button" routerLink="/ads/campaigns">Review campaigns</a
            ><a class="button" routerLink="/ads/recovery">Open recovery</a>
          </div>
        </section>
      </div>
      <section class="panel">
        <h3>Attention and boundary</h3>
        <p>
          {{
            overview?.attention_items?.join(' ') ||
              'No live spend or remote Ads API calls are connected.'
          }}
        </p>
        <p class="safe-note">
          Live provider APIs are not connected; Amazon and Flipkart use local deterministic fake
          connectors.
        </p>
        <p class="safe-note">Meesho Ads is not supported in this local slice.</p>
      </section></ng-template
    >
    <ng-template #accountsView
      ><section class="section-heading">
        <div>
          <h2>Accounts</h2>
          <p>Validate, enable, disable, replace, and audit credentials without exposing secrets.</p>
        </div>
        <button class="button" (click)="showAccountForm = !showAccountForm">
          {{ showAccountForm ? 'Close form' : 'Add account' }}
        </button>
      </section>
      @if (showAccountForm) {
        <form class="panel form-grid" (ngSubmit)="createAccount()">
          <h3>Add Ads account</h3>
          <label
            >Provider<select name="provider" [(ngModel)]="accountDraft.provider" required>
              <option value="meta">Meta</option>
              <option value="google">Google</option>
              <option value="amazon">Amazon Ads</option>
              <option value="flipkart">Flipkart Ads</option>
            </select></label
          ><label
            >Display name<input
              name="display_name"
              [(ngModel)]="accountDraft.display_name"
              required
              maxlength="160" /></label
          ><label
            >External account ID<input
              name="external_account_id"
              [(ngModel)]="accountDraft.external_account_id"
              required /></label
          ><label
            >Environment<select name="environment" [(ngModel)]="accountDraft.environment">
              <option>local</option>
              <option>sandbox</option>
              <option>production</option>
            </select></label
          ><label
            >Credential (write only)<input
              type="password"
              name="credential"
              [(ngModel)]="accountDraft.credential"
              autocomplete="new-password"
              placeholder="Stored encrypted; never returned"
          /></label>
          <div class="form-actions">
            <button class="button primary" [disabled]="submitting()">Save account</button
            ><span class="safe-note">Credentials are write-only.</span>
          </div>
        </form>
      }
      <section class="panel table-scroll">
        <table>
          <caption class="sr-only">
            Ads accounts
          </caption>
          <thead>
            <tr>
              <th>Provider</th>
              <th>Display name</th>
              <th>Status</th>
              <th>Validation</th>
              <th>Credential</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            @for (account of accounts; track account.id) {
              <tr>
                <td>{{ account.provider | titlecase }}</td>
                <td>
                  <a [routerLink]="['/ads/accounts', account.id]">{{ account.display_name }}</a
                  ><small>{{ account.external_account_id }}</small>
                </td>
                <td>
                  <span class="status" [class.good]="account.enabled">{{
                    account.enabled ? 'Enabled' : account.status
                  }}</span>
                </td>
                <td>{{ account.validated ? 'Validated' : account.validation_status }}</td>
                <td>Version {{ account.credential_version }} - write only</td>
                <td class="row-actions">
                  <button class="link-button" (click)="accountAction(account, 'validate')">
                    Validate</button
                  ><button
                    class="link-button"
                    (click)="accountAction(account, account.enabled ? 'disable' : 'enable')"
                  >
                    {{ account.enabled ? 'Disable' : 'Enable' }}</button
                  ><button class="link-button" (click)="replaceCredentials(account)">Replace</button
                  ><button class="link-button danger-text" (click)="removeCredentials(account)">
                    Remove
                  </button>
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="6" class="empty">
                  No Ads accounts yet. Add a local account to begin.
                </td>
              </tr>
            }
          </tbody>
        </table>
      </section></ng-template
    >
    <ng-template #campaignsView
      ><section class="section-heading">
        <div>
          <h2>Campaigns</h2>
          <p>Search, filter, review readiness, and open an auditable campaign detail.</p>
        </div>
        <a class="button primary" routerLink="/ads/create">Create campaign</a>
      </section>
      <section class="filters">
        <label
          >Search<input
            [(ngModel)]="campaignSearch"
            (ngModelChange)="applyCampaignFilters()"
            placeholder="Name or ID" /></label
        ><label
          >Provider<select [(ngModel)]="campaignProvider" (ngModelChange)="applyCampaignFilters()">
            <option value="">All providers</option>
            <option value="meta">Meta</option>
            <option value="google">Google</option>
            <option value="amazon">Amazon Ads</option>
            <option value="flipkart">Flipkart Ads</option>
          </select></label
        ><label
          >State<select [(ngModel)]="campaignState" (ngModelChange)="applyCampaignFilters()">
            <option value="">All states</option>
            <option>draft</option>
            <option>active</option>
            <option>paused</option>
            <option>failed</option>
          </select></label
        >
      </section>
      <section class="panel table-scroll">
        <table>
          <caption class="sr-only">
            Ads campaigns
          </caption>
          <thead>
            <tr>
              <th>Campaign</th>
              <th>Provider</th>
              <th>State</th>
              <th>Objective</th>
              <th>Budget</th>
              <th>Sync</th>
            </tr>
          </thead>
          <tbody>
            @for (campaign of filteredCampaigns; track campaign.id) {
              <tr>
                <td>
                  <a [routerLink]="['/ads/campaigns', campaign.id]"
                    ><strong>{{ campaign.name }}</strong></a
                  ><small>{{ campaign.id }}</small>
                </td>
                <td>{{ campaign.provider | titlecase }}</td>
                <td>
                  <span class="status" [class.good]="campaign.state === 'active'">{{
                    campaign.state
                  }}</span>
                </td>
                <td>{{ campaign.objective }}</td>
                <td>
                  {{
                    campaign.budget?.daily_amount || campaign.budget?.lifetime_amount || 'Not set'
                  }}
                  {{ campaign.budget?.currency || '' }}
                </td>
                <td>{{ campaign.sync_state || 'local draft' }}</td>
              </tr>
            } @empty {
              <tr>
                <td colspan="6" class="empty">No campaigns match these filters.</td>
              </tr>
            }
          </tbody>
        </table>
      </section></ng-template
    >
    <ng-template #createView
      ><section class="section-heading">
        <div>
          <h2>Create Ads campaign</h2>
          <p>
            Every step is reviewable. Provider capability and readiness remain server-authoritative.
          </p>
        </div>
        <a routerLink="/ads/campaigns">Cancel</a>
      </section>
      <ol class="steps" aria-label="Campaign creation steps">
        @for (step of wizardSteps; track step; let i = $index) {
          <li
            [class.current]="wizardStep === i"
            [attr.aria-current]="wizardStep === i ? 'step' : null"
          >
            <span>{{ i + 1 }}</span
            >{{ step }}
          </li>
        }
      </ol>
      <form
        class="panel wizard"
        (ngSubmit)="wizardStep === wizardSteps.length - 1 ? confirmCampaign() : nextStep()"
      >
        @switch (wizardStep) {
          @case (0) {
            <h3>1. Account and campaign</h3>
            <div class="form-grid">
              <label
                >Provider<select
                  name="provider"
                  [(ngModel)]="campaignDraft.provider"
                  (ngModelChange)="syncProvider()"
                >
                  <option value="meta">Meta</option>
                  <option value="google">Google</option>
                  <option value="amazon">Amazon Ads</option>
                  <option value="flipkart">Flipkart Ads</option>
                </select></label
              ><label
                >Account<select name="account_id" [(ngModel)]="campaignDraft.account_id" required>
                  <option value="">Select validated account</option>
                  @for (account of providerAccounts(); track account.id) {
                    <option [value]="account.id">
                      {{ account.display_name }} ({{ account.external_account_id }})
                    </option>
                  }
                </select></label
              ><label
                >Campaign name<input name="name" [(ngModel)]="campaignDraft.name" required /></label
              ><label
                >Objective<select name="objective" [(ngModel)]="campaignDraft.objective">
                  @for (
                    objective of providerCapability()?.objectives || [
                      'awareness',
                      'traffic',
                      'conversions',
                    ];
                    track objective
                  ) {
                    <option [value]="objective">{{ objective }}</option>
                  }
                </select></label
              >
            </div>
          }
          @case (1) {
            <h3>2. Product and audience</h3>
            <div class="form-grid">
              <label
                >Product UUID (optional)<input
                  name="product_id"
                  [(ngModel)]="campaignDraft.product_id"
                  placeholder="Trusted product UUID" /></label
              ><label
                ><label
                  >Keyword set UUID (optional)<input
                    name="keyword_set_id"
                    [(ngModel)]="campaignDraft.keyword_set_id"
                    placeholder="Server-validated keyword set" /></label
                >Audience name<input
                  name="audience_name"
                  [(ngModel)]="audienceDraft.name"
                  placeholder="Abstract audience" /></label
              ><label
                >Geography<input
                  name="geography"
                  [(ngModel)]="audienceDraft.geography"
                  placeholder="IN, US" /></label
              ><label
                >Languages<input
                  name="languages"
                  [(ngModel)]="audienceDraft.languages"
                  placeholder="en-IN" /></label
              ><label
                >Age range<input
                  name="age_range"
                  [(ngModel)]="audienceDraft.age_range"
                  placeholder="18-65"
              /></label>
            </div>
            <p class="safe-note">
              Do not enter names, emails, phone numbers, or other PII. Audience references remain
              abstract.
            </p>
          }
          @case (2) {
            <h3>3. Creative and destination</h3>
            <div class="form-grid">
              <label
                >Creative type<select
                  name="creative_type"
                  [(ngModel)]="creativeDraft.creative_type"
                >
                  <option>content</option>
                  <option>image</option>
                  <option>video</option>
                  <option>manual</option>
                </select></label
              ><label
                >Approved Artifact UUID<input
                  name="artifact_id"
                  [(ngModel)]="creativeDraft.artifact_id" /></label
              ><label
                >Exact Artifact version<input
                  type="number"
                  min="1"
                  name="artifact_version"
                  [(ngModel)]="creativeDraft.artifact_version" /></label
              ><label
                >Image/video media UUID<input
                  name="media_id"
                  [(ngModel)]="creativeDraft.media_id" /></label
              ><label
                >Exact media version<input
                  type="number"
                  min="1"
                  name="media_version"
                  [(ngModel)]="creativeDraft.media_version" /></label
              ><label
                >Destination URL<input
                  type="url"
                  name="destination_url"
                  [(ngModel)]="creativeDraft.destination_url"
                  placeholder="https://..." /></label
              ><label
                >Headline<input
                  name="headline"
                  [(ngModel)]="creativeDraft.headline"
                  maxlength="500"
              /></label>
            </div>
            <button
              class="button"
              type="button"
              (click)="checkReadiness()"
              [disabled]="submitting()"
            >
              Check server readiness
            </button>
            @if (readiness()) {
              <p
                class="alert"
                [class.error]="readiness()?.status !== 'ready'"
                [class.success]="readiness()?.status === 'ready'"
              >
                {{ readiness()?.safe_message || readiness()?.status }}
              </p>
            }
          }
          @case (3) {
            <h3>4. Budget, bidding, and schedule</h3>
            <div class="form-grid">
              <label
                >Budget type<select
                  name="budget_type"
                  [(ngModel)]="campaignDraft.budget.budget_type"
                >
                  <option value="daily">Daily</option>
                  <option value="lifetime">Lifetime</option>
                </select></label
              ><label
                >Amount<input
                  type="number"
                  min="0"
                  name="amount"
                  [(ngModel)]="campaignDraft.budget.amount"
                  required /></label
              ><label
                >Bidding strategy<select
                  name="bidding_strategy"
                  [(ngModel)]="campaignDraft.bidding_strategy"
                >
                  @for (
                    strategy of providerCapability()?.bidding_strategies || ['lowest_cost'];
                    track strategy
                  ) {
                    <option [value]="strategy">{{ strategy }}</option>
                  }
                </select></label
              ><label
                >Timezone<input
                  name="timezone_name"
                  [(ngModel)]="campaignDraft.timezone_name" /></label
              ><label
                >Start at<input
                  type="datetime-local"
                  name="start_at"
                  [(ngModel)]="campaignDraft.start_at" /></label
              ><label
                >End at<input
                  type="datetime-local"
                  name="end_at"
                  [(ngModel)]="campaignDraft.end_at"
              /></label>
            </div>
          }
          @case (4) {
            <h3>5. Review and preview</h3>
            <div class="review-grid">
              <p><strong>Provider:</strong> {{ campaignDraft.provider }}</p>
              <p>
                <strong>Account:</strong> {{ selectedAccount()?.display_name || 'Not selected' }}
              </p>
              <p><strong>Objective:</strong> {{ campaignDraft.objective }}</p>
              <p>
                <strong>Creative:</strong> {{ creativeDraft.creative_type }} / exact version
                {{ creativeDraft.artifact_version || creativeDraft.media_version || 'required' }}
              </p>
              <p>
                <strong>Budget:</strong> {{ campaignDraft.budget.amount }} INR
                {{ campaignDraft.budget.budget_type }}
              </p>
              <p><strong>Destination:</strong> {{ creativeDraft.destination_url || 'Not set' }}</p>
            </div>
            <button
              class="button"
              type="button"
              (click)="previewCampaign()"
              [disabled]="submitting()"
            >
              Run server preview
            </button>
            @if (preview()) {
              <div class="preview">
                <strong>Preview fingerprint:</strong> {{ preview()?.preview_fingerprint }}
                <p>{{ preview()?.safe_message || 'Preview ready for explicit confirmation.' }}</p>
              </div>
            }
          }
          @case (5) {
            <h3>6. Creative review</h3>
            <p>
              Review the selected creative channel and exact immutable identity before continuing.
            </p>
          }
          @case (6) {
            <h3>7. Destination</h3>
            <p>Confirm the HTTPS destination and placement policy.</p>
          }
          @case (7) {
            <h3>8. Budget review</h3>
            <p>Review the server-validated budget currency and limits.</p>
          }
          @case (8) {
            <h3>9. Bidding review</h3>
            <p>Review the provider capability response for bidding.</p>
          }
          @case (9) {
            <h3>10. Schedule review</h3>
            <p>Review timezone and start/end windows.</p>
          }
          @case (10) {
            <h3>11. Final review</h3>
            <p>Run the server preview before explicit confirmation.</p>
            <button
              class="button"
              type="button"
              (click)="previewCampaign()"
              [disabled]="submitting()"
            >
              Run server preview
            </button>
          }
          @case (11) {
            <h3>6. Confirm</h3>
            <p>Confirming creates a local queued job. No live provider call is made.</p>
            <label class="checkbox"
              ><input type="checkbox" [(ngModel)]="confirmChecked" name="confirm_checked" /> I
              reviewed the account, exact creative version, destination, budget, and
              schedule.</label
            ><button
              class="button primary"
              type="submit"
              [disabled]="submitting() || !confirmChecked"
            >
              Confirm and queue campaign
            </button>
          }
        }
      </form>
      <div class="wizard-actions">
        <button
          class="button"
          type="button"
          (click)="previousStep()"
          [disabled]="wizardStep === 0 || submitting()"
        >
          Back
        </button>
        @if (wizardStep < wizardSteps.length - 1) {
          <button
            class="button primary"
            type="button"
            (click)="nextStep()"
            [disabled]="submitting()"
          >
            Next
          </button>
        }
      </div></ng-template
    >
    <ng-template #detailView>
      @if (campaignDetail; as detail) {
        <section class="section-heading">
          <div>
            <h2>{{ detail.campaign.name }}</h2>
            <p>
              {{ detail.campaign.provider | titlecase }} - {{ detail.campaign.state }} -
              {{ detail.campaign.objective }}
            </p>
          </div>
          <a routerLink="/ads/campaigns">Back to campaigns</a>
        </section>
        <section class="metric-grid">
          <article class="metric-card">
            <span>Remote campaign</span
            ><strong>{{ detail.campaign.remote_campaign_id || 'Local' }}</strong
            ><small>{{ detail.campaign.sync_state || 'Not synced' }}</small>
          </article>
          <article class="metric-card">
            <span>Budget version</span
            ><strong>{{ detail.campaign.budget?.version || 'Unavailable' }}</strong
            ><small
              >{{
                detail.campaign.budget?.daily_amount ||
                  detail.campaign.budget?.lifetime_amount ||
                  'Not set'
              }}
              {{ detail.campaign.budget?.currency || '' }}</small
            >
          </article>
          <article class="metric-card">
            <span>Reconciliation</span
            ><strong>{{ detail.campaign.reconciliation_state || 'unknown' }}</strong
            ><small>{{ detail.campaign.failure_code || 'No failure' }}</small>
          </article>
          <article class="metric-card">
            <span>ROAS</span><strong>{{ analytics?.roas ?? 'Unavailable' }}</strong
            ><small>{{
              analytics?.profit_status === 'available'
                ? 'Profitability available'
                : 'Profitability unavailable'
            }}</small>
          </article>
        </section>
        <div class="action-list panel">
          <button
            class="button"
            (click)="
              campaignAction(
                detail.campaign,
                detail.campaign.state === 'paused' ? 'resume' : 'pause'
              )
            "
          >
            {{ detail.campaign.state === 'paused' ? 'Resume' : 'Pause' }}</button
          ><button class="button" (click)="reconcile(detail.campaign)">Reconcile</button
          ><a class="button" routerLink="/ads/recovery">Recovery</a>
        </div>
        <section class="panel">
          <h3>Approved creatives and exact lineage</h3>
          <div class="creative-grid">
            @for (creative of detail.creatives; track creative.id) {
              <article>
                <strong>{{ creative.type | titlecase }}</strong>
                <p>Approval: {{ creative.approval_status }}</p>
                <p>Destination: {{ creative.destination_url || 'Not set' }}</p>
                <small>Fingerprint: {{ creative.fingerprint || 'Unavailable' }}</small>
              </article>
            } @empty {
              <p class="empty">No creatives attached.</p>
            }
          </div>
        </section>
      } @else {
        <p class="empty">Campaign not found or unavailable.</p>
      }
    </ng-template>
    <ng-template #analyticsView
      ><section class="section-heading">
        <div>
          <h2>Analytics and profitability</h2>
          <p>
            Metrics are labeled by source and availability; unavailable values are never invented.
          </p>
        </div>
      </section>
      <section class="metric-grid">
        <article class="metric-card">
          <span>Spend</span><strong>{{ overview?.metrics?.spend ?? 'Unavailable' }}</strong
          ><small>Deterministic local metrics</small>
        </article>
        <article class="metric-card">
          <span>Impressions</span
          ><strong>{{ overview?.metrics?.impressions ?? 'Unavailable' }}</strong
          ><small>Source-labeled</small>
        </article>
        <article class="metric-card">
          <span>Clicks</span><strong>{{ overview?.metrics?.clicks ?? 'Unavailable' }}</strong
          ><small>Source-labeled</small>
        </article>
        <article class="metric-card">
          <span>ROAS / Profit</span><strong>Unavailable</strong
          ><small>No live revenue attribution connected</small>
        </article>
      </section>
      <section class="panel table-scroll">
        <table>
          <thead>
            <tr>
              <th>Campaign</th>
              <th>Provider</th>
              <th>State</th>
              <th>Metrics</th>
            </tr>
          </thead>
          <tbody>
            @for (campaign of campaigns; track campaign.id) {
              <tr>
                <td>
                  <a [routerLink]="['/ads/campaigns', campaign.id]">{{ campaign.name }}</a>
                </td>
                <td>{{ campaign.provider }}</td>
                <td>{{ campaign.state }}</td>
                <td>{{ campaign.budget?.currency || 'INR' }} local baseline</td>
              </tr>
            } @empty {
              <tr>
                <td colspan="4" class="empty">No campaign analytics yet.</td>
              </tr>
            }
          </tbody>
        </table>
      </section></ng-template
    >
    <ng-template #calendarView
      ><section class="section-heading">
        <div>
          <h2>Ads calendar</h2>
          <p>
            Scheduled windows retain campaign, provider, product, creative, and timezone lineage.
          </p>
        </div>
      </section>
      <section class="panel table-scroll">
        <table>
          <caption class="sr-only">
            Ads schedule
          </caption>
          <thead>
            <tr>
              <th>Campaign</th>
              <th>Provider</th>
              <th>Start</th>
              <th>End</th>
              <th>Timezone</th>
              <th>State</th>
            </tr>
          </thead>
          <tbody>
            @for (row of calendar; track row.id) {
              <tr>
                <td>
                  <a [routerLink]="['/ads/campaigns', row.campaign_id]">{{
                    row.campaign || row.campaign_id
                  }}</a>
                </td>
                <td>{{ row.provider || '—' }}</td>
                <td>{{ row.start_at | date: 'medium' }}</td>
                <td>{{ row.end_at | date: 'medium' }}</td>
                <td>{{ row.timezone }}</td>
                <td>{{ row.state }}</td>
              </tr>
            } @empty {
              <tr>
                <td colspan="6" class="empty">No Ads schedules yet.</td>
              </tr>
            }
          </tbody>
        </table>
      </section></ng-template
    >
    <ng-template #recoveryView
      ><section class="section-heading">
        <div>
          <h2>Recovery and failures</h2>
          <p>Actions are explicit, idempotent, and always return safe messages.</p>
        </div>
      </section>
      <section class="panel table-scroll">
        <table>
          <thead>
            <tr>
              <th>Failure code</th>
              <th>Safe message</th>
              <th>Observed</th>
              <th>Allowed actions</th>
            </tr>
          </thead>
          <tbody>
            @for (failure of recovery; track failure.failure_code) {
              <tr>
                <td>{{ failure.failure_code }}</td>
                <td>{{ failure.safe_message }}</td>
                <td>{{ failure.observed ? 'Observed' : 'Catalog' }}</td>
                <td class="row-actions">
                  @for (action of failure.recovery_actions || []; track action) {
                    @if (failure.entity_id && failure.entity_type) {
                      <button class="link-button" (click)="runRecovery(failure, action)">
                        {{ action }}
                      </button>
                    } @else {
                      <span class="muted">{{ action }}</span>
                    }
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="4" class="empty">No failures or recovery catalog entries.</td>
              </tr>
            }
          </tbody>
        </table>
      </section></ng-template
    >
    <ng-template #settingsView
      ><section class="section-heading">
        <div>
          <h2>Ads settings</h2>
          <p>Capability and safety boundary for local fake connectors.</p>
        </div>
      </section>
      <section class="two-column">
        <section class="panel">
          <h3>Server capabilities</h3>
          @for (provider of ['meta', 'google', 'amazon', 'flipkart']; track provider) {
            <div class="capability">
              <h4>{{ provider | titlecase }}</h4>
              <p>
                Objectives:
                {{
                  capabilities[provider]?.objectives?.join(', ') || 'Server response unavailable'
                }}
              </p>
              <p>
                Creative types:
                {{
                  capabilities[provider]?.creative_types?.join(', ') ||
                    'Server response unavailable'
                }}
              </p>
              <p>
                Bidding:
                {{
                  capabilities[provider]?.bidding_strategies?.join(', ') ||
                    'Server response unavailable'
                }}
              </p>
              <p>
                Targeting:
                {{ capabilities[provider]?.targeting?.join(', ') || 'Server response unavailable' }}
              </p>
            </div>
          }
        </section>
        <section class="panel">
          <h3>Operational boundary</h3>
          <ul>
            <li>Local synthetic connectors only.</li>
            <li>No credentials, tokens, cookies, SQL, or paths are shown.</li>
            <li>Provider capability and readiness responses are server-derived.</li>
            <li>Meesho Ads is not supported; no Ads connector or creation path is exposed.</li>
            <li>
              Live provider validation remains out of scope; marketplace adapters are deterministic
              local fakes.
            </li>
          </ul>
        </section>
      </section></ng-template
    >
  `,
  styles: [
    `
      :host {
        display: block;
        color: #10242b;
      }
      * {
        box-sizing: border-box;
      }
      .ads-shell {
        max-width: 1280px;
        margin: auto;
        padding: 2rem clamp(1rem, 3vw, 3rem) 4rem;
      }
      .ads-header,
      .section-heading {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 1.5rem;
      }
      .ads-header {
        margin-bottom: 1.5rem;
      }
      h1 {
        font-size: clamp(2rem, 5vw, 3.4rem);
        margin: 0.25rem 0;
      }
      h2 {
        font-size: clamp(1.6rem, 3vw, 2.4rem);
        margin: 0;
      }
      .lede,
      .section-heading p {
        color: #48636d;
      }
      .eyebrow {
        color: #17617a;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        font-size: 0.78rem;
      }
      .header-actions,
      .action-list,
      .form-actions,
      .wizard-actions,
      .row-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 0.65rem;
        align-items: center;
      }
      .badge,
      .status {
        display: inline-flex;
        border: 1px solid #17617a;
        border-radius: 999px;
        padding: 0.35rem 0.65rem;
        color: #17617a;
        font-size: 0.78rem;
        font-weight: 700;
      }
      .status.good {
        color: #14633d;
        border-color: #23824f;
      }
      .ads-nav {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        border-block: 1px solid #d4e0e3;
        padding: 0.75rem 0;
        margin-bottom: 1.5rem;
      }
      .ads-nav a {
        color: #125a73;
        padding: 0.55rem 0.75rem;
        border-radius: 6px;
        text-decoration: none;
      }
      .ads-nav a:hover,
      .ads-nav a.active {
        background: #e5f3f6;
        outline: 2px solid #61abc1;
      }
      .button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 2.7rem;
        padding: 0.55rem 0.85rem;
        border: 1px solid #17617a;
        border-radius: 7px;
        background: #fff;
        color: #125a73;
        cursor: pointer;
        text-decoration: none;
        font: inherit;
      }
      .button.primary {
        color: #fff;
        background: #17617a;
      }
      .button:disabled {
        opacity: 0.55;
        cursor: not-allowed;
      }
      button:focus-visible,
      a:focus-visible,
      input:focus-visible,
      select:focus-visible {
        outline: 3px solid #f1aa26;
        outline-offset: 2px;
      }
      .alert {
        padding: 0.85rem 1rem;
        border-radius: 6px;
        margin: 1rem 0;
      }
      .error {
        color: #8e1b26;
        background: #fff0f1;
        border-left: 4px solid #b12432;
      }
      .success {
        color: #17633f;
        background: #ecfaf1;
        border-left: 4px solid #2b8d58;
      }
      .loading {
        padding: 1.5rem 0;
      }
      .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 1rem;
        margin: 1.5rem 0;
      }
      .metric-card,
      .panel {
        border: 1px solid #cad9de;
        border-radius: 12px;
        background: #fff;
        padding: 1.1rem;
      }
      .metric-card {
        min-height: 8rem;
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
      }
      .metric-card span {
        color: #48636d;
      }
      .metric-card strong {
        font-size: 1.65rem;
        overflow-wrap: anywhere;
      }
      .metric-card small,
      .panel small {
        color: #58727b;
        display: block;
      }
      .two-column {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
        margin: 1rem 0;
      }
      .health-row {
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 0.25rem 0.75rem;
        border-bottom: 1px solid #e3ecee;
        padding: 0.6rem 0;
      }
      .health-row small {
        grid-column: 1/-1;
      }
      .safe-note,
      .muted {
        color: #506b74;
        font-size: 0.9rem;
      }
      .table-scroll {
        overflow-x: auto;
        margin-top: 1rem;
      }
      table {
        width: 100%;
        min-width: 700px;
        border-collapse: collapse;
      }
      th,
      td {
        text-align: left;
        vertical-align: top;
        padding: 0.8rem 0.65rem;
        border-bottom: 1px solid #e2eaec;
      }
      th {
        color: #395761;
        background: #f7fafb;
      }
      td small {
        margin-top: 0.2rem;
      }
      .link-button {
        border: 0;
        background: none;
        color: #125a73;
        cursor: pointer;
        font: inherit;
        padding: 0.2rem;
        text-decoration: underline;
      }
      .danger-text {
        color: #9b2530;
      }
      .empty {
        color: #5d747c;
        padding: 1.5rem;
        text-align: center;
      }
      .form-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
        margin-top: 1rem;
      }
      label {
        display: grid;
        gap: 0.35rem;
        color: #25454f;
        font-weight: 600;
      }
      input,
      select {
        width: 100%;
        min-height: 2.65rem;
        padding: 0.55rem 0.65rem;
        border: 1px solid #9cb5bd;
        border-radius: 6px;
        background: #fff;
        color: #10242b;
        font: inherit;
      }
      .form-actions {
        grid-column: 1/-1;
      }
      .filters {
        display: grid;
        grid-template-columns: 2fr 1fr 1fr;
        gap: 1rem;
        margin: 1rem 0;
      }
      .steps {
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 0.45rem;
        padding: 0;
        list-style: none;
        margin: 1.5rem 0;
      }
      .steps li {
        border: 1px solid #c4d4d8;
        border-radius: 7px;
        padding: 0.55rem;
        color: #4b6670;
        font-size: 0.85rem;
      }
      .steps li.current {
        border-color: #17617a;
        background: #e9f6f8;
        color: #10242b;
        font-weight: 700;
      }
      .steps span {
        display: inline-grid;
        place-items: center;
        width: 1.35rem;
        height: 1.35rem;
        margin-right: 0.35rem;
        border-radius: 50%;
        background: #dcecef;
      }
      .wizard {
        min-height: 18rem;
      }
      .wizard h3 {
        margin-top: 0;
      }
      .wizard-actions {
        justify-content: space-between;
        margin-top: 1rem;
        border-top: 1px solid #e2eaec;
        padding-top: 1rem;
      }
      .review-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.5rem 1rem;
      }
      .preview {
        margin-top: 1rem;
        padding: 1rem;
        background: #eef8fb;
        border-radius: 7px;
        overflow-wrap: anywhere;
      }
      .creative-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 1rem;
      }
      .creative-grid article {
        border: 1px solid #d5e1e4;
        border-radius: 8px;
        padding: 0.8rem;
      }
      .checkbox {
        display: flex;
        align-items: flex-start;
        gap: 0.5rem;
        margin: 1rem 0;
      }
      .checkbox input {
        width: auto;
        min-height: auto;
      }
      .sr-only {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
      }
      @media (max-width: 900px) {
        .metric-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .steps {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        .creative-grid {
          grid-template-columns: 1fr 1fr;
        }
      }
      @media (max-width: 600px) {
        .ads-shell {
          padding: 1rem 0.75rem 3rem;
        }
        .ads-header,
        .section-heading {
          display: block;
        }
        .header-actions {
          margin-top: 1rem;
        }
        .metric-grid,
        .two-column,
        .form-grid,
        .filters,
        .review-grid,
        .creative-grid {
          grid-template-columns: 1fr;
        }
        .steps {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .ads-nav {
          gap: 0.2rem;
        }
        .ads-nav a {
          padding: 0.5rem;
        }
      }
    `,
  ],
})
export class AdsWorkspaceComponent implements OnDestroy {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly navigation = new Subscription();
  readonly navItems = [
    { label: 'Overview', path: '/ads' },
    { label: 'Accounts', path: '/ads/accounts' },
    { label: 'Campaigns', path: '/ads/campaigns' },
    { label: 'Create', path: '/ads/create' },
    { label: 'Analytics', path: '/ads/analytics' },
    { label: 'Calendar', path: '/ads/calendar' },
    { label: 'Recovery', path: '/ads/recovery' },
    { label: 'Settings', path: '/ads/settings' },
  ];
  readonly wizardSteps = [
    'Account',
    'Product',
    'Audience',
    'Content creative',
    'Image creative',
    'Video creative',
    'Destination',
    'Budget',
    'Bidding',
    'Schedule',
    'Review',
    'Confirm',
  ];
  readonly section = signal(this.routeSection());
  readonly loading = signal(true);
  readonly submitting = signal(false);
  readonly error = signal<string | null>(null);
  readonly notice = signal<string | null>(null);
  overview: Json | null = null;
  accounts: Account[] = [];
  campaigns: Campaign[] = [];
  filteredCampaigns: Campaign[] = [];
  capabilities: Record<string, Capability> = {};
  recovery: Json[] = [];
  calendar: Json[] = [];
  campaignDetail: Json | null = null;
  analytics: Json | null = null;
  readonly readiness = signal<Json | null>(null);
  readonly preview = signal<Json | null>(null);
  showAccountForm = false;
  campaignSearch = '';
  campaignProvider = '';
  campaignState = '';
  wizardStep = 0;
  confirmChecked = false;
  accountDraft: Json = {
    provider: 'meta',
    display_name: '',
    external_account_id: '',
    environment: 'local',
    credential: '',
  };
  audienceDraft: Json = { name: '', geography: '', languages: 'en-IN', age_range: '18-65' };
  creativeDraft: Json = {
    creative_type: 'content',
    artifact_id: '',
    artifact_version: null,
    media_id: '',
    media_version: null,
    destination_url: '',
    headline: '',
  };
  campaignDraft: Json = {
    provider: 'meta',
    account_id: '',
    product_id: '',
    name: '',
    objective: 'awareness',
    timezone_name: 'Asia/Kolkata',
    bidding_strategy: 'lowest_cost',
    start_at: '',
    end_at: '',
    budget: { budget_type: 'daily', amount: 0 },
  };
  constructor() {
    this.navigation.add(
      this.router.events
        .pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd))
        .subscribe((event) => {
          this.section.set(this.routeSection(event.urlAfterRedirects));
          void this.loadSection();
        }),
    );
    void this.loadSection();
  }
  ngOnDestroy() {
    this.navigation.unsubscribe();
  }
  private routeSection(url = this.router.url): string {
    if (url.includes('/ads/create')) return 'create';
    if (url.includes('/ads/campaigns/')) return 'detail';
    if (url.includes('/ads/accounts')) return 'accounts';
    if (url.includes('/ads/campaigns')) return 'campaigns';
    if (url.includes('/ads/analytics')) return 'analytics';
    if (url.includes('/ads/calendar')) return 'calendar';
    if (url.includes('/ads/recovery')) return 'recovery';
    if (url.includes('/ads/settings')) return 'settings';
    return 'overview';
  }
  private async loadSection() {
    this.loading.set(true);
    this.error.set(null);
    try {
      const [overview, capabilities] = await Promise.all([
        firstValueFrom(this.http.get<Json>('/api/v1/ads/overview')),
        firstValueFrom(this.http.get<Record<string, Capability>>('/api/v1/ads/capabilities')),
      ]);
      this.overview = overview;
      this.capabilities = capabilities;
      this.accounts = (overview.accounts || []) as Account[];
      this.campaigns = (overview.campaigns || []) as Campaign[];
      this.filteredCampaigns = this.campaigns;
      const current = this.section();
      if (current === 'accounts')
        this.accounts = await firstValueFrom(this.http.get<Account[]>('/api/v1/ads/accounts'));
      if (current === 'campaigns' || current === 'analytics') {
        this.campaigns = await firstValueFrom(this.http.get<Campaign[]>('/api/v1/ads/campaigns'));
        this.applyCampaignFilters();
      }
      if (current === 'recovery')
        this.recovery = await firstValueFrom(this.http.get<Json[]>('/api/v1/ads/recovery'));
      if (current === 'calendar')
        this.calendar = await firstValueFrom(this.http.get<Json[]>('/api/v1/ads/calendar'));
      if (current === 'detail') await this.loadDetail();
    } catch {
      this.error.set('Ads data is unavailable. Check the authenticated API connection.');
    } finally {
      this.loading.set(false);
    }
  }
  refresh() {
    void this.loadSection();
  }
  applyCampaignFilters() {
    const query = this.campaignSearch.trim().toLowerCase();
    this.filteredCampaigns = this.campaigns.filter(
      (item) =>
        (!query || `${item.name} ${item.id}`.toLowerCase().includes(query)) &&
        (!this.campaignProvider || item.provider === this.campaignProvider) &&
        (!this.campaignState || item.state === this.campaignState),
    );
  }
  providerAccounts() {
    return this.accounts.filter(
      (account) => account.provider === this.campaignDraft.provider && account.validated,
    );
  }
  providerCapability() {
    return this.capabilities[this.campaignDraft.provider] || null;
  }
  selectedAccount() {
    return this.accounts.find((item) => item.id === this.campaignDraft.account_id) || null;
  }
  providerHealth(provider: string) {
    const account = this.accounts.find((item) => item.provider === provider);
    return account?.validated && account.enabled
      ? 'Ready'
      : account
        ? 'Needs attention'
        : 'Not configured';
  }
  overviewMetrics() {
    const metrics = this.overview?.metrics || {};
    return [
      { label: 'Accounts', value: this.accounts.length, detail: 'Meta and Google' },
      {
        label: 'Active campaigns',
        value: this.overview?.active_campaigns || 0,
        detail: 'Server state',
      },
      { label: 'Paused', value: this.overview?.paused || 0, detail: 'Explicitly paused' },
      { label: 'Failed', value: this.overview?.failed || 0, detail: 'Requires review' },
      {
        label: 'Drafts',
        value: this.campaigns.filter((item) => item.state === 'draft').length,
        detail: 'Not submitted',
      },
      { label: 'Spend', value: metrics.spend ?? 'Unavailable', detail: 'Local source' },
      { label: 'Clicks', value: metrics.clicks ?? 'Unavailable', detail: 'Local source' },
      { label: 'ROAS', value: 'Unavailable', detail: 'No live attribution' },
    ];
  }
  syncProvider() {
    this.campaignDraft.account_id = '';
    const objectives = this.providerCapability()?.objectives;
    if (objectives?.length) this.campaignDraft.objective = objectives[0];
  }
  async createAccount() {
    if (!this.accountDraft.display_name || !this.accountDraft.external_account_id) return;
    await this.mutate('account', () =>
      this.http.post('/api/v1/ads/accounts', {
        provider: this.accountDraft.provider,
        display_name: this.accountDraft.display_name,
        external_account_id: this.accountDraft.external_account_id,
        environment: this.accountDraft.environment,
        credentials: this.accountDraft.credential ? { token: this.accountDraft.credential } : {},
      }),
    );
    this.showAccountForm = false;
    this.accountDraft = {
      provider: 'meta',
      display_name: '',
      external_account_id: '',
      environment: 'local',
      credential: '',
    };
  }
  async accountAction(account: Account, action: string) {
    if (!window.confirm(`${action} ${account.display_name}?`)) return;
    await this.mutate('account', () =>
      this.http.post(`/api/v1/ads/accounts/${account.id}/${action}`, {}),
    );
  }
  async replaceCredentials(account: Account) {
    const credential = window.prompt('Enter a replacement credential (write-only):');
    if (!credential) return;
    await this.mutate('credential replacement', () =>
      this.http.patch(`/api/v1/ads/accounts/${account.id}`, { credentials: { token: credential } }),
    );
  }
  async removeCredentials(account: Account) {
    if (!window.confirm(`Remove credentials for ${account.display_name}?`)) return;
    await this.mutate('account', () =>
      this.http.delete(`/api/v1/ads/accounts/${account.id}/credentials`),
    );
  }
  private async mutate(label: string, request: () => any) {
    this.submitting.set(true);
    this.error.set(null);
    try {
      await firstValueFrom(request());
      this.notice.set(`${label} action completed safely.`);
      await this.loadSection();
    } catch (error: any) {
      this.error.set(this.safeError(error));
    } finally {
      this.submitting.set(false);
    }
  }
  private safeError(error: any) {
    const detail = error?.error?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return 'The request was rejected. Review the fields and try again.';
    return 'The request could not be completed safely. No changes were applied.';
  }
  previousStep() {
    this.wizardStep = Math.max(0, this.wizardStep - 1);
  }
  nextStep() {
    this.wizardStep = Math.min(this.wizardSteps.length - 1, this.wizardStep + 1);
  }
  async checkReadiness() {
    const body: Json = {
      campaign_id: '00000000-0000-0000-0000-000000000000',
      product_id: this.campaignDraft.product_id || null,
      creative_type: this.creativeDraft.creative_type,
      artifact_id: this.creativeDraft.artifact_id || null,
      artifact_version: this.creativeDraft.artifact_version || null,
      image_media_id:
        this.creativeDraft.creative_type === 'image' ? this.creativeDraft.media_id || null : null,
      image_version:
        this.creativeDraft.creative_type === 'image'
          ? this.creativeDraft.media_version || null
          : null,
      video_media_id:
        this.creativeDraft.creative_type === 'video' ? this.creativeDraft.media_id || null : null,
      video_version:
        this.creativeDraft.creative_type === 'video'
          ? this.creativeDraft.media_version || null
          : null,
      destination_url: this.creativeDraft.destination_url || null,
      idempotency_key: `ads-readiness-${Date.now()}`,
    };
    this.submitting.set(true);
    try {
      this.readiness.set(
        await firstValueFrom(this.http.post<Json>('/api/v1/ads/creatives/readiness', body)),
      );
    } catch (error: any) {
      this.error.set(this.safeError(error));
    } finally {
      this.submitting.set(false);
    }
  }
  private campaignPayload() {
    const budget: Json = { currency: 'INR', budget_type: this.campaignDraft.budget.budget_type };
    if (this.campaignDraft.budget.budget_type === 'lifetime')
      budget.lifetime_amount = this.campaignDraft.budget.amount;
    else budget.daily_amount = this.campaignDraft.budget.amount;
    return {
      provider: this.campaignDraft.provider,
      account_id: this.campaignDraft.account_id,
      product_id: this.campaignDraft.product_id || null,
      name: this.campaignDraft.name,
      objective: this.campaignDraft.objective,
      timezone_name: this.campaignDraft.timezone_name,
      bidding_strategy: this.campaignDraft.bidding_strategy,
      keyword_set_id: this.campaignDraft.keyword_set_id || null,
      targeting_summary: {
        audience_name: this.audienceDraft.name || 'abstract audience',
        geography: String(this.audienceDraft.geography || '')
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean),
      },
      budget,
      start_at: this.campaignDraft.start_at || null,
      end_at: this.campaignDraft.end_at || null,
      idempotency_key: `ads-campaign-${Date.now()}`,
    };
  }
  async previewCampaign() {
    this.submitting.set(true);
    this.error.set(null);
    try {
      this.preview.set(
        await firstValueFrom(
          this.http.post<Json>('/api/v1/ads/campaigns/preview', this.campaignPayload()),
        ),
      );
    } catch (error: any) {
      this.error.set(this.safeError(error));
    } finally {
      this.submitting.set(false);
    }
  }
  async confirmCampaign() {
    if (!this.confirmChecked) return;
    if (!this.preview()) await this.previewCampaign();
    const value = this.preview();
    if (!value) return;
    this.submitting.set(true);
    try {
      const result = await firstValueFrom(
        this.http.post<Json>('/api/v1/ads/campaigns/confirm', {
          campaign: this.campaignPayload(),
          preview_fingerprint: value.preview_fingerprint,
          confirm: true,
          idempotency_key: `ads-campaign-confirm-${Date.now()}`,
        }),
      );
      this.notice.set(`Campaign queued safely. Job ${result.job?.id || 'created'}.`);
      await this.router.navigate(['/ads/campaigns']);
    } catch (error: any) {
      this.error.set(this.safeError(error));
    } finally {
      this.submitting.set(false);
    }
  }
  private async loadDetail() {
    const id = this.router.url.split('/ads/campaigns/')[1]?.split('/')[0];
    if (!id) return;
    this.campaignDetail = await firstValueFrom(this.http.get<Json>(`/api/v1/ads/campaigns/${id}`));
    try {
      this.analytics = await firstValueFrom(
        this.http.get<Json>(`/api/v1/ads/campaigns/${id}/analytics`),
      );
    } catch {
      this.analytics = null;
    }
  }
  async campaignAction(campaign: Campaign, action: string) {
    if (!window.confirm(`${action} campaign ${campaign.name}?`)) return;
    await this.mutate('campaign', () =>
      this.http.post(`/api/v1/ads/campaigns/${campaign.id}/action`, {
        action,
        confirm: true,
        idempotency_key: `ads-${action}-${campaign.id}`,
      }),
    );
  }
  async reconcile(campaign: Campaign) {
    await this.mutate('reconciliation', () =>
      this.http.post(`/api/v1/ads/campaigns/${campaign.id}/reconcile`, { confirm: true }),
    );
  }
  async runRecovery(failure: Json, action: string) {
    if (!failure.entity_id || !failure.entity_type || !window.confirm(`${action} this Ads entity?`))
      return;
    await this.mutate('recovery', () =>
      this.http.post('/api/v1/ads/recovery', {
        action,
        entity_type: failure.entity_type,
        entity_id: failure.entity_id,
        failure_code: failure.failure_code,
        confirm: true,
        idempotency_key: `ads-recovery-${action}-${failure.entity_id}`,
      }),
    );
  }
}
