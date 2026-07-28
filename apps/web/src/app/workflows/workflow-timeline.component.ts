import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { WorkflowStepAttemptDetails } from '@vayujit/shared';

@Component({
  selector: 'app-workflow-timeline',
  imports: [RouterLink],
  template: `<div class="wf-timeline" aria-label="Workflow step timeline">
    @for (step of steps(); track step.id) {
      <article>
        <h3>
          {{ step.sequence_number }}. {{ label(step.step_key) }} · attempt {{ step.attempt_number }}
        </h3>
        <p>
          <span class="wf-status" [class]="step.status">{{ step.status }}</span> ·
          {{ step.step_type }}
        </p>
        <p>Started: {{ step.started_at || 'Not started' }}</p>
        <p>
          {{
            step.completed_at
              ? 'Completed: ' + step.completed_at
              : step.failed_at
                ? 'Failed: ' + step.failed_at
                : step.paused_at
                  ? 'Paused: ' + step.paused_at
                  : ''
          }}
        </p>
        <p>Retryable: {{ step.retryable ? 'Yes' : 'No' }}</p>
        @if (step.error_code) {
          <p>
            <strong>{{ step.error_code }}</strong
            >: {{ step.safe_error_message }}
          </p>
        }
        @if (step.related_id && step.related_type === 'artifact') {
          <a [routerLink]="['/ai/artifacts', step.related_id]">View Artifact</a>
        }
        @if (step.related_id && step.related_type === 'publishing_execution') {
          <a [routerLink]="['/publishing/executions', step.related_id]"
            >View Publishing execution</a
          >
        }
      </article>
    }
  </div>`,
  styleUrl: './workflow.css',
})
export class WorkflowTimelineComponent {
  readonly steps = input.required<WorkflowStepAttemptDetails[]>();
  label(key: string): string {
    return (
      (
        {
          generate_content: 'Generate content',
          wait_for_approval: 'Human approval',
          publish_content: 'Publish content',
        } as Record<string, string>
      )[key] ?? key
    );
  }
}
