import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import type { PublishingWorker } from '@vayujit/shared';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-publishing-workers',
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<section class="op-page">
    <header>
      <p class="op-eyebrow">Operations</p>
      <h1>Publishing workers</h1>
    </header>
    <div class="op-card">
      <table>
        <thead>
          <tr>
            <th>Worker</th>
            <th>Status</th>
            <th>Active</th>
            <th>Concurrency</th>
            <th>Last heartbeat</th>
          </tr>
        </thead>
        <tbody>
          @for (item of workers(); track item.worker_id) {
            <tr>
              <td>{{ item.worker_id }}</td>
              <td>{{ item.safe_status }}</td>
              <td>{{ item.active_jobs }}</td>
              <td>{{ item.concurrency }}</td>
              <td>{{ item.last_heartbeat_at | date: 'medium' }}</td>
            </tr>
          } @empty {
            <tr>
              <td colspan="5">
                No worker heartbeat has been recorded. Start the publishing worker.
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  </section>`,
})
export class WorkersComponent implements OnInit {
  private readonly publishing = inject(PublishingService);
  readonly workers = signal<PublishingWorker[]>([]);
  ngOnInit() {
    void this.load();
  }
  async load() {
    this.workers.set(await this.publishing.workers());
  }
}
