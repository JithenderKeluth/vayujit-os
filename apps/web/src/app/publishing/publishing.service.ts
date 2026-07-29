import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type {
  CreatePublishingDestinationRequest,
  CreatePublishingExecutionRequest,
  PaginatedPublishingDestinations,
  PaginatedPublishingExecutions,
  PublishingConnectorSummary,
  PublishingDestinationSummary,
  PublishingExecutionDetails,
  UpdatePublishingDestinationRequest,
  UpdateWordPressConnectorRequest,
  WordPressAuthor,
  WordPressConnectorConfiguration,
  WordPressTerm,
  WordPressValidationResult,
  PublishingReconciliationResult,
} from '@vayujit/shared';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class PublishingService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/publishing`;
  private readonly options = { withCredentials: true } as const;
  connectors() {
    return firstValueFrom(
      this.http.get<PublishingConnectorSummary[]>(`${this.base}/connectors`, this.options),
    );
  }
  destinations(
    filters: {
      search?: string;
      brandId?: string;
      connectorKey?: string;
      status?: string;
      page?: number;
      pageSize?: number;
    } = {},
  ) {
    let params = new HttpParams()
      .set('page', filters.page ?? 1)
      .set('page_size', filters.pageSize ?? 20);
    if (filters.search) params = params.set('search', filters.search);
    if (filters.brandId) params = params.set('brand_id', filters.brandId);
    if (filters.connectorKey) params = params.set('connector_key', filters.connectorKey);
    if (filters.status) params = params.set('status', filters.status);
    return firstValueFrom(
      this.http.get<PaginatedPublishingDestinations>(`${this.base}/destinations`, {
        ...this.options,
        params,
      }),
    );
  }
  destination(id: string) {
    return firstValueFrom(
      this.http.get<PublishingDestinationSummary>(`${this.base}/destinations/${id}`, this.options),
    );
  }
  createDestination(data: CreatePublishingDestinationRequest) {
    return firstValueFrom(
      this.http.post<PublishingDestinationSummary>(`${this.base}/destinations`, data, this.options),
    );
  }
  updateDestination(id: string, data: UpdatePublishingDestinationRequest) {
    return firstValueFrom(
      this.http.patch<PublishingDestinationSummary>(
        `${this.base}/destinations/${id}`,
        data,
        this.options,
      ),
    );
  }
  destinationStatus(id: string, action: 'enable' | 'disable') {
    return firstValueFrom(
      this.http.post<PublishingDestinationSummary>(
        `${this.base}/destinations/${id}/${action}`,
        {},
        this.options,
      ),
    );
  }
  executions(
    filters: {
      brandId?: string;
      productId?: string;
      artifactId?: string;
      destinationId?: string;
      connectorKey?: string;
      status?: string;
      retryable?: boolean | null;
      dateFrom?: string;
      dateTo?: string;
      page?: number;
      pageSize?: number;
    } = {},
  ) {
    let params = new HttpParams()
      .set('page', filters.page ?? 1)
      .set('page_size', filters.pageSize ?? 20);
    const values: Record<string, string | undefined> = {
      brand_id: filters.brandId,
      product_id: filters.productId,
      artifact_id: filters.artifactId,
      destination_id: filters.destinationId,
      connector_key: filters.connectorKey,
      status: filters.status,
      date_from: filters.dateFrom,
      date_to: filters.dateTo,
    };
    for (const [key, value] of Object.entries(values)) if (value) params = params.set(key, value);
    if (filters.retryable !== null && filters.retryable !== undefined)
      params = params.set('retryable', filters.retryable);
    return firstValueFrom(
      this.http.get<PaginatedPublishingExecutions>(`${this.base}/executions`, {
        ...this.options,
        params,
      }),
    );
  }
  execution(id: string) {
    return firstValueFrom(
      this.http.get<PublishingExecutionDetails>(`${this.base}/executions/${id}`, this.options),
    );
  }
  publish(data: CreatePublishingExecutionRequest) {
    return firstValueFrom(
      this.http.post<PublishingExecutionDetails>(`${this.base}/executions`, data, this.options),
    );
  }
  retry(id: string) {
    return firstValueFrom(
      this.http.post<PublishingExecutionDetails>(
        `${this.base}/executions/${id}/retry`,
        {},
        this.options,
      ),
    );
  }
  wordpressConfiguration() {
    return firstValueFrom(
      this.http.get<WordPressConnectorConfiguration>(
        `${this.base}/connectors/wordpress`,
        this.options,
      ),
    );
  }
  saveWordpressConfiguration(data: UpdateWordPressConnectorRequest) {
    return firstValueFrom(
      this.http.put<WordPressConnectorConfiguration>(
        `${this.base}/connectors/wordpress`,
        data,
        this.options,
      ),
    );
  }
  validateWordpress() {
    return firstValueFrom(
      this.http.post<WordPressValidationResult>(
        `${this.base}/connectors/wordpress/validate`,
        {},
        this.options,
      ),
    );
  }
  setWordpressEnabled(action: 'enable' | 'disable') {
    return firstValueFrom(
      this.http.post<WordPressConnectorConfiguration>(
        `${this.base}/connectors/wordpress/${action}`,
        {},
        this.options,
      ),
    );
  }
  removeWordpressCredential() {
    return firstValueFrom(
      this.http.delete<WordPressConnectorConfiguration>(
        `${this.base}/connectors/wordpress/credential`,
        this.options,
      ),
    );
  }
  wordpressCategories() {
    return firstValueFrom(
      this.http.get<WordPressTerm[]>(`${this.base}/connectors/wordpress/categories`, this.options),
    );
  }
  wordpressTags() {
    return firstValueFrom(
      this.http.get<WordPressTerm[]>(`${this.base}/connectors/wordpress/tags`, this.options),
    );
  }
  wordpressAuthors() {
    return firstValueFrom(
      this.http.get<WordPressAuthor[]>(`${this.base}/connectors/wordpress/authors`, this.options),
    );
  }
  cancel(id: string) {
    return firstValueFrom(
      this.http.post<PublishingExecutionDetails>(
        `${this.base}/executions/${id}/cancel`,
        {},
        this.options,
      ),
    );
  }
  reconcile(id: string) {
    return firstValueFrom(
      this.http.post<PublishingReconciliationResult>(
        `${this.base}/executions/${id}/reconcile`,
        {},
        this.options,
      ),
    );
  }
  moveToDraft(id: string) {
    return firstValueFrom(
      this.http.post<PublishingExecutionDetails>(
        `${this.base}/executions/${id}/move-to-draft`,
        {},
        this.options,
      ),
    );
  }

  static errorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      const body: unknown = error.error;
      if (typeof body === 'object' && body !== null && 'detail' in body) {
        if (typeof body.detail === 'string') return body.detail;
        if (typeof body.detail === 'object' && body.detail !== null && 'message' in body.detail) {
          return String(body.detail.message);
        }
        if (Array.isArray(body.detail))
          return body.detail
            .map((item: { msg?: string }) => item.msg ?? '')
            .filter(Boolean)
            .join(' ');
      }
    }
    return 'Unable to complete the publishing request. Please try again.';
  }
}
