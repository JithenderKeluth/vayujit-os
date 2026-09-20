import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

export interface ReviewContext {
  id: string;
  name: string;
  product_id: string | null;
  product_opportunity_id: string | null;
  marketplace: string;
  market: string;
  status: string;
  version: number;
}
export interface ReviewRecord {
  id: string;
  provider: string;
  provider_review_id: string | null;
  rating: string | null;
  rating_scale: string | null;
  title: string | null;
  body: string | null;
  verified_purchase: string;
  review_date: string | null;
  freshness_status: string;
  evidence_state: string;
  source_reference: string | null;
}
export interface ReviewSnapshot {
  id: string;
  snapshot_version: number;
  review_count: number;
  rated_review_count: number;
  source_inventory: Record<string, number>;
  freshness_summary: Record<string, number>;
  input_fingerprint: string;
}
export interface ReviewAnalysisItem {
  id: string;
  item_type: string;
  canonical_label: string;
  sentiment: string;
  severity: string;
  support_count: number;
  cohort_count: number;
  coverage: Record<string, number>;
  supporting_review_ids: string[];
  supporting_evidence_ids: string[];
  confidence: string;
  evidence_state: string;
  limitation: string | null;
}
export interface ReviewAnalysisAnnotation {
  id: string;
  review_record_id: string;
  sentiment: string;
  aspect_sentiments: Record<string, string>;
  topics: string[];
  confidence: string;
}
export interface ReviewAnalysis {
  id: string;
  snapshot_id: string;
  snapshot_version: number;
  mode: string;
  status: string;
  total_records: number;
  included_records: number;
  excluded_records: number;
  cohort_json: Record<string, unknown>;
  rating_distribution: Record<string, unknown>;
  sentiment_distribution: Record<string, { count: number; proportion: number }>;
  source_distribution: Record<string, number>;
  evidence_gaps: Array<Record<string, unknown>>;
  limitations: string[];
  error_message: string | null;
}
export interface ReviewAnalysisDetail {
  analysis: ReviewAnalysis;
  items: ReviewAnalysisItem[];
  annotations: ReviewAnalysisAnnotation[];
  summary: Record<string, unknown>;
}
export interface ReviewProductGap {
  id: string;
  gap_type: string;
  canonical_label: string;
  hypothesis: string;
  support_classification: string;
  support_count: number;
  cohort_count: number;
  evidence_strength: string;
  confidence: string;
  status: string;
  required_validations: string[];
  limitations: string[];
}
export interface ReviewOpportunitySignal {
  id: string;
  signal_type: string;
  canonical_label: string;
  hypothesis: string;
  explanation: string;
  status: string;
  evidence_strength: string;
  support_classification: string;
  confidence: string;
  required_validations: string[];
  limitations: string[];
}
export interface ReviewGapAnalysis {
  id: string;
  status: string;
  gap_count: number;
  signal_count: number;
  snapshot_id: string;
  review_analysis_id: string;
  input_fingerprint: string;
  limitations: string[];
}
export interface ReviewGapAnalysisDetail {
  analysis: ReviewGapAnalysis;
  product_gaps: ReviewProductGap[];
  opportunity_signals: ReviewOpportunitySignal[];
  summary: Record<string, unknown>;
}
export interface ReviewStatistics {
  review_count: number;
  rated_review_count: number;
  unrated_review_count: number;
  rating_scales: Record<string, number>;
  verified_purchase_count: number;
  unknown_verified_purchase_count: number;
  source_counts: Record<string, number>;
  freshness_counts: Record<string, number>;
  evidence_counts: Record<string, number>;
  review_date_min: string | null;
  review_date_max: string | null;
}
export interface ReviewIngestionBatch {
  id: string;
  provider: string;
  mode: string;
  status: string;
  input_count: number;
  accepted_count: number;
  rejected_count: number;
  duplicate_count: number;
  updated_observation_count: number;
  error_message: string | null;
  created_at: string;
}
export interface ReviewIngestionCandidate {
  id: string;
  ordinal: number;
  provider_review_id: string | null;
  duplicate_classification: string;
  quality_state: string;
  accepted: boolean;
  rejection_reason: string | null;
}
export interface ReviewIngestionResult {
  batch: ReviewIngestionBatch;
  candidates: ReviewIngestionCandidate[];
  summary: Record<string, unknown>;
}

