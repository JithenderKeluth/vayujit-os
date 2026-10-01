import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../environments/environment';
import type { CommerceJourney, CommerceNextAction } from './commerce-journey.types';

@Injectable()
export class CommerceJourneyService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/commerce-journeys`;

  async active(): Promise<CommerceJourney | null> {
    const response = await firstValueFrom(
      this.http.get<{ journey: CommerceJourney | null }>(`${this.base}/active`),
    );
    return response.journey;
  }

  async nextAction(id: string): Promise<CommerceNextAction> {
    const response = await firstValueFrom(
      this.http.get<{ next_action: CommerceNextAction }>(`${this.base}/${id}/next-action`),
    );
    return response.next_action;
  }

  async confirmContext(id: string, values: Record<string, unknown>): Promise<CommerceJourney> {
    const response = await firstValueFrom(
      this.http.post<{ journey: CommerceJourney }>(`${this.base}/${id}/context-confirmation`, {
        confirmed: true,
        ...values,
      }),
    );
    return response.journey;
  }
}
