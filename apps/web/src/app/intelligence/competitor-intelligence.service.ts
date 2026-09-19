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

export interface CompetitorIntegrity {
  status: string;
  counts: Record<string, number>;
  duplicate_counts: Record<string, number>;
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

  doctor(): Promise<CompetitorIntegrity> {
    return firstValueFrom(this.http.get<CompetitorIntegrity>(`${this.base}/system-doctor`));
  }
}
