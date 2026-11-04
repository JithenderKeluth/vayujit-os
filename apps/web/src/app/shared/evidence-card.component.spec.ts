import { TestBed } from '@angular/core/testing';
import { EvidenceCardComponent } from './evidence-card.component';

describe('EvidenceCardComponent heading context', () => {
  it('preserves the default and supports a nested decision brief without skipping heading levels', () => {
    const fixture = TestBed.createComponent(EvidenceCardComponent);
    fixture.componentRef.setInput('title', 'Evidence summary');
    fixture.componentRef.setInput('classification', 'SYNTHETIC');
    fixture.componentRef.setInput('summary', 'Synthetic facts remain unverified.');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('h3')?.textContent).toBe('Evidence summary');
    fixture.componentRef.setInput('headingLevel', 5);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('h3')).toBeNull();
    expect(fixture.nativeElement.querySelector('h5')?.textContent).toBe('Evidence summary');
  });
});
