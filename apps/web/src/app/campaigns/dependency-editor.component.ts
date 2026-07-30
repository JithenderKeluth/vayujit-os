import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import type { CampaignActivity } from '@vayujit/shared';
import { CampaignService } from './campaign.service';

@Component({
  selector: 'app-campaign-dependency-editor',
  imports: [FormsModule, RouterLink],
  template: `
    <section class="page">
      <header class="page-header">
        <h1>Activity dependencies</h1>
        <a [routerLink]="['/campaigns', campaignId]">Back to Campaign</a>
      </header>
      <form (ngSubmit)="add()" class="panel">
        <label
          >Predecessor<select [(ngModel)]="predecessor" name="predecessor" required>
            <option value="">Select an activity</option>
            @for (activity of activities(); track activity.id) {
              <option [value]="activity.id">
                {{ activity.sequence }}. {{ activity.name
                }}{{ activity.required ? ' (required)' : '' }}
              </option>
            }
          </select></label
        >
        <label
          >Successor<select [(ngModel)]="successor" name="successor" required>
            <option value="">Select an activity</option>
            @for (activity of activities(); track activity.id) {
              <option [value]="activity.id" [disabled]="activity.id === predecessor">
                {{ activity.sequence }}. {{ activity.name }}
              </option>
            }
          </select></label
        >
        <label
          >Dependency type<select [(ngModel)]="dependencyType" name="dependencyType">
            <option value="success_required">Success required</option>
            <option value="finish_to_start">Finish to start</option>
            <option value="completion_required">Completion required</option>
            <option value="manual_release">Manual release</option>
          </select></label
        >
        <button [disabled]="!predecessor || !successor || predecessor === successor">
          Add dependency
        </button>
      </form>
      @if (warning()) {
        <p class="error" role="alert">{{ warning() }}</p>
      }
      <section class="panel">
        <h2>Dependency order</h2>
        @if (!dependencies().length) {
          <p>No dependencies.</p>
        }
        <ol>
          @for (edge of dependencies(); track edge['id']) {
            <li>
              {{ name(edge['predecessor_activity_id']) }} →
              {{ name(edge['successor_activity_id']) }}
              <span class="badge">{{ edge['dependency_type'] }}</span>
              <button type="button" (click)="remove(edge['id']!)">Remove</button>
            </li>
          }
        </ol>
      </section>
    </section>
  `,
  styleUrl: './campaigns.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DependencyEditorComponent {
  private readonly api = inject(CampaignService);
  readonly campaignId = inject(ActivatedRoute).snapshot.paramMap.get('id')!;
  readonly activities = signal<CampaignActivity[]>([]);
  readonly dependencies = signal<Array<Record<string, string | null>>>([]);
  readonly warning = signal('');
  predecessor = '';
  successor = '';
  dependencyType = 'success_required';
  constructor() {
    void this.load();
  }
  async load(): Promise<void> {
    const [activities, dependencies] = await Promise.all([
      this.api.activities(this.campaignId),
      this.api.dependencies(this.campaignId),
    ]);
    this.activities.set(activities);
    this.dependencies.set(dependencies);
  }
  name(id: string | null): string {
    return this.activities().find((value) => value.id === id)?.name ?? 'Unknown activity';
  }
  async add(): Promise<void> {
    this.warning.set('');
    try {
      await this.api.addDependency(this.campaignId, {
        predecessor_activity_id: this.predecessor,
        successor_activity_id: this.successor,
        dependency_type: this.dependencyType,
      });
      await this.load();
    } catch {
      this.warning.set('Dependency rejected: check for a duplicate, cycle, or invalid activity.');
    }
  }
  async remove(id: string): Promise<void> {
    await this.api.removeDependency(this.campaignId, id);
    await this.load();
  }
}
