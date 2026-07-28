export type DiffState = 'unchanged' | 'added' | 'removed' | 'modified';

export interface ScalarDiff {
  state: DiffState;
  before: string;
  after: string;
}

export interface ArrayDiffItem {
  state: 'unchanged' | 'added' | 'removed';
  value: string;
}

export function scalarDiff(before = '', after = ''): ScalarDiff {
  if (before === after) return { state: 'unchanged', before, after };
  if (!before) return { state: 'added', before, after };
  if (!after) return { state: 'removed', before, after };
  return { state: 'modified', before, after };
}

export function arrayDiff(before: string[] = [], after: string[] = []): ArrayDiffItem[] {
  const result: ArrayDiffItem[] = [];
  for (const value of before) {
    result.push({ value, state: after.includes(value) ? 'unchanged' : 'removed' });
  }
  for (const value of after) {
    if (!before.includes(value)) result.push({ value, state: 'added' });
  }
  return result;
}
