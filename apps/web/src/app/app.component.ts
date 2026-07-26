import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent {
  readonly navigation = [
    ['Dashboard', '/dashboard'],
    ['Brands', '/brands'],
    ['Products', '/products'],
    ['Workflows', '/workflows'],
    ['Approvals', '/approvals'],
    ['Execution History', '/execution-history'],
    ['Settings', '/settings'],
  ] as const;
}
