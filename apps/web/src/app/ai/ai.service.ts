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
  AIStudioBrandVoice,
  AIStudioPreset,
  AIKeywordSet,
  AIStudioGenerateRequest,
  AIStudioGeneration,
  AIStudioArtifact,
  AIStudioContext,
  AIStudioComparison,
  AISEOAnalysis,
  AIStudioDiagnostics,
  AIStudioBulkRequest,
  AIStudioBulkPreview,
  AIStudioBulkStatus,
  AISEOAnalysisResponse,
  AIKeywordSuggestion,
  AIImageBulkPreview,
  AIImageBulkStatus,
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

  testProvider(providerKey: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.baseUrl}/providers/${providerKey}/test`,
        {},
        this.options,
      ),
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

  imageBulkPreview(data: Record<string, unknown>): Promise<AIImageBulkPreview> {
    return firstValueFrom(
      this.http.post<AIImageBulkPreview>(`${this.baseUrl}/images/bulk/preview`, data, this.options),
    );
  }

  imageBulkCreate(data: Record<string, unknown>): Promise<AIImageBulkStatus> {
    return firstValueFrom(
      this.http.post<AIImageBulkStatus>(`${this.baseUrl}/images/bulk`, data, this.options),
    );
  }

  imageBulkStatus(id: string): Promise<AIImageBulkStatus> {
    return firstValueFrom(
      this.http.get<AIImageBulkStatus>(`${this.baseUrl}/images/bulk/${id}`, this.options),
    );
  }

  imageBulkRetry(id: string, outputIds: string[] = []): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.baseUrl}/images/bulk/${id}/retry-failed`,
        { output_ids: outputIds },
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

  private readonly studioUrl = `${environment.apiUrl}/ai/studio`;

  studioBrandVoices(includeArchived = false): Promise<AIStudioBrandVoice[]> {
    const params = includeArchived ? new HttpParams().set('include_archived', 'true') : undefined;
    return firstValueFrom(
      this.http.get<AIStudioBrandVoice[]>(`${this.studioUrl}/brand-voices`, {
        ...this.options,
        params,
      }),
    );
  }
  createStudioBrandVoice(data: Partial<AIStudioBrandVoice>): Promise<AIStudioBrandVoice> {
    return firstValueFrom(
      this.http.post<AIStudioBrandVoice>(`${this.studioUrl}/brand-voices`, data, this.options),
    );
  }
  updateStudioBrandVoice(
    id: string,
    data: Partial<AIStudioBrandVoice>,
  ): Promise<AIStudioBrandVoice> {
    return firstValueFrom(
      this.http.patch<AIStudioBrandVoice>(
        `${this.studioUrl}/brand-voices/${id}`,
        data,
        this.options,
      ),
    );
  }
  duplicateStudioBrandVoice(id: string): Promise<AIStudioBrandVoice> {
    return firstValueFrom(
      this.http.post<AIStudioBrandVoice>(
        `${this.studioUrl}/brand-voices/${id}/duplicate`,
        {},
        this.options,
      ),
    );
  }
  previewStudioBrandVoice(
    id: string,
    data: { product_id: string; channel: string; content_type: string },
  ): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.studioUrl}/brand-voices/${id}/preview`,
        data,
        this.options,
      ),
    );
  }
  studioPresets(includeArchived = false): Promise<AIStudioPreset[]> {
    const params = includeArchived ? new HttpParams().set('include_archived', 'true') : undefined;
    return firstValueFrom(
      this.http.get<AIStudioPreset[]>(`${this.studioUrl}/presets`, { ...this.options, params }),
    );
  }
  createStudioPreset(data: Partial<AIStudioPreset>): Promise<AIStudioPreset> {
    return firstValueFrom(
      this.http.post<AIStudioPreset>(`${this.studioUrl}/presets`, data, this.options),
    );
  }
  updateStudioPreset(id: string, data: Partial<AIStudioPreset>): Promise<AIStudioPreset> {
    return firstValueFrom(
      this.http.patch<AIStudioPreset>(`${this.studioUrl}/presets/${id}`, data, this.options),
    );
  }
  duplicateStudioPreset(id: string): Promise<AIStudioPreset> {
    return firstValueFrom(
      this.http.post<AIStudioPreset>(`${this.studioUrl}/presets/${id}/duplicate`, {}, this.options),
    );
  }
  setDefaultStudioBrandVoice(id: string): Promise<AIStudioBrandVoice> {
    return firstValueFrom(
      this.http.post<AIStudioBrandVoice>(
        this.studioUrl + '/brand-voices/' + id + '/default',
        {},
        this.options,
      ),
    );
  }
  archiveStudioBrandVoice(id: string): Promise<AIStudioBrandVoice> {
    return firstValueFrom(
      this.http.post<AIStudioBrandVoice>(
        this.studioUrl + '/brand-voices/' + id + '/archive',
        {},
        this.options,
      ),
    );
  }
  restoreStudioBrandVoice(id: string): Promise<AIStudioBrandVoice> {
    return firstValueFrom(
      this.http.post<AIStudioBrandVoice>(
        this.studioUrl + '/brand-voices/' + id + '/restore',
        {},
        this.options,
      ),
    );
  }
  setDefaultStudioPreset(id: string): Promise<AIStudioPreset> {
    return firstValueFrom(
      this.http.post<AIStudioPreset>(
        this.studioUrl + '/presets/' + id + '/default',
        {},
        this.options,
      ),
    );
  }
  archiveStudioPreset(id: string): Promise<AIStudioPreset> {
    return firstValueFrom(
      this.http.post<AIStudioPreset>(
        this.studioUrl + '/presets/' + id + '/archive',
        {},
        this.options,
      ),
    );
  }
  restoreStudioPreset(id: string): Promise<AIStudioPreset> {
    return firstValueFrom(
      this.http.post<AIStudioPreset>(
        this.studioUrl + '/presets/' + id + '/restore',
        {},
        this.options,
      ),
    );
  }
  studioUsage(filters: Record<string, string> = {}): Promise<Record<string, unknown>> {
    let params = new HttpParams();
    Object.entries(filters).forEach(([key, value]) => (params = params.set(key, value)));
    return firstValueFrom(
      this.http.get<Record<string, unknown>>(`${this.studioUrl}/usage`, {
        ...this.options,
        params,
      }),
    );
  }
  studioKeywords(): Promise<AIKeywordSet[]> {
    return firstValueFrom(
      this.http.get<AIKeywordSet[]>(`${this.studioUrl}/keywords`, this.options),
    );
  }
  studioContext(productId: string): Promise<AIStudioContext> {
    return firstValueFrom(
      this.http.get<AIStudioContext>(`${this.studioUrl}/context/${productId}`, this.options),
    );
  }
  studioGenerate(data: AIStudioGenerateRequest): Promise<AIStudioGeneration> {
    return firstValueFrom(
      this.http.post<AIStudioGeneration>(`${this.studioUrl}/generate`, data, this.options),
    );
  }
  studioGeneration(id: string): Promise<AIStudioGeneration> {
    return firstValueFrom(
      this.http.get<AIStudioGeneration>(`${this.studioUrl}/generations/${id}`, this.options),
    );
  }
  studioArtifacts(params: Record<string, string> = {}): Promise<AIStudioArtifact[]> {
    let query = new HttpParams();
    Object.entries(params).forEach(([key, value]) => (query = query.set(key, value)));
    return firstValueFrom(
      this.http.get<AIStudioArtifact[]>(`${this.studioUrl}/artifacts`, {
        ...this.options,
        params: query,
      }),
    );
  }
  studioArtifact(id: string): Promise<AIStudioArtifact> {
    return firstValueFrom(
      this.http.get<AIStudioArtifact>(`${this.studioUrl}/artifacts/${id}`, this.options),
    );
  }
  studioCompare(id: string, againstId: string): Promise<AIStudioComparison> {
    return firstValueFrom(
      this.http.get<AIStudioComparison>(`${this.studioUrl}/artifacts/${id}/compare`, {
        ...this.options,
        params: { against_id: againstId },
      }),
    );
  }
  studioEdit(id: string, content: Record<string, unknown>): Promise<AIStudioArtifact> {
    return firstValueFrom(
      this.http.patch<AIStudioArtifact>(
        `${this.studioUrl}/artifacts/${id}`,
        { content },
        this.options,
      ),
    );
  }
  studioRegenerate(id: string): Promise<AIStudioGeneration> {
    return firstValueFrom(
      this.http.post<AIStudioGeneration>(
        `${this.studioUrl}/artifacts/${id}/regenerate`,
        {},
        this.options,
      ),
    );
  }
  studioApprove(id: string): Promise<AIStudioArtifact> {
    return firstValueFrom(
      this.http.post<AIStudioArtifact>(
        `${this.studioUrl}/artifacts/${id}/approve`,
        {},
        this.options,
      ),
    );
  }
  studioReject(id: string, reason: string): Promise<AIStudioArtifact> {
    return firstValueFrom(
      this.http.post<AIStudioArtifact>(
        `${this.studioUrl}/artifacts/${id}/reject`,
        { reason },
        this.options,
      ),
    );
  }
  studioListingHandoff(id: string, marketplace?: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.studioUrl}/artifacts/${id}/listing-handoff`,
        { marketplace, confirm: true },
        this.options,
      ),
    );
  }
  studioCampaignHandoff(id: string): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.studioUrl}/artifacts/${id}/campaign-handoff`,
        { confirm: true },
        this.options,
      ),
    );
  }
  studioBulkPreview(data: AIStudioBulkRequest): Promise<AIStudioBulkPreview> {
    return firstValueFrom(
      this.http.post<AIStudioBulkPreview>(`${this.studioUrl}/bulk/preview`, data, this.options),
    );
  }
  studioBulkCreate(data: AIStudioBulkRequest): Promise<AIStudioBulkStatus> {
    return firstValueFrom(
      this.http.post<AIStudioBulkStatus>(`${this.studioUrl}/bulk`, data, this.options),
    );
  }
  studioBulk(id: string): Promise<AIStudioBulkStatus> {
    return firstValueFrom(
      this.http.get<AIStudioBulkStatus>(`${this.studioUrl}/bulk/${id}`, this.options),
    );
  }
  studioBulkList(): Promise<AIStudioBulkStatus[]> {
    return firstValueFrom(
      this.http.get<AIStudioBulkStatus[]>(`${this.studioUrl}/bulk`, this.options),
    );
  }
  studioBulkRetryFailed(id: string, outputIds: string[] = []): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.studioUrl}/bulk/${id}/retry-failed`,
        { output_ids: outputIds },
        this.options,
      ),
    );
  }
  studioBulkCancel(id: string, outputIds: string[] = []): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.studioUrl}/bulk/${id}/cancel`,
        { output_ids: outputIds },
        this.options,
      ),
    );
  }
  studioSeo(data: {
    product_id: string;
    channel: string;
    primary_keyword?: string;
    secondary_keywords?: string[];
    artifact_id?: string;
  }): Promise<AISEOAnalysis> {
    return firstValueFrom(
      this.http.post<AISEOAnalysis>(`${this.studioUrl}/seo/analyze`, data, this.options),
    );
  }
  seoAnalyze(data: Record<string, unknown>): Promise<AISEOAnalysisResponse> {
    return firstValueFrom(
      this.http.post<AISEOAnalysisResponse>(
        `${environment.apiUrl}/ai/seo/analyze`,
        data,
        this.options,
      ),
    );
  }
  seoReanalyze(id: string): Promise<AISEOAnalysisResponse> {
    return firstValueFrom(
      this.http.post<AISEOAnalysisResponse>(
        `${environment.apiUrl}/ai/seo/analyses/${id}/reanalyze`,
        {},
        this.options,
      ),
    );
  }
  seoAnalyses(): Promise<AISEOAnalysisResponse[]> {
    return firstValueFrom(
      this.http.get<AISEOAnalysisResponse[]>(`${environment.apiUrl}/ai/seo/analyses`, this.options),
    );
  }
  seoCreateKeywords(data: Record<string, unknown>): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${environment.apiUrl}/ai/seo/keywords`,
        data,
        this.options,
      ),
    );
  }
  seoKeywordSuggestions(data: Record<string, unknown>): Promise<AIKeywordSuggestion[]> {
    return firstValueFrom(
      this.http.post<AIKeywordSuggestion[]>(
        `${environment.apiUrl}/ai/seo/keywords/suggestions`,
        data,
        this.options,
      ),
    );
  }
  seoCreateTags(data: Record<string, unknown>): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${environment.apiUrl}/ai/seo/tags`,
        data,
        this.options,
      ),
    );
  }
  studioDiagnostics(): Promise<AIStudioDiagnostics> {
    return firstValueFrom(
      this.http.get<AIStudioDiagnostics>(`${this.studioUrl}/diagnostics`, this.options),
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
