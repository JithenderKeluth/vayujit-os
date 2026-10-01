export type CommerceJourneyStageKey =
  | 'GOAL'
  | 'RESEARCH'
  | 'COMPARE'
  | 'SOURCE'
  | 'VERIFY'
  | 'ECONOMICS'
  | 'DECIDE'
  | 'LAUNCH';
export type CommerceJourneyStageStatus =
  | 'NOT_STARTED'
  | 'READY'
  | 'IN_PROGRESS'
  | 'COMPLETED'
  | 'BLOCKED'
  | 'NEEDS_REVIEW';

export interface CommerceJourneyStage {
  key: CommerceJourneyStageKey;
  label: string;
  status: CommerceJourneyStageStatus;
  route: string;
  entity_id?: string | null;
  reason?: string;
  blocking_prerequisites?: string[];
  completion_evidence?: Record<string, unknown>;
  next_action?: string | null;
}

export interface CommerceNextAction {
  code: string;
  title: string;
  detail: string;
  route: string;
  entity_id?: string | null;
  human_controlled: boolean;
}

export interface CommerceCommercialReadiness {
  id: string;
  readiness: {
    overall: string;
    calculations?: Record<string, { status: string; missing_inputs?: string[] }>;
    safe_next_action?: string;
    human_review_required?: boolean;
    economics_calculated?: boolean;
  };
  known_inputs: unknown[];
  claims: unknown[];
  assumptions: unknown[];
  unknown_inputs: unknown[];
  missing_inputs: unknown[];
  optional_gaps: unknown[];
  contradictions: unknown[];
  lineage: Record<string, unknown>;
}
export interface CommerceJourney {
  id: string;
  goal_id: string;
  status: string;
  stages: CommerceJourneyStage[];
  completed_stage_count: number;
  total_stage_count: number;
  next_action: CommerceNextAction;
  counts: Record<string, number>;
  context: { confirmed: boolean; values: Record<string, unknown> };
  context_confirmation: { required: boolean; source: string };
  trust?: { mode: string; label: string };
  remaining_requirements: string[];
  human_controlled: boolean;
  commercial_readiness?: CommerceCommercialReadiness | null;
}
