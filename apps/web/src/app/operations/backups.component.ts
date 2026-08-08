import { Component, OnInit, inject, signal } from '@angular/core';
import type { BackupSummary, RestoreCheck } from '@vayujit/shared';
import { OperationsService } from './operations.service';

@Component({
  selector: 'app-backups',
  template: `<section class="op-page">
    <header>
      <h1>Backups</h1>
      <button [disabled]="busy()" (click)="create()">Create full backup</button>
    </header>
    <p class="op-muted">Backups are local PostgreSQL custom-format files and are not encrypted.</p>
    @if (loading()) {
      <p role="status">Loading backup records…</p>
    }
    @if (error()) {
      <p class="op-error" role="alert">{{ error() }}</p>
    }
    @if (message()) {
      <p class="op-success" role="status">{{ message() }}</p>
    }
    @if (!loading() && items().length) {
      <article class="op-card">
        <h2>Backup habit</h2>
        <p>Latest backup: {{ items()[0].created_at }}</p>
        <p>
          Verification: {{ items()[0].verification_status }}. Verify a fresh backup before relying
          on it.
        </p>
      </article>
    }
    @if (!loading() && !items().length) {
      <article class="op-card">
        <h2>No backups</h2>
        <p>Create and verify the first backup.</p>
      </article>
    }
    @for (item of items(); track item.id) {
      <article class="op-card">
        <h2>{{ item.backup_key }}</h2>
        <p>
          {{ item.status }} · {{ item.verification_status }} · {{ item.size_bytes }} bytes · created
          {{ item.created_at }}
        </p>
        <p>Migration {{ item.migration_revision }} · {{ item.encryption_status }}</p>
        <div class="op-actions">
          <button [disabled]="busy()" (click)="verify(item.id)">Verify</button>
          <button class="secondary" [disabled]="busy()" (click)="preflight(item.id)">
            Restore preflight
          </button>
        </div>
      </article>
    }
    @if (plan(); as value) {
      <article class="op-card">
        <h2>Restore preflight</h2>
        <p>
          Compatible: {{ value.compatible ? 'Yes' : 'No' }} · checksum:
          {{ value.checksum_valid ? 'valid' : 'invalid' }}
        </p>
        <p>{{ value.operator_action }}</p>
        <strong>Automated destructive restore is not supported.</strong>
      </article>
    }
  </section>`,
  styleUrl: './operations.css',
})
export class BackupsComponent implements OnInit {
  private readonly api = inject(OperationsService);
  readonly items = signal<BackupSummary[]>([]);
  readonly plan = signal<RestoreCheck | null>(null);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  ngOnInit() {
    void this.load();
  }
  async load() {
    try {
      this.items.set(await this.api.backups());
    } catch {
      this.error.set('Backups are unavailable.');
    } finally {
      this.loading.set(false);
    }
  }
  async create() {
    if (!confirm('Create a full local database backup now? It is not encrypted.')) return;
    await this.act(async () => {
      await this.api.createBackup();
      await this.load();
      this.message.set('Backup created. Verify it before relying on it.');
    });
  }
  async verify(id: string) {
    await this.act(async () => {
      await this.api.verifyBackup(id);
      await this.load();
      this.message.set('Backup verification completed.');
    });
  }
  async preflight(id: string) {
    await this.act(async () => {
      this.plan.set(await this.api.restoreCheck(id));
    });
  }
  private async act(action: () => Promise<void>) {
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    try {
      await action();
    } catch {
      this.error.set('The backup operation failed safely. Check operator diagnostics.');
    } finally {
      this.busy.set(false);
    }
  }
}
