import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ActionPanel from './ActionPanel.vue'
import { CommandFailure } from './client'
import type { ActionView, CommandData, IncidentView, SessionView } from './types'

const action: ActionView = { id: 'action-1', status: 'PROPOSED', version: 1, scope: '초기 기록 확인',
  assignee_id: 'maintainer', due_at: '2026-10-09T04:00:00Z', completion_criteria: ['결과 원문 기록'],
  evidence_refs: ['evidence-1'], result_message_id: null }
const incident: IncidentView = { id: 'incident-1', version: 5, status: 'ACTION_REQUIRED',
  owner_id: 'owner', review_required: false, review_reason: null }
const owner: SessionView = { user_id: 'owner', role: 'supervisor' }
const maintainer: SessionView = { user_id: 'maintainer', role: 'worker' }
const saved: CommandData = { action_id: action.id, action_status: 'APPROVED', action_version: 2,
  incident_status: 'ACTION_REQUIRED', incident_version: 6 }
const button = (wrapper: ReturnType<typeof mount>, text: string) =>
  wrapper.findAll('button').find(b => b.text() === text)!

function setup(overrides: Record<string, unknown> = {}) {
  const send = vi.fn().mockResolvedValue(saved)
  const refresh = vi.fn().mockResolvedValue(undefined)
  const wrapper = mount(ActionPanel, { props: { action, incident, session: owner, approvals: [], result: null,
    evidenceOptions: [{ id: 'evidence-1', label: '합성 SOP' }], send, refresh, ...overrides } })
  return { wrapper, send, refresh }
}

