import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type {
  AIArtifactDetails,
  AIGenerationResponse,
  AIHistoryFilters,
  AIProviderSummary,
  AIProviderConfiguration,
  UpdateAIProviderConfiguration,
  AIProviderValidationResult,
  AIModelSummary,
  AIUsageSummary,
  PaginatedAIUsageHistory,
  AIGenerationAttempt,
  AICancellationResponse,
  AITemplateSummary,
  CreateAIGenerationRequest,
  PaginatedAIHistory,
} from '@vayujit/shared';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class AIService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/ai`;
  private readonly options = { withCredentials: true } as const;

  providers(): Promise<AIProviderSummary[]> {
    return firstValueFrom(
      this.http.get<AIProviderSummary[]>(`${this.baseUrl}/providers`, this.options),
    );
  }

  providerConfiguration(): Promise<AIProviderConfiguration> {
    return firstValueFrom(
      this.http.get<AIProviderConfiguration>(
        `${this.baseUrl}/providers/openai_compatible/configuration`,
        this.options,
      ),
    );
  }

  saveProvider(data: UpdateAIProviderConfiguration): Promise<AIProviderConfiguration> {
    return firstValueFrom(
      this.http.put<AIProviderConfiguration>(
        `${this.baseUrl}/providers/openai_compatible`,
        data,
        this.options,
      ),
    );
  }

  validateProvider(): Promise<AIProviderValidationResult> {
    return firstValueFrom(
      this.http.post<AIProviderValidationResult>(
        `${this.baseUrl}/providers/openai_compatible/validate`,
        {},
        this.options,
      ),
    );
  }

  removeCredential(): Promise<AIProviderConfiguration> {
    return firstValueFrom(
      this.http.delete<AIProviderConfiguration>(
        `${this.baseUrl}/providers/openai_compatible/credential`,
        this.options,
      ),
    );
  }

  models(): Promise<AIModelSummary[]> {
    return firstValueFrom(
      this.http.get<AIModelSummary[]>(
        `${this.baseUrl}/providers/openai_compatible/models`,
        this.options,
      ),
    );
  }

  usage(): Promise<AIUsageSummary> {
    return firstValueFrom(
      this.http.get<AIUsageSummary>(`${this.baseUrl}/usage/summary`, this.options),
    );
  }

  usageHistory(providerKey = ''): Promise<PaginatedAIUsageHistory> {
    const params = providerKey ? new HttpParams().set('provider_key', providerKey) : undefined;
    return firstValueFrom(
      this.http.get<PaginatedAIUsageHistory>(`${this.baseUrl}/usage/history`, {
        ...this.options,
        params,
      }),
    );
  }

  usageExport(): Promise<Blob> {
    return firstValueFrom(
      this.http.get(`${this.baseUrl}/usage/export`, {
        ...this.options,
        responseType: 'blob',
      }),
    );
  }

  attempts(id: string): Promise<AIGenerationAttempt[]> {
    return firstValueFrom(
      this.http.get<AIGenerationAttempt[]>(
        `${this.baseUrl}/generations/${id}/attempts`,
        this.options,
      ),
    );
  }

  cancel(id: string): Promise<AICancellationResponse> {
    return firstValueFrom(
      this.http.post<AICancellationResponse>(
        `${this.baseUrl}/generations/${id}/cancel`,
        {},
        this.options,
      ),
    );
  }

  templates(): Promise<AITemplateSummary[]> {
    return firstValueFrom(
      this.http.get<AITemplateSummary[]>(`${this.baseUrl}/templates`, this.options),
    );
  }

  generate(data: CreateAIGenerationRequest): Promise<AIGenerationResponse> {
    return firstValueFrom(
      this.http.post<AIGenerationResponse>(`${this.baseUrl}/generations`, data, this.options),
    );
  }

  history(filters: AIHistoryFilters = {}): Promise<PaginatedAIHistory> {
    let params = new HttpParams()
      .set('page', filters.page ?? 1)
      .set('page_size', filters.pageSize ?? 20);
    if (filters.productId) params = params.set('product_id', filters.productId);
    if (filters.brandId) params = params.set('brand_id', filters.brandId);
    if (filters.requestStatus) params = params.set('request_status', filters.requestStatus);
    if (filters.artifactStatus) params = params.set('artifact_status', filters.artifactStatus);
    if (filters.dateFrom) params = params.set('date_from', filters.dateFrom);
    if (filters.dateTo) params = params.set('date_to', filters.dateTo);
    return firstValueFrom(
      this.http.get<PaginatedAIHistory>(`${this.baseUrl}/generations`, {
        ...this.options,
        params,
      }),
    );
  }

  artifact(id: string): Promise<AIArtifactDetails> {
    return firstValueFrom(
      this.http.get<AIArtifactDetails>(`${this.baseUrl}/artifacts/${id}`, this.options),
    );
  }

  approve(id: string): Promise<AIArtifactDetails> {
    return this.decision(id, 'approve', {});
  }

  reject(id: string, reason: string): Promise<AIArtifactDetails> {
    return this.decision(id, 'reject', { reason });
  }

  regenerate(id: string): Promise<AIGenerationResponse> {
    return firstValueFrom(
      this.http.post<AIGenerationResponse>(
        `${this.baseUrl}/artifacts/${id}/regenerate`,
        {},
        this.options,
      ),
    );
  }

  static errorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      const body: unknown = error.error;
      if (
        typeof body === 'object' &&
        body !== null &&
        'detail' in body &&
        typeof body.detail === 'string'
      ) {
        return body.detail;
      }
    }
    return 'Unable to complete the AI content request. Please try again.';
  }

  private decision(
    id: string,
    action: 'approve' | 'reject',
    body: object,
  ): Promise<AIArtifactDetails> {
    return firstValueFrom(
      this.http.post<AIArtifactDetails>(
        `${this.baseUrl}/artifacts/${id}/${action}`,
        body,
        this.options,
      ),
    );
  }
}
