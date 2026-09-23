import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import { EvidenceCardComponent } from '../shared/evidence-card.component';
import { PageHeaderComponent } from '../shared/page-header.component';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { StatusBadgeComponent } from '../shared/status-badge.component';
import type { BreadcrumbItem } from '../shared/ux-foundation.types';
import { SupplierJourneyNavComponent } from './supplier-journey-nav.component';

type Gap = {
  id: string;
  dimension: string;
  classification: string;
  status: string;
  severity: string;
};
type Plan = { version?: number; status: string; task_count?: number };
type Context = {
  id: string;
  supplier_id: string;
  status: string;
  readiness: string;
  summary?: { open_gaps?: number };
  gaps?: Gap[];
  plans?: Plan[];
};

@Component({
  selector: 'app-supplier-due-diligence',
  standalone: true,
  imports: [
    BreadcrumbsComponent,
    CommonModule,
    EmptyStateComponent,
    ErrorStateComponent,
    EvidenceCardComponent,
    LoadingStateComponent,
    PageHeaderComponent,
    RouterLink,
    StatusBadgeComponent,
    SupplierJourneyNavComponent,
  ],
  template: `
    <main aria-labelledby="due-diligence-title">
      <app-breadcrumbs [items]="breadcrumbs" />
      <app-page-header
        headingId="due-diligence-title"
        eyebrow="Intelligence / Supplier Verification"
        title="Supplier Verification"
        description="Evidence-first research gaps and human-controlled readiness."
      >
        <a page-header-actions routerLink="/intelligence">Back to Intelligence</a>
      </app-page-header>
      <app-supplier-journey-nav current="verify" />
      @if (error) {
        <app-error-state
          title="Supplier verification is unavailable"
          message="Due diligence data is unavailable. Check the authenticated API connection."
          retryLabel="Retry"
          (retry)="ngOnInit()"
        />
      }
      @if (loading) {
        <app-loading-state message="Loading supplier verification..." />
      }
      <section aria-labelledby="summary-title">
        <h2 id="summary-title">What has been verified?</h2>
        <p>
          Review verified evidence, unresolved gaps, contradictions, and freshness before sourcing.
        </p>
        @if (!loading && !contexts.length) {
          <app-empty-state
            title="Verification not started"
            message="No supplier verification contexts exist yet. Start from a shortlisted supplier."
          />
        }
        @for (context of contexts; track context.id) {
          <article>
            <h3>{{ context.supplier_id }}</h3>
            <app-status-badge
              status="VERIFICATION_STATE"
              [label]="semanticStatus(context.status)"
              tone="info"
            />
            <p>
              Status: {{ semanticStatus(context.status) }} · Readiness:
              {{ semanticStatus(context.readiness) }}
            </p>
            <p>Open gaps: {{ context.summary?.open_gaps || 0 }}</p>
            <app-evidence-card
              title="Verification evidence"
              classification="DERIVED"
              [summary]="
                (context.summary?.open_gaps || 0) +
                ' authoritative verification gap(s) remain for this supplier.'
              "
              source="Supplier due-diligence projection"
            />
            <table>
              <thead>
                <tr>
                  <th scope="col">Dimension</th>
                  <th scope="col">Classification</th>
                  <th scope="col">Status</th>
                  <th scope="col">Action</th>
                </tr>
              </thead>
              <tbody>
                @for (gap of context.gaps || []; track gap.id) {
                  <tr>
                    <td>{{ gap.dimension }}</td>
                    <td>{{ gap.classification }}</td>
                    <td>{{ semanticStatus(gap.status) }} ({{ gap.severity }})</td>
                    <td>
                      <button
                        type="button"
                        (click)="act(gap.id, 'start_research')"
                        [disabled]="gap.status === 'RESOLVED' || gap.status === 'WAIVED_BY_HUMAN'"
                      >
                        Research
                      </button>
                      <button
                        type="button"
                        (click)="act(gap.id, 'research_selected_gaps')"
                        [disabled]="gap.status === 'RESOLVED' || gap.status === 'WAIVED_BY_HUMAN'"
                      >
                        Research Selected Gaps
                      </button>
                      <button
                        type="button"
                        (click)="act(gap.id, 'request_more_research')"
                        [disabled]="gap.status === 'RESOLVED' || gap.status === 'WAIVED_BY_HUMAN'"
                      >
                        Request more research
                      </button>
                      @if (gap.status === 'RESEARCHING') {
                        <button type="button" (click)="act(gap.id, 'cancel_research')">
                          Cancel research
                        </button>
                      }
                      <button
                        type="button"
                        (click)="act(gap.id, 'waive_gap')"
                        [disabled]="gap.status === 'RESOLVED' || gap.status === 'WAIVED_BY_HUMAN'"
                      >
                        Waive
                      </button>
                      <button
                        type="button"
                        (click)="act(gap.id, 'reopen_gap')"
                        [disabled]="
                          gap.status !== 'RESOLVED' &&
                          gap.status !== 'WAIVED_BY_HUMAN' &&
                          gap.status !== 'BLOCKED'
                        "
                      >
                        Reopen
                      </button>
                      <button type="button" (click)="act(gap.id, 'mark_for_human_review')">
                        Mark for human review
                      </button>
                      <button type="button" (click)="reviewEvidence(gap.id)">
                        Review Evidence
                      </button>
                      @if (reviewedGapId === gap.id) {
                        <p>Evidence detail loaded for review.</p>
                      }
                    </td>
                  </tr>
                }
              </tbody>
            </table>
            <h4>Research plans</h4>
            <ul>
              @for (plan of context.plans || []; track plan.version) {
                <li>
                  v{{ plan.version || 1 }} · {{ plan.status }} · {{ plan.task_count || 0 }} tasks
                </li>
              }
            </ul>
          </article>
        }
      </section>
    </main>
  `,
  styles: [
    `
      main {
        padding: 2rem;
      }
      article {
        border: 1px solid #c7d7df;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
      }
      table {
        width: 100%;
        overflow-x: auto;
        display: block;
      }
      button {
        margin: 0.25rem;
      }
    `,
  ],
})
export class SupplierDueDiligenceComponent implements OnInit {
  private readonly http = inject(HttpClient);
  readonly breadcrumbs: BreadcrumbItem[] = [
    { label: 'Intelligence', url: '/intelligence' },
    { label: 'Supplier verification' },
  ];
  contexts: Context[] = [];
  loading = true;
  error = false;
  reviewedGapId: string | null = null;

