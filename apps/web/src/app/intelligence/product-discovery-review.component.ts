import {
  ChangeDetectionStrategy,
  Component,
  OnChanges,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { IntelligenceService } from './intelligence.service';

type RecordValue = Record<string, unknown>;
const APPROVAL_REASON = 'External source approval is required before fetching.';

@Component({
  selector: 'app-product-discovery-review',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: `
    :host {
      display: block;
      min-width: 0;
    }
    section {
      border: 1px solid #b6d2d8;
      border-radius: 0.5rem;
      padding: 1rem;
      margin-block: 1rem;
      background: #fff;
    }
    h4 {
      margin-block: 0 0.75rem;
    }
    p,
    td,
    th {
      overflow-wrap: anywhere;
    }
    .metrics {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem 1.5rem;
    }
    .table-wrap {
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
    }
    th,
    td {
      text-align: left;
      vertical-align: top;
      padding: 0.6rem;
      border-bottom: 1px solid #d8e5e8;
    }
    label {
      display: block;
      margin-block: 0.75rem;
    }
    select,
    textarea {
      display: block;
      width: 100%;
      max-width: 100%;
      margin-top: 0.35rem;
      padding: 0.65rem;
      box-sizing: border-box;
      font: inherit;
    }
    input[type='checkbox'] {
      margin-right: 0.5rem;
    }
    button {
      padding: 0.65rem 1rem;
      font: inherit;
      cursor: pointer;
    }
    button:disabled {
      cursor: not-allowed;
    }
    :is(button, select, textarea, input, a):focus-visible {
      outline: 3px solid #007b91;
      outline-offset: 3px;
    }
    .error {
      color: #a12228;
    }
  `,
  template: `
    @if (fetches().length || queries().length) {
      <section aria-label="Product discovery evidence and source review">
        <h4>What happened during discovery</h4>
        <div class="metrics" role="status">
          <span>{{ queries().length }} search attempts</span>
          <span>{{ cachedSearches() }} reused searches (no new provider request)</span>
          <span>{{ fetches().length }} page-fetch attempts</span>
          <span
            >{{ completedFetches() }} successful page fetches ({{ reusedFetches() }} reused)</span
          >
          <span>{{ skipped().length }} non-product pages skipped; no approval needed</span>
        </div>
        @if (details()['review_guidance']) {
          <p>{{ details()['review_guidance'] }}</p>
        }
        <details>
          <summary>View search queries and page outcomes</summary>
          <ul>
            @for (query of queries(); track $index) {
              <li>{{ query['query'] }} — {{ query['status'] }}</li>
            }
          </ul>
          <div class="table-wrap">
            <table>
              <caption>
                Recorded page-fetch outcomes; search snippets are not product evidence.
              </caption>
              <thead>
                <tr>
                  <th scope="col">URL / domain</th>
                  <th scope="col">Fetch outcome</th>
                  <th scope="col">Reason / classification</th>
                </tr>
              </thead>
              <tbody>
                @for (fetch of outcomes(); track $index) {
                  <tr>
                    <td>{{ fetch['url'] }}<br />{{ fetch['domain'] }}</td>
                    <td>
                      {{
                        fetch['source_review_eligible'] === false
                          ? 'Not a product page'
                          : fetch['status']
                      }}
                    </td>
                    <td>
                      {{
                        fetch['skip_reason'] ||
                          fetch['failure'] ||
                          fetch['reason'] ||
                          fetch['page_type'] ||
                          'UNKNOWN'
                      }}
                      @if (fetch['reason_code']) {
                        <br /><small>{{ fetch['reason_code'] }}</small>
                      }
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        </details>
        @if (domains().length) {
          <h4>Review blocked sources</h4>
          <p>
            Product pages could not be read because source approval is missing. Do not retry until
            you have reviewed the relevant sources.
          </p>
          <p>
            Approval allows bounded read-only fetching from the selected domain and its subdomains,
            including future research. It does not verify a product, permit supplier contact, or
            bypass network safety controls. Leave unknown or prohibited policies unapproved.
          </p>
          <label
            >Discovered domain
            <select
              [ngModel]="activeDomain()"
              (ngModelChange)="selectDomain($event)"
              [disabled]="busy()"
            >
              @for (domain of domains(); track domain) {
                <option [value]="domain">{{ domain }}</option>
              }
            </select>
          </label>
          @if (reviewUrl(); as url) {
            <a [href]="url" target="_blank" rel="noopener noreferrer"
              >Open discovered page for policy review (new tab)</a
            >
          }
          <fieldset [disabled]="busy()">
            <legend>Explicit HUMAN source review</legend>
            <label
              ><input type="checkbox" [(ngModel)]="robotsReviewed" />I reviewed the robots policy
              and approve this read-only access.</label
            >
            <label
              ><input type="checkbox" [(ngModel)]="termsReviewed" />I reviewed the source terms and
              approve this use.</label
            >
            <label
              ><input type="checkbox" [(ngModel)]="accessReviewed" />I confirm this access is
              permitted without bypassing authentication or restrictions.</label
            >
            <p>Audit purpose recorded automatically: {{ auditPurpose }}</p>
            <label
              >Additional policy review note (optional)
              <textarea [(ngModel)]="reason" maxlength="400" rows="2"></textarea>
            </label>
          </fieldset>
          <button type="button" [disabled]="!canApprove()" (click)="approve()">
            {{ busy() ? 'Recording approval…' : 'Approve selected source for read-only research' }}
          </button>
        }
        @if (message()) {
          <p role="status">{{ message() }}</p>
        }
        @if (approvalRecorded() && !domains().length) {
          <p role="status">
            Recorded source approvals are available. Choose Continue product discovery to recheck
            evidence through the normal runtime. Approval does not guarantee a product result.
          </p>
        }
        @if (error()) {
          <p class="error" role="alert">{{ error() }}</p>
        }
      </section>
    }
  `,
})
export class ProductDiscoveryReviewComponent implements OnChanges {
  readonly auditPurpose = 'Read-only product discovery requested by the workspace owner.';
  private readonly intelligence = inject(IntelligenceService);
  readonly details = input<RecordValue>({});
  readonly busy = signal(false);
  readonly message = signal('');
  readonly error = signal('');
  private readonly approved = signal<string[]>([]);
  readonly approvalRecorded = signal(false);
  private readonly profilesLoaded = signal(false);
  private profilesLoading = false;
  private reviewDomain = '';
  readonly fetches = computed(() => this.records(this.details()['fetches']));
  readonly queries = computed(() => this.records(this.details()['queries']));
  readonly cachedSearches = computed(
    () => this.queries().filter((row) => row['provider_mode'] === 'REUSED_RECENT_SEARCH').length,
  );
  readonly skipped = computed(() =>
    this.records(this.details()['rejected_results']).filter(
      (row) => row['reason_code'] === 'NON_PRODUCT_PAGE',
    ),
  );
  readonly outcomes = computed(() => [...this.fetches(), ...this.skipped()]);
  readonly completedFetches = computed(
    () => this.fetches().filter((row) => row['status'] === 'COMPLETED').length,
  );
  readonly reusedFetches = computed(
    () =>
      this.fetches().filter((row) => row['status'] === 'COMPLETED' && row['reused'] === true)
        .length,
  );
  readonly domains = computed(() =>
    [
      ...new Set(
        this.fetches()
          .filter(
            (row) =>
              row['reason_code'] === 'SOURCE_APPROVAL_REQUIRED' ||
              row['failure'] === APPROVAL_REASON,
          )
          .filter((row) => row['source_review_eligible'] !== false)
          .map((row) => this.text(row['domain']).toLowerCase())
          .filter((domain) => /^[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,}$/.test(domain)),
      ),
    ]
      .filter(
        (domain) =>
          !this.approved().some(
            (approved) => domain === approved || domain.endsWith('.' + approved),
          ),
      )
      .sort(),
  );
  selectedDomain = '';
  reason = '';
  robotsReviewed = false;
  termsReviewed = false;
  accessReviewed = false;

  ngOnChanges(): void {
    this.syncReviewDomain();
    if (this.fetches().length && !this.profilesLoaded() && !this.profilesLoading)
      void this.loadProfiles();
  }

  private syncReviewDomain(): void {
    if (this.activeDomain() !== this.reviewDomain) {
      this.resetReview();
      this.selectedDomain = this.activeDomain();
      this.reviewDomain = this.selectedDomain;
    }
  }

  private async loadProfiles(): Promise<void> {
    this.profilesLoading = true;
    try {
      const profiles = await this.intelligence.externalSourceProfiles();
      this.error.set('');
      const domains = profiles
        .filter(
          (profile) =>
            profile['enabled'] === true &&
            ['robots_policy', 'terms_status', 'access_classification'].every(
              (field) => profile[field] === 'APPROVED',
            ) &&
            Array.isArray(profile['blocked_domains']) &&
            profile['blocked_domains'].length === 0,
        )
        .flatMap((profile) =>
          Array.isArray(profile['approved_domains']) ? profile['approved_domains'].map(String) : [],
        );
      this.approved.set(domains);
      this.syncReviewDomain();
      this.approvalRecorded.set(
        this.fetches().some((fetch) =>
          domains.some(
            (domain) =>
              fetch['domain'] === domain || this.text(fetch['domain']).endsWith('.' + domain),
          ),
        ),
      );
      this.profilesLoaded.set(true);
    } catch {
      this.error.set(
        'Current source approvals could not be loaded. Refresh the run before recording an approval.',
      );
    } finally {
      this.profilesLoading = false;
    }
  }

  activeDomain(): string {
    return this.domains().includes(this.selectedDomain)
      ? this.selectedDomain
      : this.domains()[0] || '';
  }

  reviewUrl(): string | null {
    const row = this.fetches().find((fetch) => fetch['domain'] === this.activeDomain());
    try {
      const url = new URL(this.text(row?.['url']));
      return url.protocol === 'https:' &&
        !url.username &&
        !url.password &&
        url.hostname === this.activeDomain()
        ? url.href
        : null;
    } catch {
      return null;
    }
  }

  selectDomain(value: string): void {
    this.selectedDomain = value;
    this.reviewDomain = value;
    this.resetReview();
  }

  canApprove(): boolean {
    return (
      this.profilesLoaded() &&
      !this.busy() &&
      !!this.activeDomain() &&
      this.reviewDomain === this.activeDomain() &&
      this.robotsReviewed &&
      this.termsReviewed &&
      this.accessReviewed
    );
  }

  async approve(): Promise<void> {
    if (!this.canApprove()) return;
    const domain = this.activeDomain();
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    try {
      const note = this.reason.trim().slice(0, 400);
      await this.intelligence.approveExternalSource(
        domain,
        this.auditPurpose + (note ? ` Note: ${note}` : ''),
      );
      this.approved.update((domains) => [...domains, domain]);
      this.approvalRecorded.set(true);
      this.syncReviewDomain();
      this.resetReview();
      this.message.set(
        `Approval recorded for ${domain}. No page was fetched. Review any other required sources, then choose Continue product discovery in the run controls.`,
      );
    } catch {
      this.error.set(
        'Source approval could not be recorded. Check your authenticated connection and source policy, then try again. No approval is confirmed.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  private resetReview(): void {
    this.reason = '';
    this.robotsReviewed = this.termsReviewed = this.accessReviewed = false;
  }

  private records(value: unknown): RecordValue[] {
    return Array.isArray(value)
      ? value.filter(
          (row): row is RecordValue => !!row && typeof row === 'object' && !Array.isArray(row),
        )
      : [];
  }

  private text(value: unknown): string {
    return typeof value === 'string' ? value : '';
  }
}
