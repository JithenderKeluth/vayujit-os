import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { RecoveryItem } from '@vayujit/shared';
import { OperationsService } from './operations.service';

@Component({
  selector: 'app-recovery',
  imports: [FormsModule, RouterLink],
  template: `<section class="op-page">
    <header><h1>Failure Recovery Center</h1></header>
    <div class="op-filters">
      <label
        >Category<select [(ngModel)]="category" (ngModelChange)="load()">
          <option value="">All</option>
          <option value="workflow">Workflow</option>
          <option value="publishing">Publishing</option>
          <option value="campaign">Campaign activities</option>
          <option value="media">Media and taxonomy</option>
        </select></label
      ><label
        ><input type="checkbox" [(ngModel)]="retryable" (ngModelChange)="load()" /> Retryable
        only</label
      >
    </div>
    @if (loading()) {
      <p role="status">Loading recoverable failures…</p>
    }
    @if (error()) {
      <p class="op-error" role="alert">{{ error() }}</p>
    }
    @if (!loading() && !items().length) {
      <article class="op-card"><h2>No recoverable failures</h2></article>
    }
    @for (item of items(); track item.id) {
      <article class="op-card">
        <h2>{{ item.category }} · {{ item.product_name || item.entity_type }}</h2>
        <p>{{ item.failure_code || 'unknown_failure' }}: {{ item.safe_failure_message }}</p>
        <p>Attempts {{ item.attempt_count }} · Retryable {{ item.retryable ? 'Yes' : 'No' }}</p>
        @if (item.entity_type === 'publishing_job') {
          <p>{{ item.job_state }} · {{ item.connector }} · Artifact v{{ item.artifact_version }}</p>
          <p>Scheduled {{ item.scheduled_at }} · Available {{ item.available_at }}</p>
          @if (item.lease_owner) {
            <p>Lease {{ item.lease_owner }} until {{ item.lease_expiry }}</p>
          }
          @if (item.correlation_id) {
            <p>Correlation {{ item.correlation_id }}</p>
          }
        }
        @if (item.entity_type === 'campaign_activity') {
          <p>{{ item.campaign_name }} · {{ item.activity_name }} · {{ item.job_state }}</p>
          <p>{{ item.connector || 'checkpoint' }} · Artifact v{{ item.artifact_version }}</p>
        }
        <p>Available actions: {{ item.capabilities.join(', ') || 'Review only' }}</p>
        @if (item.capabilities.includes('reschedule_activity')) {
          <p class="op-muted">Reschedule Activity is available from the Activity details.</p>
        }
        @if (item.capabilities.includes('create_one_catch_up')) {
          <p class="op-muted">Create one catch-up is available from the missed Activity details.</p>
        }
        @if (item.catch_up_status) {
          <p>Catch-up status: {{ item.catch_up_status }}</p>
          @if (item.catch_up_activity_id) {
            <a [routerLink]="['/campaigns', item.campaign_id]">Open catch-up Activity</a>
          }
        }
        <a [routerLink]="item.related_url">Open details and available actions</a>
      </article>
    }
  </section>`,
  styleUrl: './operations.css',
})
export class RecoveryComponent implements OnInit {
  private readonly api = inject(OperationsService);
  readonly items = signal<RecoveryItem[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  category = '';
  retryable = false;
  ngOnInit() {
    void this.load();
  }
  async load() {
    this.loading.set(true);
    try {
      const page = await this.api.recovery({
        category: this.category,
        retryable: this.retryable ? 'true' : undefined,
      });
      this.items.set(page.items);
      this.error.set('');
    } catch {
      this.error.set('Recovery information is unavailable.');
    } finally {
      this.loading.set(false);
    }
  }
}
