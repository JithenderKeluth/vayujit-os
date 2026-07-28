import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import type { PublishingDestinationSummary, PublishingExecutionDetails } from '@vayujit/shared';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-destination-details',
  imports: [RouterLink],
  template: ` <section class="pub-page">
    <header class="pub-header">
      <h1>Destination details</h1>
      <a routerLink="/publishing/destinations">Back to destinations</a>
    </header>
    @if (loading()) {
      <p role="status">Loading destination…</p>
    }
    @if (error()) {
      <p class="pub-error" role="alert">{{ error() }}</p>
    }
    @if (item(); as value) {
      <article class="pub-card">
        <header class="pub-header">
          <div>
            <h2>{{ value.name }}</h2>
            <span class="pub-status" [class]="value.status">{{ value.status }}</span>
          </div>
          <div class="pub-actions">
            <a class="pub-button" [routerLink]="['/publishing/destinations', value.id, 'edit']"
              >Edit</a
            >
            @if (value.status === 'active') {
              <button class="danger" (click)="disable()">Disable</button>
            } @else {
              <button (click)="enable()">Enable</button>
            }
          </div>
        </header>
        <dl class="pub-preview">
          <div>
            <dt>Connector</dt>
            <dd>Deterministic local mock</dd>
          </div>
          <div>
            <dt>Brand scope</dt>
            <dd>{{ value.brand_name || 'All Brands' }}</dd>
          </div>
          <div>
            <dt>Channel</dt>
            <dd>{{ value.configuration.channel_name }}</dd>
          </div>
          <div>
            <dt>Publication prefix</dt>
            <dd>{{ value.configuration.publication_prefix }}</dd>
          </div>
          <div>
            <dt>Created / updated</dt>
            <dd>{{ value.created_at }} / {{ value.updated_at }}</dd>
          </div>
        </dl>
        <a
          class="pub-button"
          [routerLink]="['/publishing/new']"
          [queryParams]="{ destination: value.id }"
          >Publish approved content here</a
        >
      </article>
      <article class="pub-card">
        <h2>Recent executions</h2>
        @for (execution of executions(); track execution.id) {
          <p>
            <a [routerLink]="['/publishing/executions', execution.id]"
              >{{ execution.content_snapshot['product_name'] }} · {{ execution.id.slice(0, 8) }}</a
            >
            <span class="pub-status" [class]="execution.status">{{ execution.status }}</span>
          </p>
        } @empty {
          <p class="pub-muted">This destination has no executions.</p>
        }
      </article>
    }
  </section>`,
  styleUrl: './publishing.css',
})
export class DestinationDetailsComponent implements OnInit {
  private readonly api = inject(PublishingService);
  private readonly route = inject(ActivatedRoute);
  readonly item = signal<PublishingDestinationSummary | null>(null);
  readonly executions = signal<PublishingExecutionDetails[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  private id = '';
  ngOnInit(): void {
    void this.load();
  }
  private async load() {
    this.id = this.route.snapshot.paramMap.get('id') ?? '';
    try {
      const [item, history] = await Promise.all([
        this.api.destination(this.id),
        this.api.executions({ destinationId: this.id, pageSize: 5 }),
      ]);
      this.item.set(item);
      this.executions.set(history.items);
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
  async disable() {
    const item = this.item();
    if (!item || !confirm(`Disable ${item.name}?`)) return;
    this.item.set(await this.api.destinationStatus(item.id, 'disable'));
  }
  async enable() {
    const item = this.item();
    if (item) this.item.set(await this.api.destinationStatus(item.id, 'enable'));
  }
}
