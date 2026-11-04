/** Presentation of the canonical fixture source marker, never a verification authority. */
export function supplierEvidenceOrigin(value: Record<string, unknown> | null): string {
  const freshness = value?.['freshness'];
  const sources =
    freshness && typeof freshness === 'object'
      ? (freshness as Record<string, unknown>)['sources']
      : null;
  const fixture =
    Array.isArray(sources) &&
    sources.some((source: unknown) => {
      if (!source || typeof source !== 'object') return false;
      const id = (source as Record<string, unknown>)['external_id'];
      return (
        (source as Record<string, unknown>)['synthetic'] === true ||
        (typeof id === 'string' && id.startsWith('fixture:'))
      );
    });
  return fixture
    ? 'Contains synthetic fixture evidence — not live supplier verification.'
    : 'Evidence origin must be reviewed. No live supplier verification is established here.';
}
