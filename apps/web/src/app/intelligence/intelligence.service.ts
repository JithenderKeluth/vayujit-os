import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

export interface IntelligenceOverview {
  active_projects: number;
  recent_runs: number;
  opportunities: Record<string, number>;
  hard_blocked_candidates: number;
  evidence_freshness: Record<string, number>;
  enabled_sources: number;
  source_health: Record<string, number>;
  rule_counts: Record<string, number>;
  recent_failures: number;
}

export interface IntelligenceProject {
  id: string;
  name: string;
  description: string;
  status: string;
  target_market: string;
  target_categories: string[];
  risk_profile: string;
  updated_at: string;
}

export interface IntelligenceSource {
  id: string;
  display_name: string;
  source_type: string;
  provider: string;
  access_method: string;
  enabled: boolean;
  trust_classification: string;
  configuration_status: string;
  failure_status: string | null;
}

export interface IntelligenceCandidate {
  id: string;
  title: string;
  category: string;
  subcategory: string;
  market: string;
  status: string;
  observed_price: number | null;
  currency: string;
  source_reference: string;
  freshness_state: string;
  normalized_title?: string;
  observed_brand?: string | null;
  attributes?: Record<string, unknown>;
  evidence_count?: number;
  score?: number | null;
  recommendation?: string;
}
export interface IntelligenceMission {
  id: string;
  project_id: string;
  name: string;
  enabled: boolean;
  frequency: string;
  market: string;
  categories: string[];
  status: string;
  minimum_score_threshold: number;
  last_run_at: string | null;
  profile_id?: string | null;
  timezone?: string;
  ruleset_version?: string;
  next_run_at?: string | null;
  last_run_id?: string | null;
  last_result?: string | null;
}

export interface IntelligenceMissionRun {
  id: string;
  mission_id?: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  provider_mode?: string;
  failure_code?: string | null;
  candidate_count?: number;
  opportunity_count?: number;
  blocked_count?: number;
  score_model_version?: string;
  ruleset_version?: string;
}
export interface IntelligenceProfile {
  id: string;
  name: string;
  market: string;
  currency: string;
  min_selling_price: number | null;
  max_selling_price: number | null;
  max_sourcing_estimate: number | null;
  minimum_margin: number | null;
  max_weight_kg: number | null;
  max_length_cm: number | null;
  max_width_cm: number | null;
  max_height_cm: number | null;
  categories: string[];
  excluded_categories: string[];
  competition_tolerance: string;
  risk_tolerance: string;
}

export interface IntelligenceRule {
  id: string;
  category_id?: string;
  name: string;
  description?: string;
  enabled: boolean;
  threshold?: number | null;
  severity?: string;
  action?: string;
  hard_block?: boolean;
  priority?: number;
  scope?: string;
}

export interface IntelligenceEvidence {
  id: string;
  source_id?: string;
  source_reference?: string;
  source_type?: string;
  observed_at?: string;
  retrieved_at?: string;
  freshness?: string;
  verification_status?: string;
  content_hash?: string;
  normalized_value?: Record<string, unknown>;
  excerpt?: string;
}

