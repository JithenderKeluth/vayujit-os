import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface TrendContext {
  id: string;
  name: string;
  subject_type: string;
  subject_key: string;
  status: string;
  version: number;
  product_id?: string | null;
  brand_id?: string | null;
  created_at: string;
  updated_at: string;
}
export interface TrendObservation {
  id: string;
  signal_definition_id: string;
  observed_at: string;
  measurement_type: string;
  value_numeric?: string | number | null;
  value_text?: string | null;
  value_boolean?: boolean | null;
  geography_scope: string;
  freshness_state: string;
  quality_state: string;
  source_reference: string;
}
export interface TrendSnapshot {
  id: string;
  snapshot_version: number;
  captured_at: string;
  observation_count: number;
  source_inventory: Record<string, number>;
  signal_inventory: Record<string, number>;
  freshness_summary: Record<string, number>;
}
export interface TrendPage<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface TrendAnalysis {
  id: string;
  context_id: string;
  snapshot_id: string;
  analysis_version: number;
  readiness: string;
  included_observation_count: number;
  excluded_observation_count: number;
  time_coverage: Record<string, unknown>;
  summary: Record<string, unknown>;
  limitations: string[];
  freshness_state: string;
}
export interface TrendAnalysisSeries {
  id: string;
  source_id: string;
  signal_definition_id: string;
  measurement_type: string;
  unit?: string | null;
  granularity: string;
  readiness: string;
  direction: string;
  persistence: string;
  variability_state: string;
  freshness_state: string;
  sample_size: number;
  time_start?: string | null;
  time_end?: string | null;
  missing_period_count: number;
  statistics: Record<string, unknown>;
  change: Record<string, unknown>;
  movement: Record<string, unknown>;
  limitations: string[];
  observation_ids: string[];
}
export interface TrendChangeComparison {
  id: string;
  context_id: string;
  baseline_analysis_id: string;
  current_analysis_id: string;
  baseline_snapshot_id: string;
  current_snapshot_id: string;
  comparison_version: number;
  status: string;
  summary: Record<string, unknown>;
  limitations: string[];
  created_at: string;
}
export interface TrendChangeEvent {
  id: string;
  comparison_id: string;
  signal_definition_id?: string | null;
  source_id?: string | null;
  event_type: string;
  change_semantics: string;
  old_value: unknown;
  new_value: unknown;
  absolute_delta?: string | number | null;
  relative_delta?: string | number | null;
  relative_reason?: string | null;
  momentum: string;
  materiality: string;
  status: string;
  alert_eligibility: string;
  alert_reason: string;
  freshness_state: string;
  limitations: string[];
  created_at: string;
}
export interface TrendChangeResult {
  comparison: TrendChangeComparison;
  events: TrendChangeEvent[];
}
export interface TrendIngestion {
  id: string;
  mode: string;
  status: string;
  accepted_count: number;
  rejected_count: number;
  duplicate_count: number;
  created_at: string;
}
@Injectable({ providedIn: 'root' })
export class TrendIntelligenceService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/intelligence/trends`;
  contexts(): Observable<TrendContext[]> {
    return this.http.get<TrendContext[]>(`${this.base}/contexts`);
  }
  createContext(value: Record<string, unknown>): Observable<TrendContext> {
    return this.http.post<TrendContext>(`${this.base}/contexts`, value);
  }
  observations(contextId: string): Observable<TrendPage<TrendObservation>> {
    return this.http.get<TrendPage<TrendObservation>>(
      `${this.base}/contexts/${contextId}/observations`,
    );
  }
  snapshots(contextId: string): Observable<TrendSnapshot[]> {
    return this.http.get<TrendSnapshot[]>(`${this.base}/contexts/${contextId}/snapshots`);
  }
  coverage(contextId: string): Observable<Record<string, unknown>> {
    return this.http.get<Record<string, unknown>>(`${this.base}/contexts/${contextId}/coverage`);
  }
  ingestions(contextId: string): Observable<TrendIngestion[]> {
    return this.http.get<TrendIngestion[]>(`${this.base}/contexts/${contextId}/ingestions`);
  }
  ingest(contextId: string, value: Record<string, unknown>): Observable<TrendIngestion> {
    return this.http.post<TrendIngestion>(`${this.base}/contexts/${contextId}/ingestions`, value);
  }
  createSnapshot(
    contextId: string,
    value: Record<string, unknown> = {},
  ): Observable<TrendSnapshot> {
    return this.http.post<TrendSnapshot>(`${this.base}/contexts/${contextId}/snapshots`, value);
  }
  createAnalysis(contextId: string, value: Record<string, unknown>): Observable<TrendAnalysis> {
    return this.http.post<TrendAnalysis>(`${this.base}/contexts/${contextId}/analyses`, value);
  }
  analyses(contextId: string): Observable<TrendPage<TrendAnalysis>> {
    return this.http.get<TrendPage<TrendAnalysis>>(`${this.base}/contexts/${contextId}/analyses`);
  }
  series(contextId: string, analysisId: string): Observable<TrendPage<TrendAnalysisSeries>> {
    return this.http.get<TrendPage<TrendAnalysisSeries>>(
      `${this.base}/contexts/${contextId}/analyses/${analysisId}/series`,
    );
  }
  changes(contextId: string): Observable<TrendPage<TrendChangeComparison>> {
    return this.http.get<TrendPage<TrendChangeComparison>>(
      `${this.base}/contexts/${contextId}/changes`,
    );
  }
  changeEvents(contextId: string, comparisonId: string): Observable<TrendPage<TrendChangeEvent>> {
    return this.http.get<TrendPage<TrendChangeEvent>>(
      `${this.base}/contexts/${contextId}/changes/${comparisonId}/events`,
    );
  }
  createChange(contextId: string, value: Record<string, unknown>): Observable<TrendChangeResult> {
    return this.http.post<TrendChangeResult>(`${this.base}/contexts/${contextId}/changes`, value);
  }
}
