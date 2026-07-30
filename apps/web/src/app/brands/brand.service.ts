import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type {
  ActiveBrandResponse,
  BrandDetails,
  BrandSummary,
  CreateBrandRequest,
  PaginatedBrandResponse,
  UpdateBrandRequest,
} from '@vayujit/shared';
import { environment } from '../../environments/environment';

export interface BrandListQuery {
  search?: string;
  status?: '' | 'active' | 'archived';
  includeArchived?: boolean;
  page?: number;
  pageSize?: number;
}

@Injectable({ providedIn: 'root' })
export class BrandService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/brands`;
  readonly activeBrand = signal<BrandSummary | null>(null);
  readonly activeLoaded = signal(false);

  private options = { withCredentials: true } as const;

  async loadActive(): Promise<BrandSummary | null> {
    try {
      const brand = await firstValueFrom(
        this.http.get<ActiveBrandResponse>(`${this.baseUrl}/active`, this.options),
      );
      this.activeBrand.set(brand);
      return brand;
    } finally {
      this.activeLoaded.set(true);
    }
  }

  list(query: BrandListQuery = {}): Promise<PaginatedBrandResponse> {
    let params = new HttpParams()
      .set('page', query.page ?? 1)
      .set('page_size', query.pageSize ?? 20)
      .set('include_archived', query.includeArchived ?? false);
    if (query.search) params = params.set('search', query.search);
    if (query.status) params = params.set('status', query.status);
    return firstValueFrom(
      this.http.get<PaginatedBrandResponse>(this.baseUrl, {
        ...this.options,
        params,
      }),
    );
  }

  get(id: string): Promise<BrandDetails> {
    return firstValueFrom(this.http.get<BrandDetails>(`${this.baseUrl}/${id}`, this.options));
  }

  create(data: CreateBrandRequest): Promise<BrandSummary> {
    return firstValueFrom(this.http.post<BrandSummary>(this.baseUrl, data, this.options)).then(
      (brand) => {
        if (brand.is_active_context) this.activeBrand.set(brand);
        return brand;
      },
    );
  }

  update(id: string, data: UpdateBrandRequest): Promise<BrandSummary> {
    return firstValueFrom(
      this.http.patch<BrandSummary>(`${this.baseUrl}/${id}`, data, this.options),
    ).then((brand) => {
      if (brand.is_active_context) this.activeBrand.set(brand);
      return brand;
    });
  }

  async activate(id: string): Promise<BrandSummary> {
    const brand = await firstValueFrom(
      this.http.post<BrandSummary>(`${this.baseUrl}/${id}/activate`, {}, this.options),
    );
    this.activeBrand.set(brand);
    return brand;
  }

  async archive(id: string): Promise<BrandSummary> {
    const brand = await firstValueFrom(
      this.http.post<BrandSummary>(`${this.baseUrl}/${id}/archive`, {}, this.options),
    );
    if (this.activeBrand()?.id === id) this.activeBrand.set(null);
    return brand;
  }

  restore(id: string): Promise<BrandSummary> {
    return firstValueFrom(
      this.http.post<BrandSummary>(`${this.baseUrl}/${id}/restore`, {}, this.options),
    );
  }

  static errorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      const body: unknown = error.error;
      if (typeof body === 'object' && body !== null && 'detail' in body) {
        if (typeof body.detail === 'string') return body.detail;
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
    return 'Unable to complete the brand request. Please try again.';
  }
}
