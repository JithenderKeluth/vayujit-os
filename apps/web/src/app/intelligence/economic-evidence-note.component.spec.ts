import { TestBed } from '@angular/core/testing';
import { EconomicEvidenceNoteComponent } from './economic-evidence-note.component';

describe('EconomicEvidenceNoteComponent', () => {
  it('retains original evidence without parsing it or presenting it as a verified value', () => {
    const fixture = TestBed.createComponent(EconomicEvidenceNoteComponent);
    const original = "{'key': 'freight', 'value': None, 'source_references': []}";
    fixture.componentRef.setInput('code', 'COMMERCIAL_INPUT_UNKNOWN');
    fixture.componentRef.setInput('message', original);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('UNKNOWN. It is not zero');
    expect(fixture.nativeElement.querySelector('pre').textContent).toBe(original);
    expect(fixture.nativeElement.querySelector('details').open).toBe(false);
  });
  it('renders ordinary canonical explanations as escaped text, not HTML', () => {
    const fixture = TestBed.createComponent(EconomicEvidenceNoteComponent);
    fixture.componentRef.setInput('message', '<script>bad()</script>');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('script')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('<script>bad()</script>');
  });
});
