import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { AIService } from './ai.service';
import type { AIStudioBrandVoice } from '@vayujit/shared';

@Component({
  selector: 'app-brand-voice-workspace',
  standalone: true,
  imports: [FormsModule, CommonModule],
  template: ` <section aria-labelledby="voice-title">
    <h1 id="voice-title">Brand Voices</h1>
    <p>Create a Brand Voice to keep AI-generated content consistent.</p>
    <form (ngSubmit)="save()">
      <fieldset>
        <legend>Identity</legend>
        <label>Name <input name="name" [(ngModel)]="draft.name" required maxlength="160" /></label
        ><label>Description <input name="description" [(ngModel)]="draft.description" /></label
        ><label>Locale <input name="locale" [(ngModel)]="draft.locale" /></label>
      </fieldset>
      <fieldset>
        <legend>Tone &amp; Personality</legend>
        <label>Tone <input name="tone" [(ngModel)]="draft.tone" /></label
        ><label
          >Personality <textarea name="personality" [(ngModel)]="draft.personality"></textarea>
        </label>
      </fieldset>
      <fieldset>
        <legend>Terminology and style</legend>
        <label>Preferred phrases <input name="preferred" [(ngModel)]="preferred" /></label
        ><label>Prohibited phrases <input name="prohibited" [(ngModel)]="prohibited" /></label
        ><label
          >Custom guidance
          <textarea name="guidance" [(ngModel)]="draft.custom_instructions"></textarea>
        </label>
      </fieldset>
      <button type="submit">{{ editing ? 'Save new version' : 'Create Brand Voice' }}</button>
    </form>
    <label
      >Preview Product ID
      <input name="previewProductId" [(ngModel)]="previewProductId" placeholder="Product UUID"
    /></label>
    <p role="status">{{ message }}</p>
    <ul>
      @for (voice of voices; track voice.id) {
        <li>
          <strong>{{ voice.name }}</strong> v{{ voice.version }}
          <span>{{ voice.is_default ? 'Default' : '' }}</span
          ><button type="button" (click)="edit(voice)">Edit</button
          ><button type="button" (click)="duplicate(voice)">Duplicate</button
          ><button type="button" (click)="setDefault(voice)">Set default</button
          ><button type="button" (click)="preview(voice)">Preview</button
          ><button type="button" (click)="archive(voice)">Archive</button>
        </li>
      }
    </ul>
  </section>`,
})
export class BrandVoiceWorkspaceComponent implements OnInit {
  private readonly ai = inject(AIService);
  voices: AIStudioBrandVoice[] = [];
  editing = false;
  editingId = '';
  message = '';
  previewProductId = '';
  preferred = '';
  prohibited = '';
  draft: Partial<AIStudioBrandVoice> = {
    name: '',
    description: '',
    tone: 'professional',
    locale: 'en-IN',
    personality: '',
    custom_instructions: '',
  };
  ngOnInit(): void {
    void this.load();
  }
  async load() {
    try {
      this.voices = await this.ai.studioBrandVoices();
    } catch {
      this.message = 'Brand Voices are unavailable right now.';
    }
  }
  edit(v: AIStudioBrandVoice) {
    this.editing = true;
    this.editingId = v.id;
    this.draft = { ...v };
    this.preferred = v.preferred_phrases.join(', ');
    this.prohibited = v.prohibited_phrases.join(', ');
  }
  async save() {
    const payload = {
      ...this.draft,
      preferred_phrases: this.preferred
        .split(',')
        .map((v) => v.trim())
        .filter(Boolean),
      prohibited_phrases: this.prohibited
        .split(',')
        .map((v) => v.trim())
        .filter(Boolean),
    };
    try {
      if (this.editing) await this.ai.updateStudioBrandVoice(this.editingId, payload);
      else await this.ai.createStudioBrandVoice(payload);
      this.message = 'Saved.';
      this.editing = false;
      await this.load();
    } catch {
      this.message = 'Could not save this Brand Voice.';
    }
  }
  async setDefault(v: AIStudioBrandVoice): Promise<void> {
    try {
      await this.ai.setDefaultStudioBrandVoice(v.id);
      this.message = 'Default Brand Voice updated.';
      await this.load();
    } catch {
      this.message = 'Could not set the default Brand Voice.';
    }
  }
  async archive(v: AIStudioBrandVoice): Promise<void> {
    try {
      await this.ai.archiveStudioBrandVoice(v.id);
      this.message = 'Brand Voice archived.';
      await this.load();
    } catch {
      this.message = 'Could not archive this Brand Voice.';
    }
  }
  async preview(v: AIStudioBrandVoice): Promise<void> {
    if (!this.previewProductId.trim()) {
      this.message = 'Enter a Product ID to preview this Brand Voice.';
      return;
    }
    try {
      const result = await this.ai.previewStudioBrandVoice(v.id, {
        product_id: this.previewProductId.trim(),
        channel: 'amazon',
        content_type: 'product_description',
      });
      this.message = 'Preview: ' + JSON.stringify(result['sample']);
    } catch {
      this.message = 'Could not preview this Brand Voice.';
    }
  }
  async duplicate(v: AIStudioBrandVoice) {
    try {
      await this.ai.duplicateStudioBrandVoice(v.id);
      this.message = 'Duplicated.';
      await this.load();
    } catch {
      this.message = 'Could not duplicate this Brand Voice.';
    }
  }
}
