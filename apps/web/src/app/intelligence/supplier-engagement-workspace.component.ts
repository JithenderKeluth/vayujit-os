import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../environments/environment';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import {
  BlockedStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { PageHeaderComponent } from '../shared/page-header.component';
import type { BreadcrumbItem } from '../shared/ux-foundation.types';

interface DraftView {
  id: string;
  version: number;
  status: string;
  supplier?: Record<string, unknown>;
  contact?: Record<string, unknown>;
  product?: Record<string, unknown>;
  structured_request?: Record<string, unknown>;
  subject: string;
  message_body: string;
  warnings: unknown[];
  unknowns: unknown[];
  limitations: string[];
  provenance: string;
}

interface EngagementView {
  id: string;
  goal_id: string | null;
  opportunity_id: string;
  supplier_id: string;
  contact_id: string | null;
  human_decision_id: string | null;
  engagement_type: string;
  status: string;
  blocking_reasons: Array<{ code?: string; message?: string }>;
  current_draft: DraftView | null;
  latest_approval: { state: string; provenance: string; created_at: string } | null;
  send_status: string;
  send_eligibility?: {
    can_authorize_send: boolean;
    live_provider_allowed: boolean;
    fake_provider_allowed: boolean;
    blocking_reasons: Array<{ code?: string; message?: string }>;
  } | null;
  send_authorization?: { id: string; status: string; recipient: string; draft_version: number } | null;
  send_command?: { id: string; status: string; attempt_count: number; last_error?: string | null } | null;
  safe_next_action: string;
}

interface ResponseView {
  id: string;
  supplier_id: string | null;
  opportunity_id: string | null;
  engagement_id: string | null;
  channel: string;
  sender_identity: string | null;
  received_at: string;
  raw_content: string;
  trust_environment: string;
  evidence_environment: string;
  correlation_state: string;
  correlation_reason: string;
  classification: string;
  extraction: {
    id: string;
    version: number;
    status: string;
    extracted_fields: Record<string, unknown>;
    unknown_fields: unknown[];
    warnings: unknown[];
    extraction_authority: string;
    source_raw_hash: string;
  } | null;
  reviews: Array<{ decision: string; provenance: string; reason: string; created_at: string }>;
  promotion: { status: string; supplier_evidence_id?: string | null } | null;
  safe_next_action: string;
}

interface BriefView {
  goal?: { text: string | null; provenance: string };
  product?: { name: string; category: string; marketplace: string; provenance: string };
  engagement?: EngagementView | null;
  suppliers?: { readiness: string; shortlisted_count: number; verified_count: number };
}

