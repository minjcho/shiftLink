import { afterEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';
import ResolutionPanel from '../src/features/resolution/ResolutionPanel.vue';
import CommandFeedback from '../src/components/CommandFeedback.vue';
import { detail, supervisor, maintainer, response, failure } from './fixtures';
import type { Resolution } from '../src/features/resolution/types';
const ready: Resolution = { ready: true, unmet_requirements: [], checked_version: 6, can_resolve: true, can_return: true, latest_verification: null, case: null };
const pending = (patch = {}) => ({ ...detail({ status: 'PENDING_VERIFICATION', version: 6 }), resolution: { ...ready }, ...patch });
const saved = { incident_id: 'incident-1', incident_version: 7, incident_status: 'RESOLVED', verification_id: 'verification-1', case_id: 'case-1', resolved_at: '2026-10-09T06:00:00Z' };
let wrapper: VueWrapper;
afterEach(() => { wrapper?.unmount(); vi.unstubAllGlobals(); });
function render(refresh = vi.fn().mockResolvedValue(undefined)) {
  wrapper = mount(ResolutionPanel, { props: { detail: pending(), session: supervisor, refresh } });
  return wrapper;
}
const button = (text: string) => wrapper.findAll('button').find(b => b.text() === text)!;
async function write() { await wrapper.find('textarea').setValue('  확인한 근거와 사유\n'); await wrapper.find('form').trigger('submit'); await flushPromises(); }

describe('F4 verification recovery and authority', () => {
  it('requires notes and server readiness; permits RETURN when readiness fails', async () => {
    render();
    expect(button('해결 확인').attributes()).toHaveProperty('disabled');
    await wrapper.find('textarea').setValue('사유');
    await wrapper.setProps({ detail: pending({ resolution: { ...ready, ready: false, can_resolve: false, unmet_requirements: ['REQUIRED_QUESTION_UNANSWERED'] } }) });
    expect(wrapper.text()).toContain('필수 질문 답변 필요');
    expect(button('해결 확인').attributes()).toHaveProperty('disabled');
    expect(button('검증 반려').attributes()).not.toHaveProperty('disabled');
    await wrapper.setProps({ session: maintainer });
    expect(wrapper.find('form').exists()).toBe(false);
  });
  it.each(['network', 'malformed', '503'])('replays exact body/key after %s, even when a read shows RESOLVED', async mode => {
    const fetcher = vi.fn().mockImplementationOnce(() => mode === 'network' ? Promise.reject(new Error('lost'))
      : Promise.resolve(mode === 'malformed' ? response({}) : failure('SERVICE_UNAVAILABLE', 503)))
      .mockResolvedValue(response(saved));
    vi.stubGlobal('fetch', fetcher); render(); await write();
    const feedback = wrapper.findComponent(CommandFeedback);
    expect(feedback.props('command').canRetry).toBe(true);
    await wrapper.setProps({ detail: pending({ status: 'RESOLVED', version: 7, resolution: { ...ready, can_resolve: false, can_return: false } }) });
    feedback.vm.$emit('review'); await flushPromises();
    expect(fetcher).toHaveBeenCalledTimes(1);
    await button('같은 요청 결과 확인').trigger('click'); await flushPromises();
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1][1].body).toBe(fetcher.mock.calls[0][1].body);
    expect(fetcher.mock.calls[1][1].headers['Idempotency-Key']).toBe(fetcher.mock.calls[0][1].headers['Idempotency-Key']);
    expect(wrapper.text()).toContain('해결 이력을 저장했습니다');
  });
  it('after success and failed refresh offers only a read, never another write', async () => {
    const fetcher = vi.fn().mockResolvedValue(response(saved)); vi.stubGlobal('fetch', fetcher);
    const refresh = vi.fn().mockRejectedValueOnce(new Error('read lost')).mockResolvedValue(undefined);
    render(refresh); await write();
    expect(button('해결 확인').attributes()).toHaveProperty('disabled');
    expect(wrapper.text()).toContain('저장 성공 후에는 재조회만');
    await button('저장 결과 다시 조회').trigger('click'); await flushPromises();
    expect(fetcher).toHaveBeenCalledTimes(1); expect(refresh).toHaveBeenCalledTimes(2);
  });
  it('preserves rejected command until refreshed and explicitly reviewed', async () => {
    const fetcher = vi.fn().mockResolvedValue(failure('VERSION_CONFLICT')); vi.stubGlobal('fetch', fetcher);
    const refresh = vi.fn().mockRejectedValueOnce(new Error('read lost')).mockResolvedValue(undefined);
    render(refresh); await write();
    const feedback = wrapper.findComponent(CommandFeedback);
    feedback.vm.$emit('review'); await flushPromises();
    expect(feedback.props('command').hasPending).toBe(true);
    await wrapper.setProps({ detail: pending({ version: 8 }) });
    feedback.vm.$emit('review'); await flushPromises();
    expect(feedback.props('command').hasPending).toBe(false);
    await wrapper.find('form').trigger('submit'); await flushPromises();
    expect(JSON.parse(fetcher.mock.calls[1][1].body).expected_version).toBe(8);
    expect(fetcher.mock.calls[1][1].headers['Idempotency-Key']).not.toBe(fetcher.mock.calls[0][1].headers['Idempotency-Key']);
  });
  it('requires review when polling changes a version while typing', async () => {
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); render();
    await wrapper.find('textarea').setValue('작성 중');
    await wrapper.setProps({ detail: pending({ version: 7 }) });
    expect(button('해결 확인').attributes()).toHaveProperty('disabled');
    await wrapper.find('form').trigger('submit'); expect(fetcher).not.toHaveBeenCalled();
    await button('최신 내용 다시 확인').trigger('click'); await flushPromises();
    expect(button('해결 확인').attributes()).not.toHaveProperty('disabled');
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('작성 중');
  });
  it('ignores late write results after incident/session changes', async () => {
    let finish!: (value: Response) => void;
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(resolve => { finish = resolve; })));
    const refresh = vi.fn(); render(refresh); await write();
    await wrapper.setProps({ detail: pending({ id: 'incident-2' }) });
    finish(response(saved)); await flushPromises();
    expect(refresh).not.toHaveBeenCalled(); expect(wrapper.text()).not.toContain('해결 이력을 저장했습니다');
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('');
  });
});
