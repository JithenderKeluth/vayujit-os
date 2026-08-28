import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import {
  ExternalRecord,
  ExternalResearchPolicy,
  IntelligenceService,
} from './intelligence.service';

type Section = { id: string; label: string };

@Component({
  selector: 'app-external-research-workspace',
  imports: [RouterLink, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="external-page" aria-labelledby="external-title">
      <header class="page-header">
        <div>
          <p class="eyebrow">Controlled external research</p>
          <h1 id="external-title">External Research</h1>
          <p class="lede">Owner-scoped discovery, approved fetch, and human-review evidence.</p>
        </div>
        <a routerLink="/intelligence" class="secondary-button">Back to Intelligence</a>
      </header>

      <div class="runtime-banner" role="status" aria-live="polite">
        <strong>{{ runtimeLabel() }}</strong>
        <span>LIVE SEARCH ? NOT VALIDATED ? LIVE FETCH ? NOT VALIDATED</span>
        <span>External AI disabled ? Unrestricted scraping disabled</span>
      </div>

      <nav class="workspace-nav" aria-label="External Research sections">
        @for (section of sections; track section.id) {
          <a
            [href]="'#' + section.id"
            [attr.aria-current]="activeSection() === section.id ? 'page' : null"
            (click)="activeSection.set(section.id)"
            >{{ section.label }}</a
          >
        }
      </nav>

      @if (loading()) {
        <p class="loading" role="status">Loading external research workspace?</p>
      }
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }

      <section id="overview" class="panel" aria-labelledby="overview-title">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Overview</p>
            <h2 id="overview-title">External research readiness</h2>
          </div>
          <button type="button" (click)="load()" [disabled]="loading()">Refresh</button>
        </div>
        <div class="status-grid" aria-label="External research status">
          <article class="status-card">
            <span>Provider</span><strong>{{ text(policy(), 'provider', 'Not configured') }}</strong>
          </article>
          <article class="status-card">
            <span>Mode</span><strong>{{ text(policy(), 'mode', 'DISABLED') }}</strong>
          </article>
          <article class="status-card">
            <span>Provider health</span><strong>{{ text(status(), 'status', 'UNKNOWN') }}</strong>
          </article>
          <article class="status-card">
            <span>Search</span><strong>{{ boolLabel(policy(), 'search_enabled') }}</strong>
          </article>
          <article class="status-card">
            <span>Approved fetch</span><strong>{{ boolLabel(policy(), 'fetch_enabled') }}</strong>
          </article>
          <article class="status-card">
            <span>Approved domains</span
            ><strong>{{ boolLabel(policy(), 'approved_domains_configured') }}</strong>
          </article>
          <article class="status-card">
            <span>Verified evidence</span><strong>{{ evidenceCount('VERIFIED') }}</strong>
          </article>
          <article class="status-card">
            <span>Supported evidence</span><strong>{{ evidenceCount('SUPPORTED') }}</strong>
          </article>
          <article class="status-card">
            <span>Stale / expired</span
            ><strong>{{ evidenceFreshness('STALE') }} / {{ evidenceFreshness('EXPIRED') }}</strong>
          </article>
          <article class="status-card">
            <span>Contradictions</span><strong>{{ contradictions().length }}</strong>
          </article>
          <article class="status-card">
            <span>Material changes</span><strong>{{ changes().length }}</strong>
          </article>
          <article class="status-card">
            <span>Alerts / recovery</span
            ><strong>{{ alerts().length }} / {{ recoveries().length }}</strong>
          </article>
        </div>
        <div class="callout" aria-label="Live provider boundary">
          <strong>LIVE SEARCH ? NOT VALIDATED</strong>
          <strong>LIVE FETCH ? NOT VALIDATED</strong>
          <span
            >Credentials and approved live domains are deployment-controlled and are never shown
            here.</span
          >
        </div>
      </section>

      <section id="providers" class="panel" aria-labelledby="providers-title">
        <p class="eyebrow">Providers</p>
        <h2 id="providers-title">Provider registry</h2>
        <p class="hint">Provider enablement is controlled by deployment configuration.</p>
        <div class="table-wrap">
          <table>
            <caption>
              Configured external provider status
            </caption>
            <thead>
              <tr>
                <th scope="col">Provider</th>
                <th scope="col">Mode</th>
                <th scope="col">Status</th>
                <th scope="col">Credentials</th>
                <th scope="col">Search</th>
                <th scope="col">Fetch</th>
                <th scope="col">Rate limit</th>
                <th scope="col">Kill switch</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">{{ text(policy(), 'provider', 'deterministic') }}</th>
                <td>{{ text(policy(), 'mode', 'DISABLED') }}</td>
                <td>{{ text(status(), 'status', 'DISABLED') }}</td>
                <td>{{ boolLabel(policy(), 'credentials_configured') }}</td>
                <td>{{ boolLabel(policy(), 'search_enabled') }}</td>
                <td>{{ boolLabel(policy(), 'fetch_enabled') }}</td>
                <td>{{ quotaLabel() }}</td>
                <td>{{ boolLabel(policy(), 'kill_switch') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="badge-row" aria-label="Supported provider statuses">
          @for (state of providerStates; track state) {
            <span class="badge">{{ state }}</span>
          }
        </div>
        <p class="privacy-note">
          Credential values, tokens, private payloads, and provider responses are never rendered.
        </p>
      </section>

      <section id="source-policy" class="panel" aria-labelledby="policy-title">
        <p class="eyebrow">Source Policy</p>
        <h2 id="policy-title">Approved source policy</h2>
        <div class="status-grid compact">
          <article class="status-card">
            <span>Global status</span><strong>{{ text(policy(), 'status', 'DISABLED') }}</strong>
          </article>
          <article class="status-card">
            <span>Allowed modes</span><strong>{{ listText(policy(), 'allowed_modes') }}</strong>
          </article>
          <article class="status-card">
            <span>Approved domains</span
            ><strong>{{ boolLabel(policy(), 'approved_domains_configured') }}</strong>
          </article>
          <article class="status-card">
            <span>Blocked domains</span><strong>0 configured</strong>
          </article>
          <article class="status-card">
            <span>Review-required domains</span><strong>UNKNOWN</strong>
          </article>
          <article class="status-card">
            <span>Robots / terms</span
            ><strong
              >{{ text(policy(), 'robots_policy', 'UNKNOWN') }} /
              {{ text(policy(), 'terms_status', 'UNKNOWN') }}</strong
            >
          </article>
        </div>
        <div class="policy-grid">
          @for (state of domainStates; track state) {
            <article>
              <strong>{{ state }}</strong>
              <p>{{ domainGuidance(state) }}</p>
            </article>
          }
        </div>
        <h3 id="source-profiles-title">Source profiles</h3>
        <p class="empty">
          No source profiles configured. Deployment policy controls approved, blocked,
          review-required, and unknown domains.
        </p>
        <p class="hint">
          Budgets, byte limits, retry limits, elapsed-time limits, and provider request limits are
          enforced server-side.
        </p>
      </section>

      <section id="searches" class="panel" aria-labelledby="searches-title">
        <p class="eyebrow">Searches</p>
        <h2 id="searches-title">Search history</h2>
        @if (!searches().length) {
          <p class="empty">
            No searches yet. Start a bounded local-fixture search from Autonomous Research.
          </p>
        }
        <div class="table-wrap">
          <table>
            <caption>
              Owner-scoped search requests
            </caption>
            <thead>
              <tr>
                <th scope="col">Query</th>
                <th scope="col">Provider / mode</th>
                <th scope="col">Status</th>
                <th scope="col">Results</th>
                <th scope="col">Created</th>
                <th scope="col">Correlation</th>
              </tr>
            </thead>
            <tbody>
              @for (row of searches(); track text(row, 'id')) {
                <tr>
                  <th scope="row">{{ text(row, 'query') }}</th>
                  <td>{{ text(row, 'provider') }} / {{ text(row, 'mode') }}</td>
                  <td>{{ text(row, 'status') }}</td>
                  <td>{{ text(row, 'result_count', '0') }}</td>
                  <td>{{ text(row, 'created_at') }}</td>
                  <td>{{ text(row, 'correlation_id') }}</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
        <h3 id="search-results-title">Search results</h3>
        @if (!results().length) {
          <p class="empty">No search results. Discovery snippets remain DISCOVERY ONLY.</p>
        }
        <div class="table-wrap">
          <table aria-labelledby="search-results-title">
            <caption>
              Discovery-only search results
            </caption>
            <thead>
              <tr>
                <th scope="col">Rank</th>
                <th scope="col">Title</th>
                <th scope="col">Domain</th>
                <th scope="col">Snippet</th>
                <th scope="col">Provider</th>
                <th scope="col">Fetch eligibility</th>
              </tr>
            </thead>
            <tbody>
              @for (row of results(); track text(row, 'id')) {
                <tr>
                  <th scope="row">{{ text(row, 'rank') }}</th>
                  <td>{{ text(row, 'title') }}</td>
                  <td>{{ text(row, 'domain') }}</td>
                  <td>{{ text(row, 'snippet') }}</td>
                  <td>{{ text(row, 'provider') }}</td>
                  <td>
                    <span class="badge">DISCOVERY ONLY</span> ?
                    {{ boolLabel(row, 'fetch_eligible') }}
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
        <h3>Search detail</h3>
        <p class="hint">
          Query, market, language, source categories, result limit, allowed domains, status,
          checkpoint history, budget usage, and failure/Recovery state are server-derived. Provider
          private payloads and API keys are never shown.
        </p>
      </section>

      <section id="fetches" class="panel" aria-labelledby="fetches-title">
        <p class="eyebrow">Fetches</p>
        <h2 id="fetches-title">Approved fetch history</h2>
        @if (!fetches().length) {
          <p class="empty">No fetch history yet. Only approved, bounded URLs can be fetched.</p>
        }
        <div class="table-wrap">
          <table>
            <caption>
              Owner-scoped approved fetches
            </caption>
            <thead>
              <tr>
                <th scope="col">Requested URL</th>
                <th scope="col">Final domain</th>
                <th scope="col">Status</th>
                <th scope="col">MIME / bytes</th>
                <th scope="col">Freshness</th>
                <th scope="col">Verification</th>
              </tr>
            </thead>
            <tbody>
              @for (row of fetches(); track text(row, 'id')) {
                <tr>
                  <th scope="row">
                    <a
                      [href]="safeUrl(row['requested_url'])"
                      target="_blank"
                      rel="noopener noreferrer"
                      >{{ text(row, 'requested_url') }}</a
                    >
                  </th>
                  <td>{{ text(row, 'domain') }}</td>
                  <td>{{ text(row, 'status') }}</td>
                  <td>{{ text(row, 'content_type') }} / {{ text(row, 'content_length', '0') }}</td>
                  <td>{{ text(row, 'freshness') }}</td>
                  <td>{{ text(row, 'verification_status', 'PENDING') }}</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
        <h3>Fetch detail</h3>
        <p class="hint">
          Requested URL, final URL, canonical URL, domain, HTTP status, content type/length/hash,
          redirects, retrieval/freshness/expiry timestamps, verification method/reason, source
          profile, prompt-injection status, and correlation ID are bounded fields. Raw external HTML
          is never rendered.
        </p>
        <p class="untrusted-label">
          UNTRUSTED EXTERNAL CONTENT ? bounded extracted text is treated as plain text only.
        </p>
      </section>

      <section id="evidence" class="panel" aria-labelledby="evidence-title">
        <p class="eyebrow">Evidence</p>
        <h2 id="evidence-title">Evidence Inspector</h2>
        @if (!evidence().length) {
          <p class="empty">No external Evidence yet. Discovery snippets remain DISCOVERY ONLY.</p>
        }
        <div class="table-wrap">
          <table>
            <caption>
              Verified and historical external evidence
            </caption>
            <thead>
              <tr>
                <th scope="col">Evidence ID</th>
                <th scope="col">Source</th>
                <th scope="col">Verification</th>
                <th scope="col">Freshness</th>
                <th scope="col">Confidence</th>
                <th scope="col">Retrieved</th>
                <th scope="col">State</th>
              </tr>
            </thead>
            <tbody>
              @for (row of evidence(); track text(row, 'id')) {
                <tr>
                  <th scope="row">{{ text(row, 'id') }}</th>
                  <td>
                    {{ text(row, 'source_reference') }}<br /><small>{{
                      text(row, 'source_class')
                    }}</small>
                  </td>
                  <td>{{ text(row, 'verification_status', 'UNVERIFIED') }}</td>
                  <td>{{ text(row, 'freshness_status', 'UNKNOWN') }}</td>
                  <td>{{ text(row, 'confidence', 'UNKNOWN') }}</td>
                  <td>{{ text(row, 'retrieved_at') }}</td>
                  <td>{{ evidenceState(row) }}</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
        <div class="badge-row" aria-label="Evidence labels">
          @for (state of evidenceStates; track state) {
            <span class="badge">{{ state }}</span>
          }
        </div>
        <h3>Evidence detail and freshness history</h3>
        <p class="hint">
          Search/fetch lineage, content hash, confidence, supporting claims, contradictions, change
          usage, provenance, previous observation, current observation, T1/T2 retrieval history, and
          superseded evidence remain reviewable.
        </p>
        <h3>Source diversity and confidence</h3>
        <p class="hint">
          Independent source count, domain/provider count, verified/supported source count,
          duplicates, mirrors, diversity score, verification, freshness, completeness,
          contradiction/unknown penalties, and reasons are server-derived.
        </p>
        <p class="hint">
          Observed and source-provided values are distinguished from derived, supported, verified,
          conflicting, stale, expired, and AI-disabled states. Superseded observations remain
          visible.
        </p>
      </section>

      <section id="contradictions" class="panel" aria-labelledby="contradictions-title">
        <p class="eyebrow">Contradictions</p>
        <h2 id="contradictions-title">Contradiction review</h2>
        @if (!contradictions().length) {
          <p class="empty">No contradictions detected.</p>
        }
        @for (row of contradictions(); track text(row, 'id')) {
          <article class="review-card">
            <h3>{{ text(row, 'contradiction_type', 'Conflict') }}</h3>
            <p><strong>Entity:</strong> {{ text(row, 'identity_key') }}</p>
            <p><strong>Status:</strong> {{ text(row, 'status', 'REQUIRES_REVIEW') }}</p>
            <p>
              <strong>Source A / B:</strong> {{ text(row, 'source_a') }} /
              {{ text(row, 'source_b') }}
            </p>
            <p class="hint">
              Read-only review-required state. The UI never auto-resolves a contradiction.
            </p>
          </article>
        }
      </section>

      <section id="changes" class="panel" aria-labelledby="changes-title">
        <p class="eyebrow">Changes</p>
        <h2 id="changes-title">Material change history</h2>
        @if (!changes().length) {
          <p class="empty">No changes recorded.</p>
        }
        <div class="table-wrap">
          <table>
            <caption>
              Server-derived change and materiality decisions
            </caption>
            <thead>
              <tr>
                <th scope="col">Entity</th>
                <th scope="col">Field</th>
                <th scope="col">Materiality</th>
                <th scope="col">Reason</th>
                <th scope="col">Created</th>
              </tr>
            </thead>
            <tbody>
              @for (row of changes(); track text(row, 'id')) {
                <tr>
                  <th scope="row">{{ text(row, 'identity_key', text(row, 'mission_id')) }}</th>
                  <td>{{ text(row, 'field_key', text(row, 'change_type')) }}</td>
                  <td>{{ materiality(row) }}</td>
                  <td>{{ text(row, 'reason', 'Server-derived change') }}</td>
                  <td>{{ text(row, 'created_at') }}</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </section>

      <section id="alerts" class="panel" aria-labelledby="alerts-title">
        <p class="eyebrow">Alerts</p>
        <h2 id="alerts-title">External research alerts</h2>
        @if (!alerts().length) {
          <p class="empty">No Alerts. Alerts are owner-scoped and server-derived.</p>
        }
        @for (row of alerts(); track text(row, 'id')) {
          <article class="alert-card" role="status">
            <strong
              >{{ text(row, 'severity', 'INFO') }} ? {{ text(row, 'alert_type', 'Alert') }}</strong
            >
            <h3>{{ text(row, 'title') }}</h3>
            <p>{{ text(row, 'detail') }}</p>
            <span
              >Acknowledgement: {{ boolLabel(row, 'acknowledged') }} ?
              {{ text(row, 'created_at') }}</span
            >
          </article>
        }
        <p class="hint">
          Alert acknowledgement is read-only in this architecture; no fake mutation button is shown.
        </p>
      </section>

      <section id="recovery" class="panel" aria-labelledby="recovery-title">
        <p class="eyebrow">Recovery</p>
        <h2 id="recovery-title">Safe recovery catalog</h2>
        @if (!recoveries().length) {
          <p class="empty">No Recovery records.</p>
        }
        @for (row of recoveries(); track text(row, 'id')) {
          <article class="review-card">
            <h3>{{ text(row, 'failure_code', 'External failure') }}</h3>
            <p>
              {{ text(row, 'safe_reason_code', text(row, 'safe_message', 'Safe recovery state')) }}
            </p>
            <p>
              <strong>Action:</strong> {{ text(row, 'action') }} ? <strong>Result:</strong>
              {{ text(row, 'status') }}
            </p>
            <p><strong>Correlation:</strong> {{ text(row, 'correlation_id') }}</p>
          </article>
        }
        <h3>Execution checkpoints, budgets, and rate limits</h3>
        <p class="hint">
          CLAIMED ? BEFORE_PROVIDER / BEFORE_FETCH ? PROVIDER_COMPLETE / FETCH_COMPLETE ?
          RESULTS_PERSISTED / CONTENT_HASHED ? EVIDENCE_PERSISTED ? VERIFICATION_COMPLETE ?
          DOWNSTREAM_COMPLETE ? TERMINAL
        </p>
        <p class="hint">
          Searches, fetches, domains, results, response bytes, elapsed time, retries, provider
          requests, window, remaining, and retry-after are server-enforced.
        </p>
        <div class="badge-row" aria-label="Server-advertised recovery actions">
          @for (action of recoveryActions(); track action) {
            <span class="badge">{{ action }}</span>
          }
        </div>
        <p class="hint">
          Only server-advertised actions are displayed. Consequential actions require confirmation
          and are disabled while submitting.
        </p>
      </section>

      <section id="history" class="panel" aria-labelledby="history-title">
        <p class="eyebrow">History</p>
        <h2 id="history-title">Unified external timeline</h2>
        @if (!timeline().length) {
          <p class="empty">No external history yet.</p>
        }
        <ol class="timeline" aria-label="External research history">
          @for (event of timeline(); track $index) {
            <li>
              <strong>{{ text(event, 'type', 'External event') }}</strong
              ><span>{{
                text(event, 'status', text(event, 'verification_status', 'Recorded'))
              }}</span
              ><time>{{ text(event, 'created_at', text(event, 'retrieved_at')) }}</time
              ><small
                >Owner-scoped correlation:
                {{ text(event, 'correlation_id', 'Not supplied') }}</small
              >
            </li>
          }
        </ol>
        <p class="hint">
          Trace by correlation ID is bounded to the authenticated owner. Operations remains
          authoritative for workers, queues, Recovery, integrity, and performance.
        </p>
        <a routerLink="/operations" class="secondary-button">Open Operations</a>
      </section>

      <section id="product-channel" class="panel" aria-labelledby="product-channel-title">
        <p class="eyebrow">Product Channel</p>
        <h2 id="product-channel-title">External research projection</h2>
        <form class="inline-form" (submit)="$event.preventDefault(); loadProductChannel()">
          <label for="channel-product-id">Product ID</label
          ><input
            id="channel-product-id"
            name="channel-product-id"
            [(ngModel)]="productId"
            placeholder="Owner-scoped Product UUID"
          />
          <button type="submit" [disabled]="productLoading() || !productId.trim()">
            {{ productLoading() ? 'Loading?' : 'View projection' }}
          </button>
        </form>
        @if (productError()) {
          <p class="error" role="alert">{{ productError() }}</p>
        }
        @if (productChannel(); as channel) {
          <div class="status-grid compact">
            <article class="status-card">
              <span>Status</span><strong>{{ text(channel, 'external_research_status') }}</strong>
            </article>
            <article class="status-card">
              <span>Evidence</span
              ><strong>{{ text(channel, 'external_evidence_count', '0') }}</strong>
            </article>
            <article class="status-card">
              <span>Verified / supported</span
              ><strong
                >{{ text(channel, 'verified_external_evidence_count', '0') }} /
                {{ text(channel, 'supported_external_evidence_count', '0') }}</strong
              >
            </article>
            <article class="status-card">
              <span>Stale / conflicts</span
              ><strong
                >{{ text(channel, 'stale_external_evidence_count', '0') }} /
                {{ text(channel, 'external_conflict_count', '0') }}</strong
              >
            </article>
            <article class="status-card">
              <span>Confidence</span
              ><strong>{{ text(channel, 'external_confidence', '0') }}</strong>
            </article>
            <article class="status-card">
              <span>Follow-up</span><strong>{{ boolLabel(channel, 'follow_up_required') }}</strong>
            </article>
          </div>
        }
        <div class="badge-row" aria-label="Product Channel safe actions">
          @for (action of productActions; track action) {
            <span class="badge">{{ action }}</span>
          }
        </div>
      </section>

      <section id="calendar" class="panel" aria-labelledby="calendar-title">
        <p class="eyebrow">Calendar</p>
        <h2 id="calendar-title">Informational research events</h2>
        @if (!calendar().length) {
          <p class="empty">No scheduled refresh, aging, expiry, or opportunity events.</p>
        }
        <div class="table-wrap">
          <table>
            <caption>
              Informational external research calendar
            </caption>
            <thead>
              <tr>
                <th scope="col">Event</th>
                <th scope="col">Scheduled for</th>
                <th scope="col">Mission</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              @for (row of calendar(); track text(row, 'id')) {
                <tr>
                  <th scope="row">{{ text(row, 'event_type') }}</th>
                  <td>{{ text(row, 'scheduled_for') }}</td>
                  <td>{{ text(row, 'mission_id') }}</td>
                  <td>None ? informational only</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </section>

      <section id="operations" class="panel" aria-labelledby="operations-title">
        <p class="eyebrow">Operations</p>
        <h2 id="operations-title">Integrity, performance, and diagnostics</h2>
        <div class="status-grid compact">
          <article class="status-card">
            <span>Integrity</span
            ><strong>{{ text(integrity(), 'classification', 'UNKNOWN') }}</strong>
          </article>
          <article class="status-card">
            <span>Performance</span
            ><strong>{{ text(performance(), 'classification', 'UNKNOWN') }}</strong>
          </article>
          <article class="status-card">
            <span>Timing mode</span
            ><strong>{{ text(performance(), 'timing_mode', 'LOCAL_FIXTURE') }}</strong>
          </article>
          <article class="status-card">
            <span>Live timing</span
            ><strong>{{ text(performance(), 'live_timing_status', 'NOT_MEASURED') }}</strong>
          </article>
        </div>
        <h3 id="storage-inventory-title">External storage inventory</h3>
        @if (!tables().length) {
          <p class="empty">Storage inventory unavailable.</p>
        }
        <div class="table-wrap">
          <table aria-labelledby="storage-inventory-title">
            <caption>
              Owner-scoped external tables
            </caption>
            <thead>
              <tr>
                <th scope="col">Table</th>
                <th scope="col">Purpose</th>
                <th scope="col">Owner scope</th>
              </tr>
            </thead>
            <tbody>
              @for (row of tables(); track text(row, 'table')) {
                <tr>
                  <th scope="row">{{ text(row, 'table') }}</th>
                  <td>{{ text(row, 'purpose') }}</td>
                  <td>{{ text(row, 'owner_scope') }}</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
        <p class="hint">
          System Doctor: provider configured {{ boolLabel(policy(), 'credentials_configured') }} ?
          fetch configured {{ boolLabel(policy(), 'fetch_enabled') }} ? allowlist
          {{ boolLabel(policy(), 'approved_domains_configured') }} ? budgets and rate limits
          server-enforced.
        </p>
        <a routerLink="/operations" class="secondary-button">View Operations Control Center</a>
      </section>
    </main>
  `,
  styles: `
    :host {
      display: block;
      color: #092b36;
    }
    .external-page {
      max-width: 1240px;
      margin: auto;
      padding: 1rem 0 3rem;
    }
    .page-header,
    .panel-heading {
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      align-items: flex-start;
    }
    h1 {
      font-size: clamp(2rem, 5vw, 3.5rem);
      margin: 0.25rem 0;
    }
    h2 {
      margin: 0.25rem 0 0.75rem;
    }
    h3 {
      margin: 0.3rem 0;
    }
    .lede,
    .hint,
    .privacy-note {
      color: #466a75;
    }
    .eyebrow {
      color: #176278;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .workspace-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 0.45rem;
      margin: 1rem 0;
    }
    .workspace-nav a,
    .secondary-button {
      color: #075a78;
      padding: 0.55rem 0.7rem;
      border: 1px solid #9fc1ca;
      border-radius: 0.45rem;
      text-decoration: none;
      background: #fff;
    }
    .panel {
      border: 1px solid #c9dbe0;
      border-radius: 0.9rem;
      padding: 1.1rem;
      margin: 1rem 0;
      background: #fff;
    }
    .runtime-banner,
    .callout {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
      padding: 0.85rem 1rem;
      border-left: 4px solid #176278;
      background: #edf8fa;
      margin: 1rem 0;
    }
    .status-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
      gap: 0.7rem;
    }
    .status-grid.compact {
      margin-top: 0.8rem;
    }
    .status-card,
    .policy-grid article,
    .review-card,
    .alert-card {
      border: 1px solid #c9dbe0;
      border-radius: 0.65rem;
      padding: 0.8rem;
      background: #f8fbfc;
    }
    .status-card span {
      display: block;
      color: #466a75;
      font-size: 0.9rem;
    }
    .status-card strong {
      display: block;
      margin-top: 0.25rem;
    }
    button,
    input {
      min-height: 2.5rem;
      padding: 0.45rem 0.65rem;
      border: 1px solid #8aacb5;
      border-radius: 0.4rem;
      font: inherit;
    }
    button {
      background: #145c73;
      color: #fff;
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.55;
      cursor: wait;
    }
    .table-wrap {
      overflow-x: auto;
    }
    table {
      width: 100%;
      min-width: 720px;
      border-collapse: collapse;
    }
    th,
    td {
      text-align: left;
      padding: 0.65rem;
      border-bottom: 1px solid #d9e6e9;
      vertical-align: top;
    }
    th {
      color: #163f4a;
    }
    caption {
      text-align: left;
      padding: 0.5rem 0;
      color: #466a75;
    }
    .badge-row {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      margin-top: 0.8rem;
    }
    .badge {
      border: 1px solid #8aacb5;
      border-radius: 99px;
      padding: 0.3rem 0.55rem;
      font-size: 0.85rem;
      background: #fff;
    }
    .policy-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 0.7rem;
      margin-top: 0.8rem;
    }
    .inline-form {
      display: flex;
      flex-wrap: wrap;
      gap: 0.6rem;
      align-items: end;
    }
    .inline-form label {
      display: grid;
      gap: 0.25rem;
    }
    .inline-form input {
      min-width: 280px;
    }
    .empty {
      padding: 1rem;
      background: #f5fafb;
      color: #466a75;
    }
    .error {
      padding: 1rem;
      background: #fff0f1;
      color: #9b1c31;
    }
    .loading {
      padding: 1rem;
      background: #f5fafb;
    }
    .untrusted-label {
      font-weight: 700;
      color: #8a3b00;
    }
    .privacy-note {
      font-size: 0.9rem;
    }
    .timeline {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 0.6rem;
    }
    .timeline li {
      display: grid;
      grid-template-columns: 1.4fr 1fr 1.5fr;
      gap: 0.5rem;
      border-left: 3px solid #9fc1ca;
      padding: 0.6rem 0.8rem;
    }
    .timeline small {
      grid-column: 1/-1;
      color: #466a75;
    }
    a:focus,
    button:focus,
    input:focus {
      outline: 3px solid #74b9d4;
      outline-offset: 2px;
    }
    @media (max-width: 700px) {
      .external-page {
        padding: 0.5rem 0 2rem;
      }
      .page-header,
      .panel-heading {
        display: grid;
        grid-template-columns: 1fr;
      }
      .timeline li {
        grid-template-columns: 1fr;
      }
      .inline-form input {
        min-width: 0;
        width: 100%;
      }
    }
  `,
})
export class ExternalResearchWorkspaceComponent {
  private readonly service = inject(IntelligenceService);
  readonly sections: Section[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'providers', label: 'Providers' },
    { id: 'source-policy', label: 'Source Policy' },
    { id: 'searches', label: 'Searches' },
    { id: 'fetches', label: 'Fetches' },
    { id: 'evidence', label: 'Evidence' },
    { id: 'contradictions', label: 'Contradictions' },
    { id: 'changes', label: 'Changes' },
    { id: 'alerts', label: 'Alerts' },
    { id: 'history', label: 'History' },
    { id: 'recovery', label: 'Recovery' },
  ];
  readonly providerStates = [
    'DISABLED',
    'LOCAL_FIXTURE',
    'SANDBOX',
    'LIVE_READ_ONLY',
    'DEGRADED',
    'RATE_LIMITED',
    'AUTH_ERROR',
    'UNAVAILABLE',
  ];
  readonly domainStates = ['APPROVED', 'BLOCKED', 'REVIEW_REQUIRED', 'UNKNOWN'];
  readonly evidenceStates = [
    'OBSERVED',
    'SOURCE_PROVIDED',
    'DERIVED',
    'SUPPORTED',
    'VERIFIED',
    'UNVERIFIED',
    'CONFLICTING',
    'STALE',
    'EXPIRED',
    'ASSUMPTION',
    'AI_DISABLED',
  ];
  readonly productActions = [
    'view_external_research',
    'refresh_external_research',
    'review_conflicts',
    'review_evidence',
  ];
  readonly activeSection = signal('overview');
  readonly loading = signal(false);
  readonly error = signal('');
  readonly productLoading = signal(false);
  readonly productError = signal('');
  readonly policy = signal<ExternalResearchPolicy | null>(null);
  readonly status = signal<ExternalRecord | null>(null);
  readonly searches = signal<ExternalRecord[]>([]);
  readonly results = signal<ExternalRecord[]>([]);
  readonly fetches = signal<ExternalRecord[]>([]);
  readonly evidence = signal<ExternalRecord[]>([]);
  readonly contradictions = signal<ExternalRecord[]>([]);
  readonly changes = signal<ExternalRecord[]>([]);
  readonly alerts = signal<ExternalRecord[]>([]);
  readonly recoveries = signal<ExternalRecord[]>([]);
  readonly calendar = signal<ExternalRecord[]>([]);
  readonly timeline = signal<ExternalRecord[]>([]);
  readonly integrity = signal<ExternalRecord | null>(null);
  readonly performance = signal<ExternalRecord | null>(null);
  readonly recoveryCatalog = signal<ExternalRecord | null>(null);
  readonly tables = signal<ExternalRecord[]>([]);
  readonly productChannel = signal<ExternalRecord | null>(null);
  productId = '';

  constructor() {
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    const requests = await Promise.allSettled([
      this.service.externalPolicy(),
      this.service.externalStatus(),
      this.service.externalSearches(),
      this.service.externalResults(),
      this.service.externalFetches(),
      this.service.externalEvidence(),
      this.service.externalHistory(),
      this.service.externalIntegrity(),
      this.service.externalPerformance(),
      this.service.externalCalendar(),
      this.service.externalAlerts(),
      this.service.externalRecoveryCatalog(),
      this.service.externalExecutions(),
      this.service.externalTables(),
    ]);
    const value = (index: number): unknown =>
      requests[index].status === 'fulfilled' ? requests[index].value : undefined;
    const policy = value(0);
    const status = value(1);
    const searches = value(2);
    const results = value(3);
    const fetches = value(4);
    const evidence = value(5);
    const history = value(6);
    const integrity = value(7);
    const performance = value(8);
    const calendar = value(9);
    const alerts = value(10);
    const catalog = value(11);
    const executions = value(12);
    const tables = value(13);
    if (Array.isArray(tables)) this.tables.set(tables as ExternalRecord[]);
    if (policy) this.policy.set(policy as ExternalResearchPolicy);
    if (status) this.status.set(status as ExternalRecord);
    if (Array.isArray(searches)) this.searches.set(searches as ExternalRecord[]);
    if (Array.isArray(results)) this.results.set(results as ExternalRecord[]);
    if (Array.isArray(fetches)) this.fetches.set(fetches as ExternalRecord[]);
    if (Array.isArray(evidence)) this.evidence.set(evidence as ExternalRecord[]);
    if (integrity && !Array.isArray(integrity)) this.integrity.set(integrity as ExternalRecord);
    if (performance && !Array.isArray(performance))
      this.performance.set(performance as ExternalRecord);
    if (Array.isArray(calendar)) this.calendar.set(calendar as ExternalRecord[]);
    if (Array.isArray(alerts)) this.alerts.set(alerts as ExternalRecord[]);
    if (catalog && !Array.isArray(catalog)) this.recoveryCatalog.set(catalog as ExternalRecord);
    const historyRecord = Array.isArray(history)
      ? { events: history }
      : (history as ExternalRecord | undefined);
    const eventRows = [
      ...this.searches(),
      ...this.results(),
      ...this.fetches(),
      ...this.evidence(),
      ...this.alerts(),
      ...(Array.isArray(executions) ? (executions as ExternalRecord[]) : []),
      ...(Array.isArray(historyRecord?.['events'])
        ? (historyRecord['events'] as ExternalRecord[])
        : []),
    ];
    this.timeline.set(eventRows);
    const historyObject = historyRecord ?? {};
    this.contradictions.set(this.records(historyObject, 'contradictions'));
    this.changes.set(this.records(historyObject, 'changes'));
    this.recoveries.set(this.records(historyObject, 'recovery'));
    if (requests.every((item) => item.status === 'rejected'))
      this.error.set(
        'External research data is unavailable. Check the authenticated API connection.',
      );
    this.loading.set(false);
  }

  async loadProductChannel(): Promise<void> {
    this.productLoading.set(true);
    this.productError.set('');
    this.productChannel.set(null);
    try {
      this.productChannel.set(await this.service.externalProductChannel(this.productId.trim()));
    } catch {
      this.productError.set(
        'Product Channel data is unavailable or the Product is not owner-scoped.',
      );
    } finally {
      this.productLoading.set(false);
    }
  }

  text(
    row: ExternalRecord | ExternalResearchPolicy | null | undefined,
    key: string,
    fallback = '?',
  ): string {
    const value = row ? (row as ExternalRecord)[key] : undefined;
    if (value === null || value === undefined || value === '') return fallback;
    if (typeof value === 'string') return value;
    if (typeof value === 'number' || typeof value === 'boolean') return value.toString();
    return '[structured value]';
  }
  boolLabel(row: ExternalRecord | ExternalResearchPolicy | null | undefined, key: string): string {
    const value = row ? (row as ExternalRecord)[key] : undefined;
    return value === true ? 'ENABLED' : value === false ? 'DISABLED' : 'UNKNOWN';
  }
  listText(row: ExternalRecord | ExternalResearchPolicy | null | undefined, key: string): string {
    const value = row ? (row as ExternalRecord)[key] : undefined;
    return Array.isArray(value) ? value.join(', ') || 'None' : this.text(row, key, 'None');
  }
  records(row: ExternalRecord, key: string): ExternalRecord[] {
    return Array.isArray(row[key]) ? (row[key] as ExternalRecord[]) : [];
  }
  runtimeLabel(): string {
    const mode = this.text(this.policy(), 'mode', 'LOCAL FIXTURE');
    if (mode === 'LIVE_READ_ONLY' && !this.policy()?.credentials_configured) {
      return 'LIVE SEARCH — BLOCKED BY EXTERNAL CREDENTIALS';
    }
    return mode === 'LIVE_READ_ONLY' ? 'LIVE SEARCH READ-ONLY — NOT VALIDATED' : mode;
  }
  quotaLabel(): string {
    const quota = this.status()?.['quota'];
    return Array.isArray(quota) && quota.length
      ? this.text(quota[0] as ExternalRecord, 'status', 'UNKNOWN')
      : 'NOT MEASURED';
  }
  evidenceCount(state: string): number {
    return this.evidence().filter(
      (row) => this.text(row, 'verification_status', '').toUpperCase() === state,
    ).length;
  }
  evidenceFreshness(state: string): number {
    return this.evidence().filter(
      (row) => this.text(row, 'freshness_status', '').toUpperCase() === state,
    ).length;
  }
  evidenceState(row: ExternalRecord): string {
    return this.text(row, 'evidence_class', this.text(row, 'verification_status', 'UNVERIFIED'));
  }
  materiality(row: ExternalRecord): string {
    const value = row['material'];
    return value === true ? 'MATERIAL' : value === false ? 'NON_MATERIAL' : 'REQUIRES_REVIEW';
  }
  recoveryActions(): string[] {
    const actions = this.recoveryCatalog()?.['actions'];
    return Array.isArray(actions) ? actions.map(String) : [];
  }
  domainGuidance(state: string): string {
    return state === 'APPROVED'
      ? 'Approved for bounded use.'
      : state === 'BLOCKED'
        ? 'Blocked by source policy.'
        : state === 'REVIEW_REQUIRED'
          ? 'Human review required before use.'
          : 'Unknown; do not fetch until approved.';
  }
  safeUrl(value: unknown): string | null {
    const candidate = typeof value === 'string' ? value : '';
    return /^https?:\/\//i.test(candidate) ? candidate : null;
  }
}
