import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiClient, ApiError, Command, SessionChanged } from '../src/lib/api';
import { response, failure } from './fixtures';
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
describe('browser API path configuration', () => {
  it.each([
    [undefined, '/api/v1'], ['', '/api/v1'], ['  ', '/api/v1'],
    ['/gateway/api/v1', '/gateway/api/v1'], ['/gateway/api/v1/', '/gateway/api/v1'],
    ['/gateway/api/v1///', '/gateway/api/v1'], ['/api_v1/~demo/.well-known/v1.2-beta', '/api_v1/~demo/.well-known/v1.2-beta'],
  ])('uses %s for GET and POST without changing credentials or receipt headers', async (configured, expected) => {
    vi.stubEnv('VITE_API_BASE_URL', configured);
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response({ id: 'saved' }))); vi.stubGlobal('fetch', fetcher);
    const client = new ApiClient();
    await client.request('/me');
    await client.request('/incidents', 'POST', { text: 'original' }, 'same-receipt-key');
    expect(fetcher.mock.calls.map(call => call[0])).toEqual([`${expected}/me`, `${expected}/incidents`]);
    expect(fetcher.mock.calls.every(call => call[1].credentials === 'include')).toBe(true);
    expect(fetcher.mock.calls[1][1].headers['Idempotency-Key']).toBe('same-receipt-key');
    expect(fetcher.mock.calls[1][1].body).toBe(JSON.stringify({ text: 'original' }));
  });
  it.each(['https://other.invalid/api/v1', '//other.invalid/api/v1', '/\\other.invalid/api/v1',
    'api/v1', '/', '/api/v1?host=other', '/api/v1#other', '/api\n/v1',
    '/gateway/../api/v1', '/gateway/./api/v1', '/한글/api', '/gateway//api/v1',
    '/gateway/%2e%2e/api', '/gateway/%2f/api', '/gateway/api%20v1', '/gateway/%61pi'])('rejects non-prefix configuration %s before fetching', configured => {
    vi.stubEnv('VITE_API_BASE_URL', configured);
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
    expect(() => new ApiClient()).toThrow('VITE_API_BASE_URL');
    expect(fetcher).not.toHaveBeenCalled();
  });
});
describe('AC31 command receipt identity and session boundary', () => {
  it('retries an uncertain write with exact same key and frozen original body', async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new TypeError('network')).mockResolvedValue(response({ id: 'saved' })); vi.stubGlobal('fetch', fetcher);
    const command = new Command(); const client = new ApiClient(); const body = { text: 'original', expected_version: 3 };
    await expect(command.send(client, '/incidents/i/messages', body)).rejects.toThrow(); body.text = 'changed';
    expect(command.canRetry).toBe(true); expect(command.canReview).toBe(false); await command.send(client);
    expect(fetcher.mock.calls[0][1].headers['Idempotency-Key']).toBe(fetcher.mock.calls[1][1].headers['Idempotency-Key']);
    expect(fetcher.mock.calls[1][1].body).toBe(JSON.stringify({ text: 'original', expected_version: 3 })); expect(command.hasPending).toBe(false);
  });
  it('requires explicit review after 409 and rotates key for an intentional new command', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(failure('VERSION_CONFLICT')).mockResolvedValue(response({ id: 'saved' })); vi.stubGlobal('fetch', fetcher);
    const command = new Command(); const client = new ApiClient();
    await expect(command.send(client, '/incidents/i/messages', { expected_version: 3 })).rejects.toBeInstanceOf(ApiError);
    expect(command.canRetry).toBe(false); expect(command.canReview).toBe(true); expect(fetcher).toHaveBeenCalledTimes(1);
    await expect(command.send(client, '/incidents/i/messages', { expected_version: 4 })).rejects.toThrow('이전 요청');
    command.reset(); await command.send(client, '/incidents/i/messages', { expected_version: 4 });
    expect(fetcher.mock.calls[0][1].headers['Idempotency-Key']).not.toBe(fetcher.mock.calls[1][1].headers['Idempotency-Key']);
  });
  it('does not reuse a successful key for later deliberate submissions', async () => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response({ id: 'saved' }))); vi.stubGlobal('fetch', fetcher);
    const command = new Command(); const client = new ApiClient(); await command.send(client, '/incidents', { text: 'same' }); await command.send(client, '/incidents', { text: 'same' });
    expect(fetcher.mock.calls[0][1].headers['Idempotency-Key']).not.toBe(fetcher.mock.calls[1][1].headers['Idempotency-Key']);
  });
  it('deduplicates repeated clicks while a request is in flight', async () => {
    let resolve!: (v: Response) => void; const fetcher = vi.fn().mockReturnValue(new Promise(r => resolve = r)); vi.stubGlobal('fetch', fetcher);
    const command = new Command(); const client = new ApiClient(); const first = command.send(client, '/incidents', { text: 'x' }); await command.send(client, '/incidents', { text: 'x' }); expect(fetcher).toHaveBeenCalledTimes(1); resolve(response({ id: 'one' })); await first;
  });
  it('cannot replay a saved prior-session command in a new session', async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError('offline')); vi.stubGlobal('fetch', fetcher);
    const client = new ApiClient(); const command = new Command(); await expect(command.send(client, '/incidents', { text: 'x' })).rejects.toThrow(); client.invalidateSession();
    await expect(command.send(client)).rejects.toBeInstanceOf(SessionChanged); expect(fetcher).toHaveBeenCalledTimes(1); expect(command.hasPending).toBe(false);
  });
  it('discards an old-session response even if cancellation is ignored by transport', async () => {
    let resolve!: (v: Response) => void; vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(r => resolve = r)));
    const client = new ApiClient(); const pending = client.request('/me'); client.invalidateSession(); resolve(response({ user_id: 'old' })); await expect(pending).rejects.toBeInstanceOf(SessionChanged);
  });
  it.each([[429, 'RETRY_LATER'], [503, 'SERVICE_UNAVAILABLE'], [409, 'COMMAND_IN_PROGRESS']])('allows only explicit original retry for %s %s', async (status, code) => {
    const fetcher = vi.fn().mockResolvedValue(failure(code, status)); vi.stubGlobal('fetch', fetcher); const command = new Command(); await expect(command.send(new ApiClient(), '/incidents', {})).rejects.toThrow(); expect(command.canRetry).toBe(true); expect(command.canReview).toBe(false); expect(fetcher).toHaveBeenCalledTimes(1);
  });
});

describe('F0 API routing', () => {
  it('uses a configured API prefix for both reads and writes', async () => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response({ id: 'saved' })));
    vi.stubGlobal('fetch', fetcher);
    const client = new ApiClient('/gateway/api/v1/');
    await client.request('/me');
    await client.request('/incidents', 'POST', { text: '원문' }, 'same-key');
    expect(fetcher.mock.calls.map(c => c[0])).toEqual(['/gateway/api/v1/me', '/gateway/api/v1/incidents']);
    expect(fetcher.mock.calls[1][1].headers['Idempotency-Key']).toBe('same-key');
  });
});
