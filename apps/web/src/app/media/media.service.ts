import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import type { MediaAsset, PaginatedMedia } from '@vayujit/shared';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class MediaService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/media`;
  private readonly options = { withCredentials: true } as const;

  list(
    filters: {
      search?: string;
      mimeType?: string;
      archived?: boolean;
      sort?: string;
      page?: number;
      pageSize?: number;
    } = {},
  ) {
    let params = new HttpParams()
      .set('page', filters.page ?? 1)
      .set('page_size', filters.pageSize ?? 24)
      .set('archived', filters.archived ?? false)
      .set('sort', filters.sort ?? 'newest');
    if (filters.search) params = params.set('search', filters.search);
    if (filters.mimeType) params = params.set('mime_type', filters.mimeType);
    return firstValueFrom(this.http.get<PaginatedMedia>(this.base, { ...this.options, params }));
  }

  get(id: string) {
    return firstValueFrom(this.http.get<MediaAsset>(`${this.base}/${id}`, this.options));
  }

  upload(file: File) {
    const body = new FormData();
    body.append('file', file, file.name);
    return firstValueFrom(this.http.post<MediaAsset>(this.base, body, this.options));
  }

  setArchived(id: string, action: 'archive' | 'restore') {
    return firstValueFrom(
      this.http.post<MediaAsset>(`${this.base}/${id}/${action}`, {}, this.options),
    );
  }

  previewUrl(id: string) {
    return `${this.base}/${id}/preview`;
  }
}
