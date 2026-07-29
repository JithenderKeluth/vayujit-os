import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type {
  ApprovalDetailsResponse,
  DashboardResponse,
  OwnerPreferences,
  PaginatedApprovals,
  PaginatedOperations,
  SessionSummary,
  SettingsResponse,
  SystemStatus,
  BackupSummary,
  OperationalHealth,
  RecoveryPage,
  ReleaseInfo,
  RestoreCheck,
} from '@vayujit/shared';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class OperationsService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiUrl;
  private readonly options = { withCredentials: true } as const;
  dashboard(brandId = ''): Promise<DashboardResponse> {
    const params = brandId ? new HttpParams().set('brand_id', brandId) : undefined;
    return firstValueFrom(
      this.http.get<DashboardResponse>(`${this.base}/dashboard/summary`, {
        ...this.options,
        params,
      }),
    );
  }
  approvals(filters: Record<string, string | number | undefined>): Promise<PaginatedApprovals> {
    return firstValueFrom(
      this.http.get<PaginatedApprovals>(`${this.base}/approvals`, {
        ...this.options,
        params: this.params(filters),
      }),
    );
  }
  approval(id: string): Promise<ApprovalDetailsResponse> {
    return firstValueFrom(
      this.http.get<ApprovalDetailsResponse>(`${this.base}/approvals/${id}`, this.options),
    );
  }
  history(filters: Record<string, string | number | undefined>): Promise<PaginatedOperations> {
    return firstValueFrom(
      this.http.get<PaginatedOperations>(`${this.base}/operations/history`, {
        ...this.options,
        params: this.params(filters),
      }),
    );
  }
  exportHistory(filters: Record<string, string | undefined>): Promise<Blob> {
    return firstValueFrom(
      this.http.get(`${this.base}/operations/history/export`, {
        ...this.options,
        params: this.params(filters),
        responseType: 'blob',
      }),
    );
  }
  settings(): Promise<SettingsResponse> {
    return firstValueFrom(this.http.get<SettingsResponse>(`${this.base}/settings`, this.options));
  }
  updateProfile(fullName: string): Promise<SettingsResponse> {
    return firstValueFrom(
      this.http.patch<SettingsResponse>(
        `${this.base}/settings/profile`,
        { full_name: fullName },
        this.options,
      ),
    );
  }
  updatePreferences(value: OwnerPreferences): Promise<SettingsResponse> {
    return firstValueFrom(
      this.http.patch<SettingsResponse>(`${this.base}/settings/preferences`, value, this.options),
    );
  }
  changePassword(current: string, password: string, confirmation: string): Promise<void> {
    return firstValueFrom(
      this.http.post<void>(
        `${this.base}/settings/change-password`,
        { current_password: current, new_password: password, confirmation },
        this.options,
      ),
    );
  }
  sessions(): Promise<SessionSummary[]> {
    return firstValueFrom(
      this.http.get<SessionSummary[]>(`${this.base}/settings/sessions`, this.options),
    );
  }
  revoke(scope: 'others' | 'all'): Promise<void> {
    return firstValueFrom(
      this.http.post<void>(`${this.base}/settings/sessions/revoke-${scope}`, {}, this.options),
    );
  }
  system(): Promise<SystemStatus> {
    return firstValueFrom(this.http.get<SystemStatus>(`${this.base}/system/status`, this.options));
  }
  health(): Promise<OperationalHealth> {
    return firstValueFrom(
      this.http.get<OperationalHealth>(`${this.base}/system/health`, this.options),
    );
  }
  release(): Promise<ReleaseInfo> {
    return firstValueFrom(this.http.get<ReleaseInfo>(`${this.base}/system/release`, this.options));
  }
  maintenance(): Promise<{ enabled: boolean }> {
    return firstValueFrom(
      this.http.get<{ enabled: boolean }>(`${this.base}/system/maintenance`, this.options),
    );
  }
  recovery(filters: Record<string, string | number | undefined> = {}): Promise<RecoveryPage> {
    return firstValueFrom(
      this.http.get<RecoveryPage>(`${this.base}/operations/recovery`, {
        ...this.options,
        params: this.params(filters),
      }),
    );
  }
  backups(): Promise<BackupSummary[]> {
    return firstValueFrom(
      this.http.get<BackupSummary[]>(`${this.base}/operations/backups`, this.options),
    );
  }
  createBackup(): Promise<BackupSummary> {
    return firstValueFrom(
      this.http.post<BackupSummary>(`${this.base}/operations/backups`, {}, this.options),
    );
  }
  verifyBackup(id: string): Promise<BackupSummary> {
    return firstValueFrom(
      this.http.post<BackupSummary>(
        `${this.base}/operations/backups/${id}/verify`,
        {},
        this.options,
      ),
    );
  }
  restoreCheck(id: string): Promise<RestoreCheck> {
    return firstValueFrom(
      this.http.post<RestoreCheck>(
        `${this.base}/operations/backups/${id}/restore-check`,
        {},
        this.options,
      ),
    );
  }
  private params(values: Record<string, string | number | undefined>): HttpParams {
    let result = new HttpParams();
    for (const [key, value] of Object.entries(values)) {
      if (value !== '' && value !== undefined) result = result.set(key, value);
    }
    return result;
  }
}
