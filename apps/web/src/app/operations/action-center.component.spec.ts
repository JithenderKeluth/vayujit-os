import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { ActionCenterComponent } from './action-center.component';
import { ActionCenterService } from './action-center.service';

describe('Action Center authoritative filtering', () => {
  const empty = { signals: [], total: 0, briefing: null, policy: null };
  let api: { load: ReturnType<typeof vi.fn> };
  beforeEach(async () => {
    api = { load: vi.fn().mockResolvedValue(empty) };
    await TestBed.configureTestingModule({
      imports: [ActionCenterComponent],
      providers: [provideRouter([]), { provide: ActionCenterService, useValue: api }],
    }).compileComponents();
  });
  it('reloads resolved status through the canonical API and resets pagination', async () => {
    const fixture = TestBed.createComponent(ActionCenterComponent);
    fixture.detectChanges(); await fixture.whenStable();
    fixture.componentInstance.offset = 25;
    const select = fixture.nativeElement.querySelectorAll('select')[2] as HTMLSelectElement;
    select.value = 'RESOLVED'; select.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(api.load).toHaveBeenLastCalledWith(expect.objectContaining({ status: 'RESOLVED', offset: 0, limit: 25 }));
  });
  it('uses server totals and offsets rather than paginating a truncated local dataset', async () => {
    const fixture = TestBed.createComponent(ActionCenterComponent);
    fixture.detectChanges(); await fixture.whenStable();
    api.load.mockResolvedValue({ ...empty, total: 70 });
    fixture.componentInstance.total.set(70);
    fixture.componentInstance.changePage(1); await fixture.whenStable();
    expect(api.load).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 25 }));
    fixture.componentInstance.changePage(-1); await fixture.whenStable();
    expect(api.load).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 0 }));
  });
  it('does not let an older request overwrite a newer selected status', async () => {
    const fixture = TestBed.createComponent(ActionCenterComponent);
    let older!: (value: typeof empty) => void;
    let newer!: (value: typeof empty) => void;
    api.load.mockReturnValueOnce(new Promise(resolve => { older = resolve; }))
      .mockReturnValueOnce(new Promise(resolve => { newer = resolve; }));
    const first = fixture.componentInstance.load();
    fixture.componentInstance.status = 'RESOLVED';
    const second = fixture.componentInstance.load();
    newer({ ...empty, total: 2 }); await second;
    older({ ...empty, total: 99 }); await first;
    expect(fixture.componentInstance.total()).toBe(2);
    expect(fixture.componentInstance.loading()).toBe(false);
  });
  it('shows a failure without falsely showing a successful empty state', async () => {
    api.load.mockRejectedValue(new Error('synthetic unavailable'));
    const fixture = TestBed.createComponent(ActionCenterComponent);
    fixture.detectChanges(); await fixture.whenStable(); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Action Center is unavailable');
    expect(fixture.nativeElement.textContent).not.toContain('No matching issues');
  });
});
