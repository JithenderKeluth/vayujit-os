import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../environments/environment';

export interface ProductOpportunity {
  id: string;
  owner_id: string;
  product_id: string | null;
  brand_id: string | null;
  research_run_id: string | null;
  name: string;
  description: string;
  product_concept: string;
  category: string;
  subcategory: string;
  brand_strategy: string;
  target_marketplace: string;
  target_region: string;
  customer_segment: string;
  business_model: string;
  research_objective: string;
  origin: string;
  tags: string[];
  notes: string;
  lifecycle_status: string;
  research_state: string;
  evidence_state: string;
  current_constraint_version_id: string | null;
  current_assessment_id: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface OpportunityConstraint {
  id: string;
  opportunity_id: string;
  version: number;
  available_capital: string | null;
  target_selling_price_min: string | null;
  target_selling_price_max: string | null;
  target_margin: string | null;
  maximum_landed_cost: string | null;
  maximum_moq: string | null;
  maximum_lead_time_days: number | null;
  target_launch_window: string | null;
  acceptable_risk_level: string | null;
  marketplace: string | null;
  country_region: string | null;
  category_restrictions: string[];
  supplier_geography_preferences: string[];
  minimum_evidence_confidence: string | null;
  currency: string | null;
  idempotency_key: string;
  created_at: string;
}

export interface OpportunityAssessment {
  id: string;
  opportunity_id: string;
  version: number;
  constraint_version_id: string;
  input_snapshot_id: string;
  calculation_version: string;
  evidence_state: string;
  status: string;
  created_at: string;
}

export interface OpportunityDetail extends ProductOpportunity {
  constraints: OpportunityConstraint[];
  assessments: OpportunityAssessment[];
}

export interface TrendWinningProductProjection {
  id: string;
  owner_id: string;
  opportunity_id: string;
  assessment_id: string;
  context_id: string | null;
  snapshot_id: string | null;
  analysis_id: string | null;
  comparison_id: string | null;
  validation_id: string | null;
  projection_version: number;
  contract_version: string;
  calculation_version: string;
  input_fingerprint: string;
  readiness: string;
  source_state: string;
  validated_hypotheses: Array<Record<string, unknown>>;
  signal_summaries: Array<Record<string, unknown>>;
  momentum_summaries: Array<Record<string, unknown>>;
  evidence_confidence: Record<string, unknown>;
  freshness: Record<string, unknown>;
  contradictions: Array<Record<string, unknown>>;
  research_gaps: Array<Record<string, unknown>>;
  evidence_lineage: Record<string, unknown>;
  limitations: string[];
  projection: Record<string, unknown>;
  created_at: string;
}

export interface OpportunityCreatePayload {
  name: string;
  description?: string;
  product_concept?: string;
  category?: string;
  subcategory?: string;
  brand_strategy?: string;
  target_marketplace?: string;
  target_region?: string;
  customer_segment?: string;
  business_model?: string;
  research_objective?: string;
  origin?: string;
  tags?: string[];
  notes?: string;
  product_id?: string | null;
  brand_id?: string | null;
  research_run_id?: string | null;
  idempotency_key?: string;
}

export interface OpportunityConstraintPayload {
  currency?: string;
  available_capital?: string;
  target_selling_price_min?: string;
  target_selling_price_max?: string;
  target_margin?: string;
  maximum_landed_cost?: string;
  maximum_moq?: string;
  maximum_lead_time_days?: number;
  target_launch_window?: string;
  acceptable_risk_level?: string;
  marketplace?: string;
  country_region?: string;
  minimum_evidence_confidence?: string;
  idempotency_key?: string;
}

export interface IntelligenceDimension {
  dimension: string;
  value: unknown;
  classification: string;
  evidence_state: string;
  explanation: string;
  supporting_evidence: Array<Record<string, unknown>>;
  missing_evidence: string[];
  freshness: Record<string, unknown>;
  calculation_version: string;
}

export type CommercialDimension = IntelligenceDimension;

export interface CommercialOutput {
  id: string;
  owner_id: string;
  opportunity_id: string;
  assessment_id: string;
  calculation_version: string;
  constraint_snapshot: Record<string, unknown>;
  input_snapshot: Record<string, unknown>;
  dimensions: CommercialDimension[];
  economics: Record<string, unknown>;
  sensitivity: Record<string, unknown>;
  evidence_summary: Record<string, unknown>;
  research_gaps: Array<Record<string, unknown>>;
  idempotency_key: string;
  created_at: string;
  notes: string;
}
export interface SourcingCandidate {
  supplier?: { id: string; name: string };
  matched_product?: { id: string; title: string };
  canonical_supplier_id?: string | null;
  country?: string | null;
  region?: string | null;
  source?: string | Record<string, unknown>;
  availability?: string | null;
  freshness?: string;
  alternate_readiness?: string;
  risk_warnings?: unknown;
  match_explanation?: unknown;
  match_state?: string;
  verification?: string;
  currency?: string | null;
  price?: string | null;
  moq?: string | null;
  lead_time_days?: number | null;
  shortlist?: Record<string, unknown>;
  due_diligence?: Record<string, unknown>;
}
export interface SourcingFeasibilityOutput {
  id: string;
  owner_id: string;
  opportunity_id: string;
  assessment_id: string;
  calculation_version: string;
  constraint_snapshot: Record<string, unknown>;
  upstream_lineage: Record<string, unknown>;
  summary: {
    feasibility_state?: string;
    supplier_availability?: {
      discovered?: number;
      matched?: number;
      eligible?: number;
      dd_complete?: number;
    };
    scenario_availability?: string;
    confidence?: string;
  };
  candidates: SourcingCandidate[];
  dimensions: IntelligenceDimension[];
  evidence_summary: Record<string, unknown>;
  research_gaps: string[];
  idempotency_key: string;
  created_at: string;
  notes: string;
}
export interface RiskEvidenceSynthesisOutput {
  id: string;
  owner_id: string;
  opportunity_id: string;
  assessment_id: string;
  calculation_version: string;
  input_fingerprint: string;
  upstream_lineage: Record<string, unknown>;
  summary: Record<string, unknown>;
  risks: Array<Record<string, unknown>>;
  domain_readiness: Record<string, unknown>;
  evidence_summary: Record<string, unknown>;
  research_gaps: Array<Record<string, unknown>>;
  changes: Record<string, unknown>;
  dimensions: Array<Record<string, unknown>>;
  idempotency_key: string;
  created_at: string;
  notes: string;
}
export interface ProductOpportunityScoreHistory {
  id: string;
  assessment_id: string;
  scoring_model_version: string;
  profile_version: string;
  eligibility: string;
  overall_score: string | null;
  classification: string;
  created_at: string;
}

export interface ProductOpportunityComparison {
  comparability: string;
  reason: string;
  items: ProductOpportunityScore[];
  ranking?: Array<{
    rank: number;
    assessment_id: string;
    score_id: string;
    score: string | null;
    classification: string;
    confidence: string;
    readiness: string;
  }>;
}
export interface ProductOpportunityScore {
  id: string;
  owner_id: string;
  opportunity_id: string;
  assessment_id: string;
  scoring_model_version: string;
  calculation_version: string;
  profile_version: string;
  eligibility: string;
  overall_score: string | null;
  classification: string;
  decision_label: string;
  confidence: string;
  risk_level: string;
  assessment_readiness: string;
  evidence_state: string;
  dimensions: Array<Record<string, unknown>>;
  unavailable_dimensions: string[];
  risk_adjustments: Array<Record<string, unknown>>;
  positive_drivers: string[];
  negative_drivers: string[];
  improvement_areas: string[];
  sensitivity: Record<string, unknown>;
  comparability: Record<string, unknown>;
  weights: Record<string, unknown>;
  created_at: string;
}
export interface IntelligenceOutput {
  id: string;
  owner_id: string;
  opportunity_id: string;
  assessment_id: string;
  kind: 'demand' | 'competition';
  calculation_version: string;
  input_snapshot: Record<string, unknown>;
  dimensions: IntelligenceDimension[];
  evidence_summary: Record<string, unknown>;
  research_gaps: Array<Record<string, unknown>>;
  idempotency_key: string;
  created_at: string;
  notes: string;
}

export interface CompetitionProjection {
  id: string;
  source_state: string;
  contract_version: string;
  nine_b_calculation_version: string;
  ten_c_calculation_version: string | null;
  ten_d_calculation_version: string | null;
  freshness_state: string;
  contradiction_state: string;
  research_gaps: Array<Record<string, unknown>>;
  projection: {
    cohort?: {
      confirmed_count?: number;
      probable_count?: number;
      authoritative_count?: number | null;
    };
    analysis?: {
      pricing?: Record<string, unknown>;
      concentration?: {
        brand?: Record<string, unknown>;
        seller?: Record<string, unknown>;
      };
      review?: Record<string, unknown>;
      differentiation?: unknown;
      evidence_coverage?: Record<string, unknown>;
      freshness?: Record<string, unknown>;
    };
  };
}
export interface ReviewWinningProductProjection {
  id: string;
  opportunity_id: string;
  assessment_id: string;
  context_id: string | null;
  snapshot_id: string | null;
  analysis_id: string | null;
  gap_analysis_id: string | null;
  change_comparison_id: string | null;
  contract_version: string;
  calculation_version: string;
  readiness: string;
  source_state: string;
  cohort: Record<string, unknown>;
  rating_evidence: Record<string, unknown>;
  feedback_evidence: Record<string, unknown>;
  gap_evidence: Array<Record<string, unknown>>;
  change_evidence: Record<string, unknown>;
  research_gaps: Array<Record<string, unknown>>;
  freshness: Record<string, unknown>;
  contradictions: Array<Record<string, unknown>>;
  evidence_lineage: Record<string, unknown>;
  limitations: string[];
  projection: Record<string, unknown>;
  created_at: string;
}
@Injectable({ providedIn: 'root' })
export class ProductOpportunityService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/intelligence/product-opportunities`;
  private readonly options = { withCredentials: true } as const;

  list(): Promise<ProductOpportunity[]> {
    return firstValueFrom(this.http.get<ProductOpportunity[]>(this.base, this.options));
  }

  get(id: string): Promise<OpportunityDetail> {
    return firstValueFrom(this.http.get<OpportunityDetail>(`${this.base}/${id}`, this.options));
  }

  create(payload: OpportunityCreatePayload): Promise<ProductOpportunity> {
    return firstValueFrom(this.http.post<ProductOpportunity>(this.base, payload, this.options));
  }

  update(
    id: string,
    payload: Partial<OpportunityCreatePayload> & { lifecycle_status?: string },
  ): Promise<ProductOpportunity> {
    return firstValueFrom(
      this.http.patch<ProductOpportunity>(`${this.base}/${id}`, payload, this.options),
    );
  }

  archive(id: string): Promise<ProductOpportunity> {
    return firstValueFrom(
      this.http.post<ProductOpportunity>(`${this.base}/${id}/archive`, {}, this.options),
    );
  }

  createConstraint(
    id: string,
    payload: OpportunityConstraintPayload,
  ): Promise<OpportunityConstraint> {
    return firstValueFrom(
      this.http.post<OpportunityConstraint>(
        `${this.base}/${id}/constraints`,
        payload,
        this.options,
      ),
    );
  }

  getTrendProjection(
    opportunityId: string,
    assessmentId: string,
  ): Promise<TrendWinningProductProjection> {
    return firstValueFrom(
      this.http.get<TrendWinningProductProjection>(
        this.base + '/' + opportunityId + '/assessments/' + assessmentId + '/trend-projection',
        this.options,
      ),
    );
  }

  calculateTrendProjection(
    opportunityId: string,
    assessmentId: string,
  ): Promise<TrendWinningProductProjection> {
    return firstValueFrom(
      this.http.post<TrendWinningProductProjection>(
        this.base + '/' + opportunityId + '/assessments/' + assessmentId + '/trend-projection',
        {},
        this.options,
      ),
    );
  }

  createAssessment(
    id: string,
    payload: { evidence_state?: string; input_snapshot?: Record<string, unknown> },
  ): Promise<OpportunityAssessment> {
    return firstValueFrom(
      this.http.post<OpportunityAssessment>(
        `${this.base}/${id}/assessments`,
        payload,
        this.options,
      ),
    );
  }
  calculateDemand(opportunityId: string, assessmentId: string): Promise<IntelligenceOutput> {
    return firstValueFrom(
      this.http.post<IntelligenceOutput>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/demand`,
        {},
        this.options,
      ),
    );
  }

  getDemand(opportunityId: string, assessmentId: string): Promise<IntelligenceOutput> {
    return firstValueFrom(
      this.http.get<IntelligenceOutput>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/demand`,
        this.options,
      ),
    );
  }

  calculateCompetition(opportunityId: string, assessmentId: string): Promise<IntelligenceOutput> {
    return firstValueFrom(
      this.http.post<IntelligenceOutput>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/competition`,
        {},
        this.options,
      ),
    );
  }

  getCompetition(opportunityId: string, assessmentId: string): Promise<IntelligenceOutput> {
    return firstValueFrom(
      this.http.get<IntelligenceOutput>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/competition`,
        this.options,
      ),
    );
  }

  getCompetitionProjection(
    opportunityId: string,
    assessmentId: string,
  ): Promise<CompetitionProjection> {
    return firstValueFrom(
      this.http.get<CompetitionProjection>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/competition-projection`,
        this.options,
      ),
    );
  }

  getReviewProjection(
    opportunityId: string,
    assessmentId: string,
  ): Promise<ReviewWinningProductProjection> {
    return firstValueFrom(
      this.http.get<ReviewWinningProductProjection>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/review-projection`,
        this.options,
      ),
    );
  }

  calculateReviewProjection(
    opportunityId: string,
    assessmentId: string,
  ): Promise<ReviewWinningProductProjection> {
    return firstValueFrom(
      this.http.post<ReviewWinningProductProjection>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/review-projection`,
        {},
        this.options,
      ),
    );
  }
  calculateCommercial(
    opportunityId: string,
    assessmentId: string,
    payload: Record<string, unknown> = {},
  ): Promise<CommercialOutput> {
    return firstValueFrom(
      this.http.post<CommercialOutput>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/commercial`,
        payload,
        this.options,
      ),
    );
  }

  getCommercial(opportunityId: string, assessmentId: string): Promise<CommercialOutput> {
    return firstValueFrom(
      this.http.get<CommercialOutput>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/commercial`,
        this.options,
      ),
    );
  }

  getCommercialUnitEconomics(
    opportunityId: string,
    assessmentId: string,
  ): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/commercial/unit-economics`,
        this.options,
      ),
    );
  }

  getCommercialCapital(
    opportunityId: string,
    assessmentId: string,
  ): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/commercial/capital`,
        this.options,
      ),
    );
  }

  getCommercialConstraints(
    opportunityId: string,
    assessmentId: string,
  ): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/commercial/constraints`,
        this.options,
      ),
    );
  }

  getCommercialSensitivity(
    opportunityId: string,
    assessmentId: string,
  ): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/commercial/sensitivity`,
        this.options,
      ),
    );
  }

  getCommercialEvidence(
    opportunityId: string,
    assessmentId: string,
  ): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/commercial/evidence`,
        this.options,
      ),
    );
  }

  getCommercialGaps(
    opportunityId: string,
    assessmentId: string,
  ): Promise<Array<Record<string, unknown>>> {
    return firstValueFrom(
      this.http.get<Array<Record<string, unknown>>>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/commercial/gaps`,
        this.options,
      ),
    );
  }
  listIntelligence(opportunityId: string, assessmentId: string): Promise<IntelligenceOutput[]> {
    return firstValueFrom(
      this.http.get<IntelligenceOutput[]>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/intelligence`,
        this.options,
      ),
    );
  }

  calculateRiskEvidenceSynthesis(
    opportunityId: string,
    assessmentId: string,
  ): Promise<RiskEvidenceSynthesisOutput> {
    return firstValueFrom(
      this.http.post<RiskEvidenceSynthesisOutput>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/risk-evidence-synthesis`,
        {},
        this.options,
      ),
    );
  }
  getRiskEvidenceSynthesis(
    opportunityId: string,
    assessmentId: string,
  ): Promise<RiskEvidenceSynthesisOutput> {
    return firstValueFrom(
      this.http.get<RiskEvidenceSynthesisOutput>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/risk-evidence-synthesis`,
        this.options,
      ),
    );
  }
  getRiskEvidenceSection(
    opportunityId: string,
    assessmentId: string,
    section: string,
  ): Promise<unknown> {
    return firstValueFrom(
      this.http.get<unknown>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/risk-evidence-synthesis/${section}`,
        this.options,
      ),
    );
  }

  calculateScore(
    opportunityId: string,
    assessmentId: string,
    payload: Record<string, unknown> = {},
  ): Promise<ProductOpportunityScore> {
    return firstValueFrom(
      this.http.post<ProductOpportunityScore>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/score`,
        payload,
        this.options,
      ),
    );
  }

  getScore(opportunityId: string, assessmentId: string): Promise<ProductOpportunityScore> {
    return firstValueFrom(
      this.http.get<ProductOpportunityScore>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/score`,
        this.options,
      ),
    );
  }

  getScoreHistory(opportunityId: string): Promise<ProductOpportunityScoreHistory[]> {
    return firstValueFrom(
      this.http.get<ProductOpportunityScoreHistory[]>(
        `${this.base}/${opportunityId}/score/history`,
        this.options,
      ),
    );
  }

  compareScores(assessmentIds: string[]): Promise<ProductOpportunityComparison> {
    return firstValueFrom(
      this.http.post<ProductOpportunityComparison>(
        `${this.base}/score/compare`,
        { assessment_ids: assessmentIds },
        this.options,
      ),
    );
  }

  rankScores(assessmentIds: string[]): Promise<ProductOpportunityComparison> {
    return firstValueFrom(
      this.http.post<ProductOpportunityComparison>(
        `${this.base}/score/rank`,
        { assessment_ids: assessmentIds },
        this.options,
      ),
    );
  }

  decide(
    opportunityId: string,
    assessmentId: string,
    payload: { action: string; rationale: string },
  ): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/decision`,
        payload,
        this.options,
      ),
    );
  }
  calculateSourcingFeasibility(
    opportunityId: string,
    assessmentId: string,
    payload: Record<string, unknown> = {},
  ): Promise<SourcingFeasibilityOutput> {
    return firstValueFrom(
      this.http.post<SourcingFeasibilityOutput>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/sourcing-feasibility`,
        payload,
        this.options,
      ),
    );
  }

  getSourcingFeasibility(
    opportunityId: string,
    assessmentId: string,
  ): Promise<SourcingFeasibilityOutput> {
    return firstValueFrom(
      this.http.get<SourcingFeasibilityOutput>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/sourcing-feasibility`,
        this.options,
      ),
    );
  }

  handoffSourcing(
    opportunityId: string,
    assessmentId: string,
    supplierProductId: string,
  ): Promise<{ context_id: string; external_work_started: boolean }> {
    return firstValueFrom(
      this.http.post<{ context_id: string; external_work_started: boolean }>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/sourcing-feasibility/handoff`,
        { supplier_product_id: supplierProductId, confirm: true },
        this.options,
      ),
    );
  }

  getSourcingSection(
    opportunityId: string,
    assessmentId: string,
    section: string,
  ): Promise<unknown> {
    return firstValueFrom(
      this.http.get<unknown>(
        `${this.base}/${opportunityId}/assessments/${assessmentId}/sourcing-feasibility/${section}`,
        this.options,
      ),
    );
  }
}
