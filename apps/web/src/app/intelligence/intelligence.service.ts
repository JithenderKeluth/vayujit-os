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

  createProject(payload: {
    name: string;
    description: string;
    target_market: string;
  }): Promise<IntelligenceProject> {
    return firstValueFrom(
      this.http.post<IntelligenceProject>(`${this.base}/projects`, payload, this.options),
    );
  }
}
