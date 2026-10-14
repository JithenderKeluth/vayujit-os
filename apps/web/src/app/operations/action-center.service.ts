import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

export type OperationalSignal = {
  id: string;
  signal_type: string;
  category: string;
  marketplace: string | null;
  severity: string;
  status: string;
  title: string;
  explanation: string;
  uncertainty: string | null;
  recommended_action: string;
  recommended_action_type: string;
  source_authority: string;
  source_resource_type: string;
  source_resource_id: string | null;
  source_route: string | null;
  evidence: Record<string, unknown>;
  evidence_quality: string;
  confidence: string;
  priority_score: string;
  observed_at: string;
  fresh_until: string | null;
  snoozed_until: string | null;
  updated_at: string;
};

export type ActionCenterResponse = {
  signals: OperationalSignal[];
  total: number;
  policy: OperationalPolicy;
  briefing: OperationalBriefing;
};

export type OperationalHistoryEntry = {
  from_status: string | null;
  to_status: string;
  actor_type: string;
  note: string | null;
  created_at: string;
};

export type OperationalPolicy = {
  enabled: boolean;
  dry_run: boolean;
  emergency_stop: boolean;
  severity_threshold: string;
  minimum_confidence: string;
  cooldown_seconds: number;
  maximum_actions_per_run: number;
  signal_types: Record<string, boolean>;
  notification_preferences: Record<string, boolean>;
  policy_version: string;
  updated_at: string;
};

export type OperationalBriefing = {
  generated_at: string;
  source: string;
  priorities: OperationalSignal[];
  counts: { active: number; critical: number; high: number; resolved: number };
  category_breakdown: Record<string, number>;
  changes_since_previous: string;
  read_only: boolean;
  external_writes: boolean;
};

@Injectable({ providedIn: 'root' })
export class ActionCenterService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/operations/action-center`;
  private readonly options = { withCredentials: true } as const;

  load(filters: Record<string, string | number | boolean | undefined> = {}): Promise<ActionCenterResponse> {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== '') params = params.set(key, value);
    }
    return firstValueFrom(this.http.get<ActionCenterResponse>(this.base, { ...this.options, params }));
  }

  scan(): Promise<{ status: string; signals_seen: number; scan_at: string; external_writes: boolean }> {
    return firstValueFrom(this.http.post<{ status: string; signals_seen: number; scan_at: string; external_writes: boolean }>(`${this.base}/scan`, {}, this.options));
  }

  briefing(): Promise<OperationalBriefing> {
    return firstValueFrom(this.http.get<OperationalBriefing>(`${this.base}/briefing`, this.options));
  }

  detail(id: string): Promise<{ signal: OperationalSignal; history: OperationalHistoryEntry[] }> {
    return firstValueFrom(this.http.get<{ signal: OperationalSignal; history: OperationalHistoryEntry[] }>(`${this.base}/signals/${id}`, this.options));
  }

  transition(id: string, action: 'acknowledge' | 'resolve' | 'reopen', note = ''): Promise<unknown> {
    return firstValueFrom(this.http.post(`${this.base}/signals/${id}/${action}`, { note, idempotency_key: `${action}:${id}:${Date.now()}` }, this.options));
  }

  snooze(id: string, until: string, note = ''): Promise<unknown> {
    return firstValueFrom(this.http.post(`${this.base}/signals/${id}/snooze`, { until, note, idempotency_key: `snooze:${id}:${until}` }, this.options));
  }

  policy(): Promise<OperationalPolicy> {
    return firstValueFrom(this.http.get<OperationalPolicy>(`${this.base}/policy`, this.options));
  }

  updatePolicy(value: Partial<OperationalPolicy>): Promise<OperationalPolicy> {
    return firstValueFrom(this.http.patch<OperationalPolicy>(`${this.base}/policy`, value, this.options));
  }

  requestAction(id: string, actionType: string): Promise<{ status: string; message: string; external_writes: boolean }> {
    return firstValueFrom(this.http.post<{ status: string; message: string; external_writes: boolean }>(`${this.base}/signals/${id}/action`, { action_type: actionType, actor_type: 'HUMAN', idempotency_key: `action:${id}:${actionType}` }, this.options));
  }
}
