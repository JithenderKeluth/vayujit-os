import { Component, OnInit, inject, signal } from '@angular/core';
import type { OperationalHealth, ReleaseInfo } from '@vayujit/shared';
import { OperationsService } from './operations.service';

@Component({
  selector: 'app-health',
  template: `<section class="op-page">
    <header>
      <h1>Operational health</h1>
      <button (click)="load()">Refresh</button>
    </header>
    @if (loading()) {
      <p role="status">Checking components…</p>
    }
    @if (error()) {
      <p class="op-error" role="alert">{{ error() }}</p>
    }
    @if (health(); as value) {
      <p><strong>Overall:</strong> {{ value.status }}</p>
      <div class="op-grid">
        @for (item of value.components; track item.component) {
          <article class="op-card">
            <h2>{{ item.component }}</h2>
            <p>
              <strong>{{ item.status }}</strong>
            </p>
            <p>{{ item.message }}</p>
            <small>Checked {{ item.checked_at }}</small>
          </article>
        }
      </div>
    }
    @if (release(); as value) {
      <article class="op-card">
        <h2>Release</h2>
        <p>Version {{ value.semantic_version }} · build {{ value.build_identifier }}</p>
        <p>Migration {{ value.migration_revision }} · Python {{ value.python_version }}</p>
        <p>
          Node {{ value.node_version }} · Electron {{ value.electron_version }} · Angular
          {{ value.angular_build_version }}
        </p>
        <p>Commit {{ value.git_commit }} · built {{ value.build_timestamp }}</p>
      </article>
    }
  </section>`,
  styleUrl: './operations.css',
})
export class HealthComponent implements OnInit {
  private readonly api = inject(OperationsService);
  readonly health = signal<OperationalHealth | null>(null);
  readonly release = signal<ReleaseInfo | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  ngOnInit() {
    void this.load();
  }
  async load() {
    this.loading.set(true);
    this.error.set('');
    try {
      const [health, release] = await Promise.all([this.api.health(), this.api.release()]);
      this.health.set(health);
      this.release.set(release);
    } catch {
      this.error.set('Health information is unavailable. Run system:doctor.');
    } finally {
      this.loading.set(false);
    }
  }
}