describe('F2 panel (component harness, not live E2E)', () => {
  it('shows scope and criteria, requires a reason before approval, and refreshes', async () => {
    const { wrapper, send, refresh } = setup()
    expect(wrapper.text()).toContain('초기 기록 확인')
    expect(wrapper.text()).toContain('결과 원문 기록')
    expect(button(wrapper, '작업 승인').attributes('disabled')).toBeDefined()
    await wrapper.get('textarea').setValue('내용 확인')
    await button(wrapper, '작업 승인').trigger('click')
    await flushPromises()
    expect(JSON.parse(send.mock.calls[0]![0].serializedBody)).toEqual({ decision: 'APPROVE', reason: '내용 확인',
      expected_version: 1, expected_incident_version: 5 })
    expect(refresh).toHaveBeenCalledOnce()
  })
  it('hides owner commands for assignee before approval', () => {
    const { wrapper } = setup({ session: maintainer })
    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(wrapper.text()).toContain('현재 책임자 또는 지정 작업 담당자')
  })
  it('shows start only to the designated assignee', () => {
    const { wrapper } = setup({ session: maintainer, action: { ...action, status: 'APPROVED' } })
    expect(button(wrapper, '작업 착수')).toBeDefined()
    expect(wrapper.find('textarea').exists()).toBe(false)
    const other = setup({ session: owner, action: { ...action, status: 'APPROVED' } })
    expect(other.wrapper.findAll('button')).toHaveLength(0)
  })
  it('preserves input and requires reload plus explicit review after conflict', async () => {
    const { wrapper, send, refresh } = setup()
    send.mockRejectedValueOnce(new CommandFailure('내용 변경', 'VERSION_CONFLICT'))
    await wrapper.get('textarea').setValue('원래 사유')
    await button(wrapper, '작업 승인').trigger('click')
    await flushPromises()
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('원래 사유')
    expect(send).toHaveBeenCalledOnce()
    expect(button(wrapper, '최신 내용을 확인했습니다').attributes('disabled')).toBeDefined()
    await button(wrapper, '최신 내용 불러오기').trigger('click')
    await flushPromises()
    await wrapper.setProps({ incident: { ...incident, version: 6 } })
    await button(wrapper, '최신 내용을 확인했습니다').trigger('click')
    await button(wrapper, '작업 승인').trigger('click')
    await flushPromises()
    expect(send).toHaveBeenCalledTimes(2)
    expect(send.mock.calls[0]![0].key).not.toBe(send.mock.calls[1]![0].key)
    expect(JSON.parse(send.mock.calls[1]![0].serializedBody).expected_incident_version).toBe(6)
    expect(refresh).toHaveBeenCalledTimes(2)
  })
  it('retries an uncertain command unchanged even after a polling update', async () => {
    const { wrapper, send } = setup()
    send.mockRejectedValueOnce(new CommandFailure('응답 유실', 'NETWORK', true))
    await wrapper.get('textarea').setValue('확인')
    await button(wrapper, '작업 승인').trigger('click')
    await flushPromises()
    await wrapper.setProps({ action: { ...action, status: 'APPROVED', version: 2 }, incident: { ...incident, version: 6 } })
    await button(wrapper, '같은 요청으로 다시 확인').trigger('click')
    await flushPromises()
    expect(send.mock.calls[0]![0]).toEqual(send.mock.calls[1]![0])
  })
  it('blocks stale submissions while editing until the user reviews new data', async () => {
    const { wrapper, send } = setup()
    await wrapper.get('textarea').setValue('작성 중')
    await wrapper.setProps({ incident: { ...incident, version: 7 } })
    expect(button(wrapper, '작업 승인').attributes('disabled')).toBeDefined()
    expect(send).not.toHaveBeenCalled()
  })
  it('does not resend a saved command when refresh fails', async () => {
    const { wrapper, send, refresh } = setup()
    refresh.mockRejectedValueOnce(new Error('query failed'))
    await wrapper.get('textarea').setValue('확인')
    await button(wrapper, '작업 승인').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('저장은 완료됐지만')
    expect(button(wrapper, '같은 요청으로 다시 확인')).toBeUndefined()
    await button(wrapper, '최신 내용 불러오기').trigger('click')
    await flushPromises()
    expect(send).toHaveBeenCalledOnce()
  })
  it('discards an old actor response and never replays it under a new session', async () => {
    let finish!: (data: CommandData) => void
    const send = vi.fn(() => new Promise<CommandData>(resolve => { finish = resolve }))
    const { wrapper, refresh } = setup({ send })
    await wrapper.get('textarea').setValue('확인')
    await button(wrapper, '작업 승인').trigger('click')
    await wrapper.setProps({ session: maintainer })
    finish(saved)
    await flushPromises()
    expect(refresh).not.toHaveBeenCalled()
    expect(button(wrapper, '같은 요청으로 다시 확인')).toBeUndefined()
    expect(wrapper.text()).not.toContain('처리가 저장됐습니다.')
  })
  it('submits result and optional evidence without claiming incident resolution', async () => {
    const { wrapper, send } = setup({ session: maintainer,
      action: { ...action, status: 'IN_PROGRESS', version: 3 }, incident: { ...incident, status: 'IN_PROGRESS', version: 7 } })
    send.mockResolvedValueOnce({ ...saved, action_status: 'COMPLETED', verification_ready: false })
    await wrapper.get('textarea').setValue('수행 결과')
    await wrapper.get('input[type=checkbox]').setValue(true)
    await button(wrapper, '작업 결과 제출').trigger('click')
    await flushPromises()
    expect(JSON.parse(send.mock.calls[0]![0].serializedBody)).toMatchObject({ result: '수행 결과', evidence_refs: ['evidence-1'] })
    expect(wrapper.text()).toContain('아직 사건의 검증 조건이 충족되지 않았습니다.')
  })
  it('displays persisted result without an editable completion form', () => {
    const { wrapper } = setup({ action: { ...action, status: 'COMPLETED', result_message_id: 'm1' },
      result: { id: 'm1', text: '저장된 결과', author_id: 'maintainer', received_at: '2026-10-09T04:00:00Z' } })
    expect(wrapper.text()).toContain('저장된 결과')
    expect(wrapper.find('textarea').exists()).toBe(false)
    expect(wrapper.text()).toContain('사건의 최종 해결은 별도')
  })
  it('does not expose a restart button after rejection', () => {
    const { wrapper } = setup({ action: { ...action, status: 'REJECTED' },
      incident: { ...incident, review_required: true, review_reason: '범위 검토' } })
    expect(wrapper.text()).toContain('후속 검토 필요: 범위 검토')
    expect(wrapper.findAll('button')).toHaveLength(0)
  })
})
