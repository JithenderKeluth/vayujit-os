import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../environments/environment';

export interface CompetitorContext {
  id: string;
  subject_type: string;
  subject_reference: string;
  marketplace: string;
  market: string;
  category: string;
  currency: string | null;
  status: string;
  version: number;
  updated_at: string;
}

export interface CompetitorEntity {
  id: string;
  display_name: string;
  entity_type: string;
  canonical_name: string;
  evidence_state: string;
  website_domain: string | null;
  updated_at: string;
}

export interface CompetitorProduct {
  id: string;
  context_id: string;
  entity_id: string | null;
  title: string;
  marketplace: string;
  external_identifier: string;
  availability_state: string;
  identity_state: string;
  evidence_state: string;
  last_observed: string;
}

export interface CompetitorObservation {
  id: string;
  competitor_product_id: string;
  observation_type: string;
  observed_value: Record<string, unknown>;
  numeric_value: string | null;
  currency: string | null;
  source_reference: string;
  freshness_state: string;
  observed_at: string;
}

export interface CompetitorSnapshot {
  id: string;
  context_id: string;
  product_id: string | null;
  snapshot_version: number;
  input_fingerprint: string;
  payload: Record<string, unknown>;
  captured_at: string;
}

export interface CompetitorProductDetail {
  product: CompetitorProduct;
  observations: CompetitorObservation[];
  snapshots: CompetitorSnapshot[];
}

export interface CompetitorDiscoveryRequest {
  id: string;
  context_id: string;
  provider_mode: string;
  status: string;
  maximum_candidates: number;
  version: number;
}
export interface CompetitorDiscoveryCandidate {
  id: string;
  request_id: string;
  raw_title: string;
  normalized_title: string;
  marketplace: string;
  identity_state: string;
  match_level: string;
  match_score: string | null;
  supporting_signals: unknown[];
  conflicting_signals: unknown[];
  missing_signals: unknown[];
  evidence_state: string;
  freshness_state: string;
}
export interface CompetitorIntegrity {
  status: string;
  counts: Record<string, number>;
  duplicate_counts: Record<string, number>;
}

export interface CompetitorCommercialAnalysis {
  id: string;
  owner_id: string;
  context_id: string;
  discovery_snapshot_id: string | null;
  opportunity_id: string | null;
  analysis_version: number;
  calculation_version: string;
  status: string;
  input_fingerprint: string;
  input_snapshot: Record<string, unknown>;
  cohort_summary: Record<string, unknown>;
  pricing_analysis: Record<string, unknown>;
  concentration_analysis: Record<string, unknown>;
  rating_analysis: Record<string, unknown>;
  review_analysis: Record<string, unknown>;
  assortment_analysis: Record<string, unknown>;
  positioning_analysis: Record<string, unknown>;
  differentiation_analysis: Array<Record<string, unknown>>;
  competitive_gaps: Array<Record<string, unknown>>;
  evidence_coverage: Record<string, unknown>;
  freshness_summary: Record<string, unknown>;
  contradictions: Array<Record<string, unknown>>;
  research_gaps: Array<Record<string, unknown>>;
  explanation: Record<string, unknown>;
  idempotency_key: string;
  created_at: string;
}

