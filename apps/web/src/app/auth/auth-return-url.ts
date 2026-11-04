/** Navigation only. Resource authorization still belongs to guards and the API. */
function unsafeCharacters(value: string): boolean {
  return [...value].some(
    (character) =>
      character === '\\' || character.charCodeAt(0) <= 32 || character.charCodeAt(0) === 127,
  );
}
export function authReturnUrl(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || unsafeCharacters(value))
    return '/dashboard';
  try {
    let pathname = value.split(/[?#]/, 1)[0];
    for (let i = 0; i < 3; i++) {
      if (
        !pathname.startsWith('/') ||
        pathname.startsWith('//') ||
        unsafeCharacters(pathname) ||
        /[():]/.test(pathname)
      )
        return '/dashboard';
      const decoded = decodeURIComponent(pathname);
      if (decoded === pathname) break;
      pathname = decoded;
    }
    if (/%|(?:^|\/)\.\.?(?:\/|$)/.test(pathname) || /^\/(?:login|setup)(?:\/|$)/i.test(pathname))
      return '/dashboard';
    return value;
  } catch {
    return '/dashboard';
  }
}
