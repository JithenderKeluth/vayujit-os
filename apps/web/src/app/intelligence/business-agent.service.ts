import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

export interface BusinessAgentCapability {
  id: string;
  execution_class: string;
  side_effect_class: string;
  availability: string;
}

export interface BusinessAgentGoal {
  id: string;
  raw_goal: string;
  status: string;
  structured_goal: { marketplace?: string } & Record<string, unknown>;
}

export interface BusinessAgentPlan {
  id: string;
  version: number;
  steps: Array<{ step_key: string; capability_id: string }>;
}

export interface BusinessAgentRun {
  id: string;
  status: string;
  result?: {
    decision?: string;
    integrated_slices?: string[];
    review_enabled?: boolean;
    review_capabilities?: string[];
    review_evidence_gaps?: Array<Record<string, unknown>>;
    trend_enabled?: boolean;
    trend_capabilities?: string[];
    trend_evidence_gaps?: Array<Record<string, unknown>>;
    trend_intelligence?: Record<string, unknown>;
  } & Record<string, unknown>;
  artifacts?: Array<{ artifact_type: string; payload: Record<string, unknown> }>;
  findings?: Array<{ finding_type: string; value: Record<string, unknown> }>;
  tool_invocations?: Array<{ capability_id: string; status: string; side_effect_class: string }>;
}

export interface BusinessGoalCreatePayload {
  raw_goal: string;
  idempotency_key: string;
  structured_goal?: Record<string, unknown>;
}

export interface BusinessRunCreatePayload {
  idempotency_key: string;
  max_steps: number;
}

@Injectable({ providedIn: 'root' })
export class BusinessAgentService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/intelligence/business-agent`;

  capabilities(): Promise<BusinessAgentCapability[]> {
    return firstValueFrom(this.http.get<BusinessAgentCapability[]>(`${this.base}/capabilities`));
  }

  goals(): Promise<BusinessAgentGoal[]> {
    return firstValueFrom(this.http.get<BusinessAgentGoal[]>(`${this.base}/goals`));
  }

  createGoal(payload: BusinessGoalCreatePayload): Promise<BusinessAgentGoal> {
    return firstValueFrom(this.http.post<BusinessAgentGoal>(`${this.base}/goals`, payload));
  }

  plan(id: string): Promise<BusinessAgentPlan> {
    return firstValueFrom(this.http.post<BusinessAgentPlan>(`${this.base}/goals/${id}/plan`, {}));
  }

  createRun(id: string, payload: BusinessRunCreatePayload): Promise<BusinessAgentRun> {
    return firstValueFrom(
      this.http.post<BusinessAgentRun>(`${this.base}/goals/${id}/runs`, payload),
    );
  }

  start(id: string): Promise<BusinessAgentRun> {
    return firstValueFrom(this.http.post<BusinessAgentRun>(`${this.base}/runs/${id}/start`, {}));
  }
}
