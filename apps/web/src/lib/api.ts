import type { Envelope } from './types';
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public currentVersion: number | null = null, public details: unknown = null) { super(message); }
}
export class SessionChanged extends Error {}
export class ApiClient {
  private epoch = 0;
  private pending = new Set<AbortController>();
  get sessionEpoch() { return this.epoch; }
  invalidateSession() { this.epoch += 1; this.pending.forEach(c => c.abort()); this.pending.clear(); }
  async request<T>(path: string, method = 'GET', body?: unknown, key?: string): Promise<Envelope<T>> {
    const epoch = this.epoch;
    const controller = new AbortController();
    this.pending.add(controller);
    try {
      const response = await fetch(`/api/v1${path}`, {
        method, credentials: 'include', signal: controller.signal,
        headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(key ? { 'Idempotency-Key': key } : {}) },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const value = await response.json();
      if (epoch !== this.epoch) throw new SessionChanged();
      if (!response.ok) throw new ApiError(response.status, value.error?.code ?? 'HTTP_ERROR', value.error?.message ?? '요청을 처리하지 못했습니다.', value.error?.current_version ?? null, value.error?.details);
      return value as Envelope<T>;
    } catch (error) {
      if (epoch !== this.epoch) throw new SessionChanged();
      throw error;
    } finally { this.pending.delete(controller); }
  }
}
export const api = new ApiClient();
export function errorMessage(error: unknown) {
  if (error instanceof ApiError) return `${error.message} (${error.code})`;
  return '연결을 확인해 주세요. 요청 결과를 확인하지 못했습니다.';
}
export function uncertain(error: unknown) {
  return !(error instanceof ApiError) || [429, 503].includes(error.status) || error.code === 'COMMAND_IN_PROGRESS';
}
/** One explicit user command. Retries retain the exact request snapshot and key. */
export class Command {
  private snapshot: { path: string; body: unknown; key: string; epoch: number } | null = null;
  busy = false;
  error: unknown = null;
  get hasPending() { return this.snapshot !== null; }
  get canRetry() { return this.hasPending && this.error !== null && uncertain(this.error); }
  reset() { if (this.busy) return; this.snapshot = null; this.error = null; }
  async send<T>(client: ApiClient, path?: string, body?: unknown): Promise<T | undefined> {
    if (this.busy) return;
    if (!this.snapshot) {
      if (!path) throw new Error('새 명령에 경로가 필요합니다.');
      this.snapshot = { path, body: JSON.parse(JSON.stringify(body)), key: crypto.randomUUID(), epoch: client.sessionEpoch };
    } else if (path !== undefined) { throw new Error('이전 요청을 먼저 확인해 주세요.'); }
    const snapshot = this.snapshot;
    if (snapshot.epoch !== client.sessionEpoch) { this.reset(); throw new SessionChanged(); }
    this.busy = true;
    this.error = null;
    try {
      const { data } = await client.request<T>(snapshot.path, 'POST', snapshot.body, snapshot.key);
      this.snapshot = null;
      return data;
    } catch (error) {
      if (error instanceof SessionChanged) this.snapshot = null;
      else this.error = error;
      throw error;
    } finally { this.busy = false; }
  }
}

export type CommandState = Pick<Command, keyof Command>;
