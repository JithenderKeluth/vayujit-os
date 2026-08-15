import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

interface Account {
  id: string;
  marketplace: string;
  display_name: string;
  environment: string;
  enabled: boolean;
  validation_status: string;
  capabilities: string[];
}
interface Listing {
  id: string;
  marketplace: string;
  product_id: string;
  account_id: string;
  title: string;
  marketplace_sku: string | null;
  status: string;
  publication_state: string;
  drift_state: string;
}
interface VideoGeneration {
  id: string;
  product_id: string | null;
  status: string;
  video_type: string;
  target_channel: string;
  aspect_ratio: string | null;
  resolution: string | null;
  duration_seconds: number | null;
  output_id: string | null;
  video_version: number;
  output_media_id: string | null;
  output_mime_type: string | null;
  output_size_bytes: number | null;
  output_width: number | null;
  output_height: number | null;
  output_status: string | null;
  created_at: string;
}
interface Mapping {
  id: string;
  marketplace: string;
  listing_id: string;
  account_id: string;
  product_id: string;
  video_generation_id: string;
  video_output_id: string;
  video_media_id: string;
  video_version: number;
  remote_video_id: string | null;
  attachment_state: string;
  reconciliation_state: string;
  drift_state: string;
  remote_state: Record<string, unknown> | null;
  last_reconciled_at: string | null;
  correlation_id: string;
}
interface Job {
  id: string;
  marketplace: string;
  operation: string;
  state: string;
  mapping_id: string | null;
  attempt_count: number;
  safe_error_message: string | null;
}
interface RecoveryItem {
  job_id: string;
  marketplace: string;
  error_code: string | null;
  safe_error_message: string | null;
  available_actions: string[];
}
interface HistoryItem {
  action: string;
  entity_type: string;
  entity_id: string;
  occurred_at: string;
  metadata: Record<string, unknown>;
}
interface CapabilityResponse {
  ruleset: string;
  marketplaces: Record<string, Record<string, unknown>>;
}
interface Readiness {
  status: string;
  ready: boolean;
  blockers: string[];
  warnings: string[];
  marketplace: string;
  account_id: string;
  listing_id: string;
  product_id: string;
  marketplace_sku: string | null;
  video_generation_id: string;
  video_output_id: string;
  video_media_id: string;
  video_version: number;
  video_state: { generation: string; output: string; media: string };
  media: {
    mime_type: string | null;
    size_bytes: number | null;
    width: number | null;
    height: number | null;
    duration_seconds: number | null;
    aspect_ratio: string | null;
  };
  compatibility: Record<string, unknown>;
  fingerprint: string;
  intended_mutation?: string;
  current_marketplace_video_state?: { remote_video_id: string | null; state: string };
}
interface Diagnostics {
  ruleset: string;
  active_video_mappings: number;
  pending_video_jobs: number;
  failed_video_jobs: number;
  ambiguous_states: number;
  reconciliation_lag: number;
  update_available_count: number;
}

