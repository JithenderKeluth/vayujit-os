import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type {
  CatalogChannel,
  CatalogListingDraft,
  CatalogEconomics,
  CatalogProductImage,
  CatalogProductDetails,
  CatalogReadiness,
  CatalogVariant,
} from '@vayujit/shared';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class CatalogService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/catalog`;
  private readonly options = { withCredentials: true } as const;

  getProduct(productId: string): Promise<CatalogProductDetails> {
    return firstValueFrom(
      this.http.get<CatalogProductDetails>(`${this.baseUrl}/products/${productId}`, this.options),
    );
  }

  readiness(productId: string): Promise<CatalogReadiness> {
    return firstValueFrom(
      this.http.get<CatalogReadiness>(
        `${this.baseUrl}/products/${productId}/readiness`,
        this.options,
      ),
    );
  }

  createVariant(
    productId: string,
    data: {
      variant_key: string;
      title: string;
      sku?: string | null;
      option_values?: Record<string, unknown>;
      attributes?: Record<string, unknown>;
      image_refs?: unknown[];
    },
  ): Promise<CatalogVariant> {
    return firstValueFrom(
      this.http.post<CatalogVariant>(
        `${this.baseUrl}/products/${productId}/variants`,
        data,
        this.options,
      ),
    );
  }

  updateVariant(
    variant: CatalogVariant,
    data: Partial<Pick<CatalogVariant, 'variant_key' | 'title' | 'sku' | 'option_values' | 'attributes' | 'image_refs' | 'price_amount' | 'currency' | 'status'>>,
  ): Promise<CatalogVariant> {
    return firstValueFrom(
      this.http.patch<CatalogVariant>(
        `${this.baseUrl}/variants/${variant.id}`,
        { ...data, version: variant.version },
        this.options,
      ),
    );
  }

  images(productId: string): Promise<CatalogProductImage[]> {
    return firstValueFrom(
      this.http.get<CatalogProductImage[]>(`${this.baseUrl}/products/${productId}/images`, this.options),
    );
  }

  attachImage(
    productId: string,
    data: { media_id: string; alt_text?: string | null; position?: number; is_primary?: boolean },
  ): Promise<CatalogProductImage> {
    return firstValueFrom(
      this.http.post<CatalogProductImage>(`${this.baseUrl}/products/${productId}/images`, data, this.options),
    );
  }

  updateImage(
    image: CatalogProductImage,
    data: Partial<Pick<CatalogProductImage, 'alt_text' | 'position' | 'is_primary'>>,
  ): Promise<CatalogProductImage> {
    return firstValueFrom(
      this.http.patch<CatalogProductImage>(
        `${this.baseUrl}/images/${image.id}`,
        { ...data, version: image.version },
        this.options,
      ),
    );
  }

  removeImage(image: CatalogProductImage): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.baseUrl}/images/${image.id}`, this.options));
  }

  economics(productId: string): Promise<CatalogEconomics> {
    return firstValueFrom(
      this.http.get<CatalogEconomics>(`${this.baseUrl}/products/${productId}/economics`, this.options),
    );
  }

  media(): Promise<{ items: Array<{ id: string; original_filename: string; preview_url: string; mime_type: string; status: string }>; total: number }> {
    return firstValueFrom(
      this.http.get<{ items: Array<{ id: string; original_filename: string; preview_url: string; mime_type: string; status: string }>; total: number }>(
        `${environment.apiUrl}/media?page_size=100`,
        this.options,
      ),
    );
  }

  createListingDraft(
    productId: string,
    data: {
      channel: CatalogChannel;
      title?: string;
      description?: string;
      category?: string | null;
      idempotency_key?: string;
    },
  ): Promise<CatalogListingDraft> {
    return firstValueFrom(
      this.http.post<CatalogListingDraft>(
        `${this.baseUrl}/products/${productId}/listing-drafts`,
        data,
        this.options,
      ),
    );
  }

  updateListingDraft(
    draft: CatalogListingDraft,
    data: Partial<
      Pick<
        CatalogListingDraft,
        | 'title'
        | 'description'
        | 'category'
        | 'bullets'
        | 'image_refs'
        | 'intended_price_amount'
        | 'intended_currency'
        | 'compliance'
      >
    >,
  ): Promise<CatalogListingDraft> {
    return firstValueFrom(
      this.http.patch<CatalogListingDraft>(
        `${this.baseUrl}/listing-drafts/${draft.id}`,
        { ...data, version: draft.version },
        this.options,
      ),
    );
  }

  reviewListingDraft(
    draft: CatalogListingDraft,
    decision: 'approve' | 'return_for_changes',
  ): Promise<CatalogListingDraft> {
    return firstValueFrom(
      this.http.post<CatalogListingDraft>(
        `${this.baseUrl}/listing-drafts/${draft.id}/review`,
        { version: draft.version, decision },
        this.options,
      ),
    );
  }

  static errorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      const body: unknown = error.error;
      const detail =
        typeof body === 'object' && body !== null && 'detail' in body ? body.detail : undefined;
      if (typeof detail === 'string') return detail;
      if (detail && typeof detail === 'object' && 'message' in detail) {
        return String(detail.message);
      }
    }
    return 'The catalog request could not be completed. Refresh and try again.';
  }
}
