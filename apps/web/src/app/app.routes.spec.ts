import { routes } from './app.routes';

describe('application route integrity', () => {
  it('keeps the existing AI bulk-image destination reachable', () => {
    const paths = routes.map((route) => route.path);

    expect(paths).toContain('ai/images');
    expect(paths).toContain('ai/images/bulk');
    expect(paths).toContain('settings/ai/providers');
    expect(paths.indexOf('ai/images/bulk')).toBeLessThan(paths.indexOf('ai/images'));
  });
});
