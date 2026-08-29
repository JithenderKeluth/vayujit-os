import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  IntelligenceService,
  WebsiteCalendarEvent,
  WebsiteManufacturer,
  WebsiteContradiction,
  WebsiteChange,
  WebsiteAlert,
  WebsiteReport,
  WebsiteOverview,
  WebsiteRefreshJob,
  WebsiteSourceProfile,
} from './intelligence.service';

interface WebsiteFilters {
  country: string;
  region: string;
  category: string;
  businessType: string;
  status: string;
  verification: string;
  freshness: string;
  confidence: string;
  risk: string;
}

@Component({
  selector: 'app-website-intelligence',
  standalone: true,
  imports: [DecimalPipe, FormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="website-intelligence" aria-labelledby="website-intelligence-title">
      <header class="page-header">
        <div>
          <p class="eyebrow">Intelligence / Website research</p>
          <h1 id="website-intelligence-title">Manufacturer &amp; supplier websites</h1>
          <p class="lede">
            Evidence-first, owner-scoped website intelligence. Source claims stay clearly labelled
            until independent review.
          </p>
        </div>
        <a routerLink="/intelligence">Back to Intelligence</a>
      </header>
      <section class="boundary" aria-labelledby="boundary-title">
        <h2 id="boundary-title">Runtime boundary</h2>
        <div class="boundary-grid">
          @for (item of boundaries; track item.label) {
            <span
              ><strong>{{ item.label }}</strong
              ><small>{{ item.value }}</small></span
            >
          }
        </div>
      </section>
      <nav class="tabs" aria-label="Website Intelligence sections">
        @for (item of navigation; track item.id) {
          <a [href]="'#' + item.id">{{ item.label }}</a>
        }
      </nav>
      @if (loading()) {
        <p class="loading" role="status" aria-live="polite">
          Loading website intelligenceÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦
        </p>
      }
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }

      <section id="overview" class="panel" aria-labelledby="overview-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Overview</p>
            <h2 id="overview-title">Website intelligence at a glance</h2>
          </div>
          <span class="status-pill">{{ overview()?.status || 'LOCAL / CONTROLLED' }}</span>
        </div>
        <div class="metric-grid">
          @for (metric of overviewMetrics(); track metric.label) {
            <article class="metric-card">
              <span>{{ metric.label }}</span
              ><strong>{{ metric.value }}</strong>
            </article>
          }
        </div>
        <p class="muted">
          Last successful website research:
          {{ overview()?.last_researched || 'Not yet recorded' }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· Next refresh:
          {{ nextRefresh() }}
        </p>
      </section>

      <section id="manufacturers" class="panel" aria-labelledby="manufacturers-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Manufacturer candidates</p>
            <h2 id="manufacturers-title">Server-backed manufacturer list</h2>
          </div>
          <button type="button" (click)="reloadManufacturers()" [disabled]="busy()">
            Refresh list
          </button>
        </div>
        <form
          class="filter-grid"
          (submit)="$event.preventDefault(); reloadManufacturers()"
          aria-label="Manufacturer filters"
        >
          <label>Country<input name="country" [(ngModel)]="filters.country" /></label
          ><label>Region<input name="region" [(ngModel)]="filters.region" /></label
          ><label>Category<input name="category" [(ngModel)]="filters.category" /></label
          ><label
            >Business type<input name="businessType" [(ngModel)]="filters.businessType" /></label
          ><label>Status<input name="status" [(ngModel)]="filters.status" /></label
          ><label
            >Verification<select name="verification" [(ngModel)]="filters.verification">
              <option value="">Any</option>
              <option>VERIFIED</option>
              <option>SUPPORTED</option>
              <option>UNVERIFIED</option>
              <option>REJECTED</option>
            </select></label
          ><label
            >Confidence<select name="confidence" [(ngModel)]="filters.confidence">
              <option value="">Any</option>
              <option value="0.75">ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€šÃ‚Â¥ 0.75</option>
              <option value="0.5">ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€šÃ‚Â¥ 0.50</option>
            </select></label
          ><label
            >Risk<select name="risk" [(ngModel)]="filters.risk">
              <option value="">Any</option>
              <option>LOW</option>
              <option>MEDIUM</option>
              <option>HIGH</option>
            </select></label
          ><label
            >Freshness<select name="freshness" [(ngModel)]="filters.freshness">
              <option value="">Any</option>
              <option>FRESH</option>
              <option>AGING</option>
              <option>STALE</option>
              <option>EXPIRED</option>
            </select></label
          >
        </form>
        @if (!loading() && !manufacturers().length) {
          <p class="empty">No manufacturers match these server-aligned filters.</p>
        }
        @if (manufacturers().length) {
          <div class="table-wrap">
            <table>
              <caption>
                Manufacturer candidates and evidence quality
              </caption>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Domain</th>
                  <th>Country / region</th>
                  <th>Business type</th>
                  <th>Verification</th>
                  <th>Confidence</th>
                  <th>Risk</th>
                  <th>Freshness</th>
                  <th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                @for (row of manufacturers(); track row.id) {
                  <tr>
                    <td>
                      <button class="text-button" type="button" (click)="selectManufacturer(row)">
                        {{ row.name }}
                      </button>
                    </td>
                    <td>{{ row.domain || 'Unknown' }}</td>
                    <td>{{ row.country || 'Unknown' }} / {{ row.region || 'Unknown' }}</td>
                    <td>{{ row.business_type || 'Unknown' }}</td>
                    <td>
                      <span class="state" [class]="stateClass(row.verification)">{{
                        row.verification
                      }}</span>
                    </td>
                    <td>{{ row.confidence | number: '1.2-2' }}</td>
                    <td>{{ riskText(row.risk) }}</td>
                    <td>{{ row.freshness }}</td>
                    <td>
                      {{ row.source_count }} sources ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
                      {{ row.evidence_count }} evidence
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>

      <section id="manufacturer-detail" class="panel" aria-labelledby="manufacturer-detail-title">
        <p class="eyebrow">Manufacturer / supplier detail</p>
        <h2 id="manufacturer-detail-title">Evidence detail</h2>
        @if (selectedManufacturer()) {
          <div class="detail-grid">
            <div>
              <h3>Business identity</h3>
              <dl>
                <dt>Business name</dt>
                <dd>{{ selectedManufacturer()?.['name'] || 'Unknown' }}</dd>
                <dt>Website / domain</dt>
                <dd>{{ identityWebsite() || identityDomain() || 'Unknown' }}</dd>
                <dt>Country / region</dt>
                <dd>{{ identityCountry() || 'Unknown' }} / {{ identityRegion() || 'Unknown' }}</dd>
                <dt>Verification</dt>
                <dd>
                  {{ selectedManufacturer()?.['verification'] || 'UNVERIFIED' }}
                  ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· source-provided
                </dd>
              </dl>
            </div>
            <div>
              <h3>Review boundary</h3>
              <p>
                Public business contacts may be evidence. No Contact now, Email now, WhatsApp now,
                or Call now actions are available.
              </p>
              <p><strong>Recommended follow-up:</strong> {{ selectedUnknowns() }}</p>
            </div>
          </div>
          <div class="sub-grid">
            <article>
              <h3>Products / catalog</h3>
              <p>{{ listText(selectedManufacturer()?.['products']) }}</p>
            </article>
            <article>
              <h3>Offerings &amp; match state</h3>
              <p>{{ listText(selectedManufacturer()?.['offerings']) }}</p>
              <p class="muted">
                MATCH ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· POSSIBLE_MATCH ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· NO_MATCH
                ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· REQUIRES_REVIEW
              </p>
            </article>
            <article>
              <h3>Capabilities</h3>
              <p>{{ listText(selectedManufacturer()?.['capabilities']) }}</p>
            </article>
            <article>
              <h3>Facilities</h3>
              <p>{{ listText(selectedManufacturer()?.['facilities']) }}</p>
              <p class="muted">
                Website self-claims are labelled CLAIMED unless independently upgraded.
              </p>
            </article>
          </div>
        } @else {
          <p class="empty">
            Select a manufacturer to review server-provided identity, catalog, offerings,
            capabilities, facilities, certifications, commercial terms, risk, and history.
          </p>
        }
      </section>

      <section id="supplier-websites" class="panel" aria-labelledby="supplier-title">
        <p class="eyebrow">Supplier websites</p>
        <h2 id="supplier-title">Supplier website candidates</h2>
        <p class="muted">
          Supplier candidates are shown through selected candidate detail when returned by the API.
          No contact or purchasing action is available.
        </p>
        @if (!suppliers().length) {
          <p class="empty">No supplier websites yet.</p>
        } @else {
          <div class="table-wrap">
            <table>
              <caption>
                Supplier website candidates
              </caption>
              <thead>
                <tr>
                  <th>Domain</th>
                  <th>Match</th>
                  <th>Verification</th>
                  <th>Freshness</th>
                  <th>Confidence</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                @for (supplier of suppliers(); track supplier['id'] || $index) {
                  <tr>
                    <td>{{ supplier['domain'] || 'Unknown' }}</td>
                    <td>{{ supplier['match_state'] || 'REQUIRES_REVIEW' }}</td>
                    <td>{{ supplier['verification'] || 'UNVERIFIED' }}</td>
                    <td>{{ supplier['freshness'] || 'UNKNOWN' }}</td>
                    <td>{{ supplier['confidence'] || 'Unknown' }}</td>
                    <td>{{ riskText(supplier['risk']) }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
        <p class="empty">
          {{
            manufacturers().length
              ? 'Select a candidate above to inspect supplier website evidence.'
              : 'No supplier websites yet.'
          }}
        </p>
      </section>
      <section id="offerings" class="panel" aria-labelledby="offerings-title">
        <p class="eyebrow">Products / offerings</p>
        <h2 id="offerings-title">Catalog and supplier matches</h2>
        <p class="muted">
          Product, category, model/SKU, variants, materials, dimensions, weight, packaging,
          availability, match target, confidence, and evidence are rendered from selected detail
          when persisted.
        </p>
        <p class="empty">
          {{
            selectedManufacturer()
              ? 'Offering records are available in the selected manufacturer detail.'
              : 'No offerings yet.'
          }}
        </p>
        <p class="muted">
          MATCH ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· POSSIBLE_MATCH ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· NO_MATCH
          ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· REQUIRES_REVIEW
        </p>
      </section>
      <section id="capabilities" class="panel" aria-labelledby="capabilities-title">
        <p class="eyebrow">Capabilities &amp; facilities</p>
        <h2 id="capabilities-title">Claim lifecycle</h2>
        <div class="matrix-grid">
          @for (claim of capabilityClaims; track claim) {
            <span
              ><strong>{{ claim }}</strong
              ><small
                >Current / historical ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· verification ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
                freshness ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· evidence</small
              ></span
            >
          }
        </div>
        <p class="muted">
          NO_LONGER_OBSERVED claims remain visible in history but are not currently active.
          Facilities are explicit CLAIMED statements.
        </p>
      </section>
      <section id="certifications" class="panel" aria-labelledby="certifications-title">
        <p class="eyebrow">Certifications</p>
        <h2 id="certifications-title">Certification status matrix</h2>
        <div class="matrix-grid">
          @for (state of certificationStates; track state) {
            <span class="state" [class]="stateClass(state)"
              >{{ state }}<small>Source claim / evidence / freshness</small></span
            >
          }
        </div>
        <p class="muted">
          Logo-only evidence remains CLAIMED. Expired certificates are clearly marked; history
          records validity, expiry, removal, and verification transitions.
        </p>
      </section>
      <section id="commercial" class="panel" aria-labelledby="commercial-title">
        <p class="eyebrow">Commercial intelligence</p>
        <h2 id="commercial-title">Observed terms and append-only history</h2>
        <div class="table-wrap">
          <table>
            <caption>
              Commercial terms retain source currency and observation lineage
            </caption>
            <thead>
              <tr>
                <th>Term</th>
                <th>Value</th>
                <th>Unit / currency</th>
                <th>Source</th>
                <th>Freshness</th>
                <th>Observed at</th>
                <th>Current / historical</th>
              </tr>
            </thead>
            <tbody>
              @for (term of commercialTerms; track term) {
                <tr>
                  <th>{{ term }}</th>
                  <td>{{ selectedCommercial(term) }}</td>
                  <td>Source-provided</td>
                  <td>Website evidence</td>
                  <td>{{ selectedFreshness() }}</td>
                  <td>{{ selectedObservedAt() }}</td>
                  <td>Current and historical where available</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
        <p class="muted">
          Currencies are never silently converted; derived assumptions are labelled.
        </p>
      </section>
      <section id="risk" class="panel" aria-labelledby="risk-title">
        <p class="eyebrow">Risk &amp; confidence</p>
        <h2 id="risk-title">Explainable risk review</h2>
        <div class="detail-grid">
          <div>
            <h3>Risk overview</h3>
            <p><strong>Overall risk:</strong> {{ riskText(selectedManufacturer()?.['risk']) }}</p>
            <p>
              <strong>Current signals:</strong> {{ listText(selectedManufacturer()?.['risk']) }}
            </p>
            <p><strong>Follow-up:</strong> {{ selectedUnknowns() }}</p>
          </div>
          <div>
            <h3>Confidence components</h3>
            <p>
              Identity ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· verification ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· freshness
              ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· diversity ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· commercial completeness
              ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· certification support ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· contradictions
              ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· risk ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· unknown ratio
            </p>
            <p class="muted">
              A single first-party website does not independently prove supplier legitimacy.
            </p>
          </div>
        </div>
        <div class="matrix-grid">
          @for (state of riskStates; track state) {
            <span class="state" [class]="stateClass(state)"
              >{{ state
              }}<small>ACTIVE ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· RESOLVED / NO_LONGER_ACTIVE</small></span
            >
          }
        </div>
      </section>
      <section id="contradictions" class="panel" aria-labelledby="contradictions-title">
        <p class="eyebrow">Contradictions</p>
        <h2 id="contradictions-title">Evidence comparison</h2>
        @if (!contradictions().length) {
          <p class="empty">No contradictions yet.</p>
        } @else {
          <div class="table-wrap">
            <table>
              <caption>
                Owner-scoped contradiction list
              </caption>
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Source A / B</th>
                  <th>Values</th>
                  <th>Resolution</th>
                  <th>Correlation</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                @for (item of contradictions(); track item.id) {
                  <tr>
                    <td>{{ item['field'] || item['type'] || 'Unknown' }}</td>
                    <td>
                      {{ item['source_a'] || 'Unknown' }} / {{ item['source_b'] || 'Unknown' }}
                    </td>
                    <td>{{ listText(item['value_a']) }} / {{ listText(item['value_b']) }}</td>
                    <td>{{ item['resolution_state'] || 'Unknown' }}</td>
                    <td>{{ item['correlation_id'] || 'Unknown' }}</td>
                    <td>
                      <button
                        class="text-button"
                        type="button"
                        (click)="selectContradiction(item.id)"
                      >
                        View
                      </button>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
        @if (selectedContradiction(); as detail) {
          <p class="muted">
            Selected contradiction:
            {{ detail['reason'] || detail['resolution_state'] || 'Unknown' }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
            {{ detail['correlation_id'] || 'Unknown' }}
          </p>
        }
      </section>
      <section id="changes" class="panel" aria-labelledby="changes-title">
        <p class="eyebrow">Changes</p>
        <h2 id="changes-title">Materiality and lineage</h2>
        @if (!changes().length) {
          <p class="empty">No material changes yet.</p>
        } @else {
          <div class="table-wrap">
            <table>
              <caption>
                Owner-scoped website changes
              </caption>
              <thead>
                <tr>
                  <th>Field / type</th>
                  <th>Previous</th>
                  <th>Current</th>
                  <th>Materiality</th>
                  <th>Reason</th>
                  <th>Correlation</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                @for (item of changes(); track item.id) {
                  <tr>
                    <td>{{ item['field'] || item['type'] || 'Unknown' }}</td>
                    <td>{{ listText(item['previous']) }}</td>
                    <td>{{ listText(item['current']) }}</td>
                    <td>{{ item['materiality'] || 'Unknown' }}</td>
                    <td>{{ item['reason'] || 'Unknown' }}</td>
                    <td>{{ item['correlation_id'] || 'Unknown' }}</td>
                    <td>
                      <button class="text-button" type="button" (click)="selectChange(item.id)">
                        View
                      </button>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
        @if (selectedChange(); as detail) {
          <p class="muted">
            Selected change:
            {{ detail['reason'] || detail['materiality'] || 'Unknown' }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
            {{ detail['correlation_id'] || 'Unknown' }}
          </p>
        }
      </section>
      <section id="alerts" class="panel" aria-labelledby="alerts-title">
        <p class="eyebrow">Alerts</p>
        <h2 id="alerts-title">Review alerts</h2>
        @if (!alerts().length) {
          <p class="empty">No alerts yet.</p>
        } @else {
          <div class="table-wrap">
            <table>
              <caption>
                Owner-scoped website alerts
              </caption>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Severity</th>
                  <th>Title</th>
                  <th>Review</th>
                  <th>Correlation</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                @for (item of alerts(); track item.id) {
                  <tr>
                    <td>{{ item['type'] || 'Unknown' }}</td>
                    <td>{{ item.severity || 'Unknown' }}</td>
                    <td>{{ item['title'] || 'Unknown' }}</td>
                    <td>{{ item.review_state || 'Unknown' }}</td>
                    <td>{{ item['correlation_id'] || 'Unknown' }}</td>
                    <td>
                      <button class="text-button" type="button" (click)="selectAlert(item.id)">
                        View
                      </button>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
        @if (selectedAlert(); as detail) {
          <p class="muted">
            Selected alert:
            {{ detail['detail'] || detail['title'] || 'Unknown' }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
            {{ detail['correlation_id'] || 'Unknown' }}
          </p>
        }
      </section>
      <section id="profiles" class="panel" aria-labelledby="profiles-title">
        <p class="eyebrow">Source profiles</p>
        <h2 id="profiles-title">Allowlisted source profiles</h2>
        @if (!profiles().length) {
          <p class="empty">No source profiles yet.</p>
        } @else {
          <div class="table-wrap">
            <table>
              <caption>
                Source profile policy and refresh schedule
              </caption>
              <thead>
                <tr>
                  <th>Domain</th>
                  <th>Name / type</th>
                  <th>Classification</th>
                  <th>Enabled</th>
                  <th>Search / fetch</th>
                  <th>Freshness policy</th>
                  <th>Verification</th>
                  <th>Robots / terms</th>
                  <th>Refresh target</th>
                  <th>Timezone / next refresh</th>
                  <th>Last refresh</th>
                </tr>
              </thead>
              <tbody>
                @for (profile of profiles(); track profile.id) {
                  <tr>
                    <td>{{ profile.domain }}</td>
                    <td>
                      {{ profile.display_name }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· {{ profile.source_type }}
                    </td>
                    <td>{{ profile.classification }}</td>
                    <td>{{ profile.enabled ? 'Yes' : 'No' }}</td>
                    <td>
                      {{ profile.search_allowed ? 'Search' : 'No search' }} /
                      {{ profile.fetch_allowed ? 'Fetch' : 'No fetch' }}
                    </td>
                    <td>{{ profile.freshness_policy }}</td>
                    <td>{{ profile.verification_policy }}</td>
                    <td>{{ profile.robots_terms_status }}</td>
                    <td>{{ profile.refresh_target_type }}</td>
                    <td>{{ profile.timezone }} / {{ profile.next_refresh_at || 'Manual' }}</td>
                    <td>{{ profile.last_refresh_at || 'Never' }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>
      <section id="refresh" class="panel" aria-labelledby="refresh-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Refresh</p>
            <h2 id="refresh-title">Durable refresh jobs</h2>
          </div>
          <span class="status-pill">{{ refreshSummary() }}</span>
        </div>
        <p class="muted">
          Due ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· queued ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· running ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
          succeeded ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· failed ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· skipped ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
          backlog ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· next due ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· last success.
        </p>
        @if (!jobs().length) {
          <p class="empty">No refresh jobs yet.</p>
        } @else {
          <div class="table-wrap">
            <table>
              <caption>
                Owner-scoped refresh queue
              </caption>
              <thead>
                <tr>
                  <th>Target type</th>
                  <th>Source</th>
                  <th>Scheduled</th>
                  <th>Status</th>
                  <th>Attempt / failure</th>
                  <th>Recovery</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                @for (job of jobs(); track job.id) {
                  <tr>
                    <td>{{ job.target_type }}</td>
                    <td>{{ profileName(job.source_profile_id) }}</td>
                    <td>{{ job.scheduled_for }}</td>
                    <td>
                      <span class="state" [class]="stateClass(job.status)">{{ job.status }}</span>
                    </td>
                    <td>{{ job.failure_code || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â' }}</td>
                    <td>{{ job.failure_code ? 'Available from catalog' : 'None' }}</td>
                    <td>
                      <button
                        type="button"
                        (click)="runRefresh(job)"
                        [disabled]="busy() || job.status === 'RUNNING'"
                      >
                        Rerun
                      </button>
                      @if (job.failure_code) {
                        <button type="button" (click)="recover(job)" [disabled]="busy()">
                          Recover
                        </button>
                      }
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>
      <section id="recovery" class="panel" aria-labelledby="recovery-title">
        <p class="eyebrow">Recovery</p>
        <h2 id="recovery-title">Safe recovery actions</h2>
        <p class="muted">
          Only server-advertised actions are offered. Repeated clicks are guarded and idempotent.
        </p>
        <p><strong>Failure codes:</strong> {{ recoveryFailureCodes() }}</p>
        <p><strong>Actions:</strong> {{ recoveryActions() }}</p>
      </section>
      <section id="history" class="panel" aria-labelledby="history-title">
        <p class="eyebrow">History</p>
        <h2 id="history-title">Unified website history</h2>
        <form
          class="filter-grid"
          (submit)="
            $event.preventDefault();
            reloadHistory({
              event_type: historyEventType,
              source: historySource,
              correlation_id: historyCorrelation,
            })
          "
          aria-label="History filters"
        >
          <label>Event type<input name="historyEventType" [(ngModel)]="historyEventType" /></label>
          <label>Source/domain<input name="historySource" [(ngModel)]="historySource" /></label>
          <label
            >Correlation ID<input name="historyCorrelation" [(ngModel)]="historyCorrelation"
          /></label>
          <button type="submit" [disabled]="busy()">Apply filters</button>
        </form>
        @if (!history().length) {
          <p class="empty">No history yet.</p>
        } @else {
          <div class="table-wrap">
            <table>
              <caption>
                Observation lineage and freshness
              </caption>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Value</th>
                  <th>Domain</th>
                  <th>Verification</th>
                  <th>Freshness</th>
                  <th>Retrieved</th>
                  <th>Correlation</th>
                </tr>
              </thead>
              <tbody>
                @for (item of history(); track item['id'] || $index) {
                  <tr>
                    <td>{{ item['type'] || item['claim_type'] || 'Observation' }}</td>
                    <td>{{ item['value'] || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â' }}</td>
                    <td>{{ item['domain'] || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â' }}</td>
                    <td>{{ item['verification'] || 'UNKNOWN' }}</td>
                    <td>{{ item['freshness'] || 'UNKNOWN' }}</td>
                    <td>{{ item['retrieved_at'] || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â' }}</td>
                    <td>{{ item['mission_id'] || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â' }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>
      <section id="reports" class="panel" aria-labelledby="reports-title">
        <p class="eyebrow">Reports</p>
        <h2 id="reports-title">Website intelligence reports</h2>
        <p class="muted">Reports are server-generated and rendered as safe text.</p>
        @if (!reports().length) {
          <p class="empty">No reports yet.</p>
        } @else {
          <div class="table-wrap">
            <table>
              <caption>
                Available website reports
              </caption>
              <thead>
                <tr>
                  <th>Format</th>
                  <th>Status</th>
                  <th>Mission</th>
                  <th>Created</th>
                  <th>Correlation</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                @for (item of reports(); track item.id) {
                  <tr>
                    <td>{{ item['format'] || 'Unknown' }}</td>
                    <td>{{ item['status'] || 'Unknown' }}</td>
                    <td>{{ item['mission_id'] || 'Unknown' }}</td>
                    <td>{{ item['created_at'] || 'Unknown' }}</td>
                    <td>{{ item['correlation_id'] || 'Unknown' }}</td>
                    <td>
                      <button class="text-button" type="button" (click)="selectReport(item.id)">
                        View
                      </button>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
        @if (selectedReport(); as detail) {
          <p class="muted">
            Selected report: {{ detail['format'] || 'Unknown' }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
            {{ detail['content'] || detail['safe_content'] || 'No content' }}
          </p>
        }
      </section>
      <section id="product-channel" class="panel" aria-labelledby="channel-title">
        <p class="eyebrow">Product Channel</p>
        <h2 id="channel-title">Website research channel state</h2>
        <form
          class="filter-grid"
          (submit)="$event.preventDefault(); loadProductChannel()"
          aria-label="Product Channel lookup"
        >
          <label for="website-channel-product-id">Product ID</label>
          <input
            id="website-channel-product-id"
            name="websiteChannelProductId"
            [(ngModel)]="productChannelId"
            placeholder="Owner-scoped Product UUID"
          />
          <button type="submit" [disabled]="productChannelLoading() || !productChannelId.trim()">
            {{ productChannelLoading() ? 'LoadingÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦' : 'View projection' }}
          </button>
        </form>
        @if (productChannel(); as channel) {
          <p class="muted">
            Product: {{ channel['product_name'] || productChannelId }} · Website research:
            {{ productChannelValue(channel, 'website_research_status') }}
          </p>
        }
        @if (productChannelError()) {
          <p class="error" role="alert">{{ productChannelError() }}</p>
        }
        @if (productChannel(); as channel) {
          <div class="metric-grid" aria-label="Server-derived Product Channel details">
            @for (field of productChannelFields; track field) {
              <article class="metric-card">
                <span>{{ field }}</span>
                <strong>{{ productChannelValue(channel, field) }}</strong>
              </article>
            }
          </div>
        } @else if (!productChannelLoading() && !productChannelError()) {
          <p class="empty">
            Enter an owner-scoped Product ID to view server-derived website state.
          </p>
        }
      </section>
      <section id="calendar" class="panel" aria-labelledby="calendar-title">
        <p class="eyebrow">Calendar</p>
        <h2 id="calendar-title">Refresh calendar</h2>
        @if (!calendar().length) {
          <p class="empty">No refresh events scheduled.</p>
        } @else {
          <div class="table-wrap">
            <table>
              <caption>
                Website refresh due events
              </caption>
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Target</th>
                  <th>Domain</th>
                  <th>Scheduled</th>
                  <th>Timezone</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                @for (event of calendar(); track event.id) {
                  <tr>
                    <td>{{ event.type }}</td>
                    <td>{{ event.target_type }}</td>
                    <td>{{ event.domain }}</td>
                    <td>{{ event.scheduled_at }}</td>
                    <td>{{ event.timezone }}</td>
                    <td>{{ event.status }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>
      <section id="operations" class="panel" aria-labelledby="operations-title">
        <p class="eyebrow">Operations</p>
        <h2 id="operations-title">Operational linkage</h2>
        <p>
          Worker management, scheduler control, integrity, performance, and kill switches remain in
          <a routerLink="/operations">Operations</a>. This workspace does not duplicate controls.
        </p>
        <p class="muted">
          System Doctor visibility: website intelligence ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· refresh worker
          ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· scheduler ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· profiles ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· budgets
          ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· rate limits ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· live broad web state
          ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· supplier contact disabled ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· purchasing not
          implemented.
        </p>
      </section>
    </main>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .website-intelligence {
        max-width: 120rem;
        margin: 0 auto;
      }
      .page-header,
      .section-heading {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
      }
      .page-header {
        margin-bottom: 2rem;
      }
      h1 {
        font-size: clamp(2rem, 4vw, 3.5rem);
        margin: 0.25rem 0 0.75rem;
      }
      h2 {
        margin: 0.25rem 0 1rem;
      }
      h3 {
        margin-top: 0;
      }
      .lede,
      .muted {
        color: #527078;
      }
      .boundary {
        background: #102f34;
        color: #edf8f5;
        padding: 1rem 1.25rem;
        border-radius: 0.75rem;
        margin-bottom: 1.25rem;
      }
      .boundary h2 {
        color: #fff;
        font-size: 1.05rem;
      }
      .boundary-grid,
      .metric-grid,
      .matrix-grid,
      .detail-grid,
      .sub-grid,
      .filter-grid {
        display: grid;
        gap: 0.75rem;
      }
      .boundary-grid {
        grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
      }
      .boundary-grid span {
        display: grid;
        gap: 0.2rem;
        border-left: 3px solid #78c4d7;
        padding-left: 0.65rem;
      }
      .boundary-grid small {
        color: #c7dfdc;
      }
      .tabs {
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
        margin: 1rem 0 1.5rem;
      }
      .tabs a {
        border: 1px solid #9ebfc3;
        border-radius: 999px;
        padding: 0.5rem 0.75rem;
        color: #155a73;
        background: #fff;
      }
      .panel {
        background: #fff;
        border: 1px solid #d0e0e0;
        border-radius: 0.9rem;
        padding: 1.25rem;
        margin: 1rem 0;
        scroll-margin-top: 1rem;
      }
      .metric-grid {
        grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
      }
      .metric-card {
        border: 1px solid #c8dadd;
        border-radius: 0.65rem;
        padding: 1rem;
        display: grid;
        gap: 0.5rem;
      }
      .metric-card strong {
        font-size: 1.7rem;
      }
      .status-pill,
      .state {
        display: inline-block;
        border-radius: 999px;
        padding: 0.2rem 0.5rem;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.03em;
      }
      .status-pill {
        background: #e1f2ee;
        color: #135c56;
      }
      .state {
        background: #edf0f0;
        color: #334b50;
      }
      .state-high,
      .state-failed,
      .state-expired,
      .state-rejected {
        background: #ffe4e1;
        color: #8c241b;
      }
      .state-medium,
      .state-aging,
      .state-possible_match,
      .state-requires_review {
        background: #fff3cc;
        color: #765500;
      }
      .state-low,
      .state-fresh,
      .state-verified,
      .state-succeeded,
      .state-match {
        background: #def4e8;
        color: #17633b;
      }
      .loading {
        padding: 1rem;
        background: #eaf5f7;
      }
      .error {
        padding: 1rem;
        background: #ffeded;
        color: #8b211b;
        border-left: 4px solid #b82e26;
      }
      .empty {
        border: 1px dashed #9ebfc3;
        border-radius: 0.5rem;
        padding: 1rem;
        color: #526d72;
      }
      .filter-grid {
        grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
        margin-bottom: 1rem;
      }
      label {
        display: grid;
        gap: 0.3rem;
        font-weight: 600;
        color: #29444a;
      }
      input,
      select,
      button {
        font: inherit;
      }
      input,
      select {
        min-height: 2.4rem;
        border: 1px solid #9ebfc3;
        border-radius: 0.35rem;
        padding: 0.35rem 0.5rem;
      }
      button {
        border: 1px solid #1b6176;
        background: #1b6176;
        color: #fff;
        border-radius: 0.4rem;
        padding: 0.45rem 0.7rem;
        cursor: pointer;
      }
      button:disabled {
        opacity: 0.55;
        cursor: not-allowed;
      }
      .text-button {
        border: 0;
        padding: 0;
        background: transparent;
        color: #0d6686;
        text-decoration: underline;
      }
      .table-wrap {
        overflow-x: auto;
      }
      table {
        width: 100%;
        min-width: 62rem;
        border-collapse: collapse;
      }
      caption {
        text-align: left;
        font-weight: 700;
        padding: 0.5rem 0;
      }
      th,
      td {
        text-align: left;
        vertical-align: top;
        border-bottom: 1px solid #d9e5e5;
        padding: 0.65rem 0.5rem;
      }
      th {
        color: #29444a;
      }
      .detail-grid {
        grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
      }
      .sub-grid {
        grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
        margin-top: 1rem;
      }
      .sub-grid article {
        border: 1px solid #d8e5e5;
        border-radius: 0.5rem;
        padding: 0.85rem;
      }
      .matrix-grid {
        grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
      }
      .matrix-grid span {
        display: grid;
        gap: 0.25rem;
        border: 1px solid #c8dadd;
        border-radius: 0.5rem;
        padding: 0.65rem;
      }
      .matrix-grid small {
        color: #527078;
      }
      dl {
        display: grid;
        grid-template-columns: minmax(8rem, auto) 1fr;
        gap: 0.5rem;
      }
      dt {
        font-weight: 700;
      }
      dd {
        margin: 0;
      }
      a:focus,
      button:focus,
      input:focus,
      select:focus {
        outline: 3px solid #74b9d4;
        outline-offset: 2px;
      }
      @media (max-width: 700px) {
        .page-header,
        .section-heading {
          flex-direction: column;
        }
        .panel {
          padding: 0.85rem;
        }
        table {
          min-width: 48rem;
        }
        .tabs {
          overflow-x: auto;
          flex-wrap: nowrap;
        }
      }
    `,
  ],
})
export class WebsiteIntelligenceComponent {
  private readonly intelligence = inject(IntelligenceService);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly overview = signal<WebsiteOverview | null>(null);
  readonly manufacturers = signal<WebsiteManufacturer[]>([]);
  readonly suppliers = signal<Record<string, unknown>[]>([]);
  readonly profiles = signal<WebsiteSourceProfile[]>([]);
  readonly jobs = signal<WebsiteRefreshJob[]>([]);
  readonly calendar = signal<WebsiteCalendarEvent[]>([]);
  readonly history = signal<Record<string, unknown>[]>([]);
  readonly contradictions = signal<WebsiteContradiction[]>([]);
  readonly changes = signal<WebsiteChange[]>([]);
  readonly alerts = signal<WebsiteAlert[]>([]);
  readonly reports = signal<WebsiteReport[]>([]);
  readonly selectedContradiction = signal<WebsiteContradiction | null>(null);
  readonly selectedChange = signal<WebsiteChange | null>(null);
  readonly selectedAlert = signal<WebsiteAlert | null>(null);
  readonly selectedReport = signal<WebsiteReport | null>(null);
  readonly productChannel = signal<Record<string, unknown> | null>(null);
  readonly productChannelLoading = signal(false);
  readonly productChannelError = signal('');
  readonly selectedManufacturer = signal<Record<string, unknown> | null>(null);
  readonly recoveryCatalog = signal<Record<string, unknown>>({});
  historyEventType = '';
  historySource = '';
  historyCorrelation = '';
  productChannelId = '';
  readonly filters: WebsiteFilters = {
    country: '',
    region: '',
    category: '',
    businessType: '',
    status: '',
    verification: '',
    freshness: '',
    confidence: '',
    risk: '',
  };
  readonly navigation = [
    { id: 'overview', label: 'Overview' },
    { id: 'manufacturers', label: 'Manufacturers' },
    { id: 'supplier-websites', label: 'Supplier Websites' },
    { id: 'manufacturer-detail', label: 'Detail' },
    { id: 'offerings', label: 'Offerings' },
    { id: 'capabilities', label: 'Capabilities' },
    { id: 'certifications', label: 'Certifications' },
    { id: 'commercial', label: 'Commercial Intelligence' },
    { id: 'risk', label: 'Risk' },
    { id: 'contradictions', label: 'Contradictions' },
    { id: 'changes', label: 'Changes' },
    { id: 'alerts', label: 'Alerts' },
    { id: 'profiles', label: 'Source Profiles' },
    { id: 'refresh', label: 'Refresh' },
    { id: 'recovery', label: 'Recovery' },
    { id: 'history', label: 'History' },
    { id: 'reports', label: 'Reports' },
    { id: 'product-channel', label: 'Product Channel' },
    { id: 'calendar', label: 'Calendar' },
    { id: 'operations', label: 'Operations' },
  ];
  readonly boundaries = [
    { label: 'WEBSITE INTELLIGENCE', value: 'LOCAL / CONTROLLED' },
    { label: 'LIVE BROAD WEB', value: 'DISABLED' },
    { label: 'RECURSIVE CRAWLING', value: 'DISABLED' },
    { label: 'EXTERNAL AI', value: 'NOT CONFIGURED' },
    { label: 'SUPPLIER CONTACT', value: 'DISABLED' },
    { label: 'PURCHASING', value: 'NOT IMPLEMENTED' },
  ];
  readonly capabilityClaims = [
    'OEM',
    'ODM',
    'PRIVATE_LABEL',
    'CUSTOM_PACKAGING',
    'CUSTOM_DESIGN',
    'SAMPLE_AVAILABLE',
    'LOW_MOQ',
    'BULK_PRODUCTION',
    'EXPORT_CAPABLE',
    'QUALITY_INSPECTION',
    'DESIGN_SUPPORT',
    'TOOLING_MOLD',
  ];
  readonly certificationStates = [
    'CLAIMED',
    'DOCUMENT_REFERENCED',
    'SUPPORTED',
    'VERIFIED',
    'EXPIRED',
    'UNKNOWN',
    'NO_LONGER_OBSERVED',
  ];
  readonly riskStates = ['LOW', 'MEDIUM', 'HIGH', 'ACTIVE', 'RESOLVED / NO_LONGER_ACTIVE'];
  readonly commercialTerms = [
    'Pricing',
    'MOQ',
    'Lead Time',
    'Shipping',
    'Incoterms',
    'Sample Terms',
    'Availability',
  ];
  readonly productChannelFields = [
    'website_research_status',
    'manufacturer_candidate_count',
    'supplier_website_candidate_count',
    'offering_count',
    'last_website_research_at',
    'next_website_refresh_at',
    'freshness',
    'confidence',
    'risk',
    'verification',
    'material_change_count',
    'open_contradiction_count',
    'active_alert_count',
    'refresh_due',
    'follow_up_required',
  ];
  constructor() {
    void this.load();
  }
  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    const results = await Promise.allSettled([
      this.intelligence.websiteOverview(),
      this.intelligence.websiteManufacturers(),
      this.intelligence.websiteSuppliers(),
      this.intelligence.websiteProfiles(),
      this.intelligence.websiteRefreshJobs(),
      this.intelligence.websiteCalendar(),
      this.intelligence.websiteHistory(),
      this.intelligence.websiteRecoveryCatalog(),
      this.intelligence.websiteContradictions(),
      this.intelligence.websiteChanges(),
      this.intelligence.websiteAlerts(),
      this.intelligence.websiteReports(),
    ]);
    const [
      overview,
      manufacturers,
      suppliers,
      profiles,
      jobs,
      calendar,
      history,
      recovery,
      contradictions,
      changes,
      alerts,
      reports,
    ] = results;
    if (overview.status === 'fulfilled') this.overview.set(overview.value);
    if (manufacturers.status === 'fulfilled') this.manufacturers.set(manufacturers.value);
    if (suppliers.status === 'fulfilled') this.suppliers.set(suppliers.value);
    if (profiles.status === 'fulfilled') this.profiles.set(profiles.value.profiles);
    if (jobs.status === 'fulfilled') this.jobs.set(jobs.value);
    if (calendar.status === 'fulfilled') this.calendar.set(calendar.value);
    if (history.status === 'fulfilled') this.history.set(history.value);
    if (recovery.status === 'fulfilled') this.recoveryCatalog.set(recovery.value);
    if (contradictions.status === 'fulfilled') this.contradictions.set(contradictions.value);
    if (changes.status === 'fulfilled') this.changes.set(changes.value);
    if (alerts.status === 'fulfilled') this.alerts.set(alerts.value);
    if (reports.status === 'fulfilled') this.reports.set(reports.value);
    if (results.some((item) => item['status'] === 'rejected'))
      this.error.set(
        'Website intelligence data is unavailable. Check the authenticated API connection.',
      );
    this.loading.set(false);
  }
  async reloadManufacturers(): Promise<void> {
    try {
      this.busy.set(true);
      this.error.set('');
      this.manufacturers.set(
        await this.intelligence.websiteManufacturers({
          country: this.filters.country,
          region: this.filters.region,
          category: this.filters.category,
          verification: this.filters.verification,
          freshness: this.filters.freshness,
          min_confidence: this.filters.confidence,
          risk: this.filters.risk,
          business_type: this.filters.businessType,
          status: this.filters.status,
        }),
      );
    } catch {
      this.error.set('Manufacturer data is unavailable. Check the authenticated API connection.');
    } finally {
      this.busy.set(false);
    }
  }
  async selectManufacturer(row: WebsiteManufacturer): Promise<void> {
    try {
      this.selectedManufacturer.set(await this.intelligence.websiteManufacturer(row.id));
    } catch {
      this.error.set('Manufacturer detail is unavailable.');
    }
  }
  async selectContradiction(id: string): Promise<void> {
    try {
      this.selectedContradiction.set(await this.intelligence.websiteContradiction(id));
    } catch {
      this.error.set('Contradiction detail is unavailable.');
    }
  }
  async selectChange(id: string): Promise<void> {
    try {
      this.selectedChange.set(await this.intelligence.websiteChange(id));
    } catch {
      this.error.set('Change detail is unavailable.');
    }
  }
  async selectAlert(id: string): Promise<void> {
    try {
      this.selectedAlert.set(await this.intelligence.websiteAlert(id));
    } catch {
      this.error.set('Alert detail is unavailable.');
    }
  }
  async selectReport(id: string): Promise<void> {
    try {
      this.selectedReport.set(await this.intelligence.websiteReport(id));
    } catch {
      this.error.set('Report detail is unavailable.');
    }
  }
  async reloadHistory(filters?: Record<string, string>): Promise<void> {
    try {
      this.history.set(await this.intelligence.websiteHistoryFiltered(filters));
    } catch {
      this.error.set('Website history is unavailable.');
    }
  }
  async loadProductChannel(): Promise<void> {
    const productId = this.productChannelId.trim();
    if (!productId) return;
    this.productChannelLoading.set(true);
    this.productChannelError.set('');
    this.productChannel.set(null);
    try {
      this.productChannel.set(await this.intelligence.websiteProductChannel(productId));
    } catch {
      this.productChannelError.set(
        'Product Channel data is unavailable or the Product is not owner-scoped.',
      );
    } finally {
      this.productChannelLoading.set(false);
    }
  }
  productChannelValue(channel: Record<string, unknown>, field: string): string {
    const value = channel[field];
    if (value === null || value === undefined || value === '') return 'Unknown';
    if (Array.isArray(value)) return value.join(', ') || 'None';
    if (typeof value === 'object') return '[structured value]';
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean')
      return String(value);
    return 'Unknown';
  }
  async runRefresh(job: WebsiteRefreshJob): Promise<void> {
    if (this.busy()) return;
    if (!window.confirm('Rerun this bounded website refresh?')) return;
    try {
      this.busy.set(true);
      await this.intelligence.runWebsiteRefresh(job.id);
      await this.load();
    } catch {
      this.error.set('Refresh could not be completed safely.');
    } finally {
      this.busy.set(false);
    }
  }
  async recover(job: WebsiteRefreshJob): Promise<void> {
    if (this.busy()) return;
    if (!window.confirm('Apply the server-advertised recovery action?')) return;
    const actions = this.recoveryCatalog()['actions'];
    const action = Array.isArray(actions) && actions.length ? String(actions[0]) : 'retry';
    try {
      this.busy.set(true);
      await this.intelligence.recoverWebsiteRefresh(job.id, {
        action,
        failure_code: job.failure_code,
        idempotency_key: `website-ui:${job.id}:${action}`,
      });
      await this.load();
    } catch {
      this.error.set('Recovery could not be completed safely.');
    } finally {
      this.busy.set(false);
    }
  }
  overviewMetrics(): Array<{ label: string; value: number | string }> {
    const value = this.overview();
    return [
      { label: 'Source profiles', value: this.profiles().length },
      { label: 'Manufacturer candidates', value: value?.manufacturer_candidates ?? 0 },
      { label: 'Supplier websites', value: value?.supplier_websites ?? 0 },
      { label: 'Offerings', value: value?.offering_count ?? 0 },
      { label: 'Observations', value: this.history().length },
      { label: 'Capability claims', value: this.selectedArray('capabilities').length },
      { label: 'Facility claims', value: this.selectedArray('facilities').length },
      { label: 'Certifications', value: this.selectedArray('certifications').length },
      { label: 'Commercial observations', value: this.commercialTerms.length },
      { label: 'High-risk candidates', value: value?.high_risk_suppliers ?? 0 },
      { label: 'Contradictions', value: value?.unresolved_contradictions ?? 0 },
      { label: 'Material changes', value: 0 },
      { label: 'Alerts', value: 0 },
      { label: 'Refresh due', value: this.calendar().length },
      { label: 'Queued refresh', value: value?.queue ?? 0 },
      { label: 'Failed refresh', value: value?.failed ?? 0 },
    ];
  }
  nextRefresh(): string {
    return (
      this.profiles()
        .map((profile) => profile.next_refresh_at)
        .find(Boolean) || 'Not scheduled'
    );
  }
  refreshSummary(): string {
    const statuses = this.jobs().map((job) => job.status);
    return statuses.length
      ? `${statuses.length} jobs ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· ${statuses.filter((status) => status === 'FAILED').length} failed`
      : 'No jobs';
  }
  profileName(id: string): string {
    return this.profiles().find((profile) => profile.id === id)?.domain || 'Unknown source';
  }
  stateClass(value: string): string {
    return `state-${value.toLowerCase().replaceAll(' ', '_').replaceAll('/', '_')}`;
  }
  riskText(value: unknown): string {
    return Array.isArray(value) && value.length
      ? value.join(', ')
      : typeof value === 'string' && value
        ? value
        : 'LOW / UNKNOWN';
  }
  listText(value: unknown): string {
    if (!Array.isArray(value) || !value.length) return 'No persisted records.';
    return value
      .map((item) => (typeof item === 'string' ? item : String(JSON.stringify(item))))
      .join(' ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· ');
  }
  selectedArray(key: string): unknown[] {
    const value = this.selectedManufacturer()?.[key];
    return Array.isArray(value) ? value : [];
  }
  selectedCommercial(term: string): string {
    const commercial = this.selectedManufacturer()?.['commercial'];
    const entries: unknown[] = Array.isArray(commercial) ? (commercial as unknown[]) : [];
    const item = entries.find(
      (entry: unknown) =>
        typeof entry === 'object' &&
        entry !== null &&
        Object.keys(entry).some((key) =>
          key.toLowerCase().includes(term.toLowerCase().split(' ')[0]),
        ),
    );
    return item ? String(JSON.stringify(item)) : 'Not observed';
  }
  identityValue(key: string): string {
    const identity = this.selectedManufacturer()?.['identity'];
    if (typeof identity !== 'object' || identity === null) return '';
    const value = (identity as Record<string, unknown>)[key];
    return typeof value === 'string' ? value : '';
  }
  identityWebsite(): string {
    return this.identityValue('website');
  }
  identityDomain(): string {
    return this.identityValue('domain');
  }
  identityCountry(): string {
    return this.identityValue('country');
  }
  identityRegion(): string {
    return this.identityValue('region');
  }
  selectedUnknowns(): string {
    const value = this.selectedManufacturer()?.['unknowns'];
    return Array.isArray(value) && value.length
      ? value.map(String).join(', ')
      : 'Independent verification';
  }
  selectedFreshness(): string {
    const value = this.selectedManufacturer()?.['freshness'];
    return typeof value === 'string' ? value : 'UNKNOWN';
  }
  selectedObservedAt(): string {
    const history = this.selectedArray('history');
    const item = history.at(-1);
    return typeof item === 'object' && item !== null && 'retrieved_at' in item
      ? String((item as Record<string, unknown>)['retrieved_at'])
      : 'Not observed';
  }
  recoveryFailureCodes(): string {
    const value = this.recoveryCatalog()['failure_codes'];
    return Array.isArray(value) && value.length ? value.join(', ') : 'None';
  }
  recoveryActions(): string {
    const value = this.recoveryCatalog()['actions'];
    return Array.isArray(value) && value.length ? value.join(', ') : 'None';
  }
}