  semanticStatus(status: string): string {
    const labels: Record<string, string> = {
      MISSING: 'MISSING',
      WEAK: 'WEAK',
      STALE: 'STALE',
      CONTRADICTORY: 'CONTRADICTORY',
      INSUFFICIENT: 'INSUFFICIENT',
      RESEARCHING: 'RESEARCHING',
      RESOLVED: 'RESOLVED',
      WAIVED_BY_HUMAN: 'WAIVED BY HUMAN',
      BLOCKED: 'BLOCKED',
      REVIEW_REQUIRED: 'REVIEW REQUIRED',
    };
    return labels[status] || status.replaceAll('_', ' ');
  }

  ngOnInit(): void {
    void this.loadContexts();
  }

  private async loadContexts(): Promise<void> {
    try {
      this.contexts = await firstValueFrom(
        this.http.get<Context[]>('/api/v1/intelligence/supplier-due-diligence/contexts'),
      );
      await Promise.all(
        this.contexts.map(async (context) => {
          const detail = await firstValueFrom(
            this.http.get<Context>(
              `/api/v1/intelligence/supplier-due-diligence/contexts/${context.id}`,
            ),
          );
          context.gaps = detail.gaps || [];
          context.readiness = detail.readiness;
          context.plans = await firstValueFrom(
            this.http.get<Plan[]>(
              `/api/v1/intelligence/supplier-due-diligence/contexts/${context.id}/plans`,
            ),
          );
        }),
      );
    } catch {
      this.error = true;
    } finally {
      this.loading = false;
    }
  }

  async reviewEvidence(gapId: string): Promise<void> {
    try {
      const context = this.contexts.find((item) => item.gaps?.some((gap) => gap.id === gapId));
      if (!context) {
        return;
      }
      await firstValueFrom(
        this.http.get(
          `/api/v1/intelligence/supplier-due-diligence/contexts/${context.id}/gaps/${gapId}`,
        ),
      );
      this.reviewedGapId = gapId;
    } catch {
      this.error = true;
    }
  }

  async act(gapId: string, action: string): Promise<void> {
    const reason =
      action === 'waive_gap'
        ? window.prompt('Enter a reason for waiving this evidence gap:')?.trim()
        : '';
    if (action === 'waive_gap' && !reason) {
      return;
    }
    try {
      await firstValueFrom(
        this.http.post(`/api/v1/intelligence/supplier-due-diligence/gaps/${gapId}/${action}`, {
          reason: reason || '',
        }),
      );
      this.ngOnInit();
    } catch {
      this.error = true;
    }
  }
}
