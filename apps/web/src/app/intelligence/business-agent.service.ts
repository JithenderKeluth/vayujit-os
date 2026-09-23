import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

export type BusinessAgentJson = Record<string, unknown>;

export interface BusinessAgentCapability {
  id: string;
  version: string;
  input_schema: string;
  output_schema: string;
  execution_class: string;
  side_effect_class: string;
  approval_required: boolean;
  provider_required: boolean;
  availability: string;
  health: string;
}

export interface BusinessAgentGoal {
  id: string;
  raw_goal: string;
  status: string;
  structured_goal: {
    marketplace?: string;
    include_competitor_intelligence?: boolean;
    include_review_intelligence?: boolean;
    include_trend_intelligence?: boolean;
  } & BusinessAgentJson;
  provenance: BusinessAgentJson;
  assumptions: string[];
  unresolved_questions: string[];
  extraction_version: string;
  idempotency_key: string;
  created_at: string;
  updated_at: string;
}

export interface BusinessAgentPlanStep {
  key: string;
  capability_id: string;
  dependencies: string[];
  execution_mode: string;
  side_effect_class: string;
  status: string;
}

export interface BusinessAgentPlan {
  id: string;
  goal_id: string;
  version: number;
  status: string;
  planner: string;
  plan_hash: string;
  steps: BusinessAgentPlanStep[];
}

export interface BusinessAgentApproval {
  id: string;
  run_id: string;
  step_id: string | null;
  status: string;
  reason: string;
  decision_note: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface BusinessAgentRunStep {
  id: string;
  key: string;
  capability_id: string;
  status: string;
  attempt_count: number;
  result: BusinessAgentJson;
}

export interface BusinessAgentArtifact {
  id: string;
  artifact_type: string;
  payload: BusinessAgentJson;
  provenance: BusinessAgentJson;
  created_at: string;
}

export interface BusinessAgentFinding {
  id: string;
  finding_type: string;
  value: BusinessAgentJson;
  evidence_ids: string[];
  confidence: number;
  created_at: string;
}

export interface BusinessAgentToolInvocation {
  id: string;
  step_id: string;
  capability_id: string;
  status: string;
  side_effect_class: string;
  input_hash: string;
  output_hash: string;
  created_at: string;
}

export interface BusinessAgentRun {
  id: string;
  goal_id: string;
  plan_id: string;
  status: string;
  idempotency_key: string;
  correlation_id: string;
  budget: BusinessAgentJson;
  usage: BusinessAgentJson;
  result: BusinessAgentJson;
  failure: BusinessAgentJson;
  checkpoint: BusinessAgentJson;
  approvals: BusinessAgentApproval[];
  steps: BusinessAgentRunStep[];
  artifacts: BusinessAgentArtifact[];
  findings: BusinessAgentFinding[];
  tool_invocations: BusinessAgentToolInvocation[];
}

export interface BusinessGoalCreatePayload {
  raw_goal: string;
  idempotency_key: string;
  structured_goal?: BusinessAgentJson;
  include_trend_intelligence?: boolean;
}

export interface BusinessRunCreatePayload {
  idempotency_key: string;
  max_steps: number;
  max_provider_calls?: number;
  max_elapsed_seconds?: number;
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

  run(id: string): Promise<BusinessAgentRun> {
    return firstValueFrom(this.http.get<BusinessAgentRun>(`${this.base}/runs/${id}`));
  }

  pause(id: string): Promise<BusinessAgentRun> {
    return firstValueFrom(this.http.post<BusinessAgentRun>(`${this.base}/runs/${id}/pause`, {}));
  }

  resume(id: string): Promise<BusinessAgentRun> {
    return firstValueFrom(this.http.post<BusinessAgentRun>(`${this.base}/runs/${id}/resume`, {}));
  }

  cancel(id: string): Promise<BusinessAgentRun> {
    return firstValueFrom(this.http.post<BusinessAgentRun>(`${this.base}/runs/${id}/cancel`, {}));
  }

  retry(id: string): Promise<BusinessAgentRun> {
    return firstValueFrom(this.http.post<BusinessAgentRun>(`${this.base}/runs/${id}/retry`, {}));
  }

  approve(id: string, note: string): Promise<BusinessAgentApproval> {
    return firstValueFrom(
      this.http.post<BusinessAgentApproval>(`${this.base}/approvals/${id}/approve`, { note }),
    );
  }

  reject(id: string, note: string): Promise<BusinessAgentApproval> {
    return firstValueFrom(
      this.http.post<BusinessAgentApproval>(`${this.base}/approvals/${id}/reject`, { note }),
    );
  }
}
