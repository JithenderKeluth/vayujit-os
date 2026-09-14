/** Decision support only. Decimal amounts remain strings; never coerce to binary floats. */
export interface SourcingScenarioResult {
  classification: string;
  status: string;
  missing_dimensions: string[];
  warnings: string[];
  currency: string;
  cost: { total_landed_cost: string; landed_cost_per_unit: string } | null;
  capital: { estimated_total_initial_cash: string | null };
  margin: { contribution_margin_percent: string; per_unit_contribution: string } | null;
  lead_time: { critical_path: number } | null;
  supplier_risk: string | null;
  resilience: { score: string | null; explanation: string };
  external_dispatch: false;
}
export interface SourcingComparison {
  scoring_version: string;
  recommendation: string;
  recommended_version_id: string | null;
  scenarios: {
    id: string;
    scenario_id: string;
    name: string;
    version: number;
    freshness: string;
    score: string | null;
    labels: string[];
    result: SourcingScenarioResult;
  }[];
}
export interface SourcingContextSummary {
  id: string;
  product_id?: string | null;
  status: string;
  settings: { target_market: string; target_channel: string; target_quantity: number };
}
export interface SourcingScenarioDetail {
  id: string;
  context_id: string;
  name: string;
  version: number;
  version_id: string;
  freshness: string;
  status: string;
  result: SourcingScenarioResult;
  snapshot: unknown;
}
