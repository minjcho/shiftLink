import { describe, expect, it, vi } from 'vitest'
import { createActionClient, prepareCommand } from './client'

describe('action transport', () => {
  it('uses the identical body/key on network retry and includes cookies', async () => {
    const transport = vi.fn().mockRejectedValueOnce(new Error('lost response'))
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: { action_id: 'a', incident_version: 7,
        action_version: 3, action_status: 'IN_PROGRESS', incident_status: 'IN_PROGRESS' } })))
    const send = createActionClient('/api/v1', transport)
    const body = { expected_version: 2, expected_incident_version: 6 }
    const command = prepareCommand('a', 'u', 'start', body, 'key')
    body.expected_version = 100
    await expect(send(command)).rejects.toMatchObject({ code: 'NETWORK', retrySameRequest: true })
    await send(command)
    expect(transport.mock.calls[0]).toEqual(transport.mock.calls[1])
    expect(transport.mock.calls[0]?.[1]).toMatchObject({ credentials: 'include',
      headers: { 'Idempotency-Key': 'key' }, body: '{"expected_version":2,"expected_incident_version":6}' })
  })
  it('does not automatically replay a version conflict', async () => {
    const transport = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: {
      code: 'VERSION_CONFLICT', message: '새 정보' } }), { status: 409 }))
    await expect(createActionClient('/api/v1', transport)(prepareCommand('a', 'u', 'start', {
      expected_version: 1, expected_incident_version: 5 }))).rejects.toMatchObject({
      code: 'VERSION_CONFLICT', retrySameRequest: false })
    expect(transport).toHaveBeenCalledTimes(1)
  })
  it.each([429, 500, 503])('keeps same-request recovery for status %s', async status => {
    const transport = vi.fn().mockResolvedValue(new Response('{}', { status }))
    await expect(createActionClient('/api/v1', transport)(prepareCommand('a', 'u', 'start', {
      expected_version: 1, expected_incident_version: 5 }))).rejects.toMatchObject({ retrySameRequest: true })
  })
  it('treats malformed successful responses as uncertain, not saved', async () => {
    const transport = vi.fn().mockResolvedValue(new Response('<html>gateway</html>'))
    await expect(createActionClient('/api/v1', transport)(prepareCommand('a', 'u', 'start', {
      expected_version: 1, expected_incident_version: 5 }))).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })
  })
})
