import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class SupplierShortlistingService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/intelligence/supplier-shortlisting`;
  createContext(payload: Record<string, unknown>) {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(`${this.base}/contexts`, payload),
    );
  }
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
  decide(id: string, body: Record<string, unknown>) {
    return firstValueFrom(
      this.http.post<Record<string, unknown>>(`${this.base}/contexts/${id}/decisions`, body),
    );
  }
}
