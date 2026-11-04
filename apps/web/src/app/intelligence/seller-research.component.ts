import { DatePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { BusinessAgentGoal, BusinessAgentService } from './business-agent.service';

@Component({
  selector: 'app-seller-research',
  standalone: true,
  imports: [RouterLink, DatePipe],
  template: `<section aria-labelledby="saved-research-title">
    <h1 id="saved-research-title">My research</h1>
    <p>
      Return to a saved goal, its plan, recorded evidence and product decisions. A saved goal is not
      proof that research has run or that demand is verified.
    </p>
    <a routerLink="/intelligence/business-agent">Create a research goal</a>
    @if (loading()) {
      <p role="status">Loading saved research…</p>
    }
    @if (error()) {
      <p role="alert">Saved research could not be loaded. No empty result is assumed.</p>
      <button type="button" (click)="load()">Retry saved research</button>
    }
    @if (!loading() && !error() && !goals().length) {
      <h2>No saved goals yet</h2>
      <p>
        Start with a marketplace, category, budget and constraints. Review the interpreted goal
        before research.
      </p>
    }
    @for (goal of goals(); track goal.id) {
      <article>
        <h2>{{ goal.raw_goal }}</h2>
        <p>Goal status: {{ goal.status }} · Saved {{ goal.created_at | date: 'medium' }}</p>
        <p>
          Run progress and blockers are shown inside the saved goal, not inferred from this status.
        </p>
        <a routerLink="/intelligence/business-agent" [queryParams]="{ goal_id: goal.id }"
          >Open goal, plan and research</a
        >
        ·
        <a routerLink="/intelligence/product-opportunities" [queryParams]="{ goal_id: goal.id }"
          >Review this goal's opportunities</a
        >
      </article>
    }
    <details>
      <summary>Advanced research configuration</summary>
      <a routerLink="/intelligence">Open research tools and configuration</a>
      <p>Advanced missions, rules and provider settings are separate from saved goal history.</p>
    </details>
  </section>`,
  styles: [
    `
      section {
        max-width: 70rem;
        margin: auto;
        padding: 1.5rem;
      }
      article {
        padding: 1rem;
        border: 1px solid #b8d0d4;
        border-radius: 12px;
        margin: 1rem 0;
        background: #fff;
      }
      h2 {
        font-size: 1.2rem;
        overflow-wrap: anywhere;
      }
      a,
      button,
      summary {
        display: inline-block;
        min-height: 44px;
      }
      :focus-visible {
        outline: 3px solid #b56900;
        outline-offset: 3px;
      }
    `,
  ],
})
export class SellerResearchComponent implements OnInit {
  private readonly service = inject(BusinessAgentService);
  readonly goals = signal<BusinessAgentGoal[]>([]);
  readonly loading = signal(false);
  readonly error = signal(false);
  ngOnInit(): void {
    void this.load();
  }
  async load(): Promise<void> {
    if (this.loading()) return;
    this.loading.set(true);
    this.error.set(false);
    try {
      this.goals.set(await this.service.goals());
    } catch {
      this.error.set(true);
    } finally {
      this.loading.set(false);
    }
  }
}
