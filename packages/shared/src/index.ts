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

export type BrandStatus = 'active' | 'archived';

export interface BrandSummary {
  id: string;
  name: string;
  slug: string;
  tagline: string | null;
  status: BrandStatus;
  website_url: string | null;
  primary_color: string | null;
  secondary_color: string | null;
  is_active_context: boolean;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface BrandDetails extends BrandSummary {
  description: string | null;
  recent_audit_events: Array<{ action: string; occurred_at: string }>;
}

export interface CreateBrandRequest {
  name: string;
  slug?: string | null;
  tagline?: string | null;
  description?: string | null;
  website_url?: string | null;
  primary_color?: string | null;
  secondary_color?: string | null;
}

export type UpdateBrandRequest = Partial<CreateBrandRequest>;

export interface PaginatedBrandResponse {
  items: BrandSummary[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export type ActiveBrandResponse = BrandSummary | null;

export interface ApiValidationError {
  detail:
    | string
    | Array<{
        loc: Array<string | number>;
        msg: string;
        type: string;
      }>;
}

export type ProductStatus = 'draft' | 'active' | 'archived';
export type ProductType = 'physical' | 'digital' | 'service' | 'affiliate';
export type WeightUnit = 'g' | 'kg' | 'oz' | 'lb';
export type MoneyAmount = string;

export interface ProductSummary {
  id: string;
  brand_id: string;
  brand_name: string;
  name: string;
  slug: string;
  sku: string | null;
  product_type: ProductType;
  status: ProductStatus;
  short_description: string | null;
  description: string | null;
  category: string | null;
  tags: string[];
  price_amount: MoneyAmount | null;
  price_currency: string | null;
  compare_at_price_amount: MoneyAmount | null;
  cost_amount: MoneyAmount | null;
  tax_code: string | null;
  barcode: string | null;
  weight_value: string | null;
  weight_unit: WeightUnit | null;
  inventory_tracking_enabled: boolean;
  inventory_quantity: number;
  low_stock_threshold: number;
  is_featured: boolean;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface ProductAuditSummary {
  action: string;
  occurred_at: string;
}

export interface ProductDetails extends ProductSummary {
  recent_audit_events: ProductAuditSummary[];
}

export interface CreateProductRequest {
  brand_id?: string | null;
  name: string;
  slug?: string | null;
  sku?: string | null;
  product_type: ProductType;
  short_description?: string | null;
  description?: string | null;
  category?: string | null;
  tags?: string[];
  price_amount?: MoneyAmount | null;
  price_currency?: string | null;
  compare_at_price_amount?: MoneyAmount | null;
  cost_amount?: MoneyAmount | null;
  tax_code?: string | null;
  barcode?: string | null;
  weight_value?: string | null;
  weight_unit?: WeightUnit | null;
  inventory_tracking_enabled?: boolean;
  inventory_quantity?: number;
  low_stock_threshold?: number;
  is_featured?: boolean;
}

export type UpdateProductRequest = Partial<CreateProductRequest>;

export interface PaginatedProductResponse {
  items: ProductSummary[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export type ProductSortField =
  | 'name'
  | 'created_at'
  | 'updated_at'
  | 'price'
  | 'inventory_quantity';

export interface ProductFilters {
  brandId?: string;
  allBrands?: boolean;
  includeArchived?: boolean;
  search?: string;
  sku?: string;
  category?: string;
  productType?: ProductType | '';
  status?: ProductStatus | '';
  featured?: boolean | null;
  sortBy?: ProductSortField;
  sortDirection?: 'asc' | 'desc';
  page?: number;
  pageSize?: number;
}

export interface ProductActivationErrorResponse {
  detail: {
    code: 'product_not_ready';
    message: string;
    fields: string[];
  };
}

export type AIGenerationStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type AIArtifactStatus = 'pending_review' | 'approved' | 'rejected' | 'superseded';

export interface AIProviderSummary {
  key: string;
  name: string;
  provider_type: string;
  available: boolean;
  deterministic: boolean;
  local: boolean;
}

export interface AITemplateSummary {
  id: string;
  key: string;
  name: string;
  description: string;
  version: number;
  template_type: string;
  is_default: boolean;
}

export interface CreateAIGenerationRequest {
  product_id: string;
  prompt_template_id?: string | null;
  additional_instructions?: string | null;
  provider_key?: 'deterministic_mock_v1' | 'openai_compatible' | null;
  model?: string | null;
  allow_fallback?: boolean;
}

export interface AIGenerationResponse {
  id: string;
  status: AIGenerationStatus;
  artifact_id: string | null;
  error_code: string | null;
  safe_error_message: string | null;
  provider_key: string | null;
  model: string | null;
  attempt_count: number;
  fallback_used: boolean;
  correlation_id: string | null;
}

export type AICredentialSource = 'application' | 'deployment' | 'not_configured';
export interface AIProviderConfiguration {
  provider_key: 'openai_compatible';
  display_name: string;
  configured: boolean;
  credential_source: AICredentialSource;
  masked_credential: string | null;
  base_url: string;
  default_model: string;
  manual_model_allowed: boolean;
  enabled: boolean;
  fallback_provider_key: 'deterministic_mock_v1' | null;
  request_timeout_seconds: number;
  max_retry_attempts: number;
  validation_status: 'valid' | 'invalid' | 'unknown';
  safe_validation_message: string | null;
  last_validated_at: string | null;
  last_validation_latency_ms: number | null;
}
export interface UpdateAIProviderConfiguration {
  api_key?: string | null;
  base_url: string;
  default_model: string;
  manual_model_allowed: boolean;
  enabled: boolean;
  fallback_provider_key: 'deterministic_mock_v1' | null;
  request_timeout_seconds: number;
  max_retry_attempts: number;
}
export interface AIProviderValidationResult {
  valid: boolean;
  status: string;
  safe_message: string;
  correlation_id: string | null;
  latency_ms: number;
  validated_model: string | null;
}
export interface AIModelSummary {
  identifier: string;
  provider_key: string;
  structured_output: boolean | null;
}
export interface AIGenerationAttempt {
  id: string;
  attempt_number: number;
  provider_key: string;
  model: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  usage_source: 'provider' | 'estimated' | 'unavailable';
  estimated_cost: string | null;
  cost_currency: string | null;
  retryable: boolean;
  fallback: boolean;
  error_code: string | null;
  safe_error_message: string | null;
  correlation_id: string | null;
}
export interface AIUsageSummary {
  requests: number;
  successful_generations: number;
  failed_generations: number;
  retries: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost: string | null;
  cost_currency: string | null;
}
export interface AIUsageHistoryItem {
  generation_id: string;
  created_at: string;
  provider_key: string;
  model: string | null;
  status: AIGenerationStatus;
  attempts: number;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  estimated_cost: string | null;
  cost_currency: string | null;
  brand_id: string;
  brand_name: string;
  product_id: string;
  product_name: string;
}
export interface PaginatedAIUsageHistory {
  items: AIUsageHistoryItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}
export interface AIModelPricingSummary {
  id: string;
  provider_key: 'openai_compatible';
  model_pattern: string;
  currency: string;
  input_cost_per_million_tokens: string;
  output_cost_per_million_tokens: string;
  effective_from: string;
  effective_to: string | null;
  source_note: string;
  enabled: boolean;
}
export interface AICancellationResponse {
  id: string;
  status: AIGenerationStatus;
  cancellation_requested_at: string;
  remote_cancellation: false;
}

export interface AIProductContent {
  product_title: string;
  short_description: string;
  long_description: string;
  key_features: string[];
  seo_title: string;
  seo_description: string;
  social_caption: string;
  keywords: string[];
  generation_summary: string;
}

export interface AIArtifactDetails {
  id: string;
  generation_request_id: string;
  product_id: string;
  product_name: string;
  brand_id: string;
  brand_name: string;
  template_id: string;
  template_name: string;
  template_version: number;
  provider_key: string;
  version_number: number;
  status: AIArtifactStatus;
  content: AIProductContent;
  validation_result: Record<string, unknown>;
  provider_metadata: Record<string, unknown>;
  approved_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  created_at: string;
}

export interface AIHistoryItem {
  generation_id: string;
  artifact_id: string | null;
  product_id: string;
  product_name: string;
  brand_id: string;
  brand_name: string;
  template_name: string;
  template_version: number;
  provider_key: string;
  request_status: AIGenerationStatus;
  artifact_status: AIArtifactStatus | null;
  version_number: number | null;
  created_at: string;
}

export interface PaginatedAIHistory {
  items: AIHistoryItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface AIHistoryFilters {
  productId?: string;
  brandId?: string;
  requestStatus?: AIGenerationStatus | '';
  artifactStatus?: AIArtifactStatus | '';
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
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

export interface SetupStatusResponse {
  ownerExists: boolean;
}
export interface OwnerSetupRequest {
  fullName: string;
  email: string;
  password: string;
  passwordConfirmation: string;
}
export interface LoginRequest {
  email: string;
  password: string;
}
export interface AuthenticatedUserResponse {
  id: string;
  fullName: string;
  email: string;
  role: 'owner';
}
export interface ApiError {
  code: string;
  message: string;
  correlationId?: string;
}

export type PublishingDestinationStatus = 'active' | 'disabled';
export type PublishingExecutionStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled';
export interface PublishingConnectorSummary {
  key: string;
  name: string;
  connector_type: string;
  available: boolean;
  deterministic: boolean;
  local: boolean;
}
export interface MockDestinationConfiguration {
  channel_name: string;
  publication_prefix: string;
  simulate_failure: boolean;
  failure_type: 'retryable' | 'non_retryable';
}
export interface PublishingDestinationSummary {
  id: string;
  brand_id: string | null;
  brand_name: string | null;
  connector_key: string;
  name: string;
  status: PublishingDestinationStatus;
  configuration: MockDestinationConfiguration;
  created_at: string;
  updated_at: string;
  disabled_at: string | null;
}
export interface CreatePublishingDestinationRequest {
  name: string;
  brand_id?: string | null;
  connector_key: 'mock_publisher_v1';
  configuration: MockDestinationConfiguration;
}
export type UpdatePublishingDestinationRequest = Partial<CreatePublishingDestinationRequest>;
export interface PublishingAttemptDetails {
  attempt_number: number;
  status: string;
  result: Record<string, unknown> | null;
  error_code: string | null;
  safe_error_message: string | null;
  retryable: boolean;
  started_at: string;
  completed_at: string | null;
  failed_at: string | null;
}
export interface PublishingExecutionDetails {
  id: string;
  artifact_id: string;
  destination_id: string;
  brand_id: string;
  product_id: string;
  connector_key: string;
  status: PublishingExecutionStatus;
  idempotency_key: string;
  attempt_count: number;
  content_snapshot: Record<string, unknown>;
  request_snapshot: Record<string, unknown>;
  result: Record<string, unknown> | null;
  external_reference: string | null;
  external_url: string | null;
  error_code: string | null;
  safe_error_message: string | null;
  retryable: boolean;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  attempts: PublishingAttemptDetails[];
}
export interface CreatePublishingExecutionRequest {
  artifact_id: string;
  destination_id: string;
  idempotency_key?: string;
}
export interface PaginatedPublishingDestinations {
  items: PublishingDestinationSummary[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}
export interface PaginatedPublishingExecutions {
  items: PublishingExecutionDetails[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}
export interface PublishReadinessError {
  detail: {
    code:
      | 'artifact_not_approved'
      | 'product_archived'
      | 'brand_archived'
      | 'destination_disabled'
      | 'destination_brand_mismatch'
      | 'connector_unavailable'
      | 'invalid_snapshot';
    message: string;
  };
}

export type WorkflowStatus =
  | 'draft'
  | 'running'
  | 'waiting_for_approval'
  | 'completed'
  | 'failed'
  | 'cancelled';
export type WorkflowStepType = 'ai_generate' | 'human_approval' | 'publish';
export type WorkflowStepStatus =
  | 'pending'
  | 'running'
  | 'waiting'
  | 'succeeded'
  | 'failed'
  | 'skipped'
  | 'cancelled';
export interface WorkflowTemplateSummary {
  id: string;
  key: string;
  name: string;
  description: string;
  version: number;
  workflow_type: 'product_content_publish';
  is_default: boolean;
}
export interface CreateWorkflowRequest {
  product_id: string;
  destination_id: string;
  workflow_template_id?: string | null;
  additional_instructions?: string | null;
}
export interface WorkflowStepAttemptDetails {
  id: string;
  step_key: string;
  step_type: WorkflowStepType;
  sequence_number: number;
  attempt_number: number;
  status: WorkflowStepStatus;
  related_id: string | null;
  related_type: 'artifact' | 'generation' | 'publishing_execution' | null;
  started_at: string | null;
  paused_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  cancelled_at: string | null;
  error_code: string | null;
  safe_error_message: string | null;
  retryable: boolean;
}
export interface WorkflowDetails {
  id: string;
  template_id: string;
  template_key: string;
  template_name: string;
  template_version: number;
  brand_id: string;
  brand_name: string;
  product_id: string;
  product_name: string;
  destination_id: string;
  destination_name: string;
  status: WorkflowStatus;
  current_step_key: string | null;
  artifact_id: string | null;
  artifact_status: AIArtifactStatus | null;
  generation_request_id: string | null;
  publishing_execution_id: string | null;
  publishing_status: PublishingExecutionStatus | null;
  retryable: boolean;
  started_at: string | null;
  paused_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  cancelled_at: string | null;
  error_code: string | null;
  safe_error_message: string | null;
  created_at: string;
  updated_at: string;
  steps: WorkflowStepAttemptDetails[];
}
export interface WorkflowFilters {
  brandId?: string;
  productId?: string;
  destinationId?: string;
  status?: WorkflowStatus | '';
  currentStep?: string;
  dateFrom?: string;
  dateTo?: string;
  retryable?: boolean | null;
  page?: number;
  pageSize?: number;
}
export interface PaginatedWorkflowResponse {
  items: WorkflowDetails[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}
export interface SafeWorkflowError {
  detail: string | { code: string; message: string };
}

export interface DashboardMetrics {
  total_brands: number;
  total_products: number;
  active_products: number;
  pending_approvals: number;
  approved_artifacts: number;
  active_destinations: number;
  successful_executions: number;
  failed_executions: number;
  waiting_workflows: number;
  completed_workflows: number;
  failed_workflows: number;
  retryable_failures: number;
}
export interface OperationalItem {
  id: string;
  timestamp: string;
  category: string;
  event_name: string;
  entity_type: string;
  entity_id: string;
  brand_id: string | null;
  brand_name: string | null;
  product_id: string | null;
  product_name: string | null;
  status: string | null;
  safe_summary: string;
  related_url: string | null;
  correlation_id: string | null;
}
export interface DashboardResponse {
  metrics: DashboardMetrics;
  activity: OperationalItem[];
}
export interface ApprovalQueueItem {
  id: string;
  product_id: string;
  product_name: string;
  brand_id: string;
  brand_name: string;
  version_number: number;
  template_name: string;
  template_version: number;
  generated_title: string;
  short_description: string;
  status: AIArtifactStatus;
  generated_at: string;
  decided_at: string | null;
  workflow_id: string | null;
}
export interface PaginatedApprovals {
  items: ApprovalQueueItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}
export interface ApprovalDetailsResponse {
  artifact: AIArtifactDetails;
  versions: ApprovalComparisonVersion[];
}
export interface ApprovalComparisonVersion {
  artifact: AIArtifactDetails;
  workflow_id: string | null;
}
export interface PaginatedOperations {
  items: OperationalItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}
export interface OwnerProfile {
  id: string;
  full_name: string;
  email: string;
  created_at: string;
  last_login_at: string | null;
}
export interface OwnerPreferences {
  timezone: string;
  date_format: 'medium' | 'short' | 'iso';
  default_page_size: 10 | 25 | 50 | 100;
  execution_history_page_size: 10 | 25 | 50 | 100;
  default_brand_id: string | null;
  default_prompt_template_id: string | null;
  default_publishing_destination_id: string | null;
  confirm_before_publish: boolean;
  confirm_before_retry: boolean;
  theme_preference: 'system' | 'light' | 'dark';
  density_preference: 'comfortable' | 'compact';
}
export interface SettingsResponse {
  profile: OwnerProfile;
  preferences: OwnerPreferences;
}
export interface SessionSummary {
  id: string;
  created_at: string;
  expires_at: string;
  current: boolean;
}
export interface SystemStatus {
  application_version: string;
  environment: string;
  api_status: string;
  database_status: string;
  migration_revision: string;
  expected_revision: string;
  server_time: string;
  python_version: string;
  providers: string[];
  connectors: string[];
}
export interface ComponentHealth {
  component: string;
  status: 'healthy' | 'degraded' | 'unavailable' | 'unknown';
  message: string;
  checked_at: string;
  latency_ms: number | null;
}
export interface OperationalHealth {
  status: string;
  components: ComponentHealth[];
  current_migration: string;
  expected_migration: string;
  application_version: string;
  build_identifier: string;
}
export interface ReleaseInfo {
  semantic_version: string;
  build_timestamp: string;
  git_commit: string;
  build_identifier: string;
  migration_revision: string;
  python_version: string;
  api_version: string;
  node_version: string;
  electron_version: string;
  angular_build_version: string;
}
export interface RecoveryItem {
  id: string;
  category: 'workflow' | 'publishing';
  entity_type: string;
  product_id: string | null;
  product_name: string | null;
  brand_id: string;
  failure_code: string | null;
  safe_failure_message: string;
  retryable: boolean;
  attempt_count: number;
  failed_at: string;
  workflow_id: string | null;
  capabilities: string[];
  related_url: string;
}
export interface RecoveryPage {
  items: RecoveryItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}
export interface BackupSummary {
  id: string;
  backup_key: string;
  filename: string;
  format: string;
  size_bytes: number;
  checksum_sha256: string;
  application_version: string;
  migration_revision: string;
  database_name: string;
  created_at: string;
  verified_at: string | null;
  verification_status: string;
  status: string;
  encryption_status: 'not_encrypted';
}
export interface RestoreCheck {
  backup_id: string;
  compatible: boolean;
  checksum_valid: boolean;
  target_database: string;
  requires_pre_restore_backup: boolean;
  execution_supported: false;
  operator_action: string;
}
