export interface ApiHealthResponse {
  description: string | null;
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
  configured?: boolean;
  enabled?: boolean;
  health_state?: string;
  recommended_model?: string | null;
  capabilities?: string[];
  live_validation?: string;
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
  channel?: string;
  content_type?: string;
  locale?: string;
  status: AIArtifactStatus;
  content: AIProductContent;
  validation_result: Record<string, unknown>;
  provider_metadata: Record<string, unknown>;
  approved_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  created_at: string;
  parent_artifact_id?: string | null;
  parent_artifact_version?: number | null;
  source_artifact_version?: number | null;
  source_locale?: string | null;
  source_product_context?: Record<string, unknown> | null;
  brand_voice_version?: number | null;
  preset_version?: string | null;
  source?: string;
  edited_at?: string | null;
  edited_by?: string | null;
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
  capabilities?: Record<string, boolean>;
}
export interface MockDestinationConfiguration {
  channel_name: string;
  publication_prefix: string;
  simulate_failure: boolean;
  failure_type: 'retryable' | 'non_retryable';
}
export interface WordPressDestinationConfiguration {
  post_status: 'draft' | 'publish';
  category_ids: number[];
  tag_ids: number[];
  author_id: number | null;
  media_policy: 'fail' | 'publish_without' | 'draft_degraded';
  featured_image_policy: 'none' | 'optional' | 'required';
  default_media_id: string | null;
  update_existing_remote_post: boolean;
  content_mapping_version: 1;
}
export interface ShopifyDestinationConfiguration {
  default_product_status: 'draft' | 'active';
  default_collection_ids: string[];
  default_publication_ids: string[];
  default_vendor: string;
  default_product_type: string;
  default_tags: string[];
  variant_policy: 'default_variant' | 'structured_variants';
  require_variant_price: boolean;
  require_variant_sku: boolean;
  inventory_policy: 'no_inventory_write' | 'track_without_quantity';
  media_policy: 'fail' | 'draft_without_media' | 'degraded';
  update_existing_remote_product: boolean;
  content_mapping_version: 1;
}
export type PublishingDestinationConfiguration =
  | MockDestinationConfiguration
  | WordPressDestinationConfiguration
  | ShopifyDestinationConfiguration;
