import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../environments/environment';

export interface MarketplaceAccount {
  id: string;
  marketplace: string;
  display_name: string;
  seller_account_id: string;
  environment: string;
  enabled: boolean;
  credential_status: string;
  validation_status: string;
  last_validated_at: string | null;
  capabilities: string[];
}
export interface MarketplaceListing {
  id: string;
  marketplace: string;
  product_id: string;
  account_id: string;
  title: string;
  marketplace_sku: string | null;
  status: string;
  publication_state: string;
  drift_state: string;
  external_url: string | null;
  content_artifact_id: string | null;
  content_artifact_version: number | null;
}
export interface MarketplaceInventory {
  marketplace?: string;
  id: string;
  listing_id: string;
  product_id: string;
  available_quantity: number;
  marketplace_reported_quantity: number | null;
  synchronization_status: string;
  last_synchronized_at: string | null;
}
export interface MarketplaceOrder {
  id: string;
  marketplace: string;
  remote_order_id: string;
  status: string;
  fulfilment_status: string;
  totals: Record<string, string>;
  ordered_at: string;
  buyer_summary: { display_name: string };
}
export interface MarketplaceSettlement {
  id: string;
  marketplace: string;
  remote_settlement_id: string;
  status?: string;
  period_start: string;
  period_end: string;
  gross_amount: string;
  fee_amount: string;
  refund_amount: string;
  tax_withholding_amount: string;
  net_amount: string;
  currency: string;
}
export interface ProductChannelIntelligence {
  channel: string;
  approved_artifact_id: string | null;
  approved_version: number | null;
  locale: string | null;
  content_quality_score: number | null;
  search_score: number | null;
  listing_used_version: number | null;
  blockers: string[];
  warnings: string[];
  analysis_stale: boolean;
  update_available: boolean;
  readiness: string;
}

export interface MarketplaceAnalytics {
  gross_sales: string;
  fees: string;
  refunds: string;
  net_contribution: string;
  estimated_profit: string | null;
  profit_status: string;
  order_count: number;
  active_listing_count: number;
  low_stock_count: number;
  sales_by_marketplace: Record<string, string>;
}

@Injectable({ providedIn: 'root' })
export class MarketplaceService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/marketplaces`;
  private readonly options = { withCredentials: true } as const;

  accounts(): Promise<MarketplaceAccount[]> {
    return firstValueFrom(
      this.http.get<MarketplaceAccount[]>(`${this.baseUrl}/accounts`, this.options),
    );
  }
  createAccount(payload: Record<string, unknown>): Promise<MarketplaceAccount> {
    return firstValueFrom(
      this.http.post<MarketplaceAccount>(`${this.baseUrl}/accounts`, payload, this.options),
    );
  }
  validateAccount(id: string): Promise<MarketplaceAccount> {
    return firstValueFrom(
      this.http.post<MarketplaceAccount>(
        `${this.baseUrl}/accounts/${id}/validate`,
        {},
        this.options,
      ),
    );
  }
  enableAccount(id: string): Promise<MarketplaceAccount> {
    return firstValueFrom(
      this.http.post<MarketplaceAccount>(`${this.baseUrl}/accounts/${id}/enable`, {}, this.options),
    );
  }
  disableAccount(id: string): Promise<MarketplaceAccount> {
    return firstValueFrom(
      this.http.post<MarketplaceAccount>(
        `${this.baseUrl}/accounts/${id}/disable`,
        {},
        this.options,
      ),
    );
  }
  listings(filters: { marketplace?: string; status?: string } = {}): Promise<MarketplaceListing[]> {
    let params = new HttpParams();
    if (filters.marketplace) params = params.set('marketplace', filters.marketplace);
    if (filters.status) params = params.set('status', filters.status);
    return firstValueFrom(
      this.http.get<MarketplaceListing[]>(`${this.baseUrl}/listings`, { ...this.options, params }),
    );
  }
  inventory(): Promise<MarketplaceInventory[]> {
    return firstValueFrom(
      this.http.get<MarketplaceInventory[]>(`${this.baseUrl}/inventory`, this.options),
    );
  }
  orders(): Promise<MarketplaceOrder[]> {
    return firstValueFrom(
      this.http.get<MarketplaceOrder[]>(`${this.baseUrl}/orders`, this.options),
    );
  }
  settlements(): Promise<MarketplaceSettlement[]> {
    return firstValueFrom(
      this.http.get<MarketplaceSettlement[]>(`${this.baseUrl}/settlements`, this.options),
    );
  }
  productChannelIntelligence(productId: string): Promise<ProductChannelIntelligence[]> {
    return firstValueFrom(
      this.http.get<ProductChannelIntelligence[]>(
        `${environment.apiUrl}/ai/seo/products/${productId}/channels`,
        this.options,
      ),
    );
  }
  analytics(): Promise<MarketplaceAnalytics> {
    return firstValueFrom(
      this.http.get<MarketplaceAnalytics>(`${this.baseUrl}/analytics`, this.options),
    );
  }
  static errorMessage(): string {
    return 'Marketplace data is unavailable. Check the API connection and try again.';
  }
}
