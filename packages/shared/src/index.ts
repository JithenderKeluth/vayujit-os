export interface ApiHealthResponse {
  status: 'ok' | 'degraded';
  service: string;
  version: string;
  environment: string;
}

export interface AuthenticatedUserSummary {
  id: string;
  username: string;
  role: 'owner';
}

export interface BrandSummary {
  id: string;
  name: string;
  status: 'active' | 'archived';
}

export interface ProductSummary {
  id: string;
  brandId: string;
  sku: string;
  name: string;
  status: 'active' | 'archived';
}

export type WorkflowExecutionStatus =
  | 'pending'
  | 'running'
  | 'waiting_for_approval'
  | 'approved'
  | 'rejected'
  | 'publishing'
  | 'completed'
  | 'failed'
  | 'cancelled';
