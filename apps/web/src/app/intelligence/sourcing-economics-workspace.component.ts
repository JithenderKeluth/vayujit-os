import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import { CommerceJourneyContextComponent } from '../commerce-journey-context.component';
import { CommerceJourneyService } from '../commerce-journey.service';
import {
  BlockedStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { PageHeaderComponent } from '../shared/page-header.component';
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
  converted_amount: number | string | null;
  currency: string | null;
  basis: string | null;
  provenance: string;
  freshness: string;
  evidence_ref: string | null;
  assumption_reason: string | null;
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

interface UnitEconomicsView {
  status: string;
  calculable: boolean;
  selling_price: string | number | null;
  selling_price_currency: string | null;
  selling_price_provenance: string;
  base_currency: string | null;
  quantity: string | number | null;
  selling_cost_components: Array<{
    key: string;
    basis: string;
    rate: string | number | null;
    amount: string | number | null;
    per_unit_amount: string | number | null;
    currency: string | null;
    inclusion_status: string;
    required: boolean;
    provenance: string;
    exclusion_reason: string | null;
  }>;
  per_unit_landed_cost: string | number | null;
  per_unit_selling_cost: string | number | null;
  per_unit_total_cost: string | number | null;
  per_unit_contribution: string | number | null;
  contribution_margin: string | number | null;
  order_economics: {
    order_quantity: string | number | null;
    sales_quantity: string | number | null;
    sales_claim: string;
    landed_acquisition_total: string | number | null;
    modeled_selling_cost_total: string | number | null;
    modeled_total_cost: string | number | null;
    modeled_contribution_total_if_all_ordered_units_sell: string | number | null;
    currency: string | null;
  };
  capital_available: string | number | null;
  capital_currency: string | null;
  capital_required: string | number | null;
  capital_headroom: string | number | null;
  capital_shortfall: string | number | null;
  capital_fit_status: string | null;
  unknown_excluded: Array<{ key: string; label?: string; reason: string; status: string }>;
  limitations: string[];
  explanation: { formula?: string; capital_source?: { source?: string; provenance?: string } };
  safe_next_action?: string;
  freshness?: { status: string; code: string; recalculation_required: boolean };
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

interface DecisionBriefView {
  opportunity_id: string;
  goal?: { text: string | null; provenance: string };
  product: { name: string; category: string; marketplace: string; provenance: string };
  suppliers: {
    shortlisted_count: number;
    verified_count: number;
    readiness: string;
    items: Array<{ supplier_name: string; due_diligence_status: string }>;
  };
  economics: {
    readiness: string;
    unit_economics?: UnitEconomicsView | null;
    calculation?: {
      total_included_cost: string;
      per_unit_cost: string | null;
      currency: string | null;
      status: string;
      missing_inputs: string[];
      warnings: string[];
      breakdown?: EconomicBreakdownView[];
      explanation?: { included_total_label?: string; reporting_currency?: string };
    };
    scenario_comparisons: Array<{
      scenario_name: string;
      comparability: string;
      baseline: { total: string | null; per_unit: string | null };
      scenario: { total: string | null; per_unit: string | null };
      warnings: string[];
    }>;
  };
  budget_fit: {
    status: string;
    budget: string | null;
    currency: string | null;
    remaining_or_shortfall: string | null;
    scope: string;
  };
  risk: string;
  evidence_completeness: string;
  decision_readiness: string;
  key_risks: string[];
  data_gaps: Array<{ message: string }>;
  next_options: string[];
  decision_evidence?: {
    decision_target: string;
    readiness_state: string;
    blockers: Array<{ code: string; message: string }>;
    warnings: Array<{ code: string; message: string }>;
    unknowns: Array<{ code: string; message: string }>;
    limitations: string[];
    safe_next_action: { label?: string; reason?: string };
    trust_environment: Record<string, unknown>;
  };
  decision_synthesis?: {
    posture: string;
    readiness_state: string;
    primary_reason: { explanation?: string; code?: string };
    reasons: Array<{ code: string; category?: string; explanation?: string; blocking?: boolean }>;
    supporting_evidence: Array<{ code: string; value?: unknown; state?: string }>;
    blockers: Array<{ code: string; message: string }>;
    warnings: Array<{ code: string; message: string }>;
    unknowns: Array<{ code: string; message: string }>;
    contradictions: Array<{ code: string; message: string }>;
    trust_summary: Record<string, unknown>;
    economics_summary: Record<string, unknown>;
    capital_fit_state: string;
    safe_next_actions: Array<{
      code: string;
      label: string;
      reason?: string;
      depends_on?: string[];
      external_action?: boolean;
    }>;
    human_review_required: boolean;
    explanation: string;
  };
  recommendation?: {
    id: string;
    synthesis_id: string;
    decision_target: string;
    recommendation_state: string;
    recommendation_eligible?: boolean;
    supporting_reasons: Array<{ code: string; explanation?: string; message?: string }>;
    counter_reasons: Array<{ code: string; explanation?: string; message?: string }>;
    warnings: Array<{ code: string; message?: string }>;
    unknowns: Array<{ code: string; message?: string }>;
    contradictions: Array<{ code: string; message?: string }>;
    limitations: Array<{ code?: string; message?: string }>;
    human_review_required: boolean;
    explanation: string;
  } | null;
  human_decision?: {
    id: string;
    decision: string;
    decision_target: string;
    provenance: string;
    reason: string;
    created_at: string;
  } | null;
  engagement?: {
    id: string;
    supplier_id: string;
    contact_id: string | null;
    engagement_type: string;
    status: string;
    current_draft?: {
      supplier: Record<string, unknown>;
      product: Record<string, unknown>;
      contact: Record<string, unknown>;
      structured_request: {
        requested_quantity?: number | string | null;
        requested_fields?: string[];
        [key: string]: unknown;
      };
      subject: string;
      message_body: string;
      warnings: Array<{ code?: string; message?: string }>;
      unknowns: Array<{ field?: string; reason?: string }>;
      limitations: string[];
      provenance: string;
      version: number;
    } | null;
    latest_approval?: {
      state: string;
      provenance: string;
      created_at: string;
    } | null;
    can_send: boolean;
    send_status: string;
    send_eligibility?: {
      can_authorize_send: boolean;
      fake_provider_allowed: boolean;
      live_provider_allowed: boolean;
      live_eligible: boolean;
      trust_environment: string;
      blocking_reasons: Array<{ code: string; message: string }>;
      preview?: {
        recipient?: string | null;
        subject?: string | null;
        quantity?: number | string | null;
        requested_fields?: string[];
        message?: string | null;
      };
    } | null;
    send_authorization?: {
      id: string;
      status: string;
      recipient: string;
      draft_version: number;
    } | null;
    send_command?: {
      id: string;
      status: string;
      attempt_count: number;
      provider_reference?: string | null;
      last_error?: string | null;
    } | null;
    safe_next_action: string;
  } | null;
  engagement_eligibility?: {
    state: string;
    can_send: boolean;
    send_status: string;
    safe_next_action: string;
  };
}

interface LiveSupplierApprovalView {
  id: string;
  opportunity_id: string | null;
  source_url: string;
  normalized_host: string;
  path_scope: string;
  candidate_category: string;
  operation: string;
  purpose: string;
  status: string;
  version: number;
  approved_at: string;
  expires_at: string | null;
}

interface LiveSupplierPolicyView {
  policy_version: string;
  mode: string;
  provider: string;
  read_only: boolean;
  external_writes: boolean;
  ready: boolean;
  blockers: string[];
  max_bytes: number;
  max_redirects: number;
  timeout_seconds: number;
}

interface LiveSupplierExecutionAuthorizationView {
  id: string;
  approval_id: string;
  opportunity_id: string | null;
  source_url: string;
  normalized_host: string;
  path_scope: string;
  provider: string;
  mode: string;
  actor_provenance: string;
  approval_version: number;
  status: string;
  max_requests: number;
  used_requests: number;
  expires_at: string | null;
  execution_id: string | null;
}

interface LiveSupplierCertificationView {
  id: string;
  opportunity_id: string | null;
  approval_id: string;
  source_url: string;
  provider: string;
  mode: string;
  status: string;
  gate_outcomes: Record<string, string>;
  blockers: string[];
  external_read_count: number;
  external_write_count: number;
  trust_classification: string;
  supplier_correlation: Record<string, unknown>;
  product_classification: Record<string, unknown>;
  execution: {
    id: string;
    final_url: string | null;
    content_hash: string | null;
    status: string;
    failure_code: string | null;
    provenance: Record<string, unknown>;
  } | null;
}

interface LiveSupplierExecutionAuthorizationView {
  id: string;
  approval_id: string;
  opportunity_id: string | null;
  source_url: string;
  normalized_host: string;
  path_scope: string;
  provider: string;
  mode: string;
  actor_provenance: string;
  approval_version: number;
  status: string;
  max_requests: number;
  used_requests: number;
  expires_at: string | null;
  execution_id: string | null;
}

interface SupplierResponseExtractionView {
  id: string;
  version: number;
  status: string;
  extracted_fields: Record<string, unknown>;
  field_provenance: Record<string, unknown>;
  unknown_fields: unknown[];
  warnings: unknown[];
  extraction_authority: string;
  source_raw_hash: string;
}

interface SupplierResponseReviewView {
  id: string;
  extraction_id: string;
  decision: string;
  provenance: string;
  reason: string;
  created_at: string;
}

interface SupplierResponsePromotionView {
  id: string;
  status: string;
  provenance: string;
  supplier_evidence_id: string | null;
  supplier_product_id: string | null;
  commercial_term_id: string | null;
  readiness_snapshot_id: string | null;
  contradictions: unknown[];
}

interface SupplierResponseView {
  id: string;
  supplier_id: string | null;
  opportunity_id: string | null;
  engagement_id: string | null;
  draft_id: string | null;
  send_command_id: string | null;
  channel: string;
  sender_identity: string | null;
  recipient_identity: string | null;
  received_at: string;
  attachment_refs: unknown[];
  raw_content: string;
  raw_content_hash: string;
  trust_environment: string;
  evidence_environment: string;
  correlation_state: string;
  correlation_reason: string;
  classification: string;
  extraction: SupplierResponseExtractionView | null;
  reviews: SupplierResponseReviewView[];
  promotion: SupplierResponsePromotionView | null;
  safe_next_action: string;
}

interface SupplierResponseListView {
  responses: SupplierResponseView[];
  total: number;
}

interface CommercialReassessmentView {
  id: string;
  promotion_id: string;
  commercial_term_id: string;
  supplier_id: string;
  supplier_product_id: string;
  status: string;
  review_status: string;
  quote_version: number;
  quote_evidence: {
    claim_semantics?: string;
    provenance?: string;
    trust_environment?: string;
    evidence_environment?: string;
    fields?: Record<string, unknown>;
  };
  baseline: Record<string, unknown>;
  current: Record<string, unknown>;
  comparison: {
    metrics?: Record<
      string,
      { baseline: unknown; reassessment: unknown; delta: unknown; state: string }
    >;
  };
  blockers: string[];
  assumptions: unknown[];
  review: { decision: string; provenance: string; reason: string } | null;
}

interface SupplierComparisonMetricView {
  metric: string;
  values: Array<{
    canonical_supplier_id: string;
    supplier: string;
    value: unknown;
    currency: string | null;
    unit: string | null;
    state: string;
    evidence: Record<string, unknown>;
  }>;
  delta: string | null;
  state: string;
  reason: string;
}

interface SupplierComparisonSupplierView {
  canonical_supplier_id: string;
  supplier: string;
  supplier_identity_state: string;
  supplier_verification: string;
  supplier_product_id: string;
  reassessment_id?: string;
  product: {
    title: string | null;
    category: string | null;
    specifications: Record<string, unknown>;
  };
  quote: {
    version: number;
    valid_until: string | null;
    is_current: boolean;
    source_evidence_id: string | null;
  };
  status: string;
  reassessment_status: string;
  commercial_readiness: unknown;
  metrics: Record<
    string,
    { value: unknown; currency: string | null; unit: string | null; state: string }
  >;
  unknowns: string[];
  blockers: string[];
  contradictions: unknown[];
  trust: Record<string, unknown>;
  assumptions: unknown[];
  scenario_scope: Record<string, unknown>;
}

interface SupplierComparisonView {
  id: string;
  status: string;
  snapshot_version: number;
  input_fingerprint: string;
  canonical_supplier_ids: string[];
  reassessment_ids: string[];
  suppliers: SupplierComparisonSupplierView[];
  metrics: SupplierComparisonMetricView[];
  unknowns: string[];
  blockers: string[];
  contradictions: unknown[];
  provenance: Record<string, unknown>;
  shortlist_context_id: string | null;
  shortlist_version_id: string | null;
  human_decisions: Array<{
    id: string;
    canonical_supplier_id: string;
    decision: string;
    reason: string;
    created_at: string;
  }>;
  created_at: string;
  notes: string;
  idempotent_reuse: boolean;
}

interface ProcurementReadinessDimensionView {
  status: string;
  evidence_refs: string[];
  provenance: string;
  freshness: string;
  missing_information: string[];
  contradictions: unknown[];
  blockers: string[];
  safe_next_action: string;
  values: Record<string, unknown>;
}

interface ProcurementReadinessView {
  id: string;
  canonical_supplier_id: string;
  supplier_id: string | null;
  supplier_product_id: string | null;
  shortlist_decision_id: string | null;
  comparison_id: string | null;
  snapshot_version: number;
  status: string;
  policy_version: string;
  calculation_versions: unknown[];
  dimensions: Record<string, ProcurementReadinessDimensionView>;
  blockers: unknown[];
  unknowns: unknown[];
  contradictions: unknown[];
  evidence_lineage: Record<string, unknown>;
  provenance: Record<string, unknown>;
  input_fingerprint: string;
  created_at: string;
  notes: string;
  acknowledgements: Array<{
    id: string;
    decision: string;
    provenance: string;
    reason: string;
    created_at: string;
  }>;
  idempotent_reuse?: boolean;
}

interface OpportunityScopeView {
  current_assessment_id: string | null;
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
  imports: [
    BlockedStateComponent,
    BreadcrumbsComponent,
    CommonModule,
    CommerceJourneyContextComponent,
    ErrorStateComponent,
    FormsModule,
    LoadingStateComponent,
    PageHeaderComponent,
    RouterLink,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="economics-page" aria-labelledby="economics-title">
      <app-breadcrumbs [items]="breadcrumbs" />
      <app-page-header
        eyebrow="Intelligence / Sourcing economics"
        title="Review sourcing economics"
        headingId="economics-title"
        description="Compare known costs, evidence gaps, budget fit, and risks. Sourcing economic inputs remain immutable while you calculate a reproducible known-cost subtotal before deciding."
      >
        <a page-header-actions routerLink="/intelligence">Back to Intelligence</a>
      </app-page-header>
      <app-commerce-journey-context />
      <section class="panel live-certification-panel" aria-labelledby="live-certification-title">
        <p class="eyebrow">PR-9A · LIVE SUPPLIER EVIDENCE</p>
        <h2 id="live-certification-title">Approve, authorize, then review one source</h2>
        <p>
          First approve the exact HTTPS source, then create a separate HUMAN execution
          authorization. The read is single-use, preserves its hash and provenance, and never
          contacts a supplier or sends an RFQ from this panel.
        </p>
        @if (livePolicy(); as policy) {
          <div class="live-policy-status" role="status">
            <strong>Provider readiness:</strong> {{ policy.ready ? 'READY' : 'BLOCKED' }} ·
            {{ policy.provider }} · {{ policy.mode }} · external writes
            {{ policy.external_writes ? 'ENABLED' : 'OFF' }}.
            <span
              >Kill-switch/policy blockers:
              {{ policy.blockers.join(', ') || 'none reported' }}.</span
            >
          </div>
        }
        @if (!opportunityId) {
          <p class="hint">
            Select a product opportunity first. Certification is always product-scoped.
          </p>
        } @else {
          <form class="form-grid" (submit)="$event.preventDefault(); approveLiveSource()">
            <label
              >Approved source URL
              <input
                name="liveSourceUrl"
                [(ngModel)]="liveSourceUrl"
                required
                placeholder="https://supplier.example/products/item"
              />
            </label>
            <label
              >Purpose
              <input name="liveSourcePurpose" [(ngModel)]="liveSourcePurpose" required />
            </label>
            <label
              >Source category
              <select name="liveSourceCategory" [(ngModel)]="liveSourceCategory">
                <option value="supplier_website">Supplier website</option>
                <option value="manufacturer_website">Manufacturer website</option>
                <option value="distributor_website">Distributor website</option>
              </select>
            </label>
            <button type="submit" [disabled]="busy() || !liveSourceUrl.trim()">
              Create HUMAN approval
            </button>
          </form>
          @if (liveCertificationError()) {
            <p class="warning-note" role="alert">{{ liveCertificationError() }}</p>
          }
          @if (liveApprovals().length) {
            <div class="live-certification-list">
              <h3>Scoped approvals</h3>
              @for (approval of liveApprovals(); track approval.id) {
                <article class="live-certification-card">
                  <strong>{{ approval.normalized_host }}</strong
                  ><br />
                  <span>{{ approval.source_url }}</span>
                  <p>Exact scope: {{ approval.normalized_host }}{{ approval.path_scope }}</p>
                  <p>
                    Status: <strong>{{ approval.status }}</strong> · HUMAN ·
                    {{ approval.operation }} · v{{ approval.version }}
                  </p>
                  <button
                    type="button"
                    (click)="authorizeLiveExecution(approval)"
                    [disabled]="busy() || approval.status !== 'APPROVED'"
                  >
                    Authorize one HUMAN read
                  </button>
                  @if (approval.status === 'APPROVED') {
                    <button
                      type="button"
                      class="secondary-action"
                      (click)="revokeLiveApproval(approval)"
                      [disabled]="busy()"
                    >
                      Revoke approval
                    </button>
                  }
                </article>
              }
            </div>
          }
          @if (liveAuthorizations().length) {
            <div class="live-certification-list">
              <h3>Execution authorizations</h3>
              <p class="hint">
                Source approval and execution authorization are separate. Review the exact scope,
                then explicitly execute once.
              </p>
              @for (authorization of liveAuthorizations(); track authorization.id) {
                <article class="live-certification-card" [attr.data-status]="authorization.status">
                  <strong>{{ authorization.status }}</strong> · HUMAN ·
                  {{ authorization.provider }} · v{{ authorization.approval_version }}
                  <p>{{ authorization.source_url }}</p>
                  <p>
                    Single-use: {{ authorization.used_requests }}/{{ authorization.max_requests }} ·
                    {{ authorization.mode }}
                  </p>
                  <button
                    type="button"
                    (click)="executeLiveAuthorization(authorization)"
                    [disabled]="busy() || authorization.status !== 'ACTIVE'"
                  >
                    Execute authorized read
                  </button>
                  <button
                    type="button"
                    class="secondary-action"
                    (click)="revokeLiveAuthorization(authorization)"
                    [disabled]="busy() || authorization.status !== 'ACTIVE'"
                  >
                    Revoke authorization
                  </button>
                </article>
              }
            </div>
          }
          @if (liveRuns().length) {
            <div class="live-certification-list">
              <h3>Certification history</h3>
              @for (run of liveRuns(); track run.id) {
                <article class="live-certification-card" [attr.data-status]="run.status">
                  <strong>{{ run.status }}</strong> · {{ run.mode }} · reads
                  {{ run.external_read_count }} · writes {{ run.external_write_count }}
                  <p>
                    Trust: {{ run.trust_classification }} · Supplier correlation:
                    {{ run.supplier_correlation['outcome'] || 'UNKNOWN' }}
                  </p>
                  <p>
                    Next action: review the gate outcomes and evidence hash before any downstream
                    HUMAN decision.
                  </p>
                  @if (run.blockers.length) {
                    <p class="warning-note">Blocked: {{ run.blockers.join(', ') }}</p>
                  }
                  @if (run.execution?.id) {
                    <button
                      type="button"
                      (click)="reviewLiveEvidence(run, 'ACCEPT')"
                      [disabled]="busy()"
                    >
                      Accept evidence as HUMAN-reviewed
                    </button>
                    <button
                      type="button"
                      class="secondary-action"
                      (click)="reviewLiveEvidence(run, 'CONTRADICTION')"
                      [disabled]="busy()"
                    >
                      Mark contradiction
                    </button>
                  }
                  <details>
                    <summary>Gate outcomes and provenance</summary>
                    <pre>{{ run.gate_outcomes | json }}</pre>
                    <pre>{{ run.execution?.provenance | json }}</pre>
                  </details>
                </article>
              }
            </div>
          }
        }
      </section>
      @if (error()) {
        <app-error-state
          [message]="error()"
          retryLabel="Retry decision brief"
          (retry)="retryLoad()"
        />
      }
      @if (busy()) {
        <app-loading-state message="Updating sourcing economics..." />
      }
      <section class="panel" aria-labelledby="brief-title">
        <h2 id="brief-title">Decision brief</h2>
        <p>
          Review authoritative sourcing economics, evidence gaps, budget scope, and risks before
          making an explicit human decision. Unknown values remain unknown.
        </p>
        @if (opportunityId) {
          <p class="context-note" role="status">
            Using the selected product from the guided journey{{
              journeyProductName ? ': ' + journeyProductName : ''
            }}.
          </p>
        }
        <form (submit)="$event.preventDefault(); loadDecisionBrief()" class="form-grid">
          @if (!opportunityId) {
            <app-blocked-state
              title="Select a product before reviewing economics"
              reason="Sourcing economics and the Decision Brief stay scoped to a human-selected product opportunity."
            />
            <a routerLink="/intelligence/product-opportunities">Choose a product opportunity</a>
          }
          <details>
            <summary>Advanced decision identifiers</summary>
            <label
              >Product opportunity ID
              <input name="opportunityIdAdvanced" [(ngModel)]="opportunityId" />
            </label>
            <label
              >Journey ID (for decision)
              <input
                name="journeyId"
                [(ngModel)]="journeyId"
                placeholder="Business Agent goal UUID"
            /></label>
          </details>
          <button type="submit" [disabled]="busy()">Load decision brief</button>
        </form>
        @if (decisionBrief(); as brief) {
          <div class="brief-summary" role="status">
            <h3>{{ brief.product.name }}</h3>
            <p class="context-note">
              <strong>Goal context:</strong> {{ brief.goal?.text || 'UNKNOWN' }} ·
              {{ brief.goal?.provenance || 'UNKNOWN' }}
            </p>
            <p class="context-note">
              <strong>Product context:</strong> {{ brief.product.category || 'UNKNOWN' }} ·
              {{ brief.product.marketplace || 'UNKNOWN' }} ·
              {{ brief.product.provenance || 'UNKNOWN' }}
            </p>
            <p>
              Readiness: <strong>{{ brief.decision_readiness }}</strong> Â· Risk:
              <strong>{{ brief.risk }}</strong> Â· Evidence:
              <strong>{{ brief.evidence_completeness }}</strong>
            </p>
            <p>
              Suppliers: {{ brief.suppliers.verified_count }} verified /
              {{ brief.suppliers.shortlisted_count }} shortlisted.
            </p>
            <p>
              Budget: {{ brief.budget_fit.budget || 'UNKNOWN' }}
              {{ brief.budget_fit.currency || '' }} Â· {{ brief.budget_fit.status }}
            </p>
            <p class="hint">{{ brief.budget_fit.scope }}</p>
          </div>
          @if (brief.engagement; as engagement) {
            <section class="engagement-panel" aria-labelledby="engagement-title">
              <p class="eyebrow">CONTROLLED SUPPLIER ENGAGEMENT</p>
              <h3 id="engagement-title">Review and control supplier contact</h3>
              <p>
                Approval and sending are separate human actions. Review the exact recipient and
                message below; no supplier is contacted until you explicitly choose Send RFQ.
              </p>
              <dl class="engagement-facts">
                <div>
                  <dt>Status</dt>
                  <dd>{{ engagement.status }}</dd>
                </div>
                <div>
                  <dt>Intent</dt>
                  <dd>{{ engagement.engagement_type }}</dd>
                </div>
                <div>
                  <dt>Supplier</dt>
                  <dd>
                    {{
                      engagement.current_draft?.supplier?.['display_name'] || engagement.supplier_id
                    }}
                  </dd>
                </div>
                <div>
                  <dt>Contact</dt>
                  <dd>{{ engagement.current_draft?.contact?.['name'] || 'Not available' }}</dd>
                </div>
                <div>
                  <dt>Contact provenance</dt>
                  <dd>{{ engagement.current_draft?.contact?.['provenance'] || 'UNKNOWN' }}</dd>
                </div>
                <div>
                  <dt>Verification / trust</dt>
                  <dd>
                    {{ engagement.current_draft?.contact?.['verification_status'] || 'UNKNOWN' }} ·
                    {{ engagement.current_draft?.contact?.['trust_environment'] || 'UNKNOWN' }}
                  </dd>
                </div>
                <div>
                  <dt>Product</dt>
                  <dd>{{ engagement.current_draft?.product?.['name'] || 'UNKNOWN' }}</dd>
                </div>
                <div>
                  <dt>Requested quantity</dt>
                  <dd>
                    {{
                      engagement.current_draft?.structured_request?.['requested_quantity'] ||
                        'UNKNOWN'
                    }}
                  </dd>
                </div>
                <div>
                  <dt>Requested fields</dt>
                  <dd>
                    {{
                      (
                        engagement.current_draft?.structured_request?.['requested_fields'] || []
                      ).join(', ') || 'UNKNOWN'
                    }}
                  </dd>
                </div>
                <div>
                  <dt>Draft version</dt>
                  <dd>
                    {{ engagement.current_draft?.version || 'UNKNOWN' }} ·
                    {{ engagement.current_draft?.provenance || 'UNKNOWN' }}
                  </dd>
                </div>
                <div>
                  <dt>Approval</dt>
                  <dd>{{ engagement.latest_approval?.state || 'NOT APPROVED' }}</dd>
                </div>
                <div>
                  <dt>Send state</dt>
                  <dd>
                    {{ engagement.send_command?.status || engagement.send_status }} · provider
                    acceptance is not delivery
                  </dd>
                </div>
              </dl>
              @if (engagement.current_draft; as draft) {
                <details>
                  <summary>Inspect draft message, warnings, unknowns, and limitations</summary>
                  <h4>{{ draft.subject }}</h4>
                  <pre class="engagement-message">{{ draft.message_body }}</pre>
                  <p>
                    <strong>Warnings:</strong>
                    {{ draft.warnings.length ? (draft.warnings | json) : 'None recorded' }}
                  </p>
                  <p>
                    <strong>Unknowns:</strong>
                    {{ draft.unknowns.length ? (draft.unknowns | json) : 'None recorded' }}
                  </p>
                  <p>
                    <strong>Limitations:</strong>
                    {{ draft.limitations.join('; ') || 'None recorded' }}
                  </p>
                </details>
              }
              <div class="decision-actions" role="group" aria-label="Controlled engagement actions">
                @if (engagement.status === 'NEEDS_REVIEW') {
                  <button
                    type="button"
                    (click)="approveEngagement(engagement.id)"
                    [disabled]="busy()"
                  >
                    Approve for future send (no message sent)
                  </button>
                }
                @if (engagement.send_eligibility; as send) {
                  @if (send.can_authorize_send && !engagement.send_authorization) {
                    <button
                      type="button"
                      (click)="authorizeRfqSend(engagement)"
                      [disabled]="busy()"
                    >
                      Authorize Send RFQ
                    </button>
                  }
                  @if (engagement.send_authorization && !engagement.send_command) {
                    <button type="button" (click)="sendRfq(engagement)" [disabled]="busy()">
                      Send RFQ
                    </button>
                  }
                  @if (send.blocking_reasons.length) {
                    <p class="hint">
                      <strong>Why sending is unavailable:</strong>
                      {{ send.blocking_reasons[0].message }}
                    </p>
                  }
                }
                @if (engagement.status !== 'CANCELLED') {
                  <button
                    type="button"
                    class="secondary-action"
                    (click)="cancelEngagement(engagement.id)"
                    [disabled]="busy()"
                  >
                    Cancel draft
                  </button>
                }
              </div>
              <p class="hint">
                <strong>Safe next action:</strong> {{ engagement.safe_next_action }}
              </p>
            </section>
          }
          @if (supplierResponses().length) {
            <section class="supplier-response-panel" aria-labelledby="supplier-response-title">
              <p class="eyebrow">INBOUND SUPPLIER EVIDENCE</p>
              <h3 id="supplier-response-title">Review supplier responses</h3>
              <p>
                Responses are immutable source material. Review the sender, correlation, and
                extracted claims before promoting anything into commercial evidence. Supplier text
                is untrusted content and never gives instructions to VAYUJIT.
              </p>
              @for (response of supplierResponses(); track response.id) {
                <article
                  class="supplier-response-card"
                  [attr.aria-labelledby]="'response-' + response.id"
                >
                  <div class="supplier-response-heading">
                    <h4 [id]="'response-' + response.id">
                      {{ response.classification.replaceAll('_', ' ') }}
                    </h4>
                    <span class="evidence-badge">{{ response.correlation_state }}</span>
                  </div>
                  <dl class="engagement-facts">
                    <div>
                      <dt>Supplier</dt>
                      <dd>{{ response.supplier_id || 'UNKNOWN' }}</dd>
                    </div>
                    <div>
                      <dt>Channel</dt>
                      <dd>{{ response.channel }}</dd>
                    </div>
                    <div>
                      <dt>Sender</dt>
                      <dd>{{ response.sender_identity || 'UNKNOWN' }}</dd>
                    </div>
                    <div>
                      <dt>Received</dt>
                      <dd>{{ response.received_at }}</dd>
                    </div>
                    <div>
                      <dt>Trust / evidence</dt>
                      <dd>
                        {{ response.trust_environment }} · {{ response.evidence_environment }}
                      </dd>
                    </div>
                    <div>
                      <dt>Raw hash</dt>
                      <dd>{{ response.raw_content_hash }}</dd>
                    </div>
                    <div>
                      <dt>Freshness anchor</dt>
                      <dd>
                        Received {{ response.received_at }}; canonical freshness remains reviewable
                      </dd>
                    </div>
                    <div>
                      <dt>Attachments</dt>
                      <dd>
                        {{
                          response.attachment_refs.length
                            ? (response.attachment_refs | json)
                            : 'None recorded'
                        }}
                      </dd>
                    </div>
                    <div>
                      <dt>Correlation</dt>
                      <dd>{{ response.correlation_reason }}</dd>
                    </div>
                    <div>
                      <dt>Engagement / send</dt>
                      <dd>
                        {{ response.engagement_id || 'UNKNOWN' }} ·
                        {{ response.send_command_id || 'UNKNOWN' }}
                      </dd>
                    </div>
                  </dl>
                  <details>
                    <summary>SUPPLIER SAID — inspect immutable raw response</summary>
                    <pre class="supplier-raw-response">{{ response.raw_content }}</pre>
                  </details>
                  @if (response.extraction; as extraction) {
                    <details open>
                      <summary>
                        VAYUJIT DERIVED — inspect extraction v{{ extraction.version }} and
                        provenance
                      </summary>
                      <p class="hint">
                        Deterministic extraction authority: {{ extraction.extraction_authority }} ·
                        source hash: {{ extraction.source_raw_hash }}
                      </p>
                      <dl class="input-list supplier-claim-list">
                        @for (
                          claim of claimEntries(extraction.extracted_fields);
                          track $index + ':' + claim[0]
                        ) {
                          <div>
                            <dt>{{ claim[0].replaceAll('_', ' ') }}</dt>
                            <dd>
                              {{ displayClaim(claim[1]) }}
                              <span class="claim-state">{{
                                claimProvenance(extraction, claim[0])
                              }}</span>
                            </dd>
                          </div>
                        }
                      </dl>
                      @if (extraction.unknown_fields.length) {
                        <p class="hint">
                          <strong>Unknowns:</strong> {{ extraction.unknown_fields | json }}
                        </p>
                      }
                      @if (extraction.warnings.length) {
                        <p class="warning-note">
                          <strong>Warnings:</strong> {{ extraction.warnings | json }}
                        </p>
                      }
                    </details>
                  }
                  @if (response.reviews.length) {
                    <p class="callout" role="status">
                      Latest HUMAN review: {{ latestResponseReview(response)?.decision }} ·
                      {{ latestResponseReview(response)?.created_at }}
                    </p>
                  }
                  @if (
                    !response.reviews.length &&
                    response.correlation_state === 'CORRELATED' &&
                    response.extraction
                  ) {
                    <div class="correction-editor">
                      <label [for]="'correction-' + response.id"
                        >Optional correction JSON (for example, moq: 500)</label
                      >
                      <textarea
                        [id]="'correction-' + response.id"
                        [(ngModel)]="correctionDrafts[response.id]"
                        rows="2"
                        placeholder="Leave blank to use the extracted values"
                      ></textarea>
                    </div>
                    <div
                      class="decision-actions"
                      role="group"
                      aria-label="Human response review actions"
                    >
                      <button
                        type="button"
                        (click)="reviewSupplierResponse(response, 'ACCEPT_EXTRACTION')"
                        [disabled]="busy()"
                      >
                        Accept extracted claims for promotion
                      </button>
                      <button
                        type="button"
                        (click)="correctSupplierResponse(response)"
                        [disabled]="busy()"
                      >
                        Correct extraction
                      </button>
                      <button
                        type="button"
                        class="secondary-action"
                        (click)="reviewSupplierResponse(response, 'KEEP_UNDER_REVIEW')"
                        [disabled]="busy()"
                      >
                        Keep under review
                      </button>
                      <button
                        type="button"
                        class="secondary-action"
                        (click)="reviewSupplierResponse(response, 'REJECT_EXTRACTION')"
                        [disabled]="busy()"
                      >
                        Reject extraction
                      </button>
                    </div>
                  }
                  @if (canPromoteSupplierResponse(response)) {
                    <button
                      type="button"
                      (click)="promoteSupplierResponse(response)"
                      [disabled]="busy()"
                    >
                      Promote accepted claims to PR-5A evidence
                    </button>
                  }
                  @if (response.promotion; as promotion) {
                    <p class="callout" role="status">
                      Promotion {{ promotion.status }} · HUMAN review preserved · evidence
                      {{ promotion.supplier_evidence_id || 'UNKNOWN' }}
                    </p>
                    @if (promotion.contradictions.length) {
                      <p class="warning-note">
                        <strong>Contradictions:</strong> {{ promotion.contradictions | json }}
                      </p>
                    }
                  }
                  @if (response.reviews.length) {
                    <p class="hint">
                      <strong>YOU CONFIRMED EXTRACTION:</strong>
                      {{
                        latestResponseReview(response)?.decision === 'CORRECT_EXTRACTION'
                          ? 'Human corrections were recorded as a new review decision.'
                          : latestResponseReview(response)?.decision
                      }}
                    </p>
                  }
                  <p class="hint">
                    <strong>Safe next action:</strong> {{ response.safe_next_action }}
                  </p>
                </article>
              }
            </section>
          } @else if (!supplierResponsesLoading()) {
            <section
              class="supplier-response-empty"
              aria-labelledby="supplier-response-empty-title"
            >
              <h3 id="supplier-response-empty-title">No inbound supplier responses</h3>
              <p>
                No supplier response is recorded for this selected opportunity. Nothing is promoted
                or verified automatically.
              </p>
            </section>
          }
          @if (assessmentId && reassessments().length) {
            <section class="reassessment-panel" aria-labelledby="reassessment-title">
              <h3 id="reassessment-title">Evidence-backed commercial reassessment</h3>
              <p>
                Reviewed supplier claims are compared with the immutable baseline. Supplier claims
                remain unverified, assumptions remain explicit, and no supplier is selected or
                contacted.
              </p>
              @for (item of reassessments(); track item.id) {
                <article
                  class="reassessment-card"
                  [attr.aria-labelledby]="'reassessment-' + item.id"
                >
                  <h4 [id]="'reassessment-' + item.id">
                    Quote v{{ item.quote_version }} · {{ item.status }}
                  </h4>
                  <p class="hint">
                    {{ item.quote_evidence.claim_semantics || 'SOURCE_PROVIDED_CLAIM' }} · HUMAN
                    extraction review: {{ item.quote_evidence.provenance || 'HUMAN' }}
                  </p>
                  @if (item.blockers.length) {
                    <p class="warning-note">
                      <strong>Calculation blockers:</strong> {{ item.blockers.join(', ') }}
                    </p>
                  }
                  @if (item.comparison.metrics; as metrics) {
                    <dl class="input-list reassessment-metrics">
                      @for (entry of metricEntries(metrics); track $index + ':' + entry[0]) {
                        <div>
                          <dt>{{ entry[0].replaceAll('_', ' ') }}</dt>
                          <dd>
                            {{ entry[1].reassessment ?? 'UNKNOWN' }} ({{ entry[1].state }}) · delta
                            {{ entry[1].delta ?? 'UNKNOWN' }}
                          </dd>
                        </div>
                      }
                    </dl>
                  }
                  <p>
                    <strong>Next safe action:</strong> Review the quote evidence, assumptions, and
                    blockers. This is not supplier approval.
                  </p>
                  @if (!item.review) {
                    <button
                      type="button"
                      (click)="reviewReassessment(item, 'KEEP_UNDER_REVIEW')"
                      [disabled]="busy()"
                    >
                      Acknowledge and keep under review
                    </button>
                  } @else {
                    <p class="callout" role="status">
                      {{ item.review.decision }} · {{ item.review.provenance }}
                    </p>
                  }
                </article>
              }
            </section>
          }
          @if (assessmentId && reassessments().length >= 2) {
            <section class="comparison-panel" aria-labelledby="comparison-start-title">
              <p class="eyebrow">EVIDENCE-BACKED COMPARISON</p>
              <h3 id="comparison-start-title">Compare supplier scenarios</h3>
              <p>
                Compare two or more distinct supplier reassessments side by side. This is a neutral
                trade-off view: VAYUJIT will not rank a winner or create a shortlist automatically.
              </p>
              <p class="hint">
                The comparison reuses quote evidence, PR-8A reassessments, and PR-5B/C calculations.
                Missing values remain UNKNOWN and incompatible values are not given a delta.
              </p>
              @if (comparisonCandidateIds().length >= 2) {
                <button type="button" (click)="createSupplierComparison()" [disabled]="busy()">
                  Create or refresh comparison
                </button>
              } @else {
                <p class="status-note" role="status">
                  At least two distinct supplier reassessments are required before comparison.
                </p>
              }
            </section>
          }
          @if (assessmentId && comparisonSnapshots().length) {
            <section class="comparison-panel" aria-labelledby="comparison-review-title">
              <p class="eyebrow">HUMAN REVIEW ONLY</p>
              <h3 id="comparison-review-title">Supplier comparison review</h3>
              <p>
                Review identity, product scope, evidence quality, and commercial differences before
                recording a canonical HUMAN shortlist decision. No supplier is preselected.
              </p>
              @for (snapshot of comparisonSnapshots(); track snapshot.id) {
                <article
                  class="comparison-snapshot"
                  [attr.aria-labelledby]="'comparison-' + snapshot.id"
                >
                  <div class="supplier-response-heading">
                    <h4 [id]="'comparison-' + snapshot.id">
                      Comparison v{{ snapshot.snapshot_version }}
                    </h4>
                    <span class="evidence-badge">{{ snapshot.status }}</span>
                  </div>
                  <p class="hint">
                    Created {{ snapshot.created_at }} · fingerprint {{ snapshot.input_fingerprint }}
                  </p>
                  @if (
                    snapshot.status === 'NOT_COMPARABLE' || snapshot.status === 'NEEDS_EVIDENCE'
                  ) {
                    <p class="warning-note" role="status">
                      This comparison is not decision-ready:
                      {{ snapshot.provenance['product_comparability'] | json }}
                    </p>
                  }
                  <div class="supplier-comparison-grid">
                    @for (
                      supplier of snapshot.suppliers;
                      track $index + ':' + supplier.canonical_supplier_id
                    ) {
                      <article class="supplier-comparison-card">
                        <h5>{{ supplier.supplier }}</h5>
                        <dl class="engagement-facts">
                          <div>
                            <dt>Identity</dt>
                            <dd>{{ supplier.supplier_identity_state }}</dd>
                          </div>
                          <div>
                            <dt>Verification</dt>
                            <dd>{{ supplier.supplier_verification }}</dd>
                          </div>
                          <div>
                            <dt>Product</dt>
                            <dd>{{ supplier.product.title || 'UNKNOWN' }}</dd>
                          </div>
                          <div>
                            <dt>Category</dt>
                            <dd>{{ supplier.product.category || 'UNKNOWN' }}</dd>
                          </div>
                          <div>
                            <dt>Commercial readiness</dt>
                            <dd>{{ displayClaim(supplier.commercial_readiness) }}</dd>
                          </div>
                          <div>
                            <dt>Quote</dt>
                            <dd>
                              v{{ supplier.quote.version }} ·
                              {{ supplier.quote.is_current ? 'CURRENT' : 'NOT CURRENT' }}
                            </dd>
                          </div>
                          <div>
                            <dt>Freshness / validity</dt>
                            <dd>{{ supplier.quote.valid_until || 'UNKNOWN' }}</dd>
                          </div>
                          <div>
                            <dt>Quote evidence</dt>
                            <dd>{{ supplier.quote.source_evidence_id || 'UNKNOWN' }}</dd>
                          </div>
                        </dl>
                        @if (supplier.unknowns.length) {
                          <p class="warning-note">
                            <strong>Unknowns:</strong> {{ supplier.unknowns.join('; ') }}
                          </p>
                        }
                        @if (supplier.blockers.length) {
                          <p class="warning-note">
                            <strong>Blockers:</strong> {{ supplier.blockers.join('; ') }}
                          </p>
                        }
                        @if (supplier.contradictions.length) {
                          <p class="warning-note">
                            <strong>Contradictions:</strong> {{ supplier.contradictions | json }}
                          </p>
                        }
                        <p class="hint"><strong>Trust:</strong> {{ supplier.trust | json }}</p>
                        <p class="hint">
                          <strong>Scenario scope:</strong> {{ supplier.scenario_scope | json }}
                        </p>
                        @if (supplier.assumptions.length) {
                          <p class="hint">
                            <strong>Assumptions:</strong> {{ supplier.assumptions | json }}
                          </p>
                        }
                        <div
                          class="decision-actions"
                          [attr.aria-label]="'HUMAN shortlist actions for ' + supplier.supplier"
                        >
                          <button
                            type="button"
                            (click)="
                              shortlistComparisonSupplier(
                                snapshot,
                                supplier.canonical_supplier_id,
                                'KEEP_UNDER_REVIEW'
                              )
                            "
                            [disabled]="busy()"
                          >
                            Keep under review
                          </button>
                          <button
                            type="button"
                            (click)="
                              shortlistComparisonSupplier(
                                snapshot,
                                supplier.canonical_supplier_id,
                                'APPROVE_FOR_SOURCING'
                              )
                            "
                            [disabled]="busy()"
                          >
                            Approve for sourcing (HUMAN)
                          </button>
                          <button
                            type="button"
                            class="secondary-action"
                            (click)="
                              shortlistComparisonSupplier(
                                snapshot,
                                supplier.canonical_supplier_id,
                                'REJECT'
                              )
                            "
                            [disabled]="busy()"
                          >
                            Exclude from shortlist
                          </button>
                        </div>
                        @for (decision of snapshot.human_decisions; track decision.id) {
                          @if (decision.canonical_supplier_id === supplier.canonical_supplier_id) {
                            <p class="callout" role="status">
                              HUMAN decision: {{ decision.decision }} · {{ decision.created_at }}
                            </p>
                          }
                        }
                      </article>
                    }
                  </div>
                  <section
                    class="comparison-metrics"
                    aria-labelledby="comparison-metrics-title-{{ snapshot.id }}"
                  >
                    <h5 [id]="'comparison-metrics-title-' + snapshot.id">
                      Comparable metrics and differences
                    </h5>
                    @for (metric of snapshot.metrics; track $index + ':' + metric.metric) {
                      <div class="comparison-metric-row">
                        <strong>{{ metric.metric.replaceAll('_', ' ') }}</strong>
                        <div class="comparison-metric-values">
                          @for (
                            supplier of snapshot.suppliers;
                            track $index + ':' + supplier.canonical_supplier_id
                          ) {
                            <span
                              >{{ supplier.supplier }}:
                              {{
                                comparisonMetricValue(metric, supplier.canonical_supplier_id)
                              }}</span
                            >
                          }
                        </div>
                        <span class="metric-state"
                          >{{ metric.state }}{{ metric.reason ? ' · ' + metric.reason : '' }}</span
                        >
                        <span>Delta: {{ metric.delta || 'UNKNOWN' }}</span>
                      </div>
                    }
                  </section>
                  @if (
                    snapshot.unknowns.length ||
                    snapshot.blockers.length ||
                    snapshot.contradictions.length
                  ) {
                    <div class="status-note">
                      <strong>Comparison limitations remain explicit.</strong>
                      @if (snapshot.unknowns.length) {
                        <p>Unknowns: {{ snapshot.unknowns.join('; ') }}</p>
                      }
                      @if (snapshot.blockers.length) {
                        <p>Blockers: {{ snapshot.blockers.join('; ') }}</p>
                      }
                      @if (snapshot.contradictions.length) {
                        <p>Contradictions: {{ snapshot.contradictions | json }}</p>
                      }
                    </div>
                  }
                  <p class="hint">{{ snapshot.notes }}</p>
                </article>
              }
            </section>
          }
          @if (assessmentId) {
            <section
              class="procurement-readiness-panel"
              aria-labelledby="procurement-readiness-title"
            >
              <p class="eyebrow">EVIDENCE-BACKED PROCUREMENT READINESS</p>
              <h3 id="procurement-readiness-title">
                Supplier due diligence and procurement readiness
              </h3>
              <p>
                Review one HUMAN-shortlisted supplier against canonical identity, contact,
                due-diligence, quote, economics, capital, compliance, and product evidence. This is
                a read-only assessment; it never verifies a supplier, accepts an offer, authorizes
                purchase, or sends a message.
              </p>
              @if (!procurementReadiness().length) {
                <p class="status-note" role="status">
                  Create a readiness assessment after recording a HUMAN shortlist decision in the
                  comparison above.
                </p>
              }
              @for (snapshot of comparisonSnapshots(); track snapshot.id) {
                @for (
                  supplier of snapshot.suppliers;
                  track $index + ':' + supplier.canonical_supplier_id
                ) {
                  @if (
                    humanShortlistDecision(snapshot, supplier.canonical_supplier_id);
                    as decision
                  ) {
                    <button
                      type="button"
                      (click)="createProcurementReadiness(snapshot, supplier, decision.id)"
                      [disabled]="busy()"
                    >
                      Run readiness assessment for {{ supplier.supplier }}
                    </button>
                  }
                }
              }
              @for (assessment of procurementReadiness(); track assessment.id) {
                <article
                  class="procurement-readiness-card"
                  [attr.aria-labelledby]="'procurement-' + assessment.id"
                >
                  <div class="supplier-response-heading">
                    <h4 [id]="'procurement-' + assessment.id">
                      {{ procurementSupplierName(assessment) }} · assessment v{{
                        assessment.snapshot_version
                      }}
                    </h4>
                    <span class="evidence-badge">{{ assessment.status }}</span>
                  </div>
                  <p class="hint">
                    Created {{ assessment.created_at }} · policy {{ assessment.policy_version }} ·
                    fingerprint {{ assessment.input_fingerprint }}
                  </p>
                  <p>{{ assessment.notes }}</p>
                  <div class="procurement-dimension-grid">
                    @for (
                      entry of dimensionEntries(assessment.dimensions);
                      track $index + ':' + entry[0]
                    ) {
                      <section
                        class="procurement-dimension"
                        [attr.aria-labelledby]="'dimension-' + assessment.id + '-' + entry[0]"
                      >
                        <h5 [id]="'dimension-' + assessment.id + '-' + entry[0]">
                          {{ entry[0].replaceAll('_', ' ') }}
                        </h5>
                        <p>
                          <strong>{{ entry[1].status }}</strong> · {{ entry[1].provenance }} ·
                          freshness {{ entry[1].freshness }}
                        </p>
                        @if (entry[1].missing_information.length) {
                          <p class="warning-note">
                            Unknown or missing: {{ entry[1].missing_information.join('; ') }}
                          </p>
                        }
                        @if (entry[1].blockers.length) {
                          <p class="warning-note">Blocking: {{ entry[1].blockers.join('; ') }}</p>
                        }
                        @if (entry[1].contradictions.length) {
                          <p class="warning-note">
                            Contradictions: {{ entry[1].contradictions | json }}
                          </p>
                        }
                        <p class="hint">Safe next action: {{ entry[1].safe_next_action }}</p>
                      </section>
                    }
                  </div>
                  <p class="hint">
                    <strong>Unknowns:</strong>
                    {{
                      assessment.unknowns.length ? (assessment.unknowns | json) : 'None recorded'
                    }}
                  </p>
                  <p class="hint">
                    <strong>Evidence lineage:</strong> {{ assessment.evidence_lineage | json }}
                  </p>
                  @if (assessment.acknowledgements.length) {
                    @for (ack of assessment.acknowledgements; track ack.id) {
                      <p class="callout" role="status">
                        HUMAN acknowledgement: {{ ack.decision }} · {{ ack.created_at }} · purchase
                        authorization: NO
                      </p>
                    }
                  } @else {
                    <div
                      class="decision-actions"
                      aria-label="Human procurement-readiness acknowledgement"
                    >
                      <button
                        type="button"
                        (click)="acknowledgeProcurementReadiness(assessment, 'REVIEWED')"
                        [disabled]="busy()"
                      >
                        Acknowledge review
                      </button>
                      <button
                        type="button"
                        class="secondary-action"
                        (click)="
                          acknowledgeProcurementReadiness(assessment, 'NEEDS_FURTHER_EVIDENCE')
                        "
                        [disabled]="busy()"
                      >
                        Request further evidence
                      </button>
                      <button
                        type="button"
                        class="secondary-action"
                        (click)="acknowledgeProcurementReadiness(assessment, 'KEEP_UNDER_REVIEW')"
                        [disabled]="busy()"
                      >
                        Keep under review
                      </button>
                    </div>
                  }
                </article>
              }
            </section>
          }
          @if (assessmentId && reviewedPromotions().length) {
            <section class="reassessment-panel" aria-labelledby="start-reassessment-title">
              <h3 id="start-reassessment-title">Reassess from reviewed supplier evidence</h3>
              <p class="hint">
                Choose a promoted quote to create an immutable reassessment. Missing freight,
                currency, or selling inputs stay blocked until you explicitly provide them.
              </p>
              @for (response of reviewedPromotions(); track response.id) {
                @if (response.promotion; as promotion) {
                  <button
                    type="button"
                    (click)="createCommercialReassessment(promotion.id)"
                    [disabled]="busy()"
                  >
                    Reassess reviewed supplier quote
                  </button>
                }
              }
            </section>
          }
          @if (brief.decision_evidence; as readiness) {
            <section class="decision-readiness-panel" aria-labelledby="decision-readiness-title">
              <h3 id="decision-readiness-title">Decision readiness</h3>
              <p>
                <strong>Target:</strong> {{ readiness.decision_target }} · <strong>State:</strong>
                {{ readiness.readiness_state }}
              </p>
              @if (readiness.blockers.length) {
                <h4>Blocking evidence</h4>
                <ul>
                  @for (item of readiness.blockers; track $index + ':' + item.code) {
                    <li>{{ item.message }}</li>
                  }
                </ul>
              }
              @if (readiness.warnings.length) {
                <h4>Warnings</h4>
                <ul>
                  @for (item of readiness.warnings; track $index + ':' + item.code) {
                    <li>{{ item.message }}</li>
                  }
                </ul>
              }
              @if (readiness.unknowns.length) {
                <h4>Unknowns</h4>
                <ul>
                  @for (item of readiness.unknowns; track $index + ':' + item.code) {
                    <li>{{ item.message }}</li>
                  }
                </ul>
              }
              <p class="hint">
                <strong>Next evidence step:</strong>
                {{ readiness.safe_next_action.label || 'Review evidence' }}.
                {{ readiness.safe_next_action.reason || '' }}
              </p>
              <p class="hint">
                This is evidence readiness only; it is not a recommendation or approval.
              </p>
            </section>
          }
          @if (brief.decision_synthesis; as synthesis) {
            <section class="decision-synthesis-panel" aria-labelledby="decision-synthesis-title">
              <h3 id="decision-synthesis-title">Explainable decision synthesis</h3>
              <p class="synthesis-posture" role="status">
                <strong>Posture:</strong> {{ synthesis.posture }} · <strong>Readiness:</strong>
                {{ synthesis.readiness_state }}
              </p>
              <p>{{ synthesis.explanation }}</p>
              <p>
                <strong>Why:</strong>
                {{
                  synthesis.primary_reason.explanation || 'Review the canonical evidence record.'
                }}
              </p>
              @if (synthesis.supporting_evidence.length) {
                <h4>What supports this state</h4>
                <ul>
                  @for (item of synthesis.supporting_evidence; track $index + ':' + item.code) {
                    <li>{{ item.code }}{{ item.state ? ': ' + item.state : '' }}</li>
                  }
                </ul>
              }
              @if (synthesis.blockers.length || synthesis.contradictions.length) {
                <h4>What prevents stronger progression</h4>
                <ul>
                  @for (item of synthesis.blockers; track $index + ':' + item.code) {
                    <li>{{ item.code }}: {{ item.message }}</li>
                  }
                  @for (item of synthesis.contradictions; track $index + ':' + item.code) {
                    <li>{{ item.code }}: {{ item.message }}</li>
                  }
                </ul>
              }
              @if (synthesis.warnings.length || synthesis.unknowns.length) {
                <h4>Warnings and unknowns</h4>
                <ul>
                  @for (item of synthesis.warnings; track $index + ':' + item.code) {
                    <li>{{ item.code }}: {{ item.message }}</li>
                  }
                  @for (item of synthesis.unknowns; track $index + ':' + item.code) {
                    <li>{{ item.code }}: {{ item.message }}</li>
                  }
                </ul>
              }
              <p>
                <strong>Capital fit:</strong> {{ synthesis.capital_fit_state }}.
                <strong>Human review required:</strong>
                {{ synthesis.human_review_required ? 'YES' : 'NO' }}
              </p>
              @if (synthesis.safe_next_actions.length) {
                <h4>Next safe actions</h4>
                <ol>
                  @for (action of synthesis.safe_next_actions; track $index + ':' + action.code) {
                    <li>
                      <strong>{{ action.label }}</strong> — {{ action.reason }}
                      @if (action.depends_on?.length) {
                        <span>(depends on {{ action.depends_on.join(', ') }})</span>
                      }
                    </li>
                  }
                </ol>
              }
              <p class="hint">
                This synthesis is evidence guidance only. It does not recommend a product, approve a
                launch, contact a supplier, or execute an external action.
              </p>
            </section>
          }
          <section class="decision-control-panel" aria-labelledby="controlled-decision-title">
            <h3 id="controlled-decision-title">Controlled recommendation and your decision</h3>
            <p>
              The system assessment is advisory. It never becomes your decision automatically.
              Review the evidence, then choose one explicit action.
            </p>
            @if (brief.recommendation; as recommendation) {
              <p class="synthesis-posture" role="status">
                <strong>System assessment:</strong> {{ recommendation.recommendation_state }} ·
                <strong>Target:</strong> {{ recommendation.decision_target }}
              </p>
              <p>{{ recommendation.explanation }}</p>
              @if (recommendation.supporting_reasons.length) {
                <h4>Evidence supporting progression</h4>
                <ul>
                  @for (item of recommendation.supporting_reasons; track $index + ':' + item.code) {
                    <li>
                      {{ item.code }}:
                      {{ item.explanation || item.message || 'Supported by canonical evidence.' }}
                    </li>
                  }
                </ul>
              }
              @if (recommendation.counter_reasons.length) {
                <h4>Evidence against progression or still unresolved</h4>
                <ul>
                  @for (item of recommendation.counter_reasons; track $index + ':' + item.code) {
                    <li>
                      {{ item.code }}:
                      {{ item.message || item.explanation || 'Review the canonical evidence.' }}
                    </li>
                  }
                </ul>
              }
              @if (recommendation.limitations.length) {
                <h4>Limitations</h4>
                <ul>
                  @for (
                    item of recommendation.limitations;
                    track $index + ':' + (item.code || item.message)
                  ) {
                    <li>{{ item.message || 'Evidence limitation remains.' }}</li>
                  }
                </ul>
              }
              @if (brief.human_decision; as humanDecision) {
                <p class="callout" role="status">
                  <strong>Your decision:</strong> {{ humanDecision.decision }} · HUMAN ·
                  {{ humanDecision.created_at }}
                </p>
              } @else {
                <h4>Your decision</h4>
                <p class="hint">
                  No decision is selected. Choose deliberately; this records history but does not
                  contact suppliers or execute launch.
                </p>
                <div
                  class="decision-actions"
                  role="group"
                  aria-label="Explicit human decision options"
                >
                  <button
                    type="button"
                    (click)="submitDecision('PROCEED')"
                    [disabled]="
                      busy() || recommendation.recommendation_state !== 'SYSTEM_SUPPORTS_PROCEEDING'
                    "
                  >
                    Proceed
                  </button>
                  <button
                    type="button"
                    (click)="submitDecision('KEEP_UNDER_REVIEW')"
                    [disabled]="busy()"
                  >
                    Keep under review
                  </button>
                  <button
                    type="button"
                    (click)="submitDecision('DO_NOT_PROCEED')"
                    [disabled]="busy()"
                  >
                    Do not proceed
                  </button>
                </div>
                @if (recommendation.recommendation_state !== 'SYSTEM_SUPPORTS_PROCEEDING') {
                  <p class="hint">
                    Proceed is unavailable because the canonical synthesis is not
                    recommendation-eligible. You may continue research or record a review/stop
                    decision.
                  </p>
                }
              }
              <p class="hint">
                Human review required. Recommendation and decision are separate records. No supplier
                contact, RFQ, order, payment, or launch is performed.
              </p>
            } @else {
              <p class="hint">No recommendation assessment exists for this synthesis yet.</p>
              <button type="button" (click)="createRecommendationAssessment()" [disabled]="busy()">
                Prepare advisory assessment for review
              </button>
            }
          </section>
          @if (brief.economics.calculation; as cost) {
            <h3>
              {{
                brief.economics.unit_economics?.freshness?.recalculation_required
                  ? 'Historical landed-cost evidence - recalculate before use'
                  : 'Known landed-cost evidence'
              }}
            </h3>
            <dl class="input-list">
              <div>
                <dt>Total modeled cost</dt>
                <dd>{{ cost.total_included_cost }} {{ cost.currency || '' }}</dd>
              </div>
              <div>
                <dt>Per-unit cost</dt>
                <dd>{{ cost.per_unit_cost || 'UNKNOWN' }}</dd>
              </div>
              <div>
                <dt>Calculation status</dt>
                <dd>{{ cost.status }}</dd>
              </div>
            </dl>
          } @else {
            <p class="hint">
              More commercial information is required before landed cost can be calculated.
            </p>
          }
          @if (brief.economics.calculation?.breakdown?.length; as breakdownCount) {
            <section
              class="landed-cost-breakdown"
              aria-labelledby="landed-breakdown-title"
              tabindex="0"
            >
              <h3 id="landed-breakdown-title">Explainable landed-cost breakdown</h3>
              <p class="hint">
                Backend-calculated acquisition cost only. Unknown and excluded items are not treated
                as zero.
              </p>
              <table>
                <caption>
                  Included and excluded landed acquisition components
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Component</th>
                    <th scope="col">Amount</th>
                    <th scope="col">Basis</th>
                    <th scope="col">Evidence state</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                  @for (
                    line of brief.economics.calculation.breakdown;
                    track $index + ':' + line.id
                  ) {
                    <tr>
                      <th scope="row">{{ line.category }}</th>
                      <td>
                        {{ line.converted_amount ?? line.included_amount ?? 'UNKNOWN' }}
                        {{ line.currency || '' }}
                      </td>
                      <td>{{ line.basis || 'UNKNOWN' }}</td>
                      <td>
                        {{ line.provenance
                        }}{{ line.assumption_reason ? ' â€” ' + line.assumption_reason : '' }}
                      </td>
                      <td>
                        {{ line.inclusion_status
                        }}{{ line.exclusion_reason ? ' â€” ' + line.exclusion_reason : '' }}
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </section>
          }
          @if (brief.economics.unit_economics; as unit) {
            <section class="unit-economics-summary" aria-labelledby="unit-economics-title">
              <h3 id="unit-economics-title">Modeled unit economics and capital fit</h3>
              <p class="hint">
                This is a transparent scenario, not a profitability certificate or product
                recommendation. Landed acquisition cost remains separate from future selling costs.
              </p>
              @if (unit.freshness?.recalculation_required) {
                <p class="status-note" role="status">
                  <strong
                    >{{
                      unit.freshness.status === 'STALE'
                        ? 'Stale acquisition inputs'
                        : 'Acquisition inputs need review'
                    }}.</strong
                  >
                  {{ unit.safe_next_action }} Historical results are retained, not current approval.
                </p>
              }
              @if (unit.calculable) {
                <dl class="input-list">
                  <div>
                    <dt>Selling price</dt>
                    <dd>
                      {{ unit.selling_price ?? 'UNKNOWN' }}
                      {{ unit.selling_price_currency || '' }} ({{ unit.selling_price_provenance }})
                    </dd>
                  </div>
                  <div>
                    <dt>Landed cost / unit</dt>
                    <dd>
                      {{ unit.per_unit_landed_cost ?? 'UNKNOWN' }} {{ unit.base_currency || '' }}
                    </dd>
                  </div>
                  <div>
                    <dt>Selling costs / unit</dt>
                    <dd>
                      {{ unit.per_unit_selling_cost ?? 'UNKNOWN' }} {{ unit.base_currency || '' }}
                    </dd>
                  </div>
                  <div>
                    <dt>Modeled total cost / unit</dt>
                    <dd>
                      {{ unit.per_unit_total_cost ?? 'UNKNOWN' }} {{ unit.base_currency || '' }}
                    </dd>
                  </div>
                  <div>
                    <dt>Modeled contribution / unit</dt>
                    <dd>
                      {{ unit.per_unit_contribution ?? 'UNKNOWN' }} {{ unit.base_currency || '' }}
                    </dd>
                  </div>
                  <div>
                    <dt>Contribution margin</dt>
                    <dd>{{ unit.contribution_margin ?? 'UNKNOWN' }}</dd>
                  </div>
                  <div>
                    <dt>Order quantity</dt>
                    <dd>{{ unit.order_economics.order_quantity ?? unit.quantity ?? 'UNKNOWN' }}</dd>
                  </div>
                  <div>
                    <dt>Capital available</dt>
                    <dd>
                      {{ unit.capital_available ?? 'UNKNOWN' }} {{ unit.capital_currency || '' }}
                    </dd>
                  </div>
                  <div>
                    <dt>Capital required</dt>
                    <dd>
                      {{ unit.capital_required ?? 'UNKNOWN' }} {{ unit.capital_currency || '' }}
                    </dd>
                  </div>
                  <div>
                    <dt>Capital headroom</dt>
                    <dd>
                      {{ unit.capital_headroom ?? unit.capital_shortfall ?? 'UNKNOWN' }}
                      {{ unit.capital_currency || '' }} ({{
                        unit.capital_fit_status || 'NEEDS_INPUT'
                      }})
                    </dd>
                  </div>
                </dl>
                <h4>Included selling-cost components</h4>
                <div
                  class="breakdown-scroll"
                  role="region"
                  aria-label="Modeled selling cost components"
                  tabindex="0"
                >
                  <table>
                    <caption>
                      Explicitly modeled selling costs and provenance
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Component</th>
                        <th scope="col">Basis</th>
                        <th scope="col">Amount / unit</th>
                        <th scope="col">State</th>
                        <th scope="col">Provenance</th>
                      </tr>
                    </thead>
                    <tbody>
                      @for (line of unit.selling_cost_components; track $index + ':' + line.key) {
                        <tr>
                          <th scope="row">{{ line.key }}</th>
                          <td>{{ line.basis }}</td>
                          <td>
                            {{ line.per_unit_amount ?? line.amount ?? 'UNKNOWN' }}
                            {{ line.currency || unit.base_currency || '' }}
                          </td>
                          <td>
                            {{ line.inclusion_status
                            }}{{ line.exclusion_reason ? ' — ' + line.exclusion_reason : '' }}
                          </td>
                          <td>{{ line.provenance }}</td>
                        </tr>
                      }
                    </tbody>
                  </table>
                </div>
                <p class="hint">
                  Order economics:
                  {{ unit.order_economics.landed_acquisition_total ?? 'UNKNOWN' }} landed
                  acquisition +
                  {{ unit.order_economics.modeled_selling_cost_total ?? 'UNKNOWN' }} modeled selling
                  costs. {{ unit.order_economics.sales_claim }}.
                </p>
              } @else {
                <p class="status-note">
                  Unit economics is {{ unit.status }}. Required inputs remain unresolved; no value
                  is treated as zero.
                </p>
              }
              @if (unit.unknown_excluded.length) {
                <h4>Unknown or excluded costs</h4>
                <ul>
                  @for (item of unit.unknown_excluded; track $index + ':' + item.key) {
                    <li>{{ item.label || item.key }} — {{ item.reason }}</li>
                  }
                </ul>
              }
              @if (unit.limitations.length) {
                <h4>Limitations</h4>
                <ul>
                  @for (limitation of unit.limitations; track $index + ':' + limitation) {
                    <li>{{ limitation }}</li>
                  }
                </ul>
              }
              @if (unit.safe_next_action) {
                <p class="hint">Next safe action: {{ unit.safe_next_action }}</p>
              }
            </section>
          }
          @if (brief.economics.scenario_comparisons.length) {
            <h3>Scenario comparison (no automatic winner)</h3>
            <div
              class="breakdown-scroll"
              role="region"
              aria-label="Scenario comparison results"
              tabindex="0"
            >
              <table>
                <caption>
                  Authoritative scenario results
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Scenario</th>
                    <th scope="col">Comparability</th>
                    <th scope="col">Scenario total</th>
                    <th scope="col">Per unit</th>
                  </tr>
                </thead>
                <tbody>
                  @for (
                    row of brief.economics.scenario_comparisons;
                    track $index + ':' + row.scenario_name
                  ) {
                    <tr>
                      <th scope="row">{{ row.scenario_name }}</th>
                      <td>{{ row.comparability }}</td>
                      <td>{{ row.scenario.total || 'UNKNOWN' }}</td>
                      <td>{{ row.scenario.per_unit || 'UNKNOWN' }}</td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          } @else {
            <p class="hint">The current sourcing options cannot yet be compared reliably.</p>
          }
          @if (brief.data_gaps.length) {
            <h3>What still needs review</h3>
            <ul>
              @for (gap of brief.data_gaps; track $index + ':' + gap.message) {
                <li>{{ gap.message }}</li>
              }
            </ul>
          }
          <div class="decision-actions" role="group" aria-label="Human decision options">
            @for (action of brief.next_options; track $index + ':' + action) {
              <button
                type="button"
                (click)="submitDecision(action)"
                [disabled]="busy() || !decisionActionAvailable(action)"
                [attr.title]="
                  decisionActionAvailable(action)
                    ? null
                    : 'Complete the evidence-backed decision brief first.'
                "
              >
                {{ action.replaceAll('_', ' ') }}
              </button>
            }
          </div>
          @if (
            brief.next_options.includes('PROCEED_TO_LAUNCH_PREPARATION') &&
            !decisionActionAvailable('PROCEED_TO_LAUNCH_PREPARATION')
          ) {
            <p class="hint" role="status">
              Launch preparation is unavailable until the canonical brief is ready for a HUMAN
              decision. Review the blocking evidence above first.
            </p>
          }
        }
      </section>
      <section class="panel" aria-labelledby="context-title">
        <h2 id="context-title">Sourcing context</h2>
        <p>
          Currency, quantity, geography, and ownership remain explicit. No currency conversion is
          performed.
        </p>
        <p>UNKNOWN is unavailable; it is never displayed as zero.</p>
        <form (submit)="$event.preventDefault(); createContext()" class="form-grid">
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
            Status: <strong>{{ calculation()?.status }}</strong> - Version
            {{ calculation()?.calculation_version }} - Snapshot {{ snapshot()?.version }}
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
            <div
              class="breakdown-scroll"
              role="region"
              aria-label="Supplier comparison results"
              tabindex="0"
            >
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
                  @for (line of calculation()?.breakdown; track $index + ':' + line.id) {
                    <tr>
                      <th scope="row">{{ line.category }}</th>
                      <td>{{ line.inclusion_status }}</td>
                      <td>
                        {{ line.included_amount ?? line.original_amount ?? 'UNKNOWN' }}
                        {{ line.currency || '' }}
                      </td>
                      <td>{{ line.basis || 'UNKNOWN' }}</td>
                      <td>{{ line.provenance }} - {{ line.freshness }}</td>
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
              @for (item of calculation()?.missing_inputs; track $index + ':' + item) {
                <li>{{ item }}</li>
              }
            </ul>
          }
          @if ((calculation()?.warnings?.length ?? 0) > 0) {
            <h3>Warnings</h3>
            <ul>
              @for (warning of calculation()?.warnings; track $index + ':' + warning) {
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
              @for (point of run.points; track $index + ':' + point.value) {
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
    </section>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .economics-page {
        max-width: 1100px;
        width: 100%;
        min-width: 0;
        margin: 0 auto;
        padding: 2rem;
        box-sizing: border-box;
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
        min-width: 0;
        box-sizing: border-box;
        overflow-wrap: anywhere;
      }
      .form-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
        gap: 1rem;
        align-items: end;
      }
      .form-grid > * {
        min-width: 0;
      }
      label {
        display: grid;
        gap: 0.35rem;
        font-weight: 600;
      }
      input,
      textarea,
      button {
        min-height: 2.75rem;
        padding: 0.5rem 0.7rem;
        border-radius: 0.45rem;
        border: 1px solid #78909c;
        font: inherit;
        box-sizing: border-box;
      }
      input,
      textarea {
        width: 100%;
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
        container-type: inline-size;
      }
      .landed-cost-breakdown {
        overflow-x: auto;
        container-type: inline-size;
      }
      .breakdown-scroll:focus-visible,
      .landed-cost-breakdown:focus-visible {
        outline: 3px solid var(--vj-color-brand);
        outline-offset: 3px;
      }
      .unit-economics-summary {
        margin-top: 1.5rem;
        padding-top: 1rem;
        border-top: 1px solid #d6e0e5;
      }
      .unit-economics-summary h4 {
        margin-top: 1.25rem;
      }
      .status-note {
        border-left: 4px solid #ca8a04;
        background: #fffbeb;
        padding: 1rem;
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
        inline-size: 100cqi;
        white-space: normal;
        overflow-wrap: anywhere;
        position: sticky;
        inset-inline-start: 0;
        text-align: left;
        font-weight: 700;
        padding: 0.65rem 0;
      }
      .brief-summary {
        border-left: 4px solid #0f766e;
        padding: 1rem;
        background: #f0fdfa;
      }
      .decision-readiness-panel {
        border: 1px solid #b8d5d8;
        border-left: 4px solid #0f766e;
        border-radius: 0.75rem;
        padding: 1rem;
        margin: 1rem 0;
        background: #f6fbfb;
      }
      .decision-readiness-panel ul {
        margin: 0.5rem 0 1rem;
        padding-left: 1.25rem;
      }
      .decision-synthesis-panel {
        border: 1px solid #b8d5d8;
        border-left: 4px solid #155e75;
        border-radius: 0.75rem;
        padding: 1rem;
        margin: 1rem 0;
        background: #f0f9fa;
      }
      .decision-synthesis-panel ul,
      .decision-synthesis-panel ol {
        margin: 0.5rem 0 1rem;
        padding-left: 1.25rem;
      }
      .synthesis-posture {
        font-size: 1.05rem;
      }
      .decision-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        margin-top: 1rem;
      }
      .decision-control-panel {
        border: 2px solid #0d7280;
        border-radius: 0.75rem;
        padding: 1rem;
        margin-top: 1rem;
        background: #f4fbfb;
      }
      .decision-control-panel .decision-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        margin-top: 0.75rem;
      }
      .engagement-panel {
        border: 2px solid #0f766e;
        border-radius: 0.75rem;
        padding: 1rem;
        margin: 1rem 0;
        background: #f0fdfa;
      }
      .engagement-facts {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
        gap: 0.75rem;
        margin: 1rem 0;
      }
      .engagement-facts div {
        border: 1px solid #b8d5d8;
        border-radius: 0.5rem;
        padding: 0.7rem;
        background: #fff;
      }
      .engagement-message {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        padding: 0.8rem;
        border: 1px solid #b8d5d8;
        border-radius: 0.5rem;
        background: #fff;
        font: inherit;
      }
      .supplier-response-panel,
      .supplier-response-empty {
        border: 2px solid #0f766e;
        border-radius: 0.75rem;
        padding: 1rem;
        margin: 1rem 0;
        background: #f0fdfa;
      }
      .supplier-response-empty {
        border-width: 1px;
        background: #f8fafc;
      }
      .supplier-response-card {
        border: 1px solid #b8d5d8;
        border-radius: 0.65rem;
        padding: 1rem;
        margin-top: 1rem;
        background: #fff;
      }
      .supplier-response-heading {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: baseline;
      }
      .supplier-response-heading h4 {
        margin: 0;
      }
      .evidence-badge {
        border: 1px solid #0f766e;
        border-radius: 999px;
        padding: 0.2rem 0.55rem;
        color: #0f766e;
        font-size: 0.8rem;
        font-weight: 700;
        white-space: nowrap;
      }
      .supplier-raw-response {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        max-height: 18rem;
        overflow: auto;
        padding: 0.8rem;
        border: 1px solid #d6e0e5;
        border-radius: 0.5rem;
        background: #f8fafc;
        font: inherit;
      }
      .supplier-claim-list {
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      }
      .claim-state {
        display: inline-block;
        margin-left: 0.25rem;
        color: #0f766e;
        font-size: 0.78rem;
        font-weight: 700;
      }
      .correction-editor {
        display: grid;
        gap: 0.35rem;
        margin-top: 1rem;
      }
      .correction-editor textarea {
        width: 100%;
        box-sizing: border-box;
        font: inherit;
        resize: vertical;
      }
      .warning-note {
        border-left: 4px solid #ca8a04;
        padding: 0.75rem;
        background: #fffbeb;
        overflow-wrap: anywhere;
      }
      .callout {
        border-left: 4px solid #0f766e;
        padding: 0.75rem;
        background: #f0fdfa;
      }
      .reassessment-panel {
        border: 1px solid #cbd5e1;
        border-radius: 0.65rem;
        padding: 1rem;
        margin-top: 1rem;
        background: #f8fafc;
      }
      .reassessment-card {
        border-top: 1px solid #d6e0e5;
        padding-top: 0.8rem;
        margin-top: 0.8rem;
      }
      .reassessment-metrics {
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      }
      .comparison-panel {
        border: 2px solid #0f766e;
        border-radius: 0.75rem;
        padding: 1rem;
        margin: 1rem 0;
        background: #f0fdfa;
      }
      .comparison-snapshot {
        margin-top: 1rem;
        padding: 1rem;
        border: 1px solid #b8d5d8;
        border-radius: 0.65rem;
        background: #fff;
      }
      .supplier-comparison-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 1rem;
        margin-top: 1rem;
      }
      .supplier-comparison-card {
        border: 1px solid #b8d5d8;
        border-radius: 0.6rem;
        padding: 0.9rem;
        background: #f8fafc;
      }
      .supplier-comparison-card h5,
      .comparison-metrics h5 {
        margin-top: 0;
        font-size: 1.05rem;
      }
      .comparison-metrics {
        margin-top: 1rem;
        border-top: 1px solid #d6e0e5;
        padding-top: 1rem;
      }
      .procurement-readiness-panel {
        border: 2px solid #0f766e;
        border-radius: 0.75rem;
        padding: 1rem;
        margin: 1rem 0;
        background: #ecfeff;
      }
      .procurement-readiness-card {
        margin-top: 1rem;
        padding: 1rem;
        border: 1px solid #b8d5d8;
        border-radius: 0.65rem;
        background: #fff;
      }
      .procurement-dimension-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
        gap: 0.75rem;
        margin: 1rem 0;
      }
      .procurement-dimension {
        border: 1px solid #d6e0e5;
        border-radius: 0.55rem;
        padding: 0.75rem;
        background: #f8fafc;
      }
      .procurement-dimension h5 {
        margin: 0 0 0.35rem;
        text-transform: capitalize;
      }
      .comparison-metric-row {
        display: grid;
        grid-template-columns: minmax(150px, 0.8fr) minmax(260px, 2fr) minmax(180px, 1fr) minmax(
            120px,
            0.6fr
          );
        gap: 0.75rem;
        align-items: start;
        padding: 0.75rem 0;
        border-top: 1px solid #e2e8f0;
      }
      .comparison-metric-values {
        display: grid;
        gap: 0.25rem;
      }
      .metric-state {
        font-weight: 700;
        color: #0f766e;
      }
      .secondary-action {
        background: #475569;
      }
      .live-certification-panel {
        border-left: 4px solid #0f766e;
      }
      .live-policy-status {
        display: grid;
        gap: 0.25rem;
        margin: 0.75rem 0;
        padding: 0.7rem 0.85rem;
        border: 1px solid #b8d9dd;
        border-radius: 0.5rem;
        background: #effafa;
        color: #164e63;
      }
      .live-policy-status span {
        overflow-wrap: anywhere;
      }
      .live-certification-list {
        display: grid;
        gap: 0.75rem;
        margin-top: 1rem;
      }
      .live-certification-card {
        border: 1px solid #cbd5e1;
        border-radius: 0.5rem;
        padding: 0.85rem;
        background: #f8fafc;
      }
      .live-certification-card span {
        overflow-wrap: anywhere;
      }
      .live-certification-card pre {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }
      @media (max-width: 600px) {
        .economics-page {
          padding: 1rem 0.75rem;
        }
        .panel {
          padding: 1rem;
          border-radius: 0.75rem;
        }
        .page-header {
          display: block;
        }
        .supplier-response-heading {
          display: block;
        }
        .comparison-metric-row {
          grid-template-columns: 1fr;
        }
        .decision-actions button,
        .form-grid > button {
          width: 100%;
        }
      }
    `,
  ],
})
export class SourcingEconomicsWorkspaceComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly journey = inject(CommerceJourneyService, { optional: true });
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
  readonly decisionBrief = signal<DecisionBriefView | null>(null);
  readonly supplierResponses = signal<SupplierResponseView[]>([]);
  readonly reassessments = signal<CommercialReassessmentView[]>([]);
  readonly comparisonSnapshots = signal<SupplierComparisonView[]>([]);
  readonly procurementReadiness = signal<ProcurementReadinessView[]>([]);
  readonly liveApprovals = signal<LiveSupplierApprovalView[]>([]);
  readonly liveAuthorizations = signal<LiveSupplierExecutionAuthorizationView[]>([]);
  readonly livePolicy = signal<LiveSupplierPolicyView | null>(null);
  readonly liveRuns = signal<LiveSupplierCertificationView[]>([]);
  readonly liveCertificationError = signal('');
  readonly supplierResponsesLoading = signal(false);
  private readonly route = inject(ActivatedRoute);
  opportunityId = '';
  assessmentId = '';
  journeyId = '';
  journeyProductName = '';
  decisionNote = '';
  correctionDrafts: Record<string, string> = {};
  liveSourceUrl = '';
  liveSourcePurpose = 'Bounded read-only supplier evidence certification';
  liveSourceCategory = 'supplier_website';

  ngOnInit(): void {
    this.opportunityId = this.route.snapshot.queryParamMap.get('opportunity_id') || '';
    this.journeyId = this.route.snapshot.queryParamMap.get('journey_id') || '';
    void this.loadJourneyContext();
  }

  private async loadJourneyContext(): Promise<void> {
    if (this.journey) {
      try {
        const active = await this.journey.active();
        const values = active?.context.values || {};
        if (!this.opportunityId && typeof values['selected_product_opportunity_id'] === 'string') {
          this.opportunityId = values['selected_product_opportunity_id'];
        }
        if (!this.journeyId && active?.id) this.journeyId = active.id;
        if (typeof values['product_name'] === 'string')
          this.journeyProductName = values['product_name'];
      } catch {
        // Advanced/manual identifiers remain available when the journey is unavailable.
      }
    }
    void this.loadLiveSupplierCertification();
    if (this.opportunityId) void this.loadDecisionBrief();
  }

  retryLoad(): void {
    void this.loadLiveSupplierCertification();
    if (this.opportunityId.trim()) {
      void this.loadDecisionBrief();
    }
  }

  private async loadLiveSupplierCertification(): Promise<void> {
    try {
      const [policy, approvals, authorizations, runs] = await Promise.all([
        firstValueFrom(
          this.http.get<LiveSupplierPolicyView>(
            `${environment.apiUrl}/intelligence/live-supplier-certification/policy`,
          ),
        ),
        firstValueFrom(
          this.http.get<LiveSupplierApprovalView[]>(
            `${environment.apiUrl}/intelligence/live-supplier-certification/approvals`,
          ),
        ),
        firstValueFrom(
          this.http.get<LiveSupplierExecutionAuthorizationView[]>(
            `${environment.apiUrl}/intelligence/live-supplier-certification/authorizations`,
          ),
        ),
        firstValueFrom(
          this.http.get<LiveSupplierCertificationView[]>(
            `${environment.apiUrl}/intelligence/live-supplier-certification/runs`,
          ),
        ),
      ]);
      this.livePolicy.set(policy);
      this.liveApprovals.set(
        approvals.filter(
          (item) => !item.opportunity_id || item.opportunity_id === this.opportunityId,
        ),
      );
      this.liveAuthorizations.set(
        authorizations.filter(
          (item) => !item.opportunity_id || item.opportunity_id === this.opportunityId,
        ),
      );
      this.liveRuns.set(
        runs.filter((item) => !item.opportunity_id || item.opportunity_id === this.opportunityId),
      );
    } catch {
      this.livePolicy.set(null);
      this.liveApprovals.set([]);
      this.liveAuthorizations.set([]);
      this.liveRuns.set([]);
    }
  }

  async approveLiveSource(): Promise<void> {
    if (!this.opportunityId.trim() || !this.liveSourceUrl.trim()) return;
    this.busy.set(true);
    this.liveCertificationError.set('');
    try {
      await firstValueFrom(
        this.http.post<LiveSupplierApprovalView>(
          `${environment.apiUrl}/intelligence/live-supplier-certification/approvals`,
          {
            opportunity_id: this.opportunityId.trim(),
            source_url: this.liveSourceUrl.trim(),
            candidate_category: this.liveSourceCategory,
            purpose: this.liveSourcePurpose.trim(),
            actor_provenance: 'HUMAN',
          },
        ),
      );
      await this.loadLiveSupplierCertification();
    } catch {
      this.liveCertificationError.set(
        'Approval could not be created. Admit the domain through External Research first, then retry with the exact HTTPS path.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async runLiveCertification(approval: LiveSupplierApprovalView, refresh = false): Promise<void> {
    this.busy.set(true);
    this.liveCertificationError.set('');
    try {
      await firstValueFrom(
        this.http.post<LiveSupplierCertificationView>(
          `${environment.apiUrl}/intelligence/live-supplier-certification/runs`,
          {
            approval_id: approval.id,
            opportunity_id: this.opportunityId.trim(),
            source_url: approval.source_url,
            refresh,
            ...(refresh ? { idempotency_key: `ui-refresh-${Date.now()}` } : {}),
          },
        ),
      );
      await this.loadLiveSupplierCertification();
    } catch {
      this.liveCertificationError.set(
        'Certification was blocked safely. Review the run history for the exact policy, scope, or provider blocker.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async authorizeLiveExecution(approval: LiveSupplierApprovalView): Promise<void> {
    this.busy.set(true);
    this.liveCertificationError.set('');
    try {
      await firstValueFrom(
        this.http.post<LiveSupplierExecutionAuthorizationView>(
          `${environment.apiUrl}/intelligence/live-supplier-certification/authorizations`,
          {
            approval_id: approval.id,
            opportunity_id: this.opportunityId.trim(),
            source_url: approval.source_url,
            actor_provenance: 'HUMAN',
            idempotency_key: `ui-auth-${approval.id}`,
          },
        ),
      );
      await this.loadLiveSupplierCertification();
    } catch {
      this.liveCertificationError.set(
        'Execution authorization was not created. Check provider readiness and the exact approved URL scope.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async executeLiveAuthorization(
    authorization: LiveSupplierExecutionAuthorizationView,
  ): Promise<void> {
    this.busy.set(true);
    this.liveCertificationError.set('');
    try {
      await firstValueFrom(
        this.http.post<LiveSupplierCertificationView>(
          `${environment.apiUrl}/intelligence/live-supplier-certification/authorizations/${authorization.id}/execute`,
          {
            actor_provenance: 'HUMAN',
            idempotency_key: `ui-run-${authorization.id}`,
          },
        ),
      );
      await this.loadLiveSupplierCertification();
    } catch {
      this.liveCertificationError.set(
        'The authorized read was blocked safely. No supplier contact or write occurred; review the exact blocker in history.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async revokeLiveAuthorization(
    authorization: LiveSupplierExecutionAuthorizationView,
  ): Promise<void> {
    this.busy.set(true);
    try {
      await firstValueFrom(
        this.http.post(
          `${environment.apiUrl}/intelligence/live-supplier-certification/authorizations/${authorization.id}/revoke`,
          { reason: 'Revoked by HUMAN reviewer', actor_provenance: 'HUMAN' },
        ),
      );
      await this.loadLiveSupplierCertification();
    } catch {
      this.liveCertificationError.set('Execution authorization could not be revoked.');
    } finally {
      this.busy.set(false);
    }
  }

  async reviewLiveEvidence(
    run: LiveSupplierCertificationView,
    action: 'ACCEPT' | 'CONTRADICTION',
  ): Promise<void> {
    const execution = run.execution;
    if (!execution?.id) return;
    this.busy.set(true);
    try {
      await firstValueFrom(
        this.http.post(
          `${environment.apiUrl}/intelligence/live-supplier-certification/executions/${execution.id}/evidence-review`,
          {
            action,
            rationale:
              action === 'ACCEPT'
                ? 'Reviewed by HUMAN in the sourcing workspace.'
                : 'Contradiction recorded by HUMAN reviewer.',
            evidence_hash: execution.content_hash || '',
            evidence_version: 1,
            actor_provenance: 'HUMAN',
          },
        ),
      );
      await this.loadLiveSupplierCertification();
    } catch {
      this.liveCertificationError.set(
        'Evidence review was not recorded. The snapshot may be stale.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async revokeLiveApproval(approval: LiveSupplierApprovalView): Promise<void> {
    this.busy.set(true);
    try {
      await firstValueFrom(
        this.http.post(
          `${environment.apiUrl}/intelligence/live-supplier-certification/approvals/${approval.id}/revoke`,
          { reason: 'Revoked by HUMAN reviewer', actor_provenance: 'HUMAN' },
        ),
      );
      await this.loadLiveSupplierCertification();
    } catch {
      this.liveCertificationError.set('Approval could not be revoked.');
    } finally {
      this.busy.set(false);
    }
  }

  async loadDecisionBrief(): Promise<void> {
    if (!this.opportunityId.trim()) return;
    this.busy.set(true);
    this.error.set('');
    try {
      const briefUrl = this.journeyId.trim()
        ? `${environment.apiUrl}/commerce-journeys/${this.journeyId.trim()}/decision-brief?opportunity_id=${encodeURIComponent(this.opportunityId.trim())}`
        : `${environment.apiUrl}/intelligence/product-opportunities/${this.opportunityId.trim()}/decision-brief`;
      this.decisionBrief.set(await firstValueFrom(this.http.get<DecisionBriefView>(briefUrl)));
      await this.loadSupplierResponses();
      await this.loadReassessmentContext();
    } catch {
      this.error.set(
        'The decision brief is unavailable. Complete supplier verification and economics first.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  private async loadReassessmentContext(): Promise<void> {
    if (!this.opportunityId.trim()) return;
    try {
      const scope = await firstValueFrom(
        this.http.get<OpportunityScopeView>(
          `${environment.apiUrl}/intelligence/product-opportunities/${this.opportunityId.trim()}`,
        ),
      );
      this.assessmentId = scope.current_assessment_id || '';
      if (!this.assessmentId) {
        this.reassessments.set([]);
        this.comparisonSnapshots.set([]);
        return;
      }
      this.reassessments.set(
        await firstValueFrom(
          this.http.get<CommercialReassessmentView[]>(
            `${environment.apiUrl}/intelligence/product-opportunities/${this.opportunityId.trim()}/assessments/${this.assessmentId}/commercial-reassessments`,
          ),
        ),
      );
      this.comparisonSnapshots.set(
        await firstValueFrom(
          this.http.get<SupplierComparisonView[]>(
            `${environment.apiUrl}/intelligence/product-opportunities/${this.opportunityId.trim()}/assessments/${this.assessmentId}/supplier-comparisons`,
          ),
        ),
      );
      await this.loadProcurementReadiness();
    } catch {
      this.assessmentId = '';
      this.reassessments.set([]);
      this.comparisonSnapshots.set([]);
      this.procurementReadiness.set([]);
    }
  }

  private async loadProcurementReadiness(): Promise<void> {
    if (!this.opportunityId.trim() || !this.assessmentId) {
      this.procurementReadiness.set([]);
      return;
    }
    try {
      this.procurementReadiness.set(
        await firstValueFrom(
          this.http.get<ProcurementReadinessView[]>(
            `${environment.apiUrl}/intelligence/product-opportunities/${this.opportunityId.trim()}/assessments/${this.assessmentId}/procurement-readiness`,
          ),
        ),
      );
    } catch {
      // Older environments may not have the PR-8C migration yet; retain the
      // existing workspace and let the API error surface when the user runs it.
      this.procurementReadiness.set([]);
    }
  }

  humanShortlistDecision(
    snapshot: SupplierComparisonView,
    canonicalSupplierId: string,
  ): { id: string; decision: string } | null {
    const decision = snapshot.human_decisions.find(
      (item) => item.canonical_supplier_id === canonicalSupplierId && item.decision !== 'REJECT',
    );
    return decision ? { id: decision.id, decision: decision.decision } : null;
  }

  dimensionEntries(
    dimensions: Record<string, ProcurementReadinessDimensionView>,
  ): Array<[string, ProcurementReadinessDimensionView]> {
    return Object.entries(dimensions || {});
  }

  procurementSupplierName(assessment: ProcurementReadinessView): string {
    for (const snapshot of this.comparisonSnapshots()) {
      const supplier = snapshot.suppliers.find(
        (item) => item.canonical_supplier_id === assessment.canonical_supplier_id,
      );
      if (supplier) return supplier.supplier;
    }
    return assessment.canonical_supplier_id;
  }

  async createProcurementReadiness(
    snapshot: SupplierComparisonView,
    supplier: SupplierComparisonSupplierView,
    shortlistDecisionId: string,
  ): Promise<void> {
    if (!this.opportunityId.trim() || !this.assessmentId || !snapshot.shortlist_context_id) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post<ProcurementReadinessView>(
          `${environment.apiUrl}/intelligence/product-opportunities/${this.opportunityId.trim()}/assessments/${this.assessmentId}/procurement-readiness`,
          {
            idempotency_key: `pr8c-ui-${snapshot.id}-${supplier.canonical_supplier_id}`,
            canonical_supplier_id: supplier.canonical_supplier_id,
            supplier_product_id: supplier.supplier_product_id,
            shortlist_context_id: snapshot.shortlist_context_id,
            shortlist_decision_id: shortlistDecisionId,
            reassessment_id: supplier.reassessment_id || null,
            comparison_id: snapshot.id,
          },
        ),
      );
      await this.loadProcurementReadiness();
    } catch {
      this.error.set(
        'The procurement-readiness assessment could not be created. Refresh the comparison and review its HUMAN shortlist, quote, and product scope.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async acknowledgeProcurementReadiness(
    assessment: ProcurementReadinessView,
    decision: 'REVIEWED' | 'NEEDS_FURTHER_EVIDENCE' | 'KEEP_UNDER_REVIEW',
  ): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post(
          `${environment.apiUrl}/intelligence/product-opportunities/procurement-readiness/${assessment.id}/acknowledge`,
          {
            idempotency_key: `pr8c-ui-ack-${assessment.id}-${decision}`,
            decision,
            provenance: 'HUMAN',
            reason:
              decision === 'REVIEWED'
                ? 'Owner reviewed the evidence-backed procurement-readiness assessment.'
                : 'Owner recorded that further evidence or review is required.',
          },
        ),
      );
      await this.loadProcurementReadiness();
    } catch {
      this.error.set(
        'The acknowledgement was not recorded. The assessment may be stale; refresh and create a new readiness snapshot if evidence changed.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  reviewedPromotions(): SupplierResponseView[] {
    return this.supplierResponses().filter((response) => response.promotion?.status === 'PROMOTED');
  }

  metricEntries(
    metrics: CommercialReassessmentView['comparison']['metrics'],
  ): Array<[string, { baseline: unknown; reassessment: unknown; delta: unknown; state: string }]> {
    return Object.entries(metrics || {});
  }

  comparisonCandidateIds(): string[] {
    const bySupplier = new Map<string, CommercialReassessmentView>();
    for (const item of this.reassessments()) {
      if (!bySupplier.has(item.supplier_id)) bySupplier.set(item.supplier_id, item);
    }
    return Array.from(bySupplier.values())
      .sort((left, right) => left.supplier_id.localeCompare(right.supplier_id))
      .map((item) => item.id);
  }

  comparisonMetricValue(metric: SupplierComparisonMetricView, supplierId: string): string {
    const value = metric.values.find((item) => item.canonical_supplier_id === supplierId);
    if (!value || value.value === null || value.value === undefined || value.value === '')
      return 'UNKNOWN';
    const amount = this.displayClaim(value.value);
    const basis = [value.currency, value.unit].filter(Boolean).join(' / ');
    return basis ? `${amount} (${basis})` : amount;
  }

  async createSupplierComparison(): Promise<void> {
    if (!this.opportunityId.trim() || !this.assessmentId) return;
    const reassessmentIds = this.comparisonCandidateIds();
    if (reassessmentIds.length < 2) {
      this.error.set('At least two distinct supplier reassessments are required for comparison.');
      return;
    }
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post<SupplierComparisonView>(
          `${environment.apiUrl}/intelligence/product-opportunities/${this.opportunityId.trim()}/assessments/${this.assessmentId}/supplier-comparisons`,
          {
            idempotency_key: `pr8b-ui-comparison-${reassessmentIds.join('-')}`,
            reassessment_ids: reassessmentIds,
          },
        ),
      );
      await this.loadReassessmentContext();
    } catch {
      this.error.set(
        'The supplier comparison could not be created. Review the supplier reassessments and refresh the evidence.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async shortlistComparisonSupplier(
    snapshot: SupplierComparisonView,
    supplierId: string,
    decision: 'KEEP_UNDER_REVIEW' | 'APPROVE_FOR_SOURCING' | 'REJECT',
  ): Promise<void> {
    if (!this.opportunityId.trim() || !this.assessmentId) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post(
          `${environment.apiUrl}/intelligence/product-opportunities/${this.opportunityId.trim()}/assessments/${this.assessmentId}/supplier-comparisons/${snapshot.id}/shortlist`,
          {
            canonical_supplier_id: supplierId,
            decision,
            reason: `Human reviewed comparison ${snapshot.id} and selected ${decision.replaceAll('_', ' ').toLowerCase()}.`,
            decision_key: `pr8b-ui-decision-${snapshot.id}-${supplierId}-${decision}`,
          },
        ),
      );
      await this.loadReassessmentContext();
    } catch {
      this.error.set(
        'The HUMAN shortlist decision could not be recorded. Refresh the comparison and review whether its evidence is stale.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async createCommercialReassessment(promotionId: string): Promise<void> {
    if (!this.opportunityId.trim() || !this.assessmentId || !promotionId) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post(
          `${environment.apiUrl}/intelligence/product-opportunities/${this.opportunityId.trim()}/assessments/${this.assessmentId}/commercial-reassessments`,
          {
            idempotency_key: `pr8a-ui-${promotionId}`,
            promotion_id: promotionId,
            scenario_key: 'reviewed-quote-reassessment',
          },
        ),
      );
      await this.loadReassessmentContext();
    } catch {
      this.error.set(
        'The commercial reassessment could not be created. Review the selected quote and current assessment scope.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async reviewReassessment(
    item: CommercialReassessmentView,
    decision: 'KEEP_UNDER_REVIEW' | 'ACKNOWLEDGE',
  ): Promise<void> {
    if (!this.opportunityId.trim() || !this.assessmentId) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post(
          `${environment.apiUrl}/intelligence/product-opportunities/${this.opportunityId.trim()}/assessments/${this.assessmentId}/commercial-reassessments/${item.id}/review`,
          { idempotency_key: `pr8a-ui-review-${item.id}`, decision, provenance: 'HUMAN' },
        ),
      );
      await this.loadReassessmentContext();
    } catch {
      this.error.set(
        'The reassessment review could not be recorded. Review the immutable evidence and try again.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  private async loadSupplierResponses(): Promise<void> {
    if (!this.opportunityId.trim()) {
      this.supplierResponses.set([]);
      return;
    }
    this.supplierResponsesLoading.set(true);
    try {
      const result = await firstValueFrom(
        this.http.get<SupplierResponseListView>(
          `${environment.apiUrl}/intelligence/supplier-responses?opportunity_id=${encodeURIComponent(this.opportunityId.trim())}`,
        ),
      );
      this.supplierResponses.set(result.responses || []);
    } catch {
      this.supplierResponses.set([]);
      this.error.set(
        'Supplier response evidence is unavailable. The decision brief remains read-only.',
      );
    } finally {
      this.supplierResponsesLoading.set(false);
    }
  }

  claimEntries(fields: Record<string, unknown>): Array<[string, unknown]> {
    return Object.entries(fields || {});
  }

  displayClaim(value: unknown): string {
    if (value === null || value === undefined || value === '') return 'UNKNOWN';
    if (typeof value === 'string') return value;
    return JSON.stringify(value);
  }

  claimProvenance(extraction: SupplierResponseExtractionView, key: string): string {
    const provenance = extraction.field_provenance?.[key];
    if (typeof provenance === 'object' && provenance !== null && 'provenance' in provenance) {
      const value = (provenance as { provenance?: unknown }).provenance;
      return typeof value === 'string' && value ? value : 'UNKNOWN';
    }
    return 'UNKNOWN';
  }

  latestResponseReview(response: SupplierResponseView): SupplierResponseReviewView | null {
    return response.reviews.length ? response.reviews[response.reviews.length - 1] : null;
  }

  canPromoteSupplierResponse(response: SupplierResponseView): boolean {
    const review = this.latestResponseReview(response);
    return (
      response.classification === 'QUOTE' &&
      response.correlation_state === 'CORRELATED' &&
      !response.promotion &&
      !!response.extraction &&
      !!review &&
      ['ACCEPT_EXTRACTION', 'CORRECT_EXTRACTION'].includes(review.decision)
    );
  }

  async reviewSupplierResponse(
    response: SupplierResponseView,
    decision: 'ACCEPT_EXTRACTION' | 'KEEP_UNDER_REVIEW' | 'REJECT_EXTRACTION',
  ): Promise<void> {
    if (!response.extraction) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post(
          `${environment.apiUrl}/intelligence/supplier-responses/${response.id}/review`,
          {
            decision,
            extraction_id: response.extraction.id,
            reason: `Owner selected ${decision.replaceAll('_', ' ').toLowerCase()} after reviewing the immutable response.`,
            provenance: 'HUMAN',
            idempotency_key: `pr7c-review-${response.id}-${decision}`,
          },
        ),
      );
      await this.loadSupplierResponses();
    } catch {
      this.error.set(
        'The response review could not be recorded. Refresh and review the immutable evidence again.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async correctSupplierResponse(response: SupplierResponseView): Promise<void> {
    if (!response.extraction) return;
    const rawCorrections = this.correctionDrafts[response.id]?.trim() || '';
    if (!rawCorrections) {
      this.error.set(
        'Enter at least one explicit correction as JSON, or choose Accept extracted claims.',
      );
      return;
    }
    let corrections: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(rawCorrections);
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        throw new Error('Corrections must be a JSON object.');
      }
      corrections = parsed as Record<string, unknown>;
    } catch {
      this.error.set('Corrections must be a valid JSON object, for example {"moq": 500}.');
      return;
    }
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post(
          `${environment.apiUrl}/intelligence/supplier-responses/${response.id}/review`,
          {
            decision: 'CORRECT_EXTRACTION',
            extraction_id: response.extraction.id,
            corrections,
            reason: 'Owner corrected explicit supplier-response extraction fields.',
            provenance: 'HUMAN',
            idempotency_key: `pr7c-correct-${response.id}-${response.extraction.id}`,
          },
        ),
      );
      delete this.correctionDrafts[response.id];
      await this.loadSupplierResponses();
    } catch {
      this.error.set(
        'The extraction correction could not be recorded. Review the explicit JSON and try again.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async promoteSupplierResponse(response: SupplierResponseView): Promise<void> {
    if (!this.canPromoteSupplierResponse(response)) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post(
          `${environment.apiUrl}/intelligence/supplier-responses/${response.id}/promote`,
          {},
        ),
      );
      await Promise.all([this.loadSupplierResponses(), this.loadDecisionBrief()]);
    } catch {
      this.error.set(
        'Commercial promotion was not recorded. Verify correlation and the HUMAN review state.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async createRecommendationAssessment(): Promise<void> {
    if (!this.opportunityId.trim()) {
      this.error.set('Select a product opportunity before preparing an assessment.');
      return;
    }
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post(
          `${environment.apiUrl}/intelligence/product-opportunities/${this.opportunityId.trim()}/recommendation-assessment`,
          { decision_target: 'COMMERCIAL_ASSESSMENT' },
        ),
      );
      await this.loadDecisionBrief();
    } catch {
      this.error.set(
        'The advisory assessment could not be prepared. Review the canonical evidence first.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async submitDecision(action: string): Promise<void> {
    if (!this.journeyId.trim() || !this.opportunityId.trim()) {
      this.error.set('A journey ID is required to record a human decision.');
      return;
    }
    if (!this.decisionActionAvailable(action)) {
      this.error.set(
        'Complete the evidence-backed decision brief before proceeding to launch preparation.',
      );
      return;
    }
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post(
          `${environment.apiUrl}/commerce-journeys/${this.journeyId.trim()}/decision`,
          {
            opportunity_id: this.opportunityId.trim(),
            action,
            note: this.decisionNote.trim() || null,
            idempotency_key: this.decisionIdempotencyKey(action),
          },
        ),
      );
      await this.loadDecisionBrief();
    } catch {
      this.error.set('The human decision could not be recorded. Review readiness and try again.');
    } finally {
      this.busy.set(false);
    }
  }

  decisionIdempotencyKey(action: string): string {
    return `pr6c-ui-decision-${this.journeyId.trim()}-${this.opportunityId.trim()}-${action.toUpperCase()}`;
  }

  decisionActionAvailable(action: string): boolean {
    if (action !== 'PROCEED_TO_LAUNCH_PREPARATION') return true;
    return this.decisionBrief()?.decision_readiness === 'READY_FOR_HUMAN_DECISION';
  }

  async approveEngagement(engagementId: string): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post(`${environment.apiUrl}/intelligence/engagements/${engagementId}/approve`, {
          idempotency_key: `pr7a-approve-${engagementId}`,
          reason: 'Explicit owner approval for a future send; no message is sent.',
          provenance: 'HUMAN',
        }),
      );
      await this.loadDecisionBrief();
    } catch {
      this.error.set(
        'The draft could not be approved. Review the current HUMAN decision and draft state.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async cancelEngagement(engagementId: string): Promise<void> {
    if (!globalThis.confirm('Cancel this internal draft? No message will be sent.')) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post(`${environment.apiUrl}/intelligence/engagements/${engagementId}/cancel`, {
          idempotency_key: `pr7a-cancel-${engagementId}`,
          reason: 'Cancelled by the owner during review.',
          provenance: 'HUMAN',
        }),
      );
      await this.loadDecisionBrief();
    } catch {
      this.error.set('The draft could not be cancelled. Refresh and review the current state.');
    } finally {
      this.busy.set(false);
    }
  }

  async authorizeRfqSend(engagement: NonNullable<DecisionBriefView['engagement']>): Promise<void> {
    const send = engagement.send_eligibility;
    const draft = engagement.current_draft;
    const channels = engagement.current_draft?.contact?.['channels'];
    const fallbackRecipient =
      typeof channels === 'object' && channels !== null && 'EMAIL' in channels
        ? channels['EMAIL']
        : null;
    const recipient =
      send?.preview?.recipient ||
      (typeof fallbackRecipient === 'string' ? fallbackRecipient : null);
    if (!send?.can_authorize_send || !draft) return;
    const confirmed = globalThis.confirm(
      `Authorize an EMAIL RFQ to ${String(recipient || 'the reviewed contact')}?\n\n` +
        `Subject: ${draft.subject}\nQuantity: ${String(draft.structured_request.requested_quantity ?? 'UNKNOWN')}\n\n` +
        'This records your explicit send authorization; it does not send until you choose Send RFQ.',
    );
    if (!confirmed) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post(
          `${environment.apiUrl}/intelligence/engagements/${engagement.id}/send-authorize`,
          {
            draft_version: draft.version,
            channel: 'EMAIL',
            idempotency_key: `pr7b-send-auth-${engagement.id}-${draft.version}`,
            confirm: true,
            provenance: 'HUMAN',
          },
        ),
      );
      await this.loadDecisionBrief();
    } catch {
      this.error.set(
        'Send authorization was not recorded. Refresh and review the current approval, recipient, and trust state.',
      );
    } finally {
      this.busy.set(false);
    }
  }

  async sendRfq(engagement: NonNullable<DecisionBriefView['engagement']>): Promise<void> {
    const authorization = engagement.send_authorization;
    if (!authorization) return;
    const recipient = authorization.recipient || 'the reviewed contact';
    if (
      !globalThis.confirm(
        `Send the approved RFQ by EMAIL to ${recipient}?\n\nNo CC/BCC or additional recipients will be used.`,
      )
    )
      return;
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post(`${environment.apiUrl}/intelligence/engagements/${engagement.id}/send`, {
          authorization_id: authorization.id,
          idempotency_key: `pr7b-send-${engagement.id}-${authorization.id}`,
          confirm: true,
        }),
      );
      await this.loadDecisionBrief();
    } catch {
      this.error.set(
        'The RFQ was not sent. Review the canonical delivery status and resolve any blocking reason before retrying.',
      );
    } finally {
      this.busy.set(false);
    }
  }

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
