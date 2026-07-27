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
