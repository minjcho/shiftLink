export class ApiError extends Error {
  constructor(message: string, public code: string, public retryable: boolean, public status: number) { super(message) }
}
export interface Envelope<T> { data: T; meta: { request_id: string } }
export interface PreparedCommand { readonly path: string; readonly body: string; readonly key: string }
export function prepareCommand(path: string, body: unknown, key: string = crypto.randomUUID()): PreparedCommand {
  return Object.freeze({ path, body: JSON.stringify(body), key })
}
export function createApi(transport: typeof fetch = fetch) {
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    let response: Response
    try { response = await transport(`${import.meta.env.VITE_API_BASE_URL ?? '/api/v1'}${path}`, { ...init, credentials: 'include' }) }
    catch { throw new ApiError('연결을 확인하지 못했습니다. 다시 시도해 주세요.', 'NETWORK', true, 0) }
    let body
    try { body = await response.json() } catch { throw new ApiError('응답을 확인하지 못했습니다.', 'INVALID_RESPONSE', true, response.status) }
    if (!response.ok) throw new ApiError(body?.error?.message ?? '요청을 처리하지 못했습니다.', body?.error?.code ?? 'HTTP_ERROR',
      body?.error?.retryable === true || response.status >= 500 || response.status === 429, response.status)
    if (!body || !('data' in body)) throw new ApiError('응답을 확인하지 못했습니다.', 'INVALID_RESPONSE', true, response.status)
    return body.data as T
  }
  return {
    get: <T>(path: string) => request<T>(path),
    // The only POST exempt from a domain command receipt.
    switchSession: <T>(accountKey: string) => request<T>('/demo/session', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ account_key: accountKey }) }),
    send: <T>(command: PreparedCommand) => request<T>(command.path, { method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': command.key }, body: command.body }),
  }
}
export const api = createApi()
