/** Public browser setting shared with the development proxy; never an origin. */
export function normalizeApiBasePath(value: string | undefined): string {
  const path = value?.trim() || '/api/v1';
  const normalized = path.replace(/\/+$/, '');
  if (!normalized) throw new Error('VITE_API_BASE_URL must not be the site root');
  // Keep the browser request path identical to the proxy match: URL parsers
  // otherwise encode Unicode or resolve dot segments before making the request.
  if (!/^\/[A-Za-z0-9._~-]+(?:\/[A-Za-z0-9._~-]+)*$/.test(normalized)
      || normalized.split('/').some(segment => segment === '.' || segment === '..')) {
    throw new Error('VITE_API_BASE_URL must use nonempty ASCII path segments without encoding or dot segments');
  }
  return normalized;
}