export interface PublishingDestinationSummary {
  id: string;
  brand_id: string | null;
  brand_name: string | null;
  connector_key: string;
  name: string;
  status: PublishingDestinationStatus;
  configuration: PublishingDestinationConfiguration;
  created_at: string;
  updated_at: string;
  disabled_at: string | null;
}
export interface CreatePublishingDestinationRequest {
  name: string;
  brand_id?: string | null;
  connector_key: 'mock_publisher_v1' | 'wordpress' | 'shopify';
  configuration: PublishingDestinationConfiguration;
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
  operation: string;
  latency_ms: number | null;
  response_status: number | null;
  retry_after_seconds: number | null;
  calculated_delay_ms: number | null;
  applied_delay_ms: number | null;
  ambiguous_result: boolean;
  correlation_id: string | null;
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
  requested_action: 'create_draft' | 'publish' | 'activate' | 'update' | 'archive';
  remote_entity_id: string | null;
  remote_status: string | null;
  remote_slug: string | null;
  remote_edit_url: string | null;
  reconciliation_status: string;
  last_reconciled_at: string | null;
  correlation_id: string | null;
  cancellation_requested_at: string | null;
  cancelled_at: string | null;
}
export interface CreatePublishingExecutionRequest {
  artifact_id: string;
  destination_id: string;
  idempotency_key?: string;
  generation_reason?:
    | 'studio'
    | 'regeneration'
    | 'bulk'
    | 'seo'
    | 'localization'
    | 'localized_generation'
    | 'translation';
  source_artifact_id?: string;
  source_artifact_version?: number;
  operation?: 'localized_generation' | 'translation';
  action?: 'create_draft' | 'publish' | 'activate' | 'update' | 'archive';
  featured_media_id?: string | null;
  shopify_variants?: ShopifyVariantInput[];
  shopify_media?: ShopifyMediaSelection[];
}
export interface WordPressConnectorConfiguration {
  connector_key: 'wordpress';
  display_name: string;
  configured: boolean;
  credential_source: 'application' | 'deployment' | 'not_configured';
  masked_username: string | null;
  site_url: string;
  enabled: boolean;
  default_post_status: 'draft' | 'publish';
  request_timeout_seconds: number;
  max_retry_attempts: number;
  validation_status: string;
  safe_validation_message: string | null;
  last_validated_at: string | null;
  last_validation_latency_ms: number | null;
  capabilities: Record<string, boolean>;
}
export interface UpdateWordPressConnectorRequest {
  site_url: string;
  username: string;
  application_password?: string;
  enabled: boolean;
  default_post_status: 'draft' | 'publish';
  request_timeout_seconds: number;
  max_retry_attempts: number;
}
export interface WordPressValidationResult {
  valid: boolean;
  safe_message: string;
  site_url: string;
  user_id: number | null;
  display_name: string | null;
  capabilities: Record<string, boolean>;
  latency_ms: number;
  correlation_id: string | null;
}
export interface ShopifyConnectorConfiguration {
  connector_key: 'shopify';
  display_name: string;
  configured: boolean;
  credential_source: 'application' | 'deployment' | 'not_configured';
  shop_domain: string;
  api_version: string;
  enabled: boolean;
  default_product_status: 'draft' | 'active';
  default_publication_ids: string[];
  inventory_policy: 'no_inventory_write' | 'track_without_quantity';
  variant_policy: 'default_variant' | 'structured_variants';
  media_policy: 'fail' | 'draft_without_media' | 'degraded';
  request_timeout_seconds: number;
  max_retry_attempts: number;
  validation_status: string;
  safe_validation_message: string | null;
  last_validated_at: string | null;
  last_validation_latency_ms: number | null;
  capabilities: Record<string, boolean>;
}
export interface UpdateShopifyConnectorRequest {
  shop_domain: string;
  access_token?: string;
  api_version: string;
  default_product_status: 'draft' | 'active';
  default_publication_ids: string[];
  inventory_policy: 'no_inventory_write' | 'track_without_quantity';
  variant_policy: 'default_variant' | 'structured_variants';
  media_policy: 'fail' | 'draft_without_media' | 'degraded';
  request_timeout_seconds: number;
  max_retry_attempts: number;
}
export interface ShopifyValidationResult {
  valid: boolean;
  safe_message: string;
  shop_domain: string;
  api_version: string;
  shop_id: string | null;
  shop_name: string | null;
  primary_domain: string | null;
  capabilities: Record<string, boolean>;
  latency_ms: number;
  correlation_id: string | null;
}
export interface ShopifyRemoteItem {
  id: string;
  name: string;
  handle: string | null;
}
export interface ShopifyDiscoveryPage {
  items: ShopifyRemoteItem[];
  has_more: boolean;
  end_cursor: string | null;
  cached: boolean;
  stale: boolean;
}
export interface WordPressTerm {
  id: number;
  name: string;
  slug: string;
  parent_id: number | null;
}
export interface WordPressAuthor {
  id: number;
  name: string;
  username: string | null;
}
export interface WordPressTaxonomyPage {
  items: WordPressTerm[] | WordPressAuthor[];
  page: number;
  page_size: number;
  has_more: boolean;
  cached: boolean;
  stale: boolean;
}
export interface MediaAsset {
  id: string;
  original_filename: string;
  safe_filename: string;
  mime_type: 'image/jpeg' | 'image/png' | 'image/webp';
  size_bytes: number;
  width: number;
  height: number;
  checksum_sha256: string;
  status: 'ready' | 'archived';
  upload_state: 'ready';
  usage_count: number;
  duplicate_reused: boolean;
  created_at: string;
  archived_at: string | null;
  preview_url: string;
}
export interface PaginatedMedia {
  items: MediaAsset[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}
export interface SanitizationChange {
  kind: 'escaped_html' | 'converted_paragraphs' | 'normalized_slug';
  message: string;
}
export interface PublishingPreview {
  title: string;
  slug: string;
  excerpt: string;
  sanitized_body: string;
  post_status: string;
  author_id: number | null;
  category_ids: number[];
  tag_ids: number[];
  featured_media_id: string | null;
  destination_id: string;
  destination_name: string;
  remote_update_target: string | null;
  artifact_id: string;
  artifact_version: number;
  product_id: string;
  product_name: string;
  brand_id: string;
  brand_name: string;
  original_text: string;
  sanitization_changes: SanitizationChange[];
}
export interface ShopifyPublishingPreview {
  title: string;
  sanitized_description_html: string;
  status: 'DRAFT' | 'ACTIVE' | 'ARCHIVED';
  vendor: string;
  product_type: string;
  tags: string[];
  seo_title: string;
  seo_description: string;
  collection_ids: string[];
  publication_ids: string[];
  inventory_policy: string;
  destination_id: string;
  destination_name: string;
  artifact_id: string;
  artifact_version: number;
  product_id: string;
  product_name: string;
  brand_id: string;
  brand_name: string;
  original_text: string;
}
export interface ShopifyOptionInput {
  name: string;
  value: string;
}
export interface ShopifyVariantInput {
  local_key: string;
  options: ShopifyOptionInput[];
  sku: string | null;
  price: string | null;
  compare_at_price: string | null;
  barcode: string | null;
  weight: string | null;
  weight_unit: 'g' | 'kg' | 'oz' | 'lb' | null;
  taxable: boolean;
  track_inventory: boolean;
}
export interface ShopifyMediaSelection {
  media_id: string;
  position: number;
  alt_text: string;
}
export interface ShopifyVariantMapping {
  local_variant_key: string;
  remote_product_id: string;
  remote_variant_id: string;
  remote_inventory_item_id: string | null;
  sku: string | null;
  option_signature: string;
  status: string;
}
export interface ShopifyThrottleMetadata {
  requested_cost: number | null;
  actual_cost: number | null;
  currently_available: number | null;
  restore_rate: number | null;
}
export interface ShopifyRetryDelayMetadata {
  calculated_delay_ms: number | null;
  applied_delay_ms: number | null;
  retry_after_seconds: number | null;
}
export interface RemoteDriftField {
  field: string;
  display_label: string;
  expected: unknown;
  remote: unknown;
  normalized_expected: unknown;
  normalized_remote: unknown;
  status: 'in_sync' | 'changed_remotely' | 'unknown';
  drift_type:
    | 'value_changed'
    | 'missing_remote'
    | 'extra_remote'
    | 'inaccessible'
    | 'unknown'
    | 'conflict';
  severity: 'info' | 'warning' | 'blocking';
  resolution: 'overwrite' | 'keep_remote' | 'manual' | 'none';
  safe_explanation: string;
}
export interface PublishingReconciliationResult {
  id: string;
  reconciliation_status: string;
  remote_status: string | null;
  remote_slug: string | null;
  remote_url: string | null;
  drift_fields: string[];
  differences: RemoteDriftField[];
  correlation_id: string | null;
}
export interface ShopifyOverwritePreview {
  execution_id: string;
  reconciliation_status: string;
  fields_available: string[];
  remote_only_fields_preserved: string[];
  differences: RemoteDriftField[];
  correlation_id: string | null;
}
export interface ShopifyAssignmentRemovalPreview {
  execution_id: string;
  assignment_type: 'collection' | 'publication';
  removable_target_ids: string[];
  preserved_target_ids: string[];
  required_target_ids: string[];
  activation_impact: string;
  correlation_id: string | null;
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
  publishing_action?:
    | 'default'
    | 'shopify_create_draft'
    | 'shopify_update_product'
    | 'shopify_activate_product'
    | 'shopify_archive_product';
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
  actor_id?: string | null;
  campaign_id?: string | null;
  activity_id?: string | null;
  original_scheduled_at_utc?: string | null;
  new_scheduled_at_utc?: string | null;
  reason?: string | null;
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
  category: 'workflow' | 'publishing' | 'media' | 'campaign';
  entity_type: string;
  product_id: string | null;
  product_name: string | null;
  brand_id: string | null;
  failure_code: string | null;
  safe_failure_message: string;
  retryable: boolean;
  attempt_count: number;
  failed_at: string;
  workflow_id: string | null;
  capabilities: string[];
  related_url: string;
  schedule_id?: string | null;
  job_state?: string | null;
  connector?: string | null;
  destination_id?: string | null;
  artifact_id?: string | null;
  artifact_version?: number | null;
  scheduled_at?: string | null;
  available_at?: string | null;
  lease_owner?: string | null;
  lease_expiry?: string | null;
  next_retry?: string | null;
  correlation_id?: string | null;
  campaign_id?: string | null;
  campaign_name?: string | null;
  activity_id?: string | null;
  activity_name?: string | null;
  catch_up_activity_id?: string | null;
  catch_up_schedule_id?: string | null;
  catch_up_job_id?: string | null;
  catch_up_status?: string | null;
}
export interface RecoveryPage {
  items: RecoveryItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface CampaignRecoveryProjection {
  recovery_type: string;
  campaign_id: string;
  campaign_name: string;
  campaign_status: CampaignStatus;
  activity_id: string | null;
  activity_name: string | null;
  required: boolean | null;
  product_id: string | null;
  artifact_id: string | null;
  artifact_version: number | null;
  destination_id: string | null;
  connector_key: string | null;
  schedule_id: string | null;
  job_id: string | null;
  publishing_execution_id: string | null;
  workflow_wait_id: string | null;
  safe_failure_message: string;
  correlation_id: string | null;
  eligible_actions: string[];
  catch_up_activity_id?: string | null;
  catch_up_schedule_id?: string | null;
  catch_up_job_id?: string | null;
  catch_up_status?: string | null;
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

export interface PublishingSchedule {
  id: string;
  name: string;
  connector_key: string;
  requested_action: string;
  schedule_type: 'one_time' | 'recurring';
  scheduled_at_utc: string;
  timezone_name: string;
  local_scheduled_at: string;
  recurrence_json: Record<string, unknown> | null;
  enabled: boolean;
  paused: boolean;
  archived: boolean;
  next_run_at_utc: string | null;
  last_result: string | null;
  missed_occurrence_policy: 'skip_missed' | 'next_occurrence' | 'one_catch_up';
  max_occurrences: number;
  materialized_occurrence_count: number;
}
export interface PublishingJob {
  id: string;
  schedule_id: string | null;
  publishing_execution_id: string | null;
  connector_key: string;
  requested_action: string;
  state: string;
  scheduled_at_utc: string;
  execution_attempt_count: number;
  max_execution_attempts: number;
  last_error_message: string | null;
  product_id: string;
  artifact_id: string;
  artifact_version: number;
  destination_id: string;
  claimed_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  lease_owner: string | null;
  lease_expires_at: string | null;
  next_retry_at: string | null;
  correlation_id: string | null;
  recovery_state: string | null;
  recovery_reason: string | null;
  maintenance_blocked_at: string | null;
}
export interface PublishingWorker {
  worker_id: string;
  process_started_at: string;
  last_heartbeat_at: string;
  version: string;
  concurrency: number;
  active_jobs: number;
  draining: boolean;
  shutdown_requested: boolean;
  safe_status: string;
  status?: 'online' | 'offline' | 'stale' | 'draining';
  completed_jobs: number;
  failed_jobs: number;
  lease_renewal_failures: number;
  stale_recoveries: number;
  graceful_shutdowns: number;
}
export interface PublishingJobAttempt {
  id: string;
  attempt_number: number;
  worker_id: string;
  started_at: string;
  completed_at: string | null;
  outcome: string;
  retryable: boolean;
  error_code: string | null;
  safe_error_message: string | null;
  delay_seconds: number | null;
  connector_execution_id: string | null;
  correlation_id: string | null;
}
export interface SchedulerHealth {
  scheduler_enabled: boolean;
  globally_paused: boolean;
  maintenance_blocked: boolean;
  active_schedule_count: number;
  paused_schedule_count: number;
  recurring_schedule_count: number;
  due_job_count: number;
  overdue_job_count: number;
  retry_wait_count: number;
  failed_count: number;
  dead_letter_count: number;
  cancelled_count: number;
  oldest_overdue_age_seconds: number | null;
  workers: PublishingWorker[];
  connector_backlog: Record<string, number>;
  generated_at: string;
}
export interface PublishingSchedulerPage<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export type CampaignStatus =
  | 'draft'
  | 'planning'
  | 'ready'
  | 'scheduled'
  | 'running'
  | 'paused'
  | 'partially_completed'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'archived';

export interface Campaign {
  id: string;
  owner_id: string;
  brand_id: string;
  name: string;
  slug: string;
  description: string;
  objective: string;
  status: CampaignStatus;
  priority: number;
  timezone_name: string;
  start_at_utc: string;
  end_at_utc: string;
  local_start_at: string;
  local_end_at: string;
  approval_policy: string;
  scheduling_policy: string;
  conflict_policy: string;
  created_at: string;
  updated_at: string;
  launched_at: string | null;
  paused_at: string | null;
  completed_at: string | null;
  archived_at: string | null;
  cancellation_reason: string | null;
  row_version: number;
}

export interface CampaignActivity {
  id: string;
  campaign_id: string;
  product_id: string | null;
  artifact_id: string | null;
  artifact_version: number | null;
  destination_id: string | null;
  connector_key: string | null;
  requested_action: string | null;
  activity_type: string;
  name: string;
  description: string;
  sequence: number;
  scheduled_local_date: string;
  scheduled_local_time: string;
  timezone_name: string;
  scheduled_at_utc: string;
  duration_minutes: number | null;
  status: string;
  readiness_status: string;
  schedule_id: string | null;
  job_id: string | null;
  publishing_execution_id: string | null;
  required: boolean;
  enabled: boolean;
  failure_code: string | null;
  safe_failure_message: string | null;
  correlation_id: string | null;
  replaces_activity_id?: string | null;
  replaced_by_activity_id?: string | null;
  replacement_reason?: string | null;
  replacement_created_at?: string | null;
  row_version: number;
}

export type CampaignDstClassification =
  | 'normal'
  | 'nonexistent_local_time'
  | 'ambiguous_local_time';

export interface CampaignReschedulePreviewRequest {
  activity_id: string;
  proposed_local_datetime: string;
  proposed_timezone: string;
  reason?: string;
  expected_activity_row_version: number;
  fold?: 0 | 1 | null;
}

export interface CampaignReschedulePreviewResponse {
  campaign_id: string;
  activity_id: string;
  original_scheduled_at_utc: string;
  proposed_local_datetime: string;
  proposed_scheduled_at_utc: string;
  timezone: string;
  confirmation_required: boolean;
  preview_fingerprint: string;
  safe_message: string;
  correlation_id: string;
  dst_classification: CampaignDstClassification;
  utc_offset: string | null;
  fold: 0 | 1 | null;
  issue_code: string | null;
  warnings: string[];
  readiness_issues: CampaignReadinessIssue[];
  conflicts: CampaignConflict[];
  current_schedule_status: string | null;
  current_job_status: string | null;
}

export type CampaignCatchUpPreviewRequest = CampaignReschedulePreviewRequest;

export interface CampaignCatchUpPreviewResponse extends CampaignReschedulePreviewResponse {
  original_activity_name: string;
  original_activity_status: string;
  artifact_id: string | null;
  artifact_version: number | null;
  artifact_status: string | null;
  destination_id: string | null;
  destination_status: string | null;
  dependency_warnings: string[];
}

export interface CampaignRescheduleConfirmationRequest {
  action: 'reschedule_activity' | 'create_one_catch_up';
  campaign_id: string;
  activity_id: string;
  expected_activity_row_version: number;
  proposed_local_datetime: string;
  proposed_timezone: string;
  reason?: string;
  preview_fingerprint: string;
  confirm: true;
  fold?: 0 | 1;
}

export interface CampaignRescheduleConfirmationResult {
  action: 'reschedule_activity' | 'create_one_catch_up';
  outcome: string;
  resource_ids: Record<string, string>;
  safe_message: string;
  navigation_targets: Record<string, string>;
  confirmation_required: boolean;
  correlation_id: string;
  idempotency_result: string;
  scheduled: boolean;
  status?: string | null;
  idempotent_reuse: boolean;
  publishing_execution_id?: string | null;
  reconciliation_status?: string | null;
}

export interface CampaignRescheduleHistoryItem {
  id: string;
  campaign_id: string;
  activity_id: string;
  original_schedule_id: string | null;
  replacement_schedule_id: string | null;
  original_job_id: string | null;
  replacement_job_id: string | null;
  original_scheduled_for_utc: string | null;
  requested_local_datetime: string;
  requested_timezone: string;
  resolved_scheduled_for_utc: string;
  reason: string;
  status: string;
  requested_at: string;
  confirmed_at: string | null;
  confirmed_by: string | null;
}

export interface CampaignReadinessIssue {
  code: string;
  severity: 'info' | 'warning' | 'error';
  safe_message: string;
  activity_id: string | null;
  suggested_resolution: string;
  navigation_target: string | null;
}

export interface CampaignReadiness {
  state: 'ready' | 'incomplete' | 'blocked' | 'warning' | 'invalid';
  issues: CampaignReadinessIssue[];
}

export interface CampaignConflict {
  conflict_type: string;
  severity: 'warning' | 'error';
  activity_ids: string[];
  safe_explanation: string;
  suggested_correction: string;
  override_allowed: boolean;
}

export interface CampaignCalendarEvent {
  campaign_id: string;
  campaign_name: string;
  activity_id: string;
  activity_name: string;
  brand_id: string;
  product_id: string | null;
  destination_id: string | null;
  connector_key: string | null;
  requested_action: string | null;
  status: string;
  readiness_status: string;
  scheduled_at_utc: string;
  timezone_name: string;
  has_conflict: boolean;
}

export interface CampaignMonthCalendar {
  view: 'month';
  start: string;
  end: string;
  days: Array<{
    date: string;
    activity_count: number;
    campaign_count: number;
    status_summary: Record<string, number>;
    conflict_count: number;
    previews: CampaignCalendarEvent[];
    overflow_count: number;
  }>;
}

export interface CampaignWeekCalendar {
  view: 'week';
  start: string;
  end: string;
  timezone_name: string;
  slots: Array<{
    date: string;
    events: CampaignCalendarEvent[];
    destination_workload: Record<string, number>;
    overlap_count: number;
  }>;
}

export interface CampaignAgendaCalendar {
  view: 'agenda';
  start: string;
  end: string;
  days: Array<{ date: string; events: CampaignCalendarEvent[] }>;
  next_offset: number | null;
}

export type CampaignCalendar =
  | CampaignMonthCalendar
  | CampaignWeekCalendar
  | CampaignAgendaCalendar;

export interface CampaignResumePreview {
  missed: string[];
  required_missed: string[];
  optional_missed: string[];
  to_skip: string[];
  catch_up: string | null;
  next_future: string | null;
  blocked_successors: string[];
  confirmation_required: boolean;
}

export interface CampaignWorkflowWait {
  id: string;
  campaign_id: string;
  workflow_instance_id: string;
  expected_state: string;
  current_state: string;
  correlation_id: string;
  completed_at: string | null;
  failure_code: string | null;
  safe_failure_message: string | null;
}

export interface CampaignSelectorItem {
  id: string;
  label: string;
  kind: 'brand' | 'product' | 'artifact' | 'destination' | 'manager' | 'activity';
  disabled: boolean;
  disabled_reason: string | null;
  version: number | null;
  status: string;
  connector_key: string | null;
  product_id: string | null;
}

export interface CampaignSelectorPage {
  items: CampaignSelectorItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface CampaignProgress {
  total: number;
  required: number;
  optional: number;
  ready: number;
  scheduled: number;
  running: number;
  succeeded: number;
  failed: number;
  blocked: number;
  cancelled: number;
  completion_percentage: number;
}

export interface CampaignHealth {
  active_campaigns: number;
  upcoming_activities: number;
  blocked_activities: number;
  overdue_activities: number;
  active_campaign_waits: number;
  failed_campaign_waits: number;
  missed_activities: number;
  catch_ups_created: number;
  generated_at: string;
}

export type MarketplaceId = 'amazon' | 'flipkart' | 'meesho' | 'shopify';
export type MarketplaceListingLifecycle =
  | 'draft'
  | 'ready'
  | 'submitting'
  | 'active'
  | 'paused'
  | 'rejected'
  | 'error'
  | 'archived';
export interface MarketplaceAccountSummary {
  id: string;
  marketplace: MarketplaceId;
  display_name: string;
  seller_account_id: string;
  environment: 'sandbox' | 'production';
  enabled: boolean;
  credential_status: string;
  validation_status: string;
  last_validated_at: string | null;
  capabilities: string[];
}
export interface MarketplaceListingSummary {
  id: string;
  marketplace: MarketplaceId;
  product_id: string;
  account_id: string;
  title: string;
  marketplace_sku: string | null;
  status: MarketplaceListingLifecycle;
  publication_state: string;
  drift_state: string;
}
export interface MarketplaceInventorySummary {
  id: string;
  listing_id: string;
  product_id: string;
  available_quantity: number;
  marketplace_reported_quantity: number | null;
  synchronization_status: string;
  last_synchronized_at: string | null;
}
export interface MarketplaceOrderSummary {
  id: string;
  marketplace: MarketplaceId;
  remote_order_id: string;
  status: string;
  fulfilment_status: string;
  totals: Record<string, string>;
  ordered_at: string;
  buyer_summary: { display_name: string };
}
export interface MarketplaceSettlementSummary {
  id: string;
  marketplace: MarketplaceId;
  remote_settlement_id: string;
  period_start: string;
  period_end: string;
  gross_amount: string;
  fee_amount: string;
  refund_amount: string;
  tax_withholding_amount: string;
  net_amount: string;
  currency: string;
}
export interface MarketplaceAnalyticsSummary {
  gross_sales: string;
  fees: string;
  refunds: string;
  net_contribution: string;
  estimated_profit: string | null;
  profit_status: 'available' | 'unavailable';
  order_count: number;
  active_listing_count: number;
  low_stock_count: number;
  sales_by_marketplace: Record<string, string>;
}

export interface AmazonMarketplaceSummary {
  country_code: string;
  marketplace_id: string;
  currency: string;
  locale: string;
  endpoint_region: string;
}
export interface AmazonListingPreview {
  ready: boolean;
  blocking_issues: Array<{ code: string; field?: string; message: string }>;
  warnings: string[];
  marketplace_id: string;
  product_type: string | null;
  title: string;
  sku: string | null;
}
export interface AmazonOperationIssue {
  code: string;
  message: string;
  retryable: boolean;
}
export interface AmazonSubmitResult {
  status: string;
  remote_listing_id: string | null;
  remote_status: string | null;
  retryable: boolean;
  ambiguous: boolean;
  issues: AmazonOperationIssue[];
}

export type AIStudioChannel =
  | 'amazon'
  | 'flipkart'
  | 'meesho'
  | 'shopify'
  | 'wordpress'
  | 'canonical';
export type AIStudioContentType =
  | 'marketplace_listing'
  | 'product_description'
  | 'product_title'
  | 'bullet_points'
  | 'highlights'
  | 'search_terms'
  | 'tags'
  | 'seo_metadata'
  | 'blog_content'
  | 'social_caption'
  | 'ad_copy'
  | 'video_script'
  | 'email_copy'
  | 'faq'
  | 'product_comparison'
  | 'landing_page_copy';
export interface AIStudioBrandVoice {
  id: string;
  brand_id: string | null;
  name: string;
  description: string | null;
  tone: string;
  personality: string | null;
  terminology: Record<string, unknown>;
  target_audience: string | null;
  preferred_phrases: string[];
  prohibited_phrases: string[];
  spelling_conventions: string | null;
  language: string;
  locale: string;
  formatting_preferences: Record<string, unknown>;
  compliance_notes: string | null;
  custom_instructions: string | null;
  is_default: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}
export interface AIStudioPreset {
  id: string;
  name: string;
  description: string | null;
  brand_voice_id?: string | null;
  locale?: string;
  guidance?: string | null;
  preferred_provider?: string | null;
  preferred_model?: string | null;
  output_types: string[];
  channels: string[];
  tone: string | null;
  length: string | null;
  required_context: string[];
  validation_rules: Record<string, unknown>;
  is_system: boolean;
  is_default?: boolean;
  archived?: boolean;
  version?: number;
  created_at: string;
  updated_at: string;
}
export interface AIKeywordSet {
  id: string;
  name: string;
  brand_id: string | null;
  product_id: string | null;
  primary_keywords: string[];
  secondary_keywords: string[];
  marketplace_keywords: string[];
  website_keywords: string[];
  campaign_keywords: string[];
  negative_keywords: string[];
  source: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}
export interface AIStudioGenerateRequest {
  product_ids: string[];
  channels: AIStudioChannel[];
  content_types: AIStudioContentType[];
  brand_voice_id?: string;
  preset_id?: string;
  locale?: string;
  user_instructions?: string;
  provider_key?: 'deterministic_mock_v1' | 'openai_compatible';
  model?: string;
  idempotency_key?: string;
  generation_reason?:
    | 'studio'
    | 'regeneration'
    | 'bulk'
    | 'seo'
    | 'localization'
    | 'localized_generation'
    | 'translation';
  source_artifact_id?: string;
  source_artifact_version?: number;
  operation?: 'localized_generation' | 'translation';
}
export interface AIStudioOutput {
  id: string;
  generation_id: string;
  product_id: string;
  artifact_id: string | null;
  channel: string;
  content_type: string;
  status: string;
  error_code: string | null;
  safe_error_message: string | null;
}
export interface AIStudioGeneration {
  id: string;
  status: string;
  product_ids: string[];
  channels: string[];
  content_types: string[];
  context_fingerprint: string;
  total_outputs: number;
  completed_outputs: number;
  failed_outputs: number;
  outputs: AIStudioOutput[];
  created_at: string;
  completed_at: string | null;
}
export interface AIStudioArtifact {
  id: string;
  product_id: string;
  product_name: string;
  brand_id: string;
  brand_name: string;
  channel: string;
  content_type: string;
  locale: string;
  version_number: number;
  status: string;
  source: string;
  content: Record<string, unknown>;
  validation_result: Record<string, unknown>;
  context_fingerprint: string | null;
  parent_artifact_id: string | null;
  generation_reason: string;
  provider_key: string;
  model: string | null;
  created_at: string;
  approved_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  parent_artifact_version?: number | null;
  brand_voice_version?: number | null;
  preset_version?: string | null;
  edited_at?: string | null;
  edited_by?: string | null;
}
export interface AIStudioBulkRequest {
  product_ids: string[];
  channels: AIStudioChannel[];
  content_types: AIStudioContentType[];
  brand_voice_id?: string;
  preset_id?: string;
  locale?: string;
  user_instructions?: string;
  provider_key?: string;
  model?: string;
  idempotency_key?: string;
  generation_reason?:
    | 'studio'
    | 'regeneration'
    | 'bulk'
    | 'seo'
    | 'localization'
    | 'localized_generation'
    | 'translation';
  source_artifact_id?: string;
  source_artifact_version?: number;
  operation?: 'localized_generation' | 'translation';
  failure_scenarios?: Record<string, string>;
}
export interface AIStudioBulkPreview {
  product_ids: string[];
  channels: string[];
  content_types: string[];
  product_count: number;
  channel_count: number;
  content_type_count: number;
  total_outputs: number;
  brand_voice_id: string | null;
  brand_voice_version: number | null;
  preset_id: string | null;
  preset_version: number | null;
  locale: string;
  provider_key: string;
  model: string;
  estimated_provider_calls: number;
  estimated_cost: string;
  blockers: string[];
  warnings: string[];
  operation_limits: Record<string, number>;
}
export interface AIStudioBulkOutput {
  id: string;
  product_id: string;
  product_name: string;
  channel: string;
  content_type: string;
  locale: string;
  status: string;
  artifact_id: string | null;
  artifact_version: number | null;
  job_id: string | null;
  generation_id: string | null;
  attempt_count: number;
  failure_category: string | null;
  safe_error_message: string | null;
  retryable: boolean;
  retry_eligible: boolean;
  updated_at: string;
}
export interface AIStudioBulkStatus {
  id: string;
  status: string;
  total_outputs: number;
  counts: Record<string, number>;
  progress_percentage: number;
  product_count: number;
  channel_count: number;
  content_type_count: number;
  locale: string;
  provider_key: string;
  model: string;
  brand_voice_id: string | null;
  brand_voice_version: number | null;
  preset_id: string | null;
  preset_version: number | null;
  correlation_id: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  completion_summary: Record<string, unknown>;
  cancellation_requested: boolean;
  outputs: AIStudioBulkOutput[];
}
export interface AIStudioContext {
  product_id: string;
  brand_id: string;
  context_fingerprint: string;
  context: Record<string, unknown>;
  sources: string[];
  warnings: string[];
}
export interface AIStudioComparison {
  left: AIStudioArtifact;
  right: AIStudioArtifact;
  changed_fields: string[];
  additions: string[];
  removals: string[];
  fields?: Record<
    string,
    {
      status: string;
      left?: unknown;
      right?: unknown;
      added?: unknown[];
      removed?: unknown[];
      changed?: Array<Record<string, unknown>>;
    }
  >;
}
export interface AISEOAnalysis {
  product_id: string;
  channel: string;
  score: number;
  dimensions: Record<string, number>;
  recommendations: string[];
  keyword_coverage: Record<string, unknown>;
  fact_warnings: string[];
  generated_at: string;
}
export interface AIStudioDiagnostics {
  provider: string;
  available: boolean;
  remote_calls_enabled: boolean;
  generations: { total: number; completed: number };
  safe_message: string;
}

export interface AISEODimension {
  score: number;
  explanation: string;
  checks: unknown[];
  recommendations: unknown[];
}
export interface AISEOFinding {
  severity: string;
  field: string;
  code: string;
  explanation: string;
  suggested_action?: string | null;
  actions?: Array<'edit' | 'regenerate' | 'reanalyze' | 'open_keywords' | 'review_product'>;
}
export interface AISEOAnalysisResponse {
  id: string;
  product_id: string;
  artifact_id: string | null;
  artifact_version: number | null;
  keyword_set_id: string | null;
  keyword_set_version: number | null;
  channel: string;
  seo_type: string;
  locale: string;
  intent: string;
  overall_score: number;
  dimensions: Record<string, AISEODimension>;
  findings: AISEOFinding[];
  recommendations: AISEOFinding[];
  keyword_coverage: Record<string, unknown>;
  metrics: Record<string, unknown>;
  fingerprint: string;
  rule_version: string;
  status: string;
  analyzed_at: string;
}
export interface AIKeywordSuggestion {
  keyword: string;
  category: string;
}
