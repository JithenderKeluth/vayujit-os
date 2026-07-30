import { arrayDiff, scalarDiff } from './artifact-diff';

describe('artifact diff', () => {
  it('classifies unchanged, added, removed, and modified scalar text', () => {
    expect(scalarDiff('same', 'same').state).toBe('unchanged');
    expect(scalarDiff('', '<script>alert(1)</script>')).toEqual({
      state: 'added',
      before: '',
      after: '<script>alert(1)</script>',
    });
    expect(scalarDiff('old', '').state).toBe('removed');
    expect(scalarDiff('old', 'new').state).toBe('modified');
  });

  it('preserves array order while identifying additions and removals', () => {
    expect(arrayDiff(['first', 'removed', 'last'], ['first', 'last', 'added'])).toEqual([
      { value: 'first', state: 'unchanged' },
      { value: 'removed', state: 'removed' },
      { value: 'last', state: 'unchanged' },
      { value: 'added', state: 'added' },
    ]);
  });
});
