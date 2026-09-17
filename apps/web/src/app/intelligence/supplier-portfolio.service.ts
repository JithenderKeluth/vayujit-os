import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

export type JsonMap = Record<string, unknown>;

export interface SupplierPortfolio {
  id: string;
  name: string;
  description: string;
  scope_type: string;
  scope_reference: string | null;
  status: string;
  current_assessment_version_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface PortfolioMember {
  id: string;
  portfolio_id: string;
  supplier_id: string;
  version: number;
  associated_products: string[];
  allocation_percent: string | number | null;
  evidence_freshness: string;
  confidence: string | number | null;
  risk: string | null;
  country_region: string | null;
  capabilities: string[];
  alternate_source_status: string;
  due_diligence_lineage_id: string | null;
  shortlist_lineage_id: string | null;
  sourcing_scenario_lineage_id: string | null;
}

export interface PortfolioAssessment {
  id: string;
  portfolio_id: string;
  version: number;
  status: string;
  idempotency_key: string;
  input_snapshot: JsonMap;
  created_at: string;
}

export interface PortfolioAnalysis {
  [key: string]: unknown;
  score?: number | null;
  classification?: string;
  evidence_status?: string;
  confidence_value?: number | null;
  confidence_classification?: string;
  explanation?: string;
  missing_evidence?: unknown[];
  limitations?: unknown[];
  dimensions?: PortfolioDimension[];
  risk?: JsonMap;
  confidence?: JsonMap;
  recommendations?: PortfolioRecommendation[];
}

export interface PortfolioDimension {
  dimension: string;
  score: number | null;
  classification: string;
  evidence_status: string;
  explanation: string;
  limitations: unknown[];
  missing_evidence: unknown[];
  calculation_version: string;
}

export interface PortfolioRecommendation {
  id: string;
  recommendation_type: string;
  priority: string;
  reason: string;
  status: string;
  affected_supplier_id: string | null;
  affected_product_id: string | null;
  affected_dependency_type: string | null;
  dimensions_affected: unknown[];
  evidence: unknown[];
  missing_evidence: unknown[];
  recommendation_version: string;
}

export interface PortfolioSimulation {
  id: string;
  simulation_type: string;
  status: string;
  staleness: string;
  assumptions: JsonMap;
  result: JsonMap;
  created_at: string;
}

export interface PortfolioProductChannel {
  events: JsonMap[];
  external_dispatch?: boolean;
  [key: string]: unknown;
}

export interface PortfolioOperations {
  [key: string]: unknown;
  portfolio_contexts: number;
  current_assessments: number;
  stale_assessments: number;
  low_resilience_portfolios: number;
  critical_dependencies: number;
  open_critical_recommendations: number;
  insufficient_evidence_portfolios: number;
  simulations: number;
  failed_simulations: number;
  stale_baseline_simulations: number;
  research_requests: number;
  due_diligence_requests: number;
  backup_scenario_requests: number;
  integrity_issues: number;
  drill_down: JsonMap;
}

export interface PortfolioCalendarItem {
  event_id: string;
  kind: string;
  title: string;
  status: string;
  due_at: string;
  source_ref: string;
  assessment_version_id: string | null;
}

export interface PortfolioDoctor {
  status: string;
  severity: string;
  integrity: Record<string, number>;
  configuration_warnings: string[];
  external_limitations: string[];
}

export interface PortfolioActionResult extends JsonMap {
  action: string;
  status: string;
  idempotent_reuse: boolean;
}

export interface PortfolioRecoveryResult extends JsonMap {
  action: string;
  status: string;
  idempotent_reuse: boolean;
}

@Injectable({ providedIn: 'root' })
export class SupplierPortfolioService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/intelligence/supplier-portfolios`;
  private readonly options = { withCredentials: true } as const;

  list(): Promise<SupplierPortfolio[]> {
    return firstValueFrom(this.http.get<SupplierPortfolio[]>(this.base, this.options));
  }

  detail(id: string): Promise<SupplierPortfolio> {
    return firstValueFrom(this.http.get<SupplierPortfolio>(`${this.base}/${id}`, this.options));
  }

  members(id: string): Promise<PortfolioMember[]> {
    return firstValueFrom(
      this.http.get<PortfolioMember[]>(`${this.base}/${id}/members`, this.options),
    );
  }

  assessment(id: string): Promise<PortfolioAssessment | { status: 'not_assessed' }> {
    return firstValueFrom(
      this.http.get<PortfolioAssessment | { status: 'not_assessed' }>(
        `${this.base}/${id}/assessment`,
        this.options,
      ),
    );
  }

  history(id: string): Promise<PortfolioAssessment[]> {
    return firstValueFrom(
      this.http.get<PortfolioAssessment[]>(`${this.base}/${id}/history`, this.options),
    );
  }

  concentration(id: string): Promise<JsonMap> {
    return firstValueFrom(this.http.get<JsonMap>(`${this.base}/${id}/concentration`, this.options));
  }

  dependencies(id: string): Promise<JsonMap> {
    return firstValueFrom(this.http.get<JsonMap>(`${this.base}/${id}/dependencies`, this.options));
  }

  alternates(id: string): Promise<JsonMap> {
    return firstValueFrom(this.http.get<JsonMap>(`${this.base}/${id}/alternates`, this.options));
  }

  resilience(id: string): Promise<PortfolioAnalysis> {
    return firstValueFrom(
      this.http.get<PortfolioAnalysis>(`${this.base}/${id}/resilience`, this.options),
    );
  }

  simulations(id: string): Promise<PortfolioSimulation[]> {
    return firstValueFrom(
      this.http.get<PortfolioSimulation[]>(`${this.base}/${id}/simulations`, this.options),
    );
  }

  createSimulation(id: string, payload: JsonMap): Promise<PortfolioSimulation> {
    return firstValueFrom(
      this.http.post<PortfolioSimulation>(`${this.base}/${id}/simulations`, payload, this.options),
    );
  }

  productChannel(id: string): Promise<PortfolioProductChannel> {
    return firstValueFrom(
      this.http.get<PortfolioProductChannel>(`${this.base}/${id}/product-channel`, this.options),
    );
  }

  events(id: string): Promise<JsonMap[]> {
    return firstValueFrom(this.http.get<JsonMap[]>(`${this.base}/${id}/events`, this.options));
  }

  operations(): Promise<PortfolioOperations> {
    return firstValueFrom(
      this.http.get<PortfolioOperations>(`${this.base}/operations`, this.options),
    );
  }

  calendar(): Promise<PortfolioCalendarItem[]> {
    return firstValueFrom(
      this.http.get<PortfolioCalendarItem[]>(`${this.base}/calendar`, this.options),
    );
  }

  doctor(): Promise<PortfolioDoctor> {
    return firstValueFrom(
      this.http.get<PortfolioDoctor>(`${this.base}/system-doctor`, this.options),
    );
  }

  action(id: string, payload: JsonMap): Promise<PortfolioActionResult> {
    return firstValueFrom(
      this.http.post<PortfolioActionResult>(`${this.base}/${id}/actions`, payload, this.options),
    );
  }

  recovery(id: string, payload: JsonMap): Promise<PortfolioRecoveryResult> {
    return firstValueFrom(
      this.http.post<PortfolioRecoveryResult>(`${this.base}/${id}/recovery`, payload, this.options),
    );
  }
}
