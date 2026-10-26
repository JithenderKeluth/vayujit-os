import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom, timeout } from 'rxjs';

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
  connection_state?: string;
  permission_state?: string;
  transport_mode?: string;
}
export interface MarketplaceImportJob {
  id: string;
  account_id: string;
  marketplace: string;
  operation: 'catalog' | 'orders' | 'inventory' | 'financial';
  mode: string;
  status: string;
  idempotency_key: string;
  correlation_id: string;
  checkpoint_json: Record<string, unknown>;
  summary_json: Record<string, unknown>;
  provenance_json: Record<string, unknown>;
  pages_fetched: number;
  records_seen: number;
  records_imported: number;
  records_reused: number;
  error_code: string | null;
  error_message: string | null;
  completed_at: string | null;
  last_successful_sync: string | null;
  stale_after: string | null;
}
export interface MarketplaceConnectivityStatus {
  account_id: string;
  marketplace: string;
  environment: string;
  connection_state: string;
  permission_state: string;
  credential_status: string;
  validation_status: string;
  transport_mode: string;
  last_successful_sync: string | null;
  external_writes: boolean;
  provider_contract: string;
}
export interface MarketplaceCapability {
  provider: string;
  regions: string[];
  transport_modes: string[];
  supported_operations: string[];
  repo_supported: boolean;
  synthetic_fixture: boolean;
  official_contract: string;
  sandbox: string;
  live_read_only: string;
  live_write: string;
  external_activation_required: boolean;
}
export interface MarketplaceReconciliation {
  account_id: string;
  marketplace: string;
  canonical_counts: Record<string, number>;
  latest_imports: Record<string, MarketplaceImportJob>;
  last_failed_imports: Record<string, MarketplaceImportJob>;
  freshness: Record<string, string>;
  imported_counts: Record<string, number>;
  stale_operations: string[];
  exceptions: string[];
  automatic_mutations: boolean;
  next_action: string;
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

export interface InventoryItem {
  id: string;
  product_id: string;
  variant_id: string | null;
  internal_sku: string;
  location_code: string;
  unit: string;
  on_hand_quantity: number;
  reserved_quantity: number;
  damaged_quantity: number;
  available_to_promise: number;
  low_stock_threshold: number;
  version: number;
  last_reconciled_at: string | null;
  created_at: string;
  updated_at: string;
}
export interface InventoryAdjustment {
  delta: number;
  reason: string;
  expected_version: number;
  idempotency_key: string;
}
export interface InventoryOpeningRequest {
  product_id: string;
  variant_id: string | null;
  internal_sku: string;
  location_code: string;
  unit: string;
  opening_quantity: number;
  low_stock_threshold: number;
  idempotency_key: string;
}
export interface InventoryMovement {
  id: string;
  inventory_item_id: string;
  quantity: number;
  movement_type: string;
  source_reference: string | null;
  actor_type: string;
  reason: string;
  before_on_hand: number;
  after_on_hand: number;
  before_reserved: number;
  after_reserved: number;
  created_at: string;
}
export interface ChannelSkuMapping {
  id: string;
  account_id: string;
  inventory_item_id: string;
  marketplace: string;
  external_sku: string;
  listing_id: string | null;
  status: string;
  effective_version: number;
  provenance_json: Record<string, unknown>;
}
export interface UnifiedOrder {
  id: string;
  account_id: string;
  marketplace: string;
  remote_order_id: string;
  status: string;
  fulfilment_status: string;
  reservation_state: string;
  line_count: number;
  fake_provider: boolean;
  ordered_at: string;
}
export interface ReconciliationSummary {
  inventory_items: number;
  low_stock_items: number;
  out_of_stock_items: number;
  active_reservations: number;
  reservation_failures: number;
  unmapped_order_lines: number;
  stale_provider_events: number;
  next_actions: string[];
}
export interface FinancialSummary {
  currency: string;
  evidence_status: string;
  calculation_version: string;
  basis: string;
  gross_merchandise_value: string;
  gross_sales: string;
  discounts: string;
  refunds: string;
  net_sales: string;
  fees: string;
  known_direct_costs: string;
  contribution: string;
  estimated_profit: string | null;
  margin_percent: string | null;
  order_count: number;
  event_count: number;
  missing_inputs: string[];
  synthetic_provider: boolean;
  external_writes: boolean;
  canonical_order_fallback?: boolean;
  provenance_status?: 'SYNTHETIC' | 'REPORTED' | 'UNKNOWN' | 'MIXED';
  provenance_unknown?: boolean;
  provenance_sources?: Array<{ authority: string; id: string; classification: string }>;
  currency_mismatches?: string[];
  date_from?: string | null;
  date_to?: string | null;
}
export interface FinancialProfitability {
  currency: string;
  rows: Array<Record<string, string | string[] | null>>;
  summary: FinancialSummary;
}
export interface FinancialSettlement {
  id: string;
  settlement_key: string;
  marketplace: string;
  expected_amount: string | null;
  reported_amount: string | null;
  verified_amount: string | null;
  difference_amount: string | null;
  currency: string;
  status: string;
  evidence_status: string;
  provenance: Record<string, unknown>;
  calculation_version: string;
}
export interface FinancialFees {
  currency: string;
  evidence_status: string;
  fees: Record<string, string>;
  missing_inputs: string[];
  calculation_version: string;
}
export interface FinancialAlert {
  severity: string;
  code: string;
  message: string;
}
export interface FinancialBusinessAgent {
  summary: FinancialSummary;
  actions: Array<{ type: string; label: string; reason: string }>;
  authority: string;
  external_writes: boolean;
  human_approval_required_for: string[];
}
export interface FinancialTrendPoint {
  date: string;
  gross_sales: string;
  discounts: string;
  refunds: string;
  fees: string;
  net_sales: string;
  evidence_status: string;
}
export interface FinancialRefundImpact {
  currency: string;
  total_refunds: string;
  refunds: Array<Record<string, string | null>>;
  evidence_status: string;
  basis: string;
}
export interface FinancialMarketplaceComparison {
  marketplace: string;
  evidence_status: string;
  gross_sales: string;
  net_sales: string;
  fees: string;
  contribution: string;
  estimated_profit: string | null;
  missing_inputs: string[];
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
  capabilities(): Promise<{ providers: MarketplaceCapability[]; external_writes: boolean }> {
    return firstValueFrom(
      this.http.get<{ providers: MarketplaceCapability[]; external_writes: boolean }>(
        `${this.baseUrl}/connectivity/capabilities`,
        this.options,
      ),
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
  connectivity(id: string): Promise<MarketplaceConnectivityStatus> {
    return firstValueFrom(
      this.http.get<MarketplaceConnectivityStatus>(
        `${this.baseUrl}/accounts/${id}/connectivity`,
        this.options,
      ),
    );
  }
  importJobs(id: string): Promise<MarketplaceImportJob[]> {
    return firstValueFrom(
      this.http.get<MarketplaceImportJob[]>(
        `${this.baseUrl}/accounts/${id}/import-jobs`,
        this.options,
      ),
    );
  }
  startImport(
    id: string,
    operation: 'catalog' | 'orders' | 'inventory' | 'financial',
    idempotencyKey: string,
  ): Promise<MarketplaceImportJob> {
    return firstValueFrom(
      this.http.post<MarketplaceImportJob>(
        `${this.baseUrl}/accounts/${id}/imports`,
        { operation, mode: 'SYNTHETIC', idempotency_key: idempotencyKey },
        this.options,
      ),
    );
  }
  reconciliation(id: string): Promise<MarketplaceReconciliation> {
    return firstValueFrom(
      this.http.get<MarketplaceReconciliation>(
        `${this.baseUrl}/accounts/${id}/reconciliation`,
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
  canonicalInventory(filters: { sku?: string; lowStock?: boolean } = {}): Promise<InventoryItem[]> {
    let params = new HttpParams();
    if (filters.sku) params = params.set('sku', filters.sku);
    if (filters.lowStock) params = params.set('low_stock', 'true');
    return firstValueFrom(
      this.http.get<InventoryItem[]>(`${environment.apiUrl}/inventory`, {
        ...this.options,
        params,
      }),
    );
  }
  adjustInventory(itemId: string, payload: InventoryAdjustment): Promise<InventoryItem> {
    return firstValueFrom(
      this.http.post<InventoryItem>(
        `${environment.apiUrl}/inventory/${itemId}/adjust`,
        payload,
        this.options,
      ),
    );
  }
  createInventoryItem(payload: InventoryOpeningRequest): Promise<InventoryItem> {
    return firstValueFrom(
      this.http
        .post<InventoryItem>(`${environment.apiUrl}/inventory/items`, payload, this.options)
        .pipe(timeout(20000)),
    );
  }
  inventoryLedger(itemId: string): Promise<InventoryMovement[]> {
    return firstValueFrom(
      this.http.get<InventoryMovement[]>(
        `${environment.apiUrl}/inventory/${itemId}/ledger`,
        this.options,
      ),
    );
  }
  inventoryMappings(): Promise<ChannelSkuMapping[]> {
    return firstValueFrom(
      this.http.get<ChannelSkuMapping[]>(`${environment.apiUrl}/inventory/mappings`, this.options),
    );
  }
  createInventoryMapping(payload: {
    account_id: string;
    inventory_item_id: string;
    external_sku: string;
    idempotency_key: string;
  }): Promise<ChannelSkuMapping> {
    return firstValueFrom(
      this.http.post<ChannelSkuMapping>(
        `${environment.apiUrl}/inventory/mappings`,
        payload,
        this.options,
      ),
    );
  }
  reconciliationSummary(): Promise<ReconciliationSummary> {
    return firstValueFrom(
      this.http.get<ReconciliationSummary>(
        `${environment.apiUrl}/orders/reconciliation/summary`,
        this.options,
      ),
    );
  }
  orders(): Promise<MarketplaceOrder[]> {
    return firstValueFrom(
      this.http.get<MarketplaceOrder[]>(`${this.baseUrl}/orders`, this.options),
    );
  }
  unifiedOrders(filters: { marketplace?: string; status?: string } = {}): Promise<UnifiedOrder[]> {
    let params = new HttpParams();
    if (filters.marketplace) params = params.set('marketplace', filters.marketplace);
    if (filters.status) params = params.set('status', filters.status);
    return firstValueFrom(
      this.http.get<UnifiedOrder[]>(`${environment.apiUrl}/orders`, {
        ...this.options,
        params,
      }),
    );
  }
  unifiedOrder(orderId: string): Promise<UnifiedOrder> {
    return firstValueFrom(
      this.http.get<UnifiedOrder>(`${environment.apiUrl}/orders/${orderId}`, this.options),
    );
  }
  unifiedInsights(): Promise<ReconciliationSummary> {
    return firstValueFrom(
      this.http.get<ReconciliationSummary>(`${environment.apiUrl}/orders/insights`, this.options),
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
  private financialParams(marketplace?: string, dateFrom?: string, dateTo?: string): HttpParams {
    let params = new HttpParams();
    if (marketplace) params = params.set('marketplace', marketplace);
    if (dateFrom) params = params.set('date_from', dateFrom);
    if (dateTo) params = params.set('date_to', dateTo);
    return params;
  }
  financialSummary(
    marketplace?: string,
    dateFrom?: string,
    dateTo?: string,
  ): Promise<FinancialSummary> {
    const params = this.financialParams(marketplace, dateFrom, dateTo);
    return firstValueFrom(
      this.http.get<FinancialSummary>(`${environment.apiUrl}/financial/summary`, {
        ...this.options,
        params,
      }),
    );
  }
  financialProfitability(
    marketplace?: string,
    dateFrom?: string,
    dateTo?: string,
  ): Promise<FinancialProfitability> {
    const params = this.financialParams(marketplace, dateFrom, dateTo);
    return firstValueFrom(
      this.http.get<FinancialProfitability>(`${environment.apiUrl}/financial/profitability`, {
        ...this.options,
        params,
      }),
    );
  }
  financialFees(marketplace?: string, dateFrom?: string, dateTo?: string): Promise<FinancialFees> {
    const params = this.financialParams(marketplace, dateFrom, dateTo);
    return firstValueFrom(
      this.http.get<FinancialFees>(`${environment.apiUrl}/financial/fees`, {
        ...this.options,
        params,
      }),
    );
  }
  financialSettlements(
    marketplace?: string,
    dateFrom?: string,
    dateTo?: string,
  ): Promise<{ rows: FinancialSettlement[]; count: number; synthetic_provider: boolean }> {
    const params = this.financialParams(marketplace, dateFrom, dateTo);
    return firstValueFrom(
      this.http.get<{ rows: FinancialSettlement[]; count: number; synthetic_provider: boolean }>(
        `${environment.apiUrl}/financial/settlements`,
        { ...this.options, params },
      ),
    );
  }
  financialAlerts(
    marketplace?: string,
    dateFrom?: string,
    dateTo?: string,
  ): Promise<{ alerts: FinancialAlert[]; evidence_status: string }> {
    const params = this.financialParams(marketplace, dateFrom, dateTo);
    return firstValueFrom(
      this.http.get<{ alerts: FinancialAlert[]; evidence_status: string }>(
        `${environment.apiUrl}/financial/alerts`,
        { ...this.options, params },
      ),
    );
  }
  financialRevenueTrends(
    marketplace?: string,
    dateFrom?: string,
    dateTo?: string,
  ): Promise<{ rows: FinancialTrendPoint[]; currency: string; basis: string }> {
    const params = this.financialParams(marketplace, dateFrom, dateTo);
    return firstValueFrom(
      this.http.get<{ rows: FinancialTrendPoint[]; currency: string; basis: string }>(
        `${environment.apiUrl}/financial/revenue-trends`,
        { ...this.options, params },
      ),
    );
  }
  financialMarketplaceComparison(
    dateFrom?: string,
    dateTo?: string,
  ): Promise<{ rows: FinancialMarketplaceComparison[]; currency: string; count: number }> {
    const params = this.financialParams(undefined, dateFrom, dateTo);
    return firstValueFrom(
      this.http.get<{ rows: FinancialMarketplaceComparison[]; currency: string; count: number }>(
        `${environment.apiUrl}/financial/marketplace-comparison`,
        { ...this.options, params },
      ),
    );
  }
  financialRefundImpact(
    marketplace?: string,
    dateFrom?: string,
    dateTo?: string,
  ): Promise<FinancialRefundImpact> {
    const params = this.financialParams(marketplace, dateFrom, dateTo);
    return firstValueFrom(
      this.http.get<FinancialRefundImpact>(`${environment.apiUrl}/financial/refund-impact`, {
        ...this.options,
        params,
      }),
    );
  }
  financialBusinessAgent(): Promise<FinancialBusinessAgent> {
    return firstValueFrom(
      this.http.get<FinancialBusinessAgent>(
        `${environment.apiUrl}/financial/business-agent`,
        this.options,
      ),
    );
  }
  static errorMessage(): string {
    return 'Marketplace data is unavailable. Check the API connection and try again.';
  }
}
