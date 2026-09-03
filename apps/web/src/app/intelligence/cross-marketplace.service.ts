import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';

export interface CanonicalSupplier {
  id: string;
  display_name: string;
  aliases: string[];
  identity: { state: string; rationale: string; supplier_ids: string[] };
  identity_state: string;
  confidence_score: number;
  source_diversity_score: number;
  freshness_status: string;
  source_diversity: {
    independent_source_count: number;
    source_diversity_score: number;
    provider_classes: string[];
  };
  freshness: { overall: string; sources: Array<Record<string, unknown>> };
  commercial: Record<string, unknown>;
  verification: Array<Record<string, unknown>>;
  capabilities: Array<Record<string, unknown>>;
  facilities: Array<Record<string, unknown>>;
  certifications: Array<Record<string, unknown>>;
  risk: { level: string; dimensions: Array<Record<string, unknown>> };
  confidence: Record<string, unknown>;
  contradictions: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface CrossMarketplaceOperations {
  canonical_supplier_count: number;
  multi_source_supplier_count: number;
  single_source_supplier_count: number;
  conflict_count: number;
  stale_supplier_count: number;
  high_risk_count: number;
  pending_review_count: number;
  provider_coverage: string[];
  [key: string]: unknown;
}

@Injectable({ providedIn: 'root' })
export class CrossMarketplaceService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/v1/intelligence/cross-marketplace/suppliers';
  private readonly options = { withCredentials: true };

  list(): Promise<CanonicalSupplier[]> {
    return firstValueFrom(this.http.get<CanonicalSupplier[]>(this.base, this.options));
  }
  operations(): Promise<CrossMarketplaceOperations> {
    return firstValueFrom(
      this.http.get<CrossMarketplaceOperations>(`${this.base}/operations`, this.options),
    );
  }
  reconcile(supplier_ids?: string[]): Promise<Record<string, unknown>[]> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>[]>(
        `${this.base}/reconcile`,
        { supplier_ids: supplier_ids ?? null },
        this.options,
      ),
    );
  }
  detail(id: string): Promise<CanonicalSupplier> {
    return firstValueFrom(this.http.get<CanonicalSupplier>(`${this.base}/${id}`, this.options));
  }
  compare(ids: string[]): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/compare`,
        { supplier_ids: ids },
        this.options,
      ),
    );
  }
  ranking(id: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(`${this.base}/${id}/ranking`, this.options),
    );
  }
  report(id: string, format = 'json'): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(
        `${this.base}/${id}/report?format=${encodeURIComponent(format)}`,
        this.options,
      ),
    );
  }
  handoff(id: string, confirmed: boolean, product_id?: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/${id}/sourcing-handoff`,
        { confirmed, product_id: product_id ?? null },
        this.options,
      ),
    );
  }
}
