import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type {
  CreateWorkflowRequest,
  PaginatedWorkflowResponse,
  WorkflowDetails,
  WorkflowFilters,
  WorkflowTemplateSummary,
} from '@vayujit/shared';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class WorkflowService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/workflows`;
  private readonly options = { withCredentials: true } as const;

  templates(): Promise<WorkflowTemplateSummary[]> {
    return firstValueFrom(
      this.http.get<WorkflowTemplateSummary[]>(`${this.base}/templates`, this.options),
    );
  }
  create(data: CreateWorkflowRequest): Promise<WorkflowDetails> {
    return firstValueFrom(this.http.post<WorkflowDetails>(this.base, data, this.options));
  }
  list(filters: WorkflowFilters = {}): Promise<PaginatedWorkflowResponse> {
    let params = new HttpParams()
      .set('page', filters.page ?? 1)
      .set('page_size', filters.pageSize ?? 20);
    const values: Record<string, string | undefined> = {
      brand_id: filters.brandId,
      product_id: filters.productId,
      destination_id: filters.destinationId,
      status: filters.status || undefined,
      current_step: filters.currentStep,
      date_from: filters.dateFrom,
      date_to: filters.dateTo,
    };
    for (const [key, value] of Object.entries(values)) if (value) params = params.set(key, value);
    if (filters.retryable !== null && filters.retryable !== undefined) {
      params = params.set('retryable', filters.retryable);
    }
    return firstValueFrom(
      this.http.get<PaginatedWorkflowResponse>(this.base, { ...this.options, params }),
    );
  }
  get(id: string): Promise<WorkflowDetails> {
    return firstValueFrom(this.http.get<WorkflowDetails>(`${this.base}/${id}`, this.options));
  }
  start(id: string): Promise<WorkflowDetails> {
    return this.action(id, 'start');
  }
  continue(id: string): Promise<WorkflowDetails> {
    return this.action(id, 'continue');
  }
  retry(id: string): Promise<WorkflowDetails> {
    return this.action(id, 'retry');
  }
  cancel(id: string): Promise<WorkflowDetails> {
    return this.action(id, 'cancel');
  }
  static errorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      const body: unknown = error.error;
      if (typeof body === 'object' && body !== null && 'detail' in body) {
        if (typeof body.detail === 'string') return body.detail;
        if (typeof body.detail === 'object' && body.detail !== null && 'message' in body.detail) {
          return String(body.detail.message);
        }
      }
    }
    return 'Unable to complete the Workflow request. Please try again.';
  }
  private action(id: string, action: string): Promise<WorkflowDetails> {
    return firstValueFrom(
      this.http.post<WorkflowDetails>(`${this.base}/${id}/${action}`, {}, this.options),
    );
  }
}