@Component({
  selector: 'app-marketplace-video',
  imports: [DatePipe, FormsModule, RouterLink],
  template: `
    <section class="marketplace-page video-workspace" aria-labelledby="marketplace-video-heading">
      <header class="workspace-header">
        <div>
          <p class="eyebrow">Marketplace Video</p>
          <h1 id="marketplace-video-heading">Local Video attachment workspace</h1>
          <p>One normalized workflow for Amazon, Flipkart, and Meesho.</p>
        </div>
        <div class="workspace-actions">
          <span class="certified-badge">Local Fake-Certified Marketplace Workflow</span>
          <button type="button" (click)="load()" [disabled]="loading()">Refresh data</button>
        </div>
      </header>
      <p class="marketplace-callout">
        {{ capabilities()?.ruleset || 'Server-derived capability rules' }}. No live marketplace API
        is contacted.
      </p>
      @if (loading()) {
        <p class="marketplace-callout" role="status">Loading Marketplace Video data…</p>
      }
      @if (error()) {
        <p class="marketplace-error" role="alert">{{ error() }}</p>
      }
      @if (message()) {
        <p class="marketplace-success" role="status">{{ message() }}</p>
      }

      <nav class="workspace-tabs" aria-label="Marketplace Video sections">
        @for (section of sections; track section.id) {
          <button
            type="button"
            [class.active-tab]="activeSection() === section.id"
            (click)="activeSection.set(section.id)"
          >
            {{ section.label }}
          </button>
        }
      </nav>

      <section class="marketplace-card" aria-labelledby="overview-heading">
        <h2 id="overview-heading">Overview</h2>
        <div class="marketplace-stats">
          <div>
            <dt>Configured accounts</dt>
            <dd>{{ accounts().length }}</dd>
          </div>
          <div>
            <dt>Video-capable listings</dt>
            <dd>{{ eligibleListings().length }}</dd>
          </div>
          <div>
            <dt>Active mappings</dt>
            <dd>{{ countMappings('active') }}</dd>
          </div>
          <div>
            <dt>Pending / processing</dt>
            <dd>{{ pendingJobs() }}</dd>
          </div>
          <div>
            <dt>Failed operations</dt>
            <dd>{{ failedJobs() }}</dd>
          </div>
          <div>
            <dt>Ambiguous / reconcile</dt>
            <dd>{{ diagnostics()?.ambiguous_states ?? 0 }}</dd>
          </div>
          <div>
            <dt>Update available</dt>
            <dd>{{ diagnostics()?.update_available_count ?? 0 }}</dd>
          </div>
          <div>
            <dt>Recent history</dt>
            <dd>{{ history().length }}</dd>
          </div>
        </div>
        <div class="marketplace-table">
          <table>
            <caption>
              Marketplace breakdown
            </caption>
            <thead>
              <tr>
                <th>Marketplace</th>
                <th>Accounts</th>
                <th>Eligible listings</th>
                <th>Active Videos</th>
                <th>Failures</th>
              </tr>
            </thead>
            <tbody>
              @for (marketplace of marketplaceNames; track marketplace) {
                <tr>
                  <th scope="row">{{ marketplace }}</th>
                  <td>{{ accountsFor(marketplace) }}</td>
                  <td>{{ listingsFor(marketplace) }}</td>
                  <td>{{ mappingsFor(marketplace) }}</td>
                  <td>{{ failuresFor(marketplace) }}</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </section>

      <section class="marketplace-card" aria-labelledby="selection-heading">
        <h2 id="selection-heading">Attachment workspace</h2>
        <p>
          Select every identifier explicitly. The server determines readiness and compatibility.
        </p>
        <div class="workspace-grid-form">
          <label
            >Marketplace account
            <select
              [(ngModel)]="accountId"
              (ngModelChange)="onAccountChange()"
              aria-describedby="account-help"
            >
              <option value="">Select an account</option>
              @for (account of accounts(); track account.id) {
                <option [value]="account.id">
                  {{ account.marketplace }} · {{ account.display_name }}
                </option>
              }
            </select>
          </label>
          <label
            >Listing
            <select
              [(ngModel)]="listingId"
              (ngModelChange)="onListingChange()"
              aria-describedby="listing-help"
            >
              <option value="">Select a Video-capable listing</option>
              @for (listing of eligibleListings(); track listing.id) {
                <option [value]="listing.id">
                  {{ listing.marketplace }} · {{ listing.title }} ·
                  {{ listing.marketplace_sku || 'no SKU' }}
                </option>
              }
            </select>
          </label>
          <label
            >Approved Video Output
            <select [(ngModel)]="generationId" (ngModelChange)="onGenerationChange()">
              <option value="">Select an exact approved Video</option>
              @for (video of eligibleVideos(); track video.id) {
                <option [value]="video.id">
                  {{ video.video_type }} · {{ video.id }} · v{{ videoVersion(video) }}
                </option>
              }
            </select>
          </label>
        </div>
        <p id="account-help" class="field-help">
          {{ selectedAccount() ? accountSummary(selectedAccount()!) : 'No account selected.' }}
        </p>
        <p id="listing-help" class="field-help">
          {{
            selectedListing()
              ? listingSummary(selectedListing()!)
              : 'Only active or ready listings can be selected.'
          }}
        </p>
        @if (!accounts().length) {
          <p class="marketplace-empty">
            No marketplace account. Configure one before attaching a Video.
          </p>
        }
        @if (accounts().length && !eligibleListings().length) {
          <p class="marketplace-empty">
            No Video-capable listing is ready. Create or activate a listing first.
          </p>
        }
        @if (accounts().length && !eligibleVideos().length) {
          <p class="marketplace-empty">
            No approved Video Output is available for this owner. Generate and approve a Video
            first.
          </p>
        }
        @if (selectedAccount() && !accountReady()) {
          <p class="marketplace-error" role="alert">
            This account is disabled or not validated; attachment is blocked.
          </p>
        }
        <div class="marketplace-actions">
          <button type="button" (click)="preview()" [disabled]="!canPreview() || loading()">
            Preview attachment</button
          ><button type="button" (click)="previewUpdate()" [disabled]="!selectedMapping()">
            Preview update</button
          ><a class="button-link" routerLink="/marketplaces/listings">Open listings</a>
        </div>
      </section>

      @if (previewResult(); as preview) {
        <section class="marketplace-card preview-card" aria-labelledby="preview-heading">
          <h2 id="preview-heading">Attachment preview</h2>
          <p class="preview-label">Preview only — no marketplace change has been made.</p>
          <div class="readiness-grid">
            <div>
              <h3>Target</h3>
              <p>{{ preview.marketplace }} · {{ listingTitle(preview.listing_id) }}</p>
              <p>SKU: {{ preview.marketplace_sku || 'not supplied' }}</p>
              <p>Account: {{ accountName(preview.account_id) }}</p>
            </div>
            <div>
              <h3>Exact Video</h3>
              <p>
                Output <code>{{ preview.video_output_id }}</code>
              </p>
              <p>
                Media <code>{{ preview.video_media_id }}</code>
              </p>
              <p>
                Version {{ preview.video_version }} · {{ preview.media.duration_seconds || '—' }}s ·
                {{ preview.media.aspect_ratio || '—' }}
              </p>
              <p>
                {{ preview.media.width || '—' }}×{{ preview.media.height || '—' }} ·
                {{ preview.media.mime_type || 'unknown' }}
              </p>
            </div>
            <div>
              <h3>Readiness</h3>
              <p>
                <strong>{{ preview.ready ? 'Ready' : 'Blocked' }}</strong>
              </p>
              <p>Blockers: {{ preview.blockers.join(', ') || 'none' }}</p>
              <p>Warnings: {{ preview.warnings.join(', ') || 'none' }}</p>
            </div>
          </div>
          <div class="video-placeholder" role="img" aria-label="Approved Video preview">
            Approved Video preview · {{ preview.video_output_id }}
          </div>
          <p>
            Intended mutation: {{ preview.intended_mutation || 'attach_video' }} · fingerprint
            <code>{{ preview.fingerprint }}</code>
          </p>
          <div class="marketplace-actions">
            <button type="button" (click)="confirm()" [disabled]="!preview.ready || confirming()">
              {{ confirming() ? 'Submitting…' : 'Confirm attachment' }}</button
            ><button type="button" class="secondary-button" (click)="previewResult.set(null)">
              Close preview
            </button>
          </div>
        </section>
      }

      <section class="marketplace-card" aria-labelledby="mapping-heading">
        <h2 id="mapping-heading">Video Attachments</h2>
        @if (!mappings().length) {
          <p class="marketplace-empty">
            No active Video mappings yet. Select an account, listing, and approved Video to preview
            an attachment.
          </p>
        }
        @if (mappings().length) {
          <div class="marketplace-table">
            <table>
              <caption>
                Exact local-to-remote Video mappings
              </caption>
              <thead>
                <tr>
                  <th>Marketplace</th>
                  <th>Listing / SKU</th>
                  <th>Video</th>
                  <th>Remote state</th>
                  <th>Reconciliation</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                @for (mapping of mappings(); track mapping.id) {
                  <tr>
                    <td>{{ mapping.marketplace }}</td>
                    <td>
                      {{ listingTitle(mapping.listing_id) }}<br /><small>{{
                        listingSku(mapping.listing_id)
                      }}</small>
                    </td>
                    <td>
                      v{{ mapping.video_version }}<br /><small>{{ mapping.video_output_id }}</small>
                    </td>
                    <td>
                      {{ mapping.attachment_state }}<br />{{
                        mapping.remote_video_id || 'not attached'
                      }}
                    </td>
                    <td>{{ mapping.reconciliation_state }}<br />{{ mapping.drift_state }}</td>
                    <td>
                      <button type="button" (click)="reconcile(mapping.id)">Reconcile</button
                      ><button type="button" (click)="selectMapping(mapping)">
                        Preview update
                      </button>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>

      <section class="marketplace-card" aria-labelledby="operations-heading">
        <h2 id="operations-heading">Pending Operations & Recovery</h2>
        @if (!jobs().length) {
          <p class="marketplace-empty">No pending, processing, or completed Video operations.</p>
        }
        @if (jobs().length) {
          <div class="marketplace-table">
            <table>
              <caption>
                Durable Video operations
              </caption>
              <thead>
                <tr>
                  <th>Marketplace</th>
                  <th>Operation</th>
                  <th>State</th>
                  <th>Attempts</th>
                  <th>Safe error</th>
                  <th>Recovery</th>
                </tr>
              </thead>
              <tbody>
                @for (job of jobs(); track job.id) {
                  <tr>
                    <td>{{ job.marketplace }}</td>
                    <td>{{ job.operation }}</td>
                    <td>{{ job.state }}</td>
                    <td>{{ job.attempt_count }}</td>
                    <td>{{ job.safe_error_message || '—' }}</td>
                    <td>
                      <button type="button" (click)="openRecovery(job)">Open recovery</button>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
        @if (!recovery().length) {
          <p class="field-help">No failed operations need recovery.</p>
        }
        @for (item of recovery(); track item.job_id) {
          <article class="recovery-row">
            <h3>{{ item.marketplace }} · {{ item.error_code || 'Video failure' }}</h3>
            <p>{{ item.safe_error_message || 'Review the operation safely.' }}</p>
            <p>Available actions: {{ item.available_actions.join(', ') }}</p>
            <div class="marketplace-actions">
              @for (action of item.available_actions; track action) {
                <button type="button" (click)="recover(item, action)">{{ action }}</button>
              }
            </div>
          </article>
        }
      </section>

      <section class="marketplace-card" aria-labelledby="reconciliation-heading">
        <h2 id="reconciliation-heading">Reconciliation</h2>
        <p>Remote state is never silently merged into local history.</p>
        <p>{{ diagnostics()?.reconciliation_lag || 0 }} mapping(s) require reconciliation.</p>
        <button type="button" (click)="reconcileAll()" [disabled]="!mappings().length">
          Reconcile authorized mappings
        </button>
      </section>

      <section class="marketplace-card" aria-labelledby="history-heading">
        <h2 id="history-heading">History</h2>
        @if (!history().length) {
          <p class="marketplace-empty">
            No Video history yet. Preview and confirm an attachment to create an auditable event.
          </p>
        }
        @if (history().length) {
          <div class="marketplace-table">
            <table>
              <caption>
                Safe chronological Marketplace Video history
              </caption>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Event</th>
                  <th>Marketplace</th>
                  <th>Summary</th>
                </tr>
              </thead>
              <tbody>
                @for (item of history(); track item.entity_id + item.occurred_at) {
                  <tr>
                    <td>{{ item.occurred_at | date: 'medium' }}</td>
                    <td>{{ item.action }}</td>
                    <td>{{ text(item.metadata['marketplace']) }}</td>
                    <td>{{ safeSummary(item) }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>

      <section class="marketplace-card" aria-labelledby="diagnostics-heading">
        <h2 id="diagnostics-heading">Diagnostics</h2>
        @if (diagnostics(); as diag) {
          <div class="marketplace-stats">
            <div>
              <dt>Connector ruleset</dt>
              <dd>{{ diag.ruleset }}</dd>
            </div>
            <div>
              <dt>Active mappings</dt>
              <dd>{{ diag.active_video_mappings }}</dd>
            </div>
            <div>
              <dt>Processing</dt>
              <dd>{{ diag.pending_video_jobs }}</dd>
            </div>
            <div>
              <dt>Failures</dt>
              <dd>{{ diag.failed_video_jobs }}</dd>
            </div>
            <div>
              <dt>Ambiguous</dt>
              <dd>{{ diag.ambiguous_states }}</dd>
            </div>
            <div>
              <dt>Reconciliation needed</dt>
              <dd>{{ diag.reconciliation_lag }}</dd>
            </div>
          </div>
        }
        <p class="field-help">Credentials and sensitive connector URLs are never shown.</p>
      </section>
    </section>
  `,
  styles: [
    `
      .video-workspace {
        max-width: 1280px;
        margin: 0 auto;
      }
      .workspace-header {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
        flex-wrap: wrap;
      }
      .workspace-actions,
      .marketplace-actions {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        flex-wrap: wrap;
      }
      .certified-badge {
        background: #e8f3f5;
        color: #14566f;
        border-radius: 999px;
        padding: 0.45rem 0.7rem;
        font-weight: 700;
      }
      .workspace-grid-form {
        grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      }
      .workspace-grid-form select {
        width: 100%;
      }
      .field-help {
        color: #52636a;
        margin: 0;
      }
      .preview-label {
        font-weight: 700;
        color: #14566f;
      }
      .video-placeholder {
        display: grid;
        place-items: center;
        min-height: 8rem;
        border: 1px dashed #7595a3;
        border-radius: 0.6rem;
        background: #f4f8fa;
        color: #14566f;
      }
      .button-link {
        display: inline-block;
        padding: 0.5rem 0.7rem;
        border: 1px solid #14566f;
        border-radius: 0.4rem;
        color: #14566f;
        text-decoration: none;
      }
      .secondary-button {
        background: #eef4f6 !important;
        color: #12313b !important;
      }
      .recovery-row {
        border: 1px solid #e4c9c9;
        border-left: 4px solid #912020;
        border-radius: 0.5rem;
        padding: 0.8rem;
        margin-top: 0.7rem;
      }
      code {
        overflow-wrap: anywhere;
      }
      @media (max-width: 640px) {
        .video-workspace {
          padding: 0.8rem;
        }
        .workspace-tabs button {
          flex: 1 1 45%;
        }
        .marketplace-table {
          overflow-x: auto;
        }
        .marketplace-table table {
          min-width: 720px;
        }
      }
    `,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MarketplaceVideoComponent {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/marketplaces/video`;
  private readonly options = { withCredentials: true } as const;
  readonly marketplaceNames = ['amazon', 'flipkart', 'meesho'];
  readonly sections = [
    { id: 'overview', label: 'Overview' },
    { id: 'workspace', label: 'Listings & Attach' },
    { id: 'operations', label: 'Pending Operations' },
    { id: 'reconciliation', label: 'Reconciliation' },
    { id: 'recovery', label: 'Recovery' },
    { id: 'history', label: 'History' },
    { id: 'diagnostics', label: 'Diagnostics' },
  ];
  readonly activeSection = signal('overview');
  readonly loading = signal(false);
  readonly confirming = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  readonly accounts = signal<Account[]>([]);
  readonly listings = signal<Listing[]>([]);
  readonly generations = signal<VideoGeneration[]>([]);
  readonly mappings = signal<Mapping[]>([]);
  readonly jobs = signal<Job[]>([]);
  readonly recovery = signal<RecoveryItem[]>([]);
  readonly history = signal<HistoryItem[]>([]);
  readonly capabilities = signal<CapabilityResponse | null>(null);
  readonly diagnostics = signal<Diagnostics | null>(null);
  readonly previewResult = signal<Readiness | null>(null);
  accountId = '';
  listingId = '';
  generationId = '';
  selectedMappingState = signal<Mapping | null>(null);
  private fingerprint = '';
  private replacementMappingId: string | null = null;

  constructor() {
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const [
        accounts,
        listings,
        generations,
        capabilities,
        mappings,
        jobs,
        recovery,
        history,
        diagnostics,
      ] = await Promise.all([
        firstValueFrom(
          this.http.get<Account[]>(`${environment.apiUrl}/marketplaces/accounts`, this.options),
        ),
        firstValueFrom(
          this.http.get<Listing[]>(`${environment.apiUrl}/marketplaces/listings`, this.options),
        ),
        firstValueFrom(
          this.http.get<VideoGeneration[]>(
            `${environment.apiUrl}/ai/video/generations`,
            this.options,
          ),
        ),
        firstValueFrom(
          this.http.get<CapabilityResponse>(`${this.base}/capabilities`, this.options),
        ),
        firstValueFrom(this.http.get<Mapping[]>(`${this.base}/mappings`, this.options)),
        firstValueFrom(this.http.get<Job[]>(`${this.base}/jobs`, this.options)),
        firstValueFrom(this.http.get<RecoveryItem[]>(`${this.base}/recovery`, this.options)),
        firstValueFrom(this.http.get<HistoryItem[]>(`${this.base}/history`, this.options)),
        firstValueFrom(this.http.get<Diagnostics>(`${this.base}/diagnostics`, this.options)),
      ]);
      this.accounts.set(accounts);
      this.listings.set(listings);
      this.generations.set(generations);
      this.capabilities.set(capabilities);
      this.mappings.set(mappings);
      this.jobs.set(jobs);
      this.recovery.set(recovery);
      this.history.set(history);
      this.diagnostics.set(diagnostics);
    } catch {
      this.error.set(
        'Marketplace Video data is unavailable. Check the authenticated API connection.',
      );
    } finally {
      this.loading.set(false);
    }
  }
  selectedAccount(): Account | undefined {
    return this.accounts().find((item) => item.id === this.accountId);
  }
  selectedListing(): Listing | undefined {
    return this.listings().find((item) => item.id === this.listingId);
  }
  accountReady(): boolean {
    const account = this.selectedAccount();
    return Boolean(account?.enabled && account.validation_status === 'valid');
  }
  eligibleListings(): Listing[] {
    return this.listings().filter(
      (item) =>
        ['active', 'ready'].includes(item.status) &&
        (!this.accountId || item.account_id === this.accountId),
    );
  }
  eligibleVideos(): VideoGeneration[] {
    return this.generations().filter(
      (item) =>
        item.status === 'succeeded' &&
        item.output_status === 'approved' &&
        (!this.selectedListing()?.product_id ||
          item.product_id === this.selectedListing()?.product_id),
    );
  }
  selectedMapping(): Mapping | null {
    return this.selectedMappingState();
  }
  canPreview(): boolean {
    return Boolean(this.accountId && this.listingId && this.generationId && this.accountReady());
  }
  onAccountChange(): void {
    if (!this.eligibleListings().some((item) => item.id === this.listingId)) this.listingId = '';
    this.previewResult.set(null);
  }
  onListingChange(): void {
    const listing = this.selectedListing();
    if (listing) this.accountId = listing.account_id;
    this.generationId = '';
    this.previewResult.set(null);
  }
  onGenerationChange(): void {
    this.previewResult.set(null);
  }
  videoVersion(video: VideoGeneration): number {
    return video.video_version || 1;
  }
  request(): Record<string, unknown> {
    const video = this.generations().find((item) => item.id === this.generationId);
    return {
      listing_id: this.listingId,
      account_id: this.accountId,
      video_generation_id: this.generationId,
      video_output_id: video?.output_id,
      video_media_id: video?.output_media_id,
      video_version: video ? this.videoVersion(video) : 1,
    };
  }
  async preview(): Promise<void> {
    if (!this.canPreview()) return;
    this.error.set('');
    this.message.set('');
    this.replacementMappingId = null;
    try {
      const value = await firstValueFrom(
        this.http.post<Readiness>(`${this.base}/preview`, this.request(), this.options),
      );
      this.previewResult.set(value);
      this.fingerprint = value.fingerprint;
      this.activeSection.set('workspace');
    } catch {
      this.error.set('Unable to prepare a safe Marketplace Video preview.');
    }
  }
  async confirm(): Promise<void> {
    const preview = this.previewResult();
    if (
      !preview ||
      !preview.ready ||
      !window.confirm(
        'Confirm this exact Video attachment? No connector call is made by the browser.',
      )
    )
      return;
    this.confirming.set(true);
    try {
      const endpoint = this.replacementMappingId
        ? `${this.base}/replacement/confirm`
        : `${this.base}/confirm`;
      const value = await firstValueFrom(
        this.http.post<Record<string, unknown>>(
          endpoint,
          {
            ...this.request(),
            ...(this.replacementMappingId ? { mapping_id: this.replacementMappingId } : {}),
            fingerprint: this.fingerprint,
            confirm: true,
            idempotency_key: this.replacementMappingId
              ? `ui:replace:${this.replacementMappingId}:${this.generationId}`
              : `ui:${this.listingId}:${this.generationId}`,
          },
          this.options,
        ),
      );
      this.message.set(
        `Attachment confirmed. Job ${this.text(value['job_id'] ?? 'created')} is durable and ready for the local worker.`,
      );
      this.previewResult.set(null);
      await this.load();
    } catch {
      this.error.set('Marketplace Video confirmation was rejected safely.');
    } finally {
      this.confirming.set(false);
    }
  }
  async previewUpdate(): Promise<void> {
    const mapping = this.selectedMapping();
    if (!mapping) return;
    this.accountId = mapping.account_id;
    this.listingId = mapping.listing_id;
    this.replacementMappingId = mapping.id;
    this.generationId =
      this.generations().find(
        (item) =>
          item.product_id === mapping.product_id &&
          item.id !== mapping.video_generation_id &&
          item.video_version > mapping.video_version &&
          item.status === 'succeeded' &&
          item.output_status === 'approved',
      )?.id || '';
    if (this.generationId) {
      try {
        const value = await firstValueFrom(
          this.http.post<Readiness>(
            `${this.base}/replacement/preview`,
            { ...this.request(), mapping_id: mapping.id },
            this.options,
          ),
        );
        this.previewResult.set(value);
        this.fingerprint = value.fingerprint;
      } catch {
        this.error.set('Unable to prepare a safe Video replacement preview.');
      }
    } else this.message.set('No newer approved Video is available for this mapping.');
  }
  async reconcile(id: string): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post(`${this.base}/mappings/${id}/reconcile`, {}, this.options),
      );
      this.message.set('Mapping reconciled from the authorized connector state.');
      await this.load();
    } catch {
      this.error.set('Marketplace Video reconciliation failed safely.');
    }
  }
  async reconcileAll(): Promise<void> {
    for (const mapping of this.mappings()) await this.reconcile(mapping.id);
  }
  async recover(item: RecoveryItem, action: string): Promise<void> {
    if (!window.confirm(`Confirm recovery action: ${action}?`)) return;
    try {
      await firstValueFrom(
        this.http.post(
          `${this.base}/recovery/actions`,
          { job_id: item.job_id, action, confirm: true },
          this.options,
        ),
      );
      this.message.set('Recovery action submitted.');
      await this.load();
    } catch {
      this.error.set('Recovery action was rejected safely.');
    }
  }
  openRecovery(job: Job): void {
    this.activeSection.set('recovery');
    const item = this.recovery().find((value) => value.job_id === job.id);
    if (item)
      this.message.set(`Recovery options available for ${job.marketplace} ${job.operation}.`);
  }
  selectMapping(mapping: Mapping): void {
    this.selectedMappingState.set(mapping);
    void this.previewUpdate();
  }
  countMappings(state: string): number {
    return this.mappings().filter((item) => item.attachment_state === state).length;
  }
  pendingJobs(): number {
    return this.jobs().filter((item) => ['pending', 'running'].includes(item.state)).length;
  }
  failedJobs(): number {
    return this.jobs().filter((item) => item.state === 'failed').length;
  }
  accountsFor(marketplace: string): number {
    return this.accounts().filter((item) => item.marketplace === marketplace).length;
  }
  listingsFor(marketplace: string): number {
    return this.eligibleListings().filter((item) => item.marketplace === marketplace).length;
  }
  mappingsFor(marketplace: string): number {
    return this.mappings().filter(
      (item) => item.marketplace === marketplace && item.attachment_state === 'active',
    ).length;
  }
  failuresFor(marketplace: string): number {
    return this.jobs().filter((item) => item.marketplace === marketplace && item.state === 'failed')
      .length;
  }
  accountName(id: string): string {
    return this.accounts().find((item) => item.id === id)?.display_name || 'Account unavailable';
  }
  listingTitle(id: string): string {
    return this.listings().find((item) => item.id === id)?.title || id;
  }
  listingSku(id: string): string {
    return this.listings().find((item) => item.id === id)?.marketplace_sku || 'SKU unavailable';
  }
  accountSummary(account: Account): string {
    return `${account.marketplace} · ${account.enabled ? 'enabled' : 'disabled'} · validation ${account.validation_status} · ${account.environment} · Video ${account.capabilities.includes('video') ? 'supported' : 'not declared'}`;
  }
  listingSummary(listing: Listing): string {
    return `${listing.marketplace} · ${listing.title} · ${listing.marketplace_sku || 'no SKU'} · ${listing.status} · drift ${listing.drift_state}`;
  }
  text(value: unknown): string {
    return typeof value === 'string' ? value : value == null ? '—' : JSON.stringify(value);
  }
  safeSummary(item: HistoryItem): string {
    const metadata = item.metadata;
    return this.text(metadata['summary'] || metadata['operation'] || item.action);
  }
}
