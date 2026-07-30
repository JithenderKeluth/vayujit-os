import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-operations-home',
  imports: [RouterLink],
  template: `<section class="op-page">
    <header>
      <h1>Operations</h1>
      <p>Health, recovery, backups, and audit visibility.</p>
    </header>
    <div class="op-grid">
      <a class="op-card" routerLink="/operations/health"
        ><h2>Health</h2>
        <p>Component readiness and release diagnostics.</p></a
      >
      <a class="op-card" routerLink="/operations/recovery"
        ><h2>Recovery</h2>
        <p>Owner-scoped failures and valid recovery actions.</p></a
      >
      <a class="op-card" routerLink="/operations/backups"
        ><h2>Backups</h2>
        <p>Create, list, verify, and preflight local backups.</p></a
      >
      <a class="op-card" routerLink="/operations/audit"
        ><h2>Audit</h2>
        <p>Filter and export the safe operational event projection.</p></a
      >
    </div>
  </section>`,
  styleUrl: './operations.css',
})
export class OperationsHomeComponent {}