export interface CompetitorChangeEvent {
  id: string;
  context_id: string;
  comparison_id: string;
  product_id: string | null;
  change_type: string;
  observed_or_derived: string;
  old_value: unknown;
  new_value: unknown;
  absolute_delta: string | null;
  percentage_delta: string | null;
  currency: string | null;
  freshness_state: string;
  evidence_state: string;
  materiality: string;
  status: string;
  confidence: string | null;
  alert_eligibility: string;
  first_observed: string | null;
  last_observed: string | null;
  calculation_version: string;
}
@Injectable({ providedIn: 'root' })
export class CompetitorIntelligenceService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/intelligence/competitors`;

  contexts(): Promise<CompetitorContext[]> {
    return firstValueFrom(this.http.get<CompetitorContext[]>(`${this.base}/contexts`));
  }

  entities(): Promise<CompetitorEntity[]> {
    return firstValueFrom(this.http.get<CompetitorEntity[]>(`${this.base}/entities`));
  }

  products(contextId: string): Promise<CompetitorProduct[]> {
    return firstValueFrom(
      this.http.get<CompetitorProduct[]>(`${this.base}/contexts/${contextId}/products`),
    );
  }

  productDetail(productId: string): Promise<CompetitorProductDetail> {
    return firstValueFrom(
      this.http.get<CompetitorProductDetail>(`${this.base}/products/${productId}`),
    );
  }

  createContext(payload: Record<string, unknown>): Promise<CompetitorContext> {
    return firstValueFrom(this.http.post<CompetitorContext>(`${this.base}/contexts`, payload));
  }

  createEntity(payload: Record<string, unknown>): Promise<CompetitorEntity> {
    return firstValueFrom(this.http.post<CompetitorEntity>(`${this.base}/entities`, payload));
  }

  createProduct(contextId: string, payload: Record<string, unknown>): Promise<CompetitorProduct> {
    return firstValueFrom(
      this.http.post<CompetitorProduct>(`${this.base}/contexts/${contextId}/products`, payload),
    );
  }

  identity(productId: string, identityState: string): Promise<CompetitorProduct> {
    return firstValueFrom(
      this.http.patch<CompetitorProduct>(`${this.base}/products/${productId}/identity`, {
        identity_state: identityState,
      }),
    );
  }

  createDiscoveryRequest(
    contextId: string,
    payload: Record<string, unknown>,
  ): Promise<CompetitorDiscoveryRequest> {
    return firstValueFrom(
      this.http.post<CompetitorDiscoveryRequest>(
        this.base + '/discovery/contexts/' + contextId + '/requests',
        payload,
      ),
    );
  }

  executeDiscovery(
    requestId: string,
  ): Promise<{ request: CompetitorDiscoveryRequest; candidates: CompetitorDiscoveryCandidate[] }> {
    return firstValueFrom(
      this.http.post<{
        request: CompetitorDiscoveryRequest;
        candidates: CompetitorDiscoveryCandidate[];
      }>(this.base + '/discovery/requests/' + requestId + '/execute', {}),
    );
  }

  discoveryCandidates(requestId: string): Promise<CompetitorDiscoveryCandidate[]> {
    return firstValueFrom(
      this.http.get<CompetitorDiscoveryCandidate[]>(
        this.base + '/discovery/requests/' + requestId + '/candidates',
      ),
    );
  }

  resolveDiscoveryCandidate(
    candidateId: string,
    state: 'confirm' | 'reject' | 'ambiguous',
  ): Promise<CompetitorDiscoveryCandidate> {
    return firstValueFrom(
      this.http.post<CompetitorDiscoveryCandidate>(
        this.base + '/discovery/candidates/' + candidateId + '/' + state,
        { confirm: state === 'confirm', reason: 'Reviewed in Competitor Intelligence workspace.' },
      ),
    );
  }

  runCommercialAnalysis(
    contextId: string,
    payload: Record<string, unknown> = {},
  ): Promise<CompetitorCommercialAnalysis> {
    return firstValueFrom(
      this.http.post<CompetitorCommercialAnalysis>(
        this.base + '/commercial-analysis/contexts/' + contextId + '/analyses/run',
        payload,
      ),
    );
  }

  currentCommercialAnalysis(contextId: string): Promise<CompetitorCommercialAnalysis> {
    return firstValueFrom(
      this.http.get<CompetitorCommercialAnalysis>(
        this.base + '/commercial-analysis/contexts/' + contextId + '/analyses/current',
      ),
    );
  }

  commercialAnalysisHistory(contextId: string): Promise<CompetitorCommercialAnalysis[]> {
    return firstValueFrom(
      this.http.get<CompetitorCommercialAnalysis[]>(
        this.base + '/commercial-analysis/contexts/' + contextId + '/analyses',
      ),
    );
  }

  runChangeComparison(
    contextId: string,
    payload: Record<string, unknown> = {},
  ): Promise<{ comparison: Record<string, unknown>; events: CompetitorChangeEvent[] }> {
    return firstValueFrom(
      this.http.post<{ comparison: Record<string, unknown>; events: CompetitorChangeEvent[] }>(
        this.base + '/change-intelligence/contexts/' + contextId + '/comparisons/run',
        payload,
      ),
    );
  }

  currentChanges(contextId: string): Promise<{ items: CompetitorChangeEvent[]; total: number }> {
    return firstValueFrom(
      this.http.get<{ items: CompetitorChangeEvent[]; total: number }>(
        this.base + '/change-intelligence/contexts/' + contextId + '/changes',
      ),
    );
  }
  doctor(): Promise<CompetitorIntegrity> {
    return firstValueFrom(this.http.get<CompetitorIntegrity>(`${this.base}/system-doctor`));
  }
}
