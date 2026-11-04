import { FinancialWorkspaceComponent } from './financial-workspace.component';
import { FinancialSummary } from './marketplace.service';

describe('Financial provenance label fails closed', () => {
  const label = FinancialWorkspaceComponent.prototype.provenanceLabel;
  it('does not infer real evidence from false or missing synthetic status', () => {
    expect(label({ synthetic_provider: false } as FinancialSummary)).toBe('Provenance UNKNOWN');
    expect(label({} as FinancialSummary)).toBe('Provenance UNKNOWN');
  });
  it('keeps reported evidence distinct from verified real data', () => {
    expect(label({ provenance_status: 'REPORTED' } as FinancialSummary)).toBe('Reported evidence');
    expect(label({ synthetic_provider: true, provenance_status: 'REPORTED' } as FinancialSummary)).toBe('Synthetic fixture');
  });
});
