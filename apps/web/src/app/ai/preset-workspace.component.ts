import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AIService } from './ai.service';
import type { AIStudioPreset } from '@vayujit/shared';
@Component({
  selector: 'app-preset-workspace',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `<section aria-labelledby="preset-title">
    <h1 id="preset-title">Generation Presets</h1>
    <p>Create a preset to reuse the same channel and content configuration.</p>
    <form (ngSubmit)="save()">
      <fieldset>
        <legend>Basics</legend>
        <label>Name <input name="name" [(ngModel)]="draft.name" required /></label
        ><label>Description <input name="description" [(ngModel)]="draft.description" /></label>
      </fieldset>
      <fieldset>
        <legend>Channels and outputs</legend>
        <label>Channels <input name="channels" [(ngModel)]="channels" /></label
        ><label>Content types <input name="outputs" [(ngModel)]="outputs" /></label>
        <p role="status">
          {{channels.split(',').filter((value) => value.trim().length > 0).length}} channels �
          {{outputs.split(',').filter((value) => value.trim().length > 0).length}} output types
        </p>
      </fieldset>
      <fieldset>
        <legend>Advanced guidance</legend>
        <label>Guidance <textarea name="guidance" [(ngModel)]="draft.guidance"></textarea></label>
      </fieldset>
      <button type="submit">Create preset</button>
    </form>
    <p role="status">{{ message }}</p>
    <ul>
      @for (preset of presets; track preset.id) {
        <li>
          <strong>{{ preset.name }}</strong> v{{ preset.version || 1 }}
          <button type="button" (click)="duplicate(preset)">Duplicate</button>
          <button type="button" (click)="setDefault(preset)">Set default</button>
          <button type="button" (click)="archive(preset)">Archive</button>
        </li>
      }
    </ul>
  </section>`,
})
export class PresetWorkspaceComponent implements OnInit {
  private readonly ai = inject(AIService);
  presets: AIStudioPreset[] = [];
  message = '';
  channels = 'amazon,flipkart';
  outputs = 'marketplace_listing';
  draft: Partial<AIStudioPreset> = { name: '', description: '', guidance: '' };
  ngOnInit(): void {
    void this.load();
  }
  async load() {
    try {
      this.presets = await this.ai.studioPresets();
    } catch {
      this.message = 'Presets are unavailable right now.';
    }
  }
  async save() {
    try {
      await this.ai.createStudioPreset({
        ...this.draft,
        channels: this.channels
          .split(',')
          .map((v) => v.trim())
          .filter((value) => value.trim().length > 0),
        output_types: this.outputs
          .split(',')
          .map((v) => v.trim())
          .filter((value) => value.trim().length > 0),
      });
      this.message = 'Preset created.';
      await this.load();
    } catch {
      this.message = 'Could not create this preset.';
    }
  }
  async setDefault(p: AIStudioPreset): Promise<void> {
    try {
      await this.ai.setDefaultStudioPreset(p.id);
      this.message = 'Default preset updated.';
      await this.load();
    } catch {
      this.message = 'Could not set the default preset.';
    }
  }
  async archive(p: AIStudioPreset): Promise<void> {
    try {
      await this.ai.archiveStudioPreset(p.id);
      this.message = 'Preset archived.';
      await this.load();
    } catch {
      this.message = 'Could not archive this preset.';
    }
  }
  async duplicate(p: AIStudioPreset) {
    try {
      await this.ai.duplicateStudioPreset(p.id);
      this.message = 'Duplicated.';
      await this.load();
    } catch {
      this.message = 'Could not duplicate this preset.';
    }
  }
}
