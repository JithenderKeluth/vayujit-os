import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import type { AIArtifactDetails, ApprovalComparisonVersion } from '@vayujit/shared';
import { OperationsService } from '../operations/operations.service';
import { WorkflowService } from '../workflows/workflow.service';
import { arrayDiff, scalarDiff } from './artifact-diff';
import { AIService } from './ai.service';

@Component({
  selector: 'app-ai-artifact',
  imports: [FormsModule, RouterLink],
  template: ` <section class="ai-page">
    <header class="ai-header">
      <div>
        <h1>Content review</h1>
        @if (artifact()) {
          <p class="ai-muted">
            {{ artifact()!.brand_name }} · {{ artifact()!.product_name }} · Version
            {{ artifact()!.version_number }}
          </p>
        }
      </div>
      <a routerLink="/ai/history">History</a>
    </header>
    @if (workflowId) {
      <article class="ai-card">
        <strong>Workflow approval step</strong>
        <p>Approving or rejecting this Artifact will continue the waiting Workflow.</p>
        <a [routerLink]="['/workflows', workflowId]">Back to Workflow</a>
      </article>
    }
    @if (error()) {
      <p class="ai-error">{{ error() }}</p>
    }
    @if (artifact(); as item) {
      <article class="ai-card">
        <h2>Compare versions</h2>
        @if (versions().length > 1) {
          <div class="ai-compare-selectors">
            <label
              >Previous version
              <select [ngModel]="leftId()" (ngModelChange)="selectLeft($event)">
                @for (version of versions(); track version.artifact.id) {
                  <option
                    [value]="version.artifact.id"
                    [disabled]="version.artifact.id === rightId()"
                  >
                    Version {{ version.artifact.version_number }} · {{ version.artifact.status }}
                  </option>
                }
              </select></label
            ><label
              >Current version
              <select [ngModel]="rightId()" (ngModelChange)="selectRight($event)">
                @for (version of versions(); track version.artifact.id) {
                  <option
                    [value]="version.artifact.id"
                    [disabled]="version.artifact.id === leftId()"
                  >
                    Version {{ version.artifact.version_number }} · {{ version.artifact.status }}
                  </option>
                }
              </select></label
            >
          </div>
          <div class="ai-compare" aria-label="Artifact version comparison">
            @for (field of scalarFields; track field[0]) {
              <section [attr.data-state]="scalar(field[1]).state">
                <h3>{{ field[0] }}</h3>
                <div>
                  <strong>Previous</strong>
                  <p>{{ scalar(field[1]).before || '—' }}</p>
                </div>
                <div>
                  <strong>Current</strong>
                  <p>{{ scalar(field[1]).after || '—' }}</p>
                </div>
              </section>
            }
            @for (field of arrayFields; track field[0]) {
              <section>
                <h3>{{ field[0] }}</h3>
                <ul>
                  @for (entry of array(field[1]); track entry.state + entry.value) {
                    <li [attr.data-state]="entry.state">{{ entry.state }}: {{ entry.value }}</li>
                  }
                </ul>
              </section>
            }
          </div>
          <div class="ai-version-meta">
            @for (version of [left(), right()]; track version?.artifact?.id) {
              @if (version; as selected) {
                <p>
                  <strong>Version {{ selected.artifact.version_number }}</strong> · generated
                  {{ selected.artifact.created_at }} · {{ selected.artifact.status }} ·
                  {{ selected.artifact.template_name }} v{{ selected.artifact.template_version }} ·
                  {{ selected.artifact.provider_key }}
                  @if (selected.workflow_id) {
                    · <a [routerLink]="['/workflows', selected.workflow_id]">Workflow</a>
                  }
                </p>
              }
            }
          </div>
        } @else {
          <p>No previous eligible version exists for this Product and prompt template.</p>
        }
      </article>
      <article class="ai-card">
        <p class="ai-status">Status: {{ item.status }}</p>
        <h2>{{ item.content.product_title }}</h2>
        <p>
          <strong>{{ item.content.short_description }}</strong>
        </p>
        <p class="ai-content">{{ item.content.long_description }}</p>
        <h3>Key features</h3>
        <ul>
          @for (feature of item.content.key_features; track feature) {
            <li>{{ feature }}</li>
          }
        </ul>
        <h3>SEO</h3>
        <p>
          <strong>{{ item.content.seo_title }}</strong>
        </p>
        <p>{{ item.content.seo_description }}</p>
        <h3>Social caption</h3>
        <p>{{ item.content.social_caption }}</p>
        <div class="ai-keywords">
          @for (keyword of item.content.keywords; track keyword) {
            <span>{{ keyword }}</span>
          }
        </div>
        <p class="ai-muted">
          {{ item.content.generation_summary }} · {{ item.template_name }} v{{
            item.template_version
          }}
          · {{ item.provider_key }}
        </p>
      </article>
      @if (item.status === 'pending_review') {
        <article class="ai-card ai-form">
          <div class="ai-actions">
            <button [disabled]="busy()" (click)="approve()">Approve</button>
            <button class="ai-secondary" [disabled]="busy()" (click)="regenerate()">
              Regenerate selected current version
            </button>
          </div>
          <label>Rejection reason<textarea rows="3" [(ngModel)]="reason"></textarea></label>
          <div>
            <button class="ai-danger" [disabled]="busy() || !reason.trim()" (click)="reject()">
              Reject
            </button>
          </div>
          <a [routerLink]="['/ai/artifacts', rightId()]">Open full Artifact details</a> ·
          <a routerLink="/approvals">Return to approval queue</a>
        </article>
      }
      @if (item.rejection_reason) {
        <article class="ai-card">
          <strong>Rejection reason:</strong> {{ item.rejection_reason }}
        </article>
      }
    }
  </section>`,
  styleUrl: './ai.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AIArtifactComponent implements OnInit {
  private readonly ai = inject(AIService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly workflows = inject(WorkflowService);
  private readonly operations = inject(OperationsService);
  readonly artifact = signal<AIArtifactDetails | null>(null);
  readonly versions = signal<ApprovalComparisonVersion[]>([]);
  readonly leftId = signal('');
  readonly rightId = signal('');
  readonly left = computed(
    () => this.versions().find((item) => item.artifact.id === this.leftId()) ?? null,
  );
  readonly right = computed(
    () => this.versions().find((item) => item.artifact.id === this.rightId()) ?? null,
  );
  readonly busy = signal(false);
  readonly error = signal('');
  reason = '';
  readonly workflowId = this.route.snapshot.queryParamMap.get('workflow') ?? '';
  readonly scalarFields = [
    ['Generated title', 'product_title'],
    ['Short description', 'short_description'],
    ['Long description', 'long_description'],
    ['SEO title', 'seo_title'],
    ['SEO description', 'seo_description'],
    ['Social caption', 'social_caption'],
    ['Generation summary', 'generation_summary'],
  ] as const;
  readonly arrayFields = [
    ['Key features', 'key_features'],
    ['Keywords', 'keywords'],
  ] as const;
  ngOnInit(): void {
    void this.load();
  }
  async approve(): Promise<void> {
    if (
      !window.confirm(
        'Approve this content? Approved content becomes eligible for workflow continuation and publishing.',
      )
    ) {
      return;
    }
    await this.reviewAndContinue(() => this.ai.approve(this.rightId() || this.id));
  }
  async reject(): Promise<void> {
    if (!window.confirm('Reject this content with the supplied reason?')) {
      return;
    }
    await this.reviewAndContinue(() => this.ai.reject(this.rightId() || this.id, this.reason));
  }
  async regenerate(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      const result = await this.ai.regenerate(this.rightId() || this.id);
      if (result.artifact_id) await this.router.navigate(['/ai/artifacts', result.artifact_id]);
      else this.error.set(result.safe_error_message ?? 'Regeneration failed.');
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
  private get id(): string {
    return this.route.snapshot.paramMap.get('id') ?? '';
  }
  private async load(): Promise<void> {
    try {
      const response = await this.operations.approval(this.id);
      this.artifact.set(response.artifact);
      this.versions.set(response.versions);
      this.rightId.set(response.artifact.id);
      const index = response.versions.findIndex(
        (version) => version.artifact.id === response.artifact.id,
      );
      const previous =
        response.versions
          .slice(index + 1)
          .find((version) => version.artifact.version_number < response.artifact.version_number) ??
        response.versions.find((version) => version.artifact.id !== response.artifact.id);
      this.leftId.set(previous?.artifact.id ?? '');
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    }
  }
  selectLeft(id: string): void {
    if (id !== this.rightId()) this.leftId.set(id);
  }
  selectRight(id: string): void {
    if (id !== this.leftId()) {
      this.rightId.set(id);
      const selected = this.right();
      if (selected) this.artifact.set(selected.artifact);
    }
  }
  scalar(field: keyof AIArtifactDetails['content']) {
    const before = this.left()?.artifact.content[field];
    const after = this.right()?.artifact.content[field];
    return scalarDiff(
      typeof before === 'string' ? before : '',
      typeof after === 'string' ? after : '',
    );
  }
  array(field: 'key_features' | 'keywords') {
    return arrayDiff(
      this.left()?.artifact.content[field] ?? [],
      this.right()?.artifact.content[field] ?? [],
    );
  }
  private async act(action: () => Promise<AIArtifactDetails>): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      this.artifact.set(await action());
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
  private async reviewAndContinue(action: () => Promise<AIArtifactDetails>): Promise<void> {
    if (!this.workflowId) {
      await this.act(action);
      return;
    }
    this.busy.set(true);
    this.error.set('');
    try {
      this.artifact.set(await action());
      await this.workflows.continue(this.workflowId);
      await this.router.navigate(['/workflows', this.workflowId]);
    } catch (error) {
      this.error.set(WorkflowService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
}