export interface ReviewPage {
  items: ReviewRecord[];
  total: number;
  limit: number;
  offset: number;
}

@Injectable({ providedIn: 'root' })
export class ReviewIntelligenceService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/intelligence/reviews`;
  contexts(): Promise<ReviewContext[]> {
    return firstValueFrom(this.http.get<ReviewContext[]>(`${this.base}/contexts`));
  }
  createContext(payload: Record<string, unknown>): Promise<ReviewContext> {
    return firstValueFrom(this.http.post<ReviewContext>(`${this.base}/contexts`, payload));
  }
  reviews(contextId: string): Promise<ReviewPage> {
    return firstValueFrom(this.http.get<ReviewPage>(`${this.base}/contexts/${contextId}/reviews`));
  }
  createReview(contextId: string, payload: Record<string, unknown>): Promise<ReviewRecord> {
    return firstValueFrom(
      this.http.post<ReviewRecord>(`${this.base}/contexts/${contextId}/reviews`, payload),
    );
  }
  statistics(contextId: string): Promise<ReviewStatistics> {
    return firstValueFrom(
      this.http.get<ReviewStatistics>(`${this.base}/contexts/${contextId}/statistics`),
    );
  }
  snapshots(contextId: string): Promise<ReviewSnapshot[]> {
    return firstValueFrom(
      this.http.get<ReviewSnapshot[]>(`${this.base}/contexts/${contextId}/snapshots`),
    );
  }
  createSnapshot(
    contextId: string,
    payload: Record<string, unknown> = {},
  ): Promise<ReviewSnapshot> {
    return firstValueFrom(
      this.http.post<ReviewSnapshot>(`${this.base}/contexts/${contextId}/snapshots`, payload),
    );
  }
  ingestions(contextId: string): Promise<ReviewIngestionBatch[]> {
    return firstValueFrom(
      this.http.get<ReviewIngestionBatch[]>(`${this.base}/contexts/${contextId}/ingestions`),
    );
  }
  ingest(contextId: string, payload: Record<string, unknown>): Promise<ReviewIngestionResult> {
    return firstValueFrom(
      this.http.post<ReviewIngestionResult>(
        `${this.base}/contexts/${contextId}/ingestions`,
        payload,
      ),
    );
  }
  ingestionSummary(contextId: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(
        `${this.base}/contexts/${contextId}/ingestion-summary`,
      ),
    );
  }
  analyses(contextId: string): Promise<ReviewAnalysis[]> {
    return firstValueFrom(
      this.http.get<ReviewAnalysis[]>(`${this.base}/contexts/${contextId}/analyses`),
    );
  }
  createAnalysis(
    contextId: string,
    payload: Record<string, unknown> = {},
  ): Promise<ReviewAnalysisDetail> {
    return firstValueFrom(
      this.http.post<ReviewAnalysisDetail>(`${this.base}/contexts/${contextId}/analyses`, payload),
    );
  }
  currentAnalysis(contextId: string): Promise<ReviewAnalysisDetail | null> {
    return firstValueFrom(
      this.http.get<ReviewAnalysisDetail | null>(
        `${this.base}/contexts/${contextId}/analyses/current`,
      ),
    );
  }
  createGapAnalysis(contextId: string, reviewAnalysisId: string): Promise<ReviewGapAnalysisDetail> {
    return firstValueFrom(
      this.http.post<ReviewGapAnalysisDetail>(`${this.base}/contexts/${contextId}/gap-analyses`, {
        review_analysis_id: reviewAnalysisId,
      }),
    );
  }
  currentGapAnalysis(contextId: string): Promise<ReviewGapAnalysisDetail | null> {
    return firstValueFrom(
      this.http.get<ReviewGapAnalysisDetail | null>(
        `${this.base}/contexts/${contextId}/gap-analyses/current`,
      ),
    );
  }
  analysisDetail(contextId: string, analysisId: string): Promise<ReviewAnalysisDetail> {
    return firstValueFrom(
      this.http.get<ReviewAnalysisDetail>(
        `${this.base}/contexts/${contextId}/analyses/${analysisId}`,
      ),
    );
  }
  doctor(): Promise<{ status: string; counts: Record<string, number> }> {
    return firstValueFrom(
      this.http.get<{ status: string; counts: Record<string, number> }>(
        `${this.base}/system-doctor`,
      ),
    );
  }
}
