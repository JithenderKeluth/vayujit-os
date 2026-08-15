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
  environment?: string;
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
  brand_id?: string;
  product_id?: string | null;
  account_id?: string;
  video_output_id?: string | null;
  video_media_id?: string | null;
  video_version?: number | null;
  metadata_artifact_id?: string | null;
  metadata_artifact_version?: number | null;
  thumbnail_output_id?: string | null;
  thumbnail_version?: number | null;
  caption_track_id?: string | null;
  caption_version?: number | null;
  locale?: string;
  description?: string | null;
  hashtags?: string[];
  correlation_id?: string;
  schedule_id?: string | null;
  preview_fingerprint?: string | null;
  failure_code?: string | null;
  safe_failure_message?: string | null;
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
  correlation_id?: string | null;
  retryable?: boolean;
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
  social_post_id?: string;
  video_output_id?: string | null;
  video_version?: number | null;
  schedule_id?: string | null;
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
  video?: {
    publications: number;
    impressions: number | null;
    views: number | null;
    engagement: number | null;
    breakdown: Array<Record<string, unknown>>;
  };
}

export interface SocialPreview {
  post_id: string;
  platform: string;
  account: SocialAccount;
  format: string;
  caption: string | null;
  title: string | null;
  description: string | null;
  media_ids: string[];
  hashtags: string[];
  cta: Record<string, unknown> | null;
  schedule: Record<string, unknown>;
  readiness: Record<string, unknown>;
  fingerprint: string;
}

export interface SocialChannelProjection {
  product_id: string;
  channel: string;
  update_available: boolean;
  posts: SocialPost[];
  video: Array<Record<string, unknown>>;
}

@Injectable({ providedIn: 'root' })
export class SocialService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiUrl + '/social';
  private readonly options = { withCredentials: true } as const;

  accounts(): Promise<SocialAccount[]> {
    return firstValueFrom(this.http.get<SocialAccount[]>(this.baseUrl + '/accounts', this.options));
  }

  posts(): Promise<SocialPost[]> {
    return firstValueFrom(this.http.get<SocialPost[]>(this.baseUrl + '/posts', this.options));
  }

  platforms(): Promise<Array<Record<string, unknown>>> {
    return firstValueFrom(
      this.http.get<Array<Record<string, unknown>>>(this.baseUrl + '/platforms', this.options),
    );
  }

  recovery(): Promise<SocialRecoveryItem[]> {
    return firstValueFrom(
      this.http.get<SocialRecoveryItem[]>(this.baseUrl + '/recovery', this.options),
    );
  }

  analytics(): Promise<SocialAnalyticsSummary> {
    return firstValueFrom(
      this.http.get<SocialAnalyticsSummary>(this.baseUrl + '/analytics/summary', this.options),
    );
  }

  calendar(params: Record<string, string> = {}): Promise<SocialCalendarEvent[]> {
    const query = new URLSearchParams(params).toString();
    return firstValueFrom(
      this.http.get<SocialCalendarEvent[]>(
        this.baseUrl + '/calendar' + (query ? '?' + query : ''),
        this.options,
      ),
    );
  }

  history(postId: string): Promise<SocialHistoryItem[]> {
    return firstValueFrom(
      this.http.get<SocialHistoryItem[]>(
        this.baseUrl + '/posts/' + postId + '/history',
        this.options,
      ),
    );
  }

  post(postId: string): Promise<SocialPost> {
    return firstValueFrom(
      this.http.get<SocialPost>(this.baseUrl + '/posts/' + postId, this.options),
    );
  }

  preview(postId: string): Promise<SocialPreview> {
    return firstValueFrom(
      this.http.get<SocialPreview>(this.baseUrl + '/posts/' + postId + '/preview', this.options),
    );
  }

  createPost(payload: Record<string, unknown>): Promise<SocialPost> {
    return firstValueFrom(
      this.http.post<SocialPost>(this.baseUrl + '/posts', payload, this.options),
    );
  }

  schedulePost(
    postId: string,
    payload: Record<string, unknown>,
    publishNow = false,
  ): Promise<SocialPost> {
    const path = publishNow ? 'publish-now' : 'schedule';
    return firstValueFrom(
      this.http.post<SocialPost>(
        this.baseUrl + '/posts/' + postId + '/' + path,
        payload,
        this.options,
      ),
    );
  }

  recoveryAction(payload: Record<string, unknown>): Promise<{ result?: Record<string, unknown> }> {
    return firstValueFrom(
      this.http.post<{ result?: Record<string, unknown> }>(
        this.baseUrl + '/recovery/actions',
        payload,
        this.options,
      ),
    );
  }

  videoGenerations(): Promise<Array<Record<string, unknown>>> {
    return firstValueFrom(
      this.http.get<Array<Record<string, unknown>>>(
        environment.apiUrl + '/ai/video/generations',
        this.options,
      ),
    );
  }

  productChannel(productId: string): Promise<SocialChannelProjection> {
    return firstValueFrom(
      this.http.get<SocialChannelProjection>(
        this.baseUrl + '/products/' + productId + '/channel',
        this.options,
      ),
    );
  }
}
