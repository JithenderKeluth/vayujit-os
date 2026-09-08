import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class SupplierShortlistingService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/v1/intelligence/supplier-shortlisting';
  contexts() {
    return firstValueFrom(this.http.get<unknown[]>(`${this.base}/contexts`));
  }
  operations() {
    return firstValueFrom(this.http.get<Record<string, unknown>>(`${this.base}/operations`));
  }
  doctor() {
    return firstValueFrom(this.http.get<Record<string, unknown>>(`${this.base}/system-doctor`));
  }
  shortlist(id: string, body: unknown) {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(`${this.base}/contexts/${id}/shortlists`, body),
    );
  }
}
