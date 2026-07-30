import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type {
  Campaign,
  CampaignActivity,
  CampaignCalendar,
  CampaignConflict,
  CampaignProgress,
  CampaignReadiness,
  CampaignHealth,
  CampaignSelectorPage,
} from '@vayujit/shared';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class CampaignService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/campaigns`;
  private readonly options = { withCredentials: true } as const;

  list(status = ''): Promise<Campaign[]> {
    const params = status ? new HttpParams().set('status', status) : undefined;
    return firstValueFrom(this.http.get<Campaign[]>(this.base, { ...this.options, params }));
  }
  get(id: string): Promise<Campaign> {
    return firstValueFrom(this.http.get<Campaign>(`${this.base}/${id}`, this.options));
  }
  create(data: Record<string, unknown>): Promise<Campaign> {
    return firstValueFrom(this.http.post<Campaign>(this.base, data, this.options));
  }
  update(id: string, data: Record<string, unknown>): Promise<Campaign> {
    return firstValueFrom(this.http.put<Campaign>(`${this.base}/${id}`, data, this.options));
  }
  activities(id: string): Promise<CampaignActivity[]> {
    return firstValueFrom(
      this.http.get<CampaignActivity[]>(`${this.base}/${id}/activities`, this.options),
    );
  }
  createActivity(id: string, data: Record<string, unknown>): Promise<CampaignActivity> {
    return firstValueFrom(
      this.http.post<CampaignActivity>(`${this.base}/${id}/activities`, data, this.options),
    );
  }
  lookup(
    kind: string,
    search = '',
    filters: { productId?: string; campaignId?: string; connectorKey?: string } = {},
  ): Promise<CampaignSelectorPage> {
    let params = new HttpParams().set('search', search).set('page_size', 50);
    if (filters.productId) params = params.set('product_id', filters.productId);
    if (filters.campaignId) params = params.set('campaign_id', filters.campaignId);
    if (filters.connectorKey) params = params.set('connector_key', filters.connectorKey);
    return firstValueFrom(
      this.http.get<CampaignSelectorPage>(`${this.base}/lookups/${kind}`, {
        ...this.options,
        params,
      }),
    );
  }
  dependencies(id: string): Promise<Array<Record<string, string | null>>> {
    return firstValueFrom(
      this.http.get<Array<Record<string, string | null>>>(
        `${this.base}/${id}/dependencies`,
        this.options,
      ),
    );
  }
  addDependency(id: string, data: Record<string, string>): Promise<Record<string, string>> {
    return firstValueFrom(
      this.http.post<Record<string, string>>(`${this.base}/${id}/dependencies`, data, this.options),
    );
  }
  removeDependency(id: string, dependencyId: string): Promise<void> {
    return firstValueFrom(
      this.http.delete<void>(`${this.base}/${id}/dependencies/${dependencyId}`, this.options),
    );
  }
  readiness(id: string): Promise<CampaignReadiness> {
    return firstValueFrom(
      this.http.post<CampaignReadiness>(`${this.base}/${id}/validate`, {}, this.options),
    );
  }
  conflicts(id: string): Promise<CampaignConflict[]> {
    return firstValueFrom(
      this.http.get<CampaignConflict[]>(`${this.base}/${id}/conflicts`, this.options),
    );
  }
  progress(id: string): Promise<CampaignProgress> {
    return firstValueFrom(
      this.http.get<CampaignProgress>(`${this.base}/${id}/progress`, this.options),
    );
  }
  health(): Promise<CampaignHealth> {
    return firstValueFrom(this.http.get<CampaignHealth>(`${this.base}/health`, this.options));
  }
  release(id: string): Promise<Campaign> {
    return this.lifecycle(id, 'release', { confirm: true });
  }
  pause(id: string): Promise<Campaign> {
    return this.lifecycle(id, 'pause', {});
  }
  resume(id: string, policy: string): Promise<Campaign> {
    return this.lifecycle(id, 'resume', { missed_activity_policy: policy });
  }
  cancel(id: string, reason: string): Promise<Campaign> {
    return this.lifecycle(id, 'cancel', { reason });
  }
  schedule(id: string, activityIds: string[] = []): Promise<Record<string, unknown>> {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(
        `${this.base}/${id}/schedule`,
        { activity_ids: activityIds, behavior: 'require_all_ready', confirm: true },
        this.options,
      ),
    );
  }
  calendar(
    start: string,
    end: string,
    view: 'month' | 'week' | 'agenda',
    campaignId?: string,
  ): Promise<CampaignCalendar> {
    let params = new HttpParams().set('start', start).set('end', end).set('view', view);
    if (campaignId) params = params.set('campaign_id', campaignId);
    return firstValueFrom(
      this.http.get<CampaignCalendar>(`${this.base}/calendar`, {
        ...this.options,
        params,
      }),
    );
  }
  private lifecycle(id: string, action: string, body: Record<string, unknown>): Promise<Campaign> {
    return firstValueFrom(
      this.http.post<Campaign>(`${this.base}/${id}/${action}`, body, this.options),
    );
  }
}
