import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

export interface SocialAccount {
  id: string;
  platform: string;
  display_name: string;
  remote_account_id: string;
  enabled: boolean;
  validation_status: string;
  capabilities: Record<string, unknown>;
  credential_configured: boolean;
}

export interface SocialPost {
  id: string;
  platform: string;
  content_type: string;
  lifecycle_status: string;
  content_artifact_id: string;
  content_artifact_version: number;
  media_ids: string[];
  caption: string | null;
  title: string | null;
  remote_publication_id: string | null;
  scheduled_at_utc: string | null;
}

@Injectable({ providedIn: 'root' })
export class SocialService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/social`;
  private readonly options = { withCredentials: true } as const;

  accounts(): Promise<SocialAccount[]> {
    return firstValueFrom(this.http.get<SocialAccount[]>(`${this.baseUrl}/accounts`, this.options));
  }

  posts(): Promise<SocialPost[]> {
    return firstValueFrom(this.http.get<SocialPost[]>(`${this.baseUrl}/posts`, this.options));
  }

  platforms(): Promise<Array<Record<string, unknown>>> {
    return firstValueFrom(
      this.http.get<Array<Record<string, unknown>>>(`${this.baseUrl}/platforms`, this.options),
    );
  }

  recovery(): Promise<SocialRecoveryItem[]> {
    return firstValueFrom(
      this.http.get<SocialRecoveryItem[]>(`${this.baseUrl}/recovery`, this.options),
    );
  }

  analytics(): Promise<SocialAnalyticsSummary> {
    return firstValueFrom(
      this.http.get<SocialAnalyticsSummary>(`${this.baseUrl}/analytics/summary`, this.options),
    );
  }

  calendar(params: Record<string, string> = {}): Promise<SocialCalendarEvent[]> {
    const query = new URLSearchParams(params).toString();
    const suffix = query ? `?${query}` : '';
    return firstValueFrom(
      this.http.get<SocialCalendarEvent[]>(`${this.baseUrl}/calendar${suffix}`, this.options),
    );
  }

  history(postId: string): Promise<SocialHistoryItem[]> {
    return firstValueFrom(
      this.http.get<SocialHistoryItem[]>(`${this.baseUrl}/posts/${postId}/history`, this.options),
    );
  }
}

export interface SocialRecoveryItem {
  post_id: string;
  platform: string;
  content_type: string;
  lifecycle_status: string;
  failure_code: string | null;
  safe_failure_message: string | null;
  remote_publication_id: string | null;
  available_actions: string[];
}

export interface SocialCalendarEvent {
  id: string;
  type: string;
  platform: string;
  channel: string;
  content_type: string;
  status: string;
  scheduled_at_utc: string;
  timezone: string | null;
  brand_id: string;
  product_id: string | null;
  campaign_id: string | null;
  account_id: string;
  artifact_id: string;
  artifact_version: number;
  failure_code: string | null;
  readiness: string;
}

export interface SocialHistoryItem {
  id: string;
  action: string;
  occurred_at: string;
  metadata: Record<string, unknown>;
}

export interface SocialAnalyticsSummary {
  publications: number;
  published: number;
  failed: number;
  scheduled: number;
  metrics: Record<string, number>;
  synthetic: boolean;
}
