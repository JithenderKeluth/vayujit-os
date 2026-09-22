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
}
