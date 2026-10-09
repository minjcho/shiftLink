import { describe, expect, it, vi } from 'vitest'
import { ApiError, createApi, prepareCommand } from './api'
import { createSessionStore } from './session'
import type { SessionView } from './contracts'

const user: SessionView = { user_id: 'user-1', site_id: 'site-1', role: 'worker', display_name: '작업자',
  site_name: '사업장', shift_occurrence_id: 'shift-1', duties: ['OPERATOR'] }

describe('shared client', () => {
  it('preserves command key/body through transport failure', async () => {
    const transport = vi.fn().mockRejectedValueOnce(new Error('lost')).mockResolvedValueOnce(
      new Response(JSON.stringify({ data: { saved: true } })))
    const client = createApi(transport)
    const command = prepareCommand('/incidents', { text: '원문' })
    await expect(client.send(command)).rejects.toMatchObject({ retryable: true })
    await expect(client.send(command)).resolves.toEqual({ saved: true })
    expect(transport.mock.calls[0]).toEqual(transport.mock.calls[1])
    expect(transport.mock.calls[0][1].credentials).toBe('include')
  })
  it('does not automatically replay a version conflict', async () => {
    const transport = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: {
      code: 'VERSION_CONFLICT', message: '변경됨', retryable: false } }), { status: 409 }))
    await expect(createApi(transport).send(prepareCommand('/incidents', {}))).rejects.toMatchObject({ code: 'VERSION_CONFLICT', retryable: false })
    expect(transport).toHaveBeenCalledTimes(1)
  })
  it('only session bootstrap omits command receipt header', async () => {
    const transport = vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: user })))
    await createApi(transport).switchSession('reporter')
    expect(transport.mock.calls[0][1].headers).not.toHaveProperty('Idempotency-Key')
    expect(JSON.parse(transport.mock.calls[0][1].body)).toEqual({ account_key: 'reporter' })
  })
})

describe('server session state', () => {
  it('clears old actor while switching and accepts only server role', async () => {
    let finish: (u: SessionView) => void = () => {}
    const client = { get: vi.fn().mockResolvedValue(user), send: vi.fn(),
      switchSession: vi.fn().mockImplementation(() => new Promise<SessionView>(resolve => { finish = resolve })) }
    const store = createSessionStore(client)
    await store.load()
    expect(store.user.value?.role).toBe('worker')
    const pending = store.load('incoming_supervisor')
    expect(store.user.value).toBeNull()
    finish({ ...user, user_id: 'user-2', role: 'supervisor' })
    await pending
    expect(store.user.value?.user_id).toBe('user-2')
  })
  it('does not restore old actor after a failed switch', async () => {
    const client = { get: vi.fn().mockResolvedValue(user), send: vi.fn(),
      switchSession: vi.fn().mockRejectedValue(new ApiError('세션 오류', 'NETWORK', true, 0)) }
    const store = createSessionStore(client)
    await store.load(); await store.load('maintainer')
    expect(store.user.value).toBeNull()
    expect(store.error.value).toBe('세션 오류')
  })
})
