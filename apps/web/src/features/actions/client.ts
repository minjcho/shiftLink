import type { CommandBody, CommandData, CommandKind, PendingCommand, SendCommand } from './types'

export class CommandFailure extends Error {
  constructor(message: string, public code: string, public retrySameRequest = false) {
    super(message)
  }
}

export function prepareCommand(actionId: string, actorId: string, kind: CommandKind,
  body: CommandBody, key: string = crypto.randomUUID()): PendingCommand {
  return Object.freeze({ actionId, actorId, kind, key, serializedBody: JSON.stringify(body) })
}

export function createActionClient(baseUrl = '/api/v1', transport: typeof fetch = fetch): SendCommand {
  return async command => {
    let response: Response
    try {
      response = await transport(`${baseUrl}/actions/${encodeURIComponent(command.actionId)}/${command.kind}`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': command.key },
        body: command.serializedBody,
      })
    } catch {
      throw new CommandFailure('응답을 확인하지 못했습니다. 같은 요청으로 다시 확인해 주세요.', 'NETWORK', true)
    }
    let body
    try { body = await response.json() } catch {
      throw new CommandFailure('서버 응답을 확인하지 못했습니다.', 'INVALID_RESPONSE', true)
    }
    if (!response.ok) {
      const code = body?.error?.code ?? 'HTTP_ERROR'
      throw new CommandFailure(body?.error?.message ?? '요청을 처리하지 못했습니다.', code,
        code === 'COMMAND_IN_PROGRESS' || response.status === 429 || response.status >= 500)
    }
    const data = body?.data
    if (data?.action_id !== command.actionId || !Number.isInteger(data?.incident_version)
      || !Number.isInteger(data?.action_version) || typeof data?.incident_status !== 'string'
      || !['PROPOSED', 'APPROVED', 'IN_PROGRESS', 'COMPLETED', 'REJECTED'].includes(data?.action_status)) {
      throw new CommandFailure('저장 응답을 확인하지 못했습니다.', 'INVALID_RESPONSE', true)
    }
    return data as CommandData
  }
}