@Component({
  selector: 'app-supplier-engagement-workspace',
  standalone: true,
  imports: [
    BlockedStateComponent,
    BreadcrumbsComponent,
    CommonModule,
    ErrorStateComponent,
    FormsModule,
    LoadingStateComponent,
    PageHeaderComponent,
    RouterLink,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="engagement-page" aria-labelledby="engagement-title">
      <app-breadcrumbs [items]="breadcrumbs" />
      <app-page-header
        headingId="engagement-title"
        eyebrow="Intelligence / Supplier engagement"
        title="Prepare and review supplier engagement"
        description="Keep the selected product, supplier evidence, RFQ draft, approval, response, and procurement-readiness context together. No message is sent automatically."
      >
        <a page-header-actions routerLink="/intelligence/sourcing-economics">Review economics</a>
      </app-page-header>

      <p class="boundary" role="note">
        INTERNAL REVIEW ONLY · DRAFTS ARE NOT AUTHORIZATIONS · NO SUPPLIER CONTACT · NO RFQ SENT · NO PURCHASE · NO PAYMENT
      </p>

      @if (error()) {
        <app-error-state [message]="error()" retryLabel="Retry" (retry)="load()" />
      }
      @if (loading()) {
        <app-loading-state message="Loading engagement context and evidence..." />
      }

      @if (!opportunityId) {
        <app-blocked-state
          title="Select a product opportunity first"
          reason="Supplier engagement must remain scoped to a human-selected product opportunity."
        />
        <a class="next-link" routerLink="/intelligence/product-opportunities">Choose a product opportunity</a>
      } @else {
        <section class="context-card" aria-labelledby="context-title">
          <div>
            <p class="eyebrow">ACTIVE CONTEXT</p>
            <h2 id="context-title">{{ brief()?.product?.name || 'Selected product opportunity' }}</h2>
            <p>{{ brief()?.product?.category || 'Category UNKNOWN' }} · {{ brief()?.product?.marketplace || 'Marketplace UNKNOWN' }}</p>
            <p class="muted">Goal: {{ brief()?.goal?.text || 'UNKNOWN' }}</p>
          </div>
          <dl class="context-facts">
            <div><dt>Opportunity</dt><dd>{{ opportunityId }}</dd></div>
            <div><dt>Supplier</dt><dd>{{ supplierId || engagement()?.supplier_id || 'Not selected' }}</dd></div>
            <div><dt>Supplier readiness</dt><dd>{{ brief()?.suppliers?.readiness || 'UNKNOWN' }}</dd></div>
          </dl>
        </section>

        @if (!engagement()) {
          <section class="panel" aria-labelledby="prepare-title">
            <p class="eyebrow">RFQ PREPARATION</p>
            <h2 id="prepare-title">Prepare a supplier information request</h2>
            <p>
              This creates an immutable internal draft from canonical product, supplier, contact, and HUMAN decision context. It does not contact the supplier.
            </p>
            @if (!supplierId) {
              <app-blocked-state
                title="Select a supplier before preparing a draft"
                reason="Open supplier verification or supplier shortlisting, confirm the supplier and contact, then return here with the scoped supplier context."
              />
              <div class="next-actions">
                <a routerLink="/intelligence/due-diligence">Open supplier verification</a>
                <a routerLink="/intelligence/supplier-shortlisting">Open supplier shortlisting</a>
              </div>
            } @else {
              <form class="form-grid" (submit)="$event.preventDefault(); prepareDraft()">
                <label>Supplier ID<input name="supplierId" [value]="supplierId" readonly /></label>
                <label>Contact ID<input name="contactId" [(ngModel)]="contactId" placeholder="Canonical contact UUID" /></label>
                <label>Requested quantity<input name="requestedQuantity" type="number" min="1" [(ngModel)]="requestedQuantity" required /></label>
                <label>Destination region<input name="destinationRegion" [(ngModel)]="destinationRegion" /></label>
                <label class="wide">Questions to request<input name="requestedFields" [(ngModel)]="requestedFields" /></label>
                <button type="submit" [disabled]="busy()">Prepare internal draft</button>
              </form>
              <p class="hint">The current HUMAN supplier decision must be PROCEED. If it is missing or stale, the server will keep this engagement blocked.</p>
            }
          </section>
        } @else {
          <section class="panel" aria-labelledby="status-title">
            <div class="status-heading">
              <div>
                <p class="eyebrow">ENGAGEMENT STATUS</p>
                <h2 id="status-title">{{ statusLabel(engagement()!.status) }}</h2>
              </div>
              <span class="status-badge" [class.blocked]="isBlocked(engagement()!)">{{ engagement()!.status }}</span>
            </div>
            @if (engagement()!.blocking_reasons.length) {
              <div class="warning" role="status">
                <strong>Why this is blocked</strong>
                <ul>@for (reason of engagement()!.blocking_reasons; track reason.code) { <li>{{ reason.message || reason.code }}</li> }</ul>
              </div>
            }
            <dl class="facts-grid">
              <div><dt>Supplier</dt><dd>{{ engagement()!.current_draft?.supplier?.['display_name'] || engagement()!.supplier_id }}</dd></div>
              <div><dt>Contact</dt><dd>{{ engagement()!.current_draft?.contact?.['name'] || 'UNKNOWN' }}</dd></div>
              <div><dt>Contact trust</dt><dd>{{ engagement()!.current_draft?.contact?.['trust_environment'] || 'UNKNOWN' }} · {{ engagement()!.current_draft?.contact?.['verification_status'] || 'UNKNOWN' }}</dd></div>
              <div><dt>Draft version</dt><dd>{{ engagement()!.current_draft?.version || 'NONE' }}</dd></div>
              <div><dt>Approval</dt><dd>{{ engagement()!.latest_approval?.state || 'NOT APPROVED' }}</dd></div>
              <div><dt>Send state</dt><dd>{{ engagement()!.send_command?.status || engagement()!.send_status || 'NOT_EXECUTED' }}</dd></div>
            </dl>
            <p class="next-action"><strong>Safe next action:</strong> {{ engagement()!.safe_next_action }}</p>
          </section>

          @if (engagement()!.current_draft; as draft) {
            <section class="panel" aria-labelledby="draft-title">
              <p class="eyebrow">DRAFT · VERSION {{ draft.version }}</p>
              <h2 id="draft-title">Review the exact RFQ draft</h2>
              <p class="draft-state">{{ draft.status }} · provenance {{ draft.provenance }}</p>
              <dl class="facts-grid">
                <div><dt>Subject</dt><dd>{{ draft.subject }}</dd></div>
                <div><dt>Quantity</dt><dd>{{ draft.structured_request?.['requested_quantity'] || 'UNKNOWN' }}</dd></div>
                <div class="wide"><dt>Requested fields</dt><dd>{{ requestedFieldText(draft) }}</dd></div>
              </dl>
              <details>
                <summary>Inspect draft message and evidence limitations</summary>
                <pre class="message">{{ draft.message_body }}</pre>
                <p><strong>Warnings:</strong> {{ listOrUnknown(draft.warnings) }}</p>
                <p><strong>Unknowns:</strong> {{ listOrUnknown(draft.unknowns) }}</p>
                <p><strong>Limitations:</strong> {{ draft.limitations.join('; ') || 'None recorded' }}</p>
              </details>
              <div class="action-row" aria-label="HUMAN draft controls">
                @if (engagement()!.status === 'NEEDS_REVIEW') {
                  <button type="button" (click)="approveDraft()" [disabled]="busy()">Approve draft for future review</button>
                }
                @if (engagement()!.status !== 'CANCELLED') {
                  <button type="button" class="secondary" (click)="cancelDraft()" [disabled]="busy()">Cancel internal draft</button>
                }
              </div>
              <p class="hint">Approval is not authorization. Authorization is not proof of delivery. No external action occurs in this workspace automatically.</p>
            </section>
          }

          <section class="panel" aria-labelledby="authorization-title">
            <p class="eyebrow">AUTHORIZATION BOUNDARY</p>
            <h2 id="authorization-title">Separate approval from execution</h2>
            @if (engagement()!.send_eligibility?.blocking_reasons?.length) {
              <div class="warning" role="status">
                <strong>Execution is unavailable</strong>
                <ul>@for (reason of engagement()!.send_eligibility!.blocking_reasons; track reason.code) { <li>{{ reason.message || reason.code }}</li> }</ul>
              </div>
            } @else if (!engagement()!.send_authorization) {
              <p>After a current HUMAN approval, the server may allow a separate single-use authorization. No authorization exists yet.</p>
              @if (engagement()!.send_eligibility?.can_authorize_send) {
                <button type="button" (click)="authorizeSend()" [disabled]="busy()">Issue single-use send authorization</button>
              }
            } @else {
              <p><strong>Authorization:</strong> {{ engagement()!.send_authorization!.status }} · recipient {{ engagement()!.send_authorization!.recipient }}</p>
              <p class="warning">A send would be an external effect. Certification uses no-send fixtures; do not execute it here.</p>
            }
          </section>
        }

        <section class="panel" aria-labelledby="responses-title">
          <p class="eyebrow">SUPPLIER RESPONSES</p>
          <h2 id="responses-title">Review inbound evidence</h2>
          <p>Supplier-provided claims remain untrusted until a HUMAN reviews extraction. Unknown MOQ, price, lead time, and payment terms remain unknown.</p>
          @if (!responses().length) {
            <p class="empty" role="status">No supplier response is recorded for this product opportunity.</p>
          }
          @for (response of responses(); track response.id) {
            <article class="response-card">
              <div class="status-heading"><h3>{{ response.classification.replaceAll('_', ' ') }}</h3><span class="status-badge">{{ response.correlation_state }}</span></div>
              <dl class="facts-grid">
                <div><dt>Channel</dt><dd>{{ response.channel }}</dd></div>
                <div><dt>Sender</dt><dd>{{ response.sender_identity || 'UNKNOWN' }}</dd></div>
                <div><dt>Trust environment</dt><dd>{{ response.trust_environment }}</dd></div>
                <div><dt>Received</dt><dd>{{ response.received_at }}</dd></div>
                <div class="wide"><dt>Correlation</dt><dd>{{ response.correlation_reason }}</dd></div>
              </dl>
              <details><summary>Inspect immutable supplier response</summary><pre class="message">{{ response.raw_content }}</pre></details>
              @if (response.extraction) {
                <p class="hint">Extraction v{{ response.extraction.version }} · {{ response.extraction.extraction_authority }} · raw hash {{ response.extraction.source_raw_hash }}</p>
                <p><strong>Unknowns:</strong> {{ listOrUnknown(response.extraction.unknown_fields) }}</p>
              }
              @if (response.reviews.length) {
                <p class="callout" role="status">HUMAN review: {{ response.reviews[response.reviews.length - 1].decision }}</p>
              } @else if (response.extraction && response.correlation_state === 'CORRELATED') {
                <div class="action-row">
                  <button type="button" (click)="reviewResponse(response, 'ACCEPT_EXTRACTION')" [disabled]="busy()">Accept extracted claims</button>
                  <button type="button" class="secondary" (click)="reviewResponse(response, 'KEEP_UNDER_REVIEW')" [disabled]="busy()">Keep under review</button>
                </div>
              }
              @if (response.promotion) { <p class="callout" role="status">Promotion: {{ response.promotion.status }} · evidence remains source-provided</p> }
              <p class="hint"><strong>Safe next action:</strong> {{ response.safe_next_action }}</p>
            </article>
          }
        </section>

        <section class="panel" aria-labelledby="readiness-title">
          <p class="eyebrow">PROCUREMENT READINESS</p>
          <h2 id="readiness-title">Continue only after evidence review</h2>
          <p>Procurement readiness is an evidence assessment, not purchase authorization. Review economics and canonical readiness before recording a HUMAN acknowledgement.</p>
          <a class="next-link" [routerLink]="['/intelligence/sourcing-economics']" [queryParams]="{ opportunity_id: opportunityId, journey_id: journeyId }">Review sourcing economics and readiness</a>
        </section>

        @if (engagement()) {
          <section class="panel" aria-labelledby="history-title">
            <h2 id="history-title">Engagement history</h2>
            <button type="button" class="secondary" (click)="loadHistory()" [disabled]="busy()">Refresh history</button>
            @if (history().length) {
              <ol class="history">@for (event of history(); track event.id) { <li><strong>{{ event.event_type }}</strong> · {{ event.provenance }} · draft v{{ event.draft_version }} · {{ event.created_at }}</li> }</ol>
            } @else { <p class="empty">History is not loaded yet.</p> }
          </section>
        }
      }
    </main>
  `,
  styles: [
    `
      :host { display:block; }
      .engagement-page { max-width: 1180px; margin: 0 auto; padding: 2rem; color:#123447; }
      .boundary { padding: .8rem 1rem; border-left: 4px solid #d97706; background:#fff7dd; font-weight:700; overflow-wrap:anywhere; }
      .panel, .context-card { margin:1rem 0; padding:1.25rem; border:1px solid #cbdde2; border-radius:.8rem; background:#fff; box-sizing:border-box; min-width:0; overflow-wrap:anywhere; }
      .context-card { display:grid; grid-template-columns: minmax(0, 1.4fr) minmax(250px, 1fr); gap:1.25rem; background:#eef8f8; }
      .context-facts, .facts-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.75rem; margin:0; }
      dl div { min-width:0; }
      dt { color:#52707c; font-size:.82rem; font-weight:700; text-transform:uppercase; letter-spacing:.04em; }
      dd { margin:.2rem 0 0; overflow-wrap:anywhere; }
      .form-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; }
      label { display:grid; gap:.35rem; font-weight:700; }
      input { width:100%; min-width:0; box-sizing:border-box; padding:.65rem; border:1px solid #9bbbc4; border-radius:.35rem; font:inherit; }
      .wide { grid-column:1 / -1; }
      button, .next-link, .action-row a { display:inline-block; padding:.65rem 1rem; border:1px solid #0c6575; border-radius:.35rem; background:#0c6575; color:#fff; font:inherit; font-weight:700; text-decoration:none; cursor:pointer; }
      button.secondary { background:#fff; color:#0c6575; }
      button:disabled { opacity:.55; cursor:not-allowed; }
      .next-actions, .action-row { display:flex; flex-wrap:wrap; gap:.6rem; margin-top:1rem; }
      .next-actions a { color:#5b2c83; font-weight:700; }
      .status-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; }
      .status-heading h2, .status-heading h3 { margin-top:0; }
      .status-badge { display:inline-block; padding:.25rem .55rem; border:1px solid #6ea8b4; border-radius:999px; background:#e8f7f8; font-weight:700; overflow-wrap:anywhere; }
      .status-badge.blocked, .warning { background:#fff3dc; border-color:#d99a1e; }
      .warning, .callout, .next-action { margin-top:1rem; padding:.8rem; border-left:4px solid #d99a1e; background:#fff8e8; overflow-wrap:anywhere; }
      .callout { border-left-color:#0c6575; background:#eef8f8; }
      .hint, .muted { color:#52707c; overflow-wrap:anywhere; }
      .draft-state { font-weight:700; color:#0c6575; }
      details { margin-top:1rem; }
      summary { cursor:pointer; font-weight:700; }
      .message { white-space:pre-wrap; overflow-wrap:anywhere; max-width:100%; background:#f7fafb; padding:1rem; border-radius:.4rem; }
      .response-card { margin-top:1rem; padding:1rem; border:1px solid #cbdde2; border-radius:.6rem; background:#fbfdfd; min-width:0; overflow-wrap:anywhere; }
      .response-card p, .response-card dd, .response-card summary, .response-card h3 { overflow-wrap:anywhere; word-break:break-word; }
      .empty { padding:1rem; border:1px dashed #9bbbc4; color:#52707c; }
      .history { padding-left:1.25rem; }
      .history li { margin:.45rem 0; overflow-wrap:anywhere; }
      @media (max-width:700px) { .engagement-page { padding:1rem .75rem; } .context-card, .form-grid { grid-template-columns:1fr; } .context-facts, .facts-grid { grid-template-columns:1fr; } .wide { grid-column:auto; } .action-row button, .form-grid > button { width:100%; } }
    `,
  ],
})
export class SupplierEngagementWorkspaceComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  readonly breadcrumbs: BreadcrumbItem[] = [
    { label: 'Intelligence', url: '/intelligence' },
    { label: 'Supplier engagement' },
  ];
  readonly loading = signal(false);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly brief = signal<BriefView | null>(null);
  readonly engagement = signal<EngagementView | null>(null);
  readonly responses = signal<ResponseView[]>([]);
  readonly history = signal<Array<{ id: string; event_type: string; draft_version: number; provenance: string; created_at: string }>>([]);
  opportunityId = '';
  journeyId = '';
  supplierId = '';
  contactId = '';
  humanDecisionId = '';
  assessmentId = '';
  engagementId = '';
  requestedQuantity = 100;
  destinationRegion = 'IN';
  requestedFields = 'unit_price, moq, lead_time, incoterm, payment_terms';

  ngOnInit(): void {
    const params = this.route.snapshot.queryParamMap;
    this.opportunityId = params.get('opportunity_id') || '';
    this.journeyId = params.get('journey_id') || '';
    this.supplierId = params.get('supplier_id') || '';
    this.contactId = params.get('contact_id') || '';
    this.humanDecisionId = params.get('human_decision_id') || '';
    this.assessmentId = params.get('assessment_id') || '';
    this.engagementId = params.get('engagement_id') || '';
    void this.load();
  }

  async load(): Promise<void> {
    if (!this.opportunityId) return;
    this.loading.set(true);
    this.error.set('');
    try {
      const briefUrl = this.journeyId
        ? `${environment.apiUrl}/commerce-journeys/${this.journeyId}/decision-brief?opportunity_id=${encodeURIComponent(this.opportunityId)}`
        : `${environment.apiUrl}/intelligence/product-opportunities/${this.opportunityId}/decision-brief`;
      this.brief.set(await firstValueFrom(this.http.get<BriefView>(briefUrl)));
      const projected = this.brief()?.engagement || null;
      if (projected) {
        this.engagement.set(projected);
        this.engagementId = projected.id;
        this.supplierId ||= projected.supplier_id;
      } else if (this.engagementId) {
        await this.loadEngagement();
      } else {
        this.engagement.set(null);
      }
      await this.loadResponses();
      if (this.engagement()) await this.loadHistory();
    } catch {
      this.error.set('The engagement context is unavailable. Confirm the selected product, supplier, and authenticated owner scope.');
    } finally {
      this.loading.set(false);
    }
  }

  private async loadEngagement(): Promise<void> {
    if (!this.engagementId) return;
    this.engagement.set(await firstValueFrom(this.http.get<EngagementView>(`${environment.apiUrl}/intelligence/engagements/${this.engagementId}`)));
  }

  private async loadResponses(): Promise<void> {
    const value = await firstValueFrom(this.http.get<{ responses: ResponseView[] }>(`${environment.apiUrl}/intelligence/supplier-responses?opportunity_id=${encodeURIComponent(this.opportunityId)}`));
    this.responses.set(value.responses || []);
  }

  async prepareDraft(): Promise<void> {
    if (!this.opportunityId || !this.supplierId) {
      this.error.set('A selected product and supplier are required before preparing an internal draft.');
      return;
    }
    this.busy.set(true);
    this.error.set('');
    try {
      const created = await firstValueFrom(this.http.post<EngagementView>(`${environment.apiUrl}/intelligence/engagements`, {
        opportunity_id: this.opportunityId,
        supplier_id: this.supplierId,
        contact_id: this.contactId || null,
        human_decision_id: this.humanDecisionId || null,
        engagement_type: 'REQUEST_QUOTE',
        decision_target: 'SUPPLIER_SELECTION',
        requested_quantity: Number(this.requestedQuantity),
        destination_region: this.destinationRegion.trim(),
        requested_fields: this.requestedFields.split(',').map((item) => item.trim()).filter(Boolean),
        idempotency_key: `pruxe01e-engagement-${this.opportunityId}-${this.supplierId}`,
      }));
      this.engagement.set(created);
      this.engagementId = created.id;
      await this.loadHistory();
    } catch {
      this.error.set('The draft could not be prepared. The server may require a current HUMAN PROCEED, verified supplier contact, or fresh scope.');
    } finally {
      this.busy.set(false);
    }
  }

  async approveDraft(): Promise<void> {
    const engagement = this.engagement();
    if (!engagement) return;
    this.busy.set(true);
    try {
      this.engagement.set(await firstValueFrom(this.http.post<EngagementView>(`${environment.apiUrl}/intelligence/engagements/${engagement.id}/approve`, {
        idempotency_key: `pruxe01e-approve-${engagement.id}-${engagement.current_draft?.version || 0}`,
        reason: 'Owner reviewed the exact draft and approved it for a future controlled send.',
        provenance: 'HUMAN',
      })));
      await this.loadHistory();
    } catch {
      this.error.set('Approval was not recorded. Review the current HUMAN decision and draft version.');
    } finally { this.busy.set(false); }
  }

  async cancelDraft(): Promise<void> {
    const engagement = this.engagement();
    if (!engagement || !globalThis.confirm('Cancel this internal draft? No supplier message will be sent.')) return;
    this.busy.set(true);
    try {
      this.engagement.set(await firstValueFrom(this.http.post<EngagementView>(`${environment.apiUrl}/intelligence/engagements/${engagement.id}/cancel`, {
        idempotency_key: `pruxe01e-cancel-${engagement.id}`,
        reason: 'Owner cancelled the draft during review.',
        provenance: 'HUMAN',
      })));
      await this.loadHistory();
    } catch { this.error.set('The internal draft could not be cancelled. Refresh and review the current state.'); }
    finally { this.busy.set(false); }
  }

  async authorizeSend(): Promise<void> {
    const engagement = this.engagement();
    const draft = engagement?.current_draft;
    if (!engagement || !draft || !engagement.send_eligibility?.can_authorize_send) return;
    if (!globalThis.confirm('Issue a single-use authorization for this exact draft? This does not send a message.')) return;
    this.busy.set(true);
    try {
      this.engagement.set(await firstValueFrom(this.http.post<EngagementView>(`${environment.apiUrl}/intelligence/engagements/${engagement.id}/send-authorize`, {
        draft_version: draft.version,
        channel: 'EMAIL',
        idempotency_key: `pruxe01e-authorize-${engagement.id}-${draft.version}`,
        confirm: true,
        provenance: 'HUMAN',
      })));
    } catch { this.error.set('The execution authorization was not created. Review provider mode, approval, and draft freshness.'); }
    finally { this.busy.set(false); }
  }

  async reviewResponse(response: ResponseView, decision: 'ACCEPT_EXTRACTION' | 'KEEP_UNDER_REVIEW'): Promise<void> {
    if (!response.extraction) return;
    this.busy.set(true);
    try {
      await firstValueFrom(this.http.post(`${environment.apiUrl}/intelligence/supplier-responses/${response.id}/review`, {
        decision,
        extraction_id: response.extraction.id,
        reason: `Owner selected ${decision.replaceAll('_', ' ').toLowerCase()} after reviewing immutable supplier evidence.`,
        provenance: 'HUMAN',
        idempotency_key: `pruxe01e-response-review-${response.id}-${decision}`,
      }));
      await this.loadResponses();
    } catch { this.error.set('The supplier-response review could not be recorded. Refresh the immutable evidence.'); }
    finally { this.busy.set(false); }
  }

  async loadHistory(): Promise<void> {
    const engagement = this.engagement();
    if (!engagement) return;
    try { this.history.set(await firstValueFrom(this.http.get<Array<{ id: string; event_type: string; draft_version: number; provenance: string; created_at: string }>>(`${environment.apiUrl}/intelligence/engagements/${engagement.id}/history`))); }
    catch { this.error.set('Engagement history is unavailable; the current draft remains read-only.'); }
  }

  statusLabel(status: string): string {
    return status.replaceAll('_', ' ');
  }

  isBlocked(value: EngagementView): boolean {
    return value.status === 'BLOCKED' || value.blocking_reasons.length > 0;
  }

  requestedFieldText(draft: DraftView): string {
    const fields = draft.structured_request?.['requested_fields'];
    return Array.isArray(fields) && fields.length ? fields.join(', ') : 'UNKNOWN';
  }

  listOrUnknown(value: unknown): string {
    return Array.isArray(value) && value.length ? JSON.stringify(value) : 'None recorded';
  }
}
