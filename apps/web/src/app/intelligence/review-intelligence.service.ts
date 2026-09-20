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
  doctor(): Promise<{ status: string; counts: Record<string, number> }> {
    return firstValueFrom(
      this.http.get<{ status: string; counts: Record<string, number> }>(
        `${this.base}/system-doctor`,
      ),
    );
  }
}
