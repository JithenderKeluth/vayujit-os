import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type {
  CreateProductRequest,
  PaginatedProductResponse,
  ProductDetails,
  ProductFilters,
  ProductSummary,
  UpdateProductRequest,
} from '@vayujit/shared';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class ProductService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/products`;
  private readonly options = { withCredentials: true } as const;

  list(filters: ProductFilters = {}): Promise<PaginatedProductResponse> {
    let params = new HttpParams()
      .set('page', filters.page ?? 1)
      .set('page_size', filters.pageSize ?? 20)
      .set('all_brands', filters.allBrands ?? false)
      .set('include_archived', filters.includeArchived ?? false)
      .set('sort_by', filters.sortBy ?? 'name')
      .set('sort_direction', filters.sortDirection ?? 'asc');
    if (filters.brandId) params = params.set('brand_id', filters.brandId);
    if (filters.search) params = params.set('search', filters.search);
    if (filters.sku) params = params.set('sku', filters.sku);
    if (filters.category) params = params.set('category', filters.category);
    if (filters.productType) params = params.set('product_type', filters.productType);
    if (filters.status) params = params.set('status', filters.status);
    if (filters.featured !== null && filters.featured !== undefined) {
      params = params.set('featured', filters.featured);
    }
    return firstValueFrom(
      this.http.get<PaginatedProductResponse>(this.baseUrl, {
        ...this.options,
        params,
      }),
    );
  }

  get(id: string): Promise<ProductDetails> {
    return firstValueFrom(this.http.get<ProductDetails>(`${this.baseUrl}/${id}`, this.options));
  }

  create(data: CreateProductRequest): Promise<ProductSummary> {
    return firstValueFrom(this.http.post<ProductSummary>(this.baseUrl, data, this.options));
  }

  update(id: string, data: UpdateProductRequest): Promise<ProductSummary> {
    return firstValueFrom(
      this.http.patch<ProductSummary>(`${this.baseUrl}/${id}`, data, this.options),
    );
  }

  activate(id: string): Promise<ProductSummary> {
    return this.transition(id, 'activate');
  }

  moveToDraft(id: string): Promise<ProductSummary> {
    return this.transition(id, 'move-to-draft');
  }

  archive(id: string): Promise<ProductSummary> {
    return this.transition(id, 'archive');
  }

  restore(id: string): Promise<ProductSummary> {
    return this.transition(id, 'restore');
  }

  private transition(id: string, action: string): Promise<ProductSummary> {
    return firstValueFrom(
      this.http.post<ProductSummary>(`${this.baseUrl}/${id}/${action}`, {}, this.options),
    );
  }

  static errorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      const body: unknown = error.error;
      if (typeof body === 'object' && body !== null && 'detail' in body) {
        if (typeof body.detail === 'string') return body.detail;
        if (typeof body.detail === 'object' && body.detail !== null) {
          const detail = body.detail;
          if ('message' in detail && typeof detail.message === 'string') {
            const fields =
              'fields' in detail && Array.isArray(detail.fields)
                ? ` Required: ${detail.fields.join(', ')}.`
                : '';
            return `${detail.message}${fields}`;
          }
        }
        if (Array.isArray(body.detail)) {
          return body.detail
            .map((item: unknown) =>
              typeof item === 'object' && item !== null && 'msg' in item ? String(item.msg) : '',
            )
            .filter(Boolean)
            .join(' ');
        }
      }
    }
    return 'Unable to complete the product request. Please try again.';
  }
}
