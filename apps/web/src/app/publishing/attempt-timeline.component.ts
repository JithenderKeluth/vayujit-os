import { Component, input } from '@angular/core';
import { JsonPipe } from '@angular/common';
import type { PublishingAttemptDetails } from '@vayujit/shared';

@Component({
  selector: 'app-attempt-timeline',
  imports: [JsonPipe],
  template: `<div class="pub-timeline" aria-label="Execution attempt timeline">
    @for (item of attempts(); track item.attempt_number) {
      <article>
        <h3>
          Attempt {{ item.attempt_number }} ·
          <span class="pub-status" [class]="item.status">{{ item.status }}</span>
        </h3>
        <p>Started: {{ item.started_at }}</p>
        <p>
          {{
            item.completed_at
              ? 'Completed: ' + item.completed_at
              : item.failed_at
                ? 'Failed: ' + item.failed_at
                : 'In progress'
          }}
        </p>
        <p>Retryable: {{ item.retryable ? 'Yes' : 'No' }}</p>
        @if (item.calculated_delay_ms) {
          <p>
            Retry delay: {{ item.applied_delay_ms }} ms applied ({{ item.calculated_delay_ms }} ms
            calculated).
          </p>
        }
        @if (item.result?.['throttle']) {
          <p>Shopify throttle: {{ item.result['throttle'] | json }}</p>
        }
        @if (item.error_code) {
          <p>
            <strong>{{ item.error_code }}</strong
            >: {{ item.safe_error_message }}
          </p>
        }
        @if (item.result?.['publication_id']) {
          <p>Publication reference: {{ item.result['publication_id'] }}</p>
        }
      </article>
    }
  </div>`,
  styleUrl: './publishing.css',
})
export class AttemptTimelineComponent {
  readonly attempts = input.required<PublishingAttemptDetails[]>();
}
