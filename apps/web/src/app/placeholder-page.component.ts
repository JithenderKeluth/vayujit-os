import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-placeholder-page',
  template: `
    <section>
      <p class="eyebrow">Walking skeleton</p>
      <h1>{{ title() }}</h1>
      <p>This feature is intentionally reserved for a later Sprint 1 task.</p>
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlaceholderPageComponent {
  readonly title = input.required<string>();
}
