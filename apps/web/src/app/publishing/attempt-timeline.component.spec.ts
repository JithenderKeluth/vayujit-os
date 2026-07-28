import { TestBed } from '@angular/core/testing';
import { AttemptTimelineComponent } from './attempt-timeline.component';

describe('AttemptTimelineComponent', () => {
  it('shows safe failure and subsequent success in order', () => {
    const fixture = TestBed.createComponent(AttemptTimelineComponent);
    fixture.componentRef.setInput('attempts', [
      {
        attempt_number: 1,
        status: 'failed',
        retryable: true,
        error_code: 'mock_retryable_failure',
        safe_error_message: 'Safe failure',
        started_at: 'start',
        failed_at: 'fail',
        completed_at: null,
        result: null,
      },
      {
        attempt_number: 2,
        status: 'succeeded',
        retryable: false,
        error_code: null,
        safe_error_message: null,
        started_at: 'start2',
        failed_at: null,
        completed_at: 'done',
        result: { publication_id: 'PUB-1' },
      },
    ]);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Attempt 1');
    expect(fixture.nativeElement.textContent).toContain('mock_retryable_failure');
    expect(fixture.nativeElement.textContent).toContain('PUB-1');
  });
});
