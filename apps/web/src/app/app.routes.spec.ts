import { routes } from './app.routes';

describe('application route integrity', () => {
  it('keeps the existing AI bulk-image destination reachable', () => {
    const paths = routes.map((route) => route.path);

    expect(paths).toContain('ai/images');
    expect(paths).toContain('ai/images/bulk');
    expect(paths).toContain('settings/ai/providers');
    expect(paths.indexOf('ai/images/bulk')).toBeLessThan(paths.indexOf('ai/images'));
  });

  it('keeps the core seller journey destinations reachable', () => {
    const paths = routes.map((route) => route.path);

    expect(paths).toEqual(
      expect.arrayContaining([
        'dashboard',
        'intelligence/business-agent',
        'intelligence/product-opportunities',
        'intelligence/sourcing',
        'intelligence/sourcing-economics',
        'intelligence/supplier-shortlisting',
        'intelligence/due-diligence',
      ]),
    );
  });

  it('exposes the seller catalog list and product workspace routes', () => {
    const paths = routes.map((route) => route.path);
    expect(paths).toEqual(expect.arrayContaining(['catalog', 'catalog/:id']));
  });
});