export interface IntelligenceHistory {
  runs: IntelligenceMissionRun[];
  score_evaluations?: Record<string, unknown>[];
  reports?: IntelligenceReport[];
  recovery?: Record<string, unknown>[];
}
export interface IntelligenceReport {
  id: string;
  run_id: string;
  format: string;
  title: string;
  content: string;
  provenance_json: Record<string, unknown>;
  created_at?: string;
  report_version?: string;
  score_model_version?: string;
  ruleset_version?: string;
  evidence_count?: number;
  assumption_count?: number;
}
export interface IntelligenceOpportunity {
  id: string;
  title: string;
  category: string;
  market: string;
  status: string;
  score: number;
  confidence: number;
  hard_blocked: boolean;
  evidence_count: number;
  freshness_state: string;
  primary_reasons: string[];
  risk_summary?: string;
  trend_state?: string;
  competition?: string;
  estimated_economics?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

export interface IntelligenceSupplier {
  id: string;
  display_name: string;
  legal_name: string | null;
  supplier_type: string;
  country_code: string | null;
  country: string | null;
  region?: string | null;
  city?: string | null;
  website?: string | null;
  source_identity: string;
  normalized_identity: string;
  is_offline: boolean;
  verification_state: string;
  communication_status: string;
  score?: number | null;
  recommendation?: string | null;
  risk?: Record<string, unknown>;
  offering_count?: number;
  evidence_count?: number;
  shortlist_state?: string | null;
  [key: string]: unknown;
}

export interface IntelligenceSupplierOverview {
  supplier_count: number;
  verified_count: number;
  unverified_count: number;
  shortlisted_count: number;
  high_risk_count: number;
  stale_count: number;
  recent_searches: number;
  recent_failures: number;
  provider_mode: string;
  external_connectors: Record<string, string>;
}

export interface AutonomousResearchOverview {
  active_missions: number;
  queued_tasks: number;
  completed_missions: number;
  partial_missions: number;
  failed_missions: number;
  contradictions: number;
  recovery: number;
  external_research: string;
  ai_mode: string;
}

export type ExternalRecord = Record<string, unknown>;

export interface ExternalResearchPolicy {
  provider: string;
  mode: string;
  status: string;
  search_enabled: boolean;
  fetch_enabled: boolean;
  kill_switch: boolean;
  provider_kill_switch: boolean;
  approved_domains_configured: boolean;
  credentials_configured: boolean;
  credential_status?: 'CONFIGURED' | 'NOT_CONFIGURED' | 'INVALID' | 'UNKNOWN';
}
export interface WebsiteOverview {
  manufacturer_candidates: number;
  supplier_websites: number;
  offering_count: number;
  last_researched: string | null;
  status: string;
  queue: number;
  running: number;
  failed: number;
  refresh_backlog: number;
  stale_sources: number;
  expired_sources: number;
  high_risk_suppliers: number;
  unresolved_contradictions: number;
  recovery: number;
}

export interface WebsiteManufacturer {
  id: string;
  name: string;
  website: string;
  domain: string;
  country: string;
  region: string;
  business_type: string;
  verification: string;
  freshness: string;
  confidence: number;
  risk: string[];
  source_count: number;
  evidence_count: number;
}

export interface WebsiteContradiction {
  [key: string]: unknown;
  id: string;
  field?: string;
  resolution_state?: string;
  correlation_id?: string;
}
export interface WebsiteChange {
  [key: string]: unknown;
  id: string;
  field?: string;
  materiality?: string;
  correlation_id?: string;
}
export interface WebsiteAlert {
  [key: string]: unknown;
  id: string;
  type?: string;
  severity?: string;
  review_state?: string;
  correlation_id?: string;
}
export interface WebsiteReport {
  [key: string]: unknown;
  id: string;
  mission_id?: string;
  format?: string;
  status?: string;
  content?: string;
}
export interface WebsiteSourceProfile {
  id: string;
  domain: string;
  display_name: string;
  source_type: string;
  classification: string;
  enabled: boolean;
  search_allowed: boolean;
  fetch_allowed: boolean;
  freshness_policy: string;
  verification_policy: string;
  robots_terms_status: string;
  refresh_target_type: string;
  timezone: string;
  next_refresh_at: string | null;
  last_refresh_at: string | null;
  last_success_at: string | null;
  last_failure_at: string | null;
  refresh_failure_code: string | null;
  known_mirror_domains: string[];
  notes: string;
}

export interface WebsiteRefreshJob {
  id: string;
  source_profile_id: string;
  target_type: string;
  scheduled_for: string;
  status: string;
  failure_code: string | null;
  mission_id: string | null;
}

export interface WebsiteCalendarEvent {
  id: string;
  type: string;
  target_type: string;
  source_profile_id: string;
  domain: string;
  frequency: string;
  scheduled_at: string;
  timezone: string;
  status: string;
}
@Injectable({ providedIn: 'root' })
export class IntelligenceService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/intelligence`;
  private readonly options = { withCredentials: true } as const;

  overview(): Promise<IntelligenceOverview> {
    return firstValueFrom(
      this.http.get<IntelligenceOverview>(`${this.base}/overview`, this.options),
    );
  }

  projects(): Promise<IntelligenceProject[]> {
    return firstValueFrom(
      this.http.get<IntelligenceProject[]>(`${this.base}/projects`, this.options),
    );
  }

  sources(): Promise<IntelligenceSource[]> {
    return firstValueFrom(
      this.http.get<IntelligenceSource[]>(`${this.base}/sources`, this.options),
    );
  }

  opportunities(): Promise<IntelligenceOpportunity[]> {
    return firstValueFrom(
      this.http.get<IntelligenceOpportunity[]>(`${this.base}/opportunities`, this.options),
    );
  }

  candidates(filters?: {
    status?: string;
    market?: string;
    category?: string;
  }): Promise<IntelligenceCandidate[]> {
    const params = new URLSearchParams();
    if (filters?.status) params.set('status', filters.status);
    if (filters?.market) params.set('market', filters.market);
    if (filters?.category) params.set('category', filters.category);
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return firstValueFrom(
      this.http.get<IntelligenceCandidate[]>(`${this.base}/candidates${suffix}`, this.options),
    );
  }

  missions(): Promise<IntelligenceMission[]> {
    return firstValueFrom(
      this.http.get<IntelligenceMission[]>(`${this.base}/missions`, this.options),
    );
  }

  runMission(id: string): Promise<{ id: string; status: string }> {
    return firstValueFrom(
      this.http.post<{ id: string; status: string }>(
        `${this.base}/missions/${id}/run-now`,
        {},
        this.options,
      ),
    );
  }

  report(
    runId: string,
    format: 'json' | 'markdown' | 'html' = 'markdown',
  ): Promise<IntelligenceReport> {
    return firstValueFrom(
      this.http.post<IntelligenceReport>(
        `${this.base}/runs/${runId}/reports?format=${format}`,
        {},
        this.options,
      ),
    );
  }
  createMission(payload: {
    project_id: string;
    profile_id?: string | null;
    name: string;
    frequency: string;
    timezone: string;
    market: string;
    categories: string[];
    ruleset_version: string;
    minimum_score_threshold: number;
    notification_threshold: number;
  }): Promise<IntelligenceMission> {
    return firstValueFrom(
      this.http.post<IntelligenceMission>(this.base + '/missions', payload, this.options),
    );
  }

  updateMission(id: string, payload: Partial<IntelligenceMission>): Promise<IntelligenceMission> {
    return firstValueFrom(
      this.http.patch<IntelligenceMission>(this.base + '/missions/' + id, payload, this.options),
    );
  }

  pauseMission(id: string): Promise<IntelligenceMission> {
    return firstValueFrom(
      this.http.post<IntelligenceMission>(
        this.base + '/missions/' + id + '/pause',
        {},
        this.options,
      ),
    );
  }

  resumeMission(id: string): Promise<IntelligenceMission> {
    return firstValueFrom(
      this.http.post<IntelligenceMission>(
        this.base + '/missions/' + id + '/resume',
        {},
        this.options,
      ),
    );
  }

  scheduleMission(
    id: string,
    payload: { frequency: string; timezone: string },
  ): Promise<IntelligenceMission> {
    return firstValueFrom(
      this.http.post<IntelligenceMission>(
        this.base + '/missions/' + id + '/schedule',
        payload,
        this.options,
      ),
    );
  }

  missionRuns(projectId: string): Promise<IntelligenceMissionRun[]> {
    return firstValueFrom(
      this.http.get<IntelligenceMissionRun[]>(
        this.base + '/projects/' + projectId + '/runs',
        this.options,
      ),
    );
  }

  runCandidates(runId: string): Promise<IntelligenceCandidate[]> {
    return firstValueFrom(
      this.http.get<IntelligenceCandidate[]>(
        this.base + '/runs/' + runId + '/candidates',
        this.options,
      ),
    );
  }

  history(runId: string): Promise<IntelligenceHistory> {
    return firstValueFrom(
      this.http.get<IntelligenceHistory>(this.base + '/runs/' + runId + '/history', this.options),
    );
  }

  candidate(id: string): Promise<IntelligenceCandidate> {
    return firstValueFrom(
      this.http.get<IntelligenceCandidate>(this.base + '/candidates/' + id, this.options),
    );
  }

  signals(id: string): Promise<Record<string, unknown>[]> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>[]>(
        this.base + '/candidates/' + id + '/signals',
        this.options,
      ),
    );
  }

  trends(id: string): Promise<Record<string, unknown>[]> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>[]>(
        this.base + '/candidates/' + id + '/trends',
        this.options,
      ),
    );
  }

  opportunity(id: string): Promise<IntelligenceOpportunity & Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<IntelligenceOpportunity & Record<string, unknown>>(
        this.base + '/opportunities/' + id,
        this.options,
      ),
    );
  }

  profiles(): Promise<IntelligenceProfile[]> {
    return firstValueFrom(
      this.http.get<IntelligenceProfile[]>(this.base + '/profiles', this.options),
    );
  }

  createProfile(payload: Record<string, unknown>): Promise<IntelligenceProfile> {
    return firstValueFrom(
      this.http.post<IntelligenceProfile>(this.base + '/profiles', payload, this.options),
    );
  }

  rules(): Promise<IntelligenceRule[]> {
    return firstValueFrom(this.http.get<IntelligenceRule[]>(this.base + '/rules', this.options));
  }

  ruleCategories(): Promise<Record<string, unknown>[]> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>[]>(this.base + '/rules/categories', this.options),
    );
  }

  compare(candidateIds: string[]): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        this.base + '/compare',
        { candidate_ids: candidateIds },
        this.options,
      ),
    );
  }

  simulateRules(
    candidateIds: string[],
    minimumScoreThreshold = 45,
  ): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        this.base + '/rules/simulate',
        { candidate_ids: candidateIds, minimum_score_threshold: minimumScoreThreshold },
        this.options,
      ),
    );
  }

  evidence(): Promise<IntelligenceEvidence[]> {
    return firstValueFrom(
      this.http.get<IntelligenceEvidence[]>(this.base + '/evidence', this.options),
    );
  }

  evidenceDetail(id: string): Promise<IntelligenceEvidence> {
    return firstValueFrom(
      this.http.get<IntelligenceEvidence>(this.base + '/evidence/' + id, this.options),
    );
  }

  reportById(id: string): Promise<IntelligenceReport> {
    return firstValueFrom(
      this.http.get<IntelligenceReport>(this.base + '/reports/' + id, this.options),
    );
  }

  supplierOverview(): Promise<IntelligenceSupplierOverview> {
    return firstValueFrom(
      this.http.get<IntelligenceSupplierOverview>(`${this.base}/suppliers/overview`, this.options),
    );
  }

  suppliers(filters?: {
    source?: string;
    country?: string;
    verification?: string;
    offline?: boolean;
  }): Promise<IntelligenceSupplier[]> {
    const params = new URLSearchParams();
    if (filters?.source) params.set('source', filters.source);
    if (filters?.country) params.set('country', filters.country);
    if (filters?.verification) params.set('verification', filters.verification);
    if (filters?.offline !== undefined) params.set('offline', String(filters.offline));
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return firstValueFrom(
      this.http.get<IntelligenceSupplier[]>(`${this.base}/suppliers${suffix}`, this.options),
    );
  }

  supplier(id: string): Promise<IntelligenceSupplier> {
    return firstValueFrom(
      this.http.get<IntelligenceSupplier>(`${this.base}/suppliers/${id}`, this.options),
    );
  }

  supplierSearch(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/suppliers/searches`,
        payload,
        this.options,
      ),
    );
  }

  runSupplierSearch(id: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/suppliers/searches/${id}/run`,
        {},
        this.options,
      ),
    );
  }

  createManualSupplier(payload: Record<string, unknown>): Promise<IntelligenceSupplier> {
    return firstValueFrom(
      this.http.post<IntelligenceSupplier>(`${this.base}/suppliers/manual`, payload, this.options),
    );
  }

  decideSupplier(id: string, decision: string, reason: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/suppliers/${id}/decisions`,
        { decision, reason },
        this.options,
      ),
    );
  }

  verifySupplier(id: string, state: string, reason: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/suppliers/${id}/verification`,
        { state, reason },
        this.options,
      ),
    );
  }

  compareSuppliers(ids: string[]): Promise<IntelligenceSupplier[]> {
    return firstValueFrom(
      this.http.post<IntelligenceSupplier[]>(
        `${this.base}/suppliers/compare`,
        { supplier_ids: ids },
        this.options,
      ),
    );
  }

  supplierReport(id: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(`${this.base}/suppliers/${id}/report`, this.options),
    );
  }
  createProject(payload: {
    name: string;
    description: string;
    target_market: string;
  }): Promise<IntelligenceProject> {
    return firstValueFrom(
      this.http.post<IntelligenceProject>(`${this.base}/projects`, payload, this.options),
    );
  }

  sourcingOverview(): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(`${this.base}/sourcing/overview`, this.options),
    );
  }
  createSourcingRequirement(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/sourcing/requirements`,
        payload,
        this.options,
      ),
    );
  }
  sourcingRequirements(): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(`${this.base}/sourcing/requirements`, this.options),
    );
  }
  createRFQ(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(`${this.base}/sourcing/rfqs`, payload, this.options),
    );
  }
  sourcingQuotes(): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(`${this.base}/sourcing/quotes`, this.options),
    );
  }
  createSourcingQuote(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/sourcing/quotes`,
        payload,
        this.options,
      ),
    );
  }
  compareSourcingQuotes(rfqId: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(
        `${this.base}/sourcing/rfqs/${rfqId}/compare`,
        this.options,
      ),
    );
  }
  createSampleRequest(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/sourcing/samples`,
        payload,
        this.options,
      ),
    );
  }
  sourcingSamples(): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(`${this.base}/sourcing/samples`, this.options),
    );
  }
  createCostScenario(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/sourcing/scenarios`,
        payload,
        this.options,
      ),
    );
  }
  sourcingRFQVersions(rfqId: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(
        `${this.base}/sourcing/rfqs/${rfqId}/versions`,
        this.options,
      ),
    );
  }
  reviseSourcingRFQ(
    rfqId: string,
    payload: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/sourcing/rfqs/${rfqId}/versions`,
        { payload },
        this.options,
      ),
    );
  }
  sourcingCalendar(): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(`${this.base}/sourcing/calendar`, this.options),
    );
  }
  sourcingHistory(): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(`${this.base}/sourcing/history/unified`, this.options),
    );
  }
  sourcingReport(format: 'json' | 'markdown' | 'html'): Promise<unknown> {
    return firstValueFrom(
      this.http.get<unknown>(`${this.base}/sourcing/report/${format}`, this.options),
    );
  }
  evaluateSourcingScore(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/sourcing/scores/evaluate`,
        payload,
        this.options,
      ),
    );
  }
  calculateSourcingSensitivity(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/sourcing/economics/sensitivity`,
        payload,
        this.options,
      ),
    );
  }
  calculateSourcingCapital(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/sourcing/economics/capital`,
        payload,
        this.options,
      ),
    );
  }
  autonomousOverview(): Promise<AutonomousResearchOverview> {
    return firstValueFrom(
      this.http.get<AutonomousResearchOverview>(`${this.base}/autonomous/overview`, this.options),
    );
  }

  autonomousPolicy(): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(`${this.base}/autonomous/policy`, this.options),
    );
  }

  externalPolicy(): Promise<ExternalResearchPolicy> {
    return firstValueFrom(
      this.http.get<ExternalResearchPolicy>(`${this.base}/external/policy`, this.options),
    );
  }

  externalPreflight(): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(`${this.base}/external/preflight`, this.options),
    );
  }
  externalStatus(): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(`${this.base}/external/status`, this.options),
    );
  }

  externalSearch(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/external/search`,
        payload,
        this.options,
      ),
    );
  }

  externalFetch(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(`${this.base}/external/fetch`, payload, this.options),
    );
  }

  externalSearches(): Promise<ExternalRecord[]> {
    return firstValueFrom(
      this.http.get<ExternalRecord[]>(`${this.base}/external/searches`, this.options),
    );
  }

  externalResults(searchId?: string): Promise<ExternalRecord[]> {
    const suffix = searchId ? `?search_id=${encodeURIComponent(searchId)}` : '';
    return firstValueFrom(
      this.http.get<ExternalRecord[]>(`${this.base}/external/results${suffix}`, this.options),
    );
  }

  externalFetches(): Promise<ExternalRecord[]> {
    return firstValueFrom(
      this.http.get<ExternalRecord[]>(`${this.base}/external/fetches`, this.options),
    );
  }

  externalEvidence(): Promise<ExternalRecord[]> {
    return firstValueFrom(
      this.http.get<ExternalRecord[]>(`${this.base}/external/evidence`, this.options),
    );
  }

  externalHistory(): Promise<ExternalRecord> {
    return firstValueFrom(
      this.http.get<ExternalRecord>(`${this.base}/external/history`, this.options),
    );
  }

  externalTables(): Promise<ExternalRecord[]> {
    return firstValueFrom(
      this.http.get<ExternalRecord[]>(`${this.base}/external/tables`, this.options),
    );
  }

  externalIntegrity(): Promise<ExternalRecord> {
    return firstValueFrom(
      this.http.get<ExternalRecord>(`${this.base}/external/integrity`, this.options),
    );
  }

  externalPerformance(): Promise<ExternalRecord> {
    return firstValueFrom(
      this.http.get<ExternalRecord>(`${this.base}/external/performance`, this.options),
    );
  }

  externalProductChannel(productId: string): Promise<ExternalRecord> {
    return firstValueFrom(
      this.http.get<ExternalRecord>(
        `${this.base}/external/products/${encodeURIComponent(productId)}/channel`,
        this.options,
      ),
    );
  }

  externalCalendar(): Promise<ExternalRecord[]> {
    return firstValueFrom(
      this.http.get<ExternalRecord[]>(`${this.base}/external/calendar`, this.options),
    );
  }

  externalAlerts(): Promise<ExternalRecord[]> {
    return firstValueFrom(
      this.http.get<ExternalRecord[]>(`${this.base}/external/alerts`, this.options),
    );
  }

  externalRecoveryCatalog(): Promise<ExternalRecord> {
    return firstValueFrom(
      this.http.get<ExternalRecord>(`${this.base}/external/recovery/catalog`, this.options),
    );
  }

  externalExecutions(): Promise<ExternalRecord[]> {
    return firstValueFrom(
      this.http.get<ExternalRecord[]>(`${this.base}/external/executions`, this.options),
    );
  }

  externalRecovery(payload: Record<string, unknown>): Promise<ExternalRecord> {
    return firstValueFrom(
      this.http.post<ExternalRecord>(`${this.base}/external/recovery`, payload, this.options),
    );
  }

  websiteOverview(): Promise<WebsiteOverview> {
    return firstValueFrom(
      this.http.get<WebsiteOverview>(`${this.base}/websites/overview`, this.options),
    );
  }

  websiteManufacturers(filters?: {
    country?: string;
    region?: string;
    category?: string;
    verification?: string;
    freshness?: string;
    min_confidence?: string;
    risk?: string;
    business_type?: string;
    status?: string;
  }): Promise<WebsiteManufacturer[]> {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(filters ?? {})) {
      if (value) params.set(key, value);
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return firstValueFrom(
      this.http.get<WebsiteManufacturer[]>(
        `${this.base}/websites/manufacturers${suffix}`,
        this.options,
      ),
    );
  }

  websiteSuppliers(): Promise<Record<string, unknown>[]> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>[]>(`${this.base}/websites/suppliers`, this.options),
    );
  }

  websiteManufacturer(id: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(
        `${this.base}/websites/manufacturers/${id}`,
        this.options,
      ),
    );
  }

  websiteProfiles(): Promise<{ profiles: WebsiteSourceProfile[]; status: string }> {
    return firstValueFrom(
      this.http.get<{ profiles: WebsiteSourceProfile[]; status: string }>(
        `${this.base}/websites/profiles`,
        this.options,
      ),
    );
  }

  websiteHistory(): Promise<Record<string, unknown>[]> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>[]>(`${this.base}/websites/history`, this.options),
    );
  }

  websiteContradictions(filters?: Record<string, string>): Promise<WebsiteContradiction[]> {
    return firstValueFrom(
      this.http.get<WebsiteContradiction[]>(
        `${this.base}/websites/contradictions${this.query(filters)}`,
        this.options,
      ),
    );
  }
  websiteContradiction(id: string): Promise<WebsiteContradiction> {
    return firstValueFrom(
      this.http.get<WebsiteContradiction>(
        `${this.base}/websites/contradictions/${encodeURIComponent(id)}`,
        this.options,
      ),
    );
  }
  websiteChanges(filters?: Record<string, string>): Promise<WebsiteChange[]> {
    return firstValueFrom(
      this.http.get<WebsiteChange[]>(
        `${this.base}/websites/changes${this.query(filters)}`,
        this.options,
      ),
    );
  }
  websiteChange(id: string): Promise<WebsiteChange> {
    return firstValueFrom(
      this.http.get<WebsiteChange>(
        `${this.base}/websites/changes/${encodeURIComponent(id)}`,
        this.options,
      ),
    );
  }
  websiteAlerts(filters?: Record<string, string>): Promise<WebsiteAlert[]> {
    return firstValueFrom(
      this.http.get<WebsiteAlert[]>(
        `${this.base}/websites/alerts${this.query(filters)}`,
        this.options,
      ),
    );
  }
  websiteAlert(id: string): Promise<WebsiteAlert> {
    return firstValueFrom(
      this.http.get<WebsiteAlert>(
        `${this.base}/websites/alerts/${encodeURIComponent(id)}`,
        this.options,
      ),
    );
  }
  websiteReports(): Promise<WebsiteReport[]> {
    return firstValueFrom(
      this.http.get<WebsiteReport[]>(`${this.base}/websites/reports`, this.options),
    );
  }
  websiteReport(id: string): Promise<WebsiteReport> {
    return firstValueFrom(
      this.http.get<WebsiteReport>(
        `${this.base}/websites/reports/${encodeURIComponent(id)}`,
        this.options,
      ),
    );
  }
  websiteProductChannel(productId: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(
        `${this.base}/websites/product-channel/${encodeURIComponent(productId)}`,
        this.options,
      ),
    );
  }
  websiteHistoryFiltered(filters?: Record<string, string>): Promise<Record<string, unknown>[]> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>[]>(
        `${this.base}/websites/history${this.query(filters)}`,
        this.options,
      ),
    );
  }
  private query(filters?: Record<string, string>): string {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(filters ?? {})) if (value) params.set(key, value);
    const suffix = params.toString();
    return suffix ? `?${suffix}` : '';
  }
  websiteRefreshJobs(): Promise<WebsiteRefreshJob[]> {
    return firstValueFrom(
      this.http.get<WebsiteRefreshJob[]>(`${this.base}/websites/refresh/jobs`, this.options),
    );
  }

  websiteCalendar(): Promise<WebsiteCalendarEvent[]> {
    return firstValueFrom(
      this.http.get<WebsiteCalendarEvent[]>(`${this.base}/websites/calendar`, this.options),
    );
  }

  websiteRecoveryCatalog(): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(
        `${this.base}/websites/refresh/recovery/catalog`,
        this.options,
      ),
    );
  }

  runWebsiteRefresh(id: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/websites/refresh/jobs/${id}/run`,
        {},
        this.options,
      ),
    );
  }

  recoverWebsiteRefresh(
    id: string,
    payload: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/websites/refresh/jobs/${id}/recover`,
        payload,
        this.options,
      ),
    );
  }
  autonomousMissions(): Promise<Record<string, unknown>[]> {
    return firstValueFrom(
      this.http.get<Record<string, unknown>[]>(`${this.base}/autonomous/missions`, this.options),
    );
  }

  createAutonomousMission(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/autonomous/missions`,
        payload,
        this.options,
      ),
    );
  }

  runAutonomousMission(id: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/autonomous/missions/${id}/run`,
        { confirm: true },
        this.options,
      ),
    );
  }
  createSourcingDecision(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/sourcing/decisions`,
        payload,
        this.options,
      ),
    );
  }
}
