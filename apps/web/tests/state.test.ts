import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils';
import IncidentDetail from '../src/features/intake/IncidentDetail.vue';
import { detail, equipment, job, maintainer, reporter, supervisor, response } from './fixtures';
import type { IncidentDetail as Detail, Job } from '../src/lib/types';
const wrappers: VueWrapper[] = [];
afterEach(() => { wrappers.forEach(w => w.unmount()); wrappers.length = 0; vi.unstubAllGlobals(); });
async function render(data = detail(), account = maintainer, actualJob: Job = job) {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => Promise.resolve(response(url.includes('/jobs/') ? actualJob : data))));
  const wrapper = mount(IncidentDetail, { props: { id: data.id, me: account, equipment } }); wrappers.push(wrapper); await flushPromises(); return wrapper;
}
describe('AC30 actual response state rendering', () => {
  it('shows required question identity, target, purpose, evidence and only its target can answer', async () => {
    const wrapper = await render(); expect(wrapper.text()).toContain('request-1'); expect(wrapper.text()).toContain('점검 범위 확인'); expect(wrapper.text()).toContain('필수 · 답변 대기'); expect(wrapper.text()).toContain('evidence-1'); expect(wrapper.find('#reply-request-1').exists()).toBe(true);
    await wrapper.setProps({ me: supervisor }); expect(wrapper.find('#reply-request-1').exists()).toBe(false); expect(wrapper.text()).toContain('지정된 담당자만');
  });
  it('keeps human statements, hypotheses and source records distinct', async () => {
    const wrapper = await render(); expect(wrapper.text()).toContain('사람 진술'); expect(wrapper.text()).toContain('가설 · 확인된 사실 아님'); expect(wrapper.text()).toContain('미확인 정보'); expect(wrapper.text()).toContain('들었다는 사실과 직접 관찰을 구분한 원문'); expect(wrapper.text()).toContain('과거 사례는 현재 설비의 측정 결과가 아닙니다');
  });
  it('shows stale analysis even when handover is acknowledged and self-version change says is_stale false', async () => {
    const wrapper = await render(detail({ handover: { ack_status: 'ACKNOWLEDGED', is_stale: false }, analysis: { ...detail().analysis!, is_stale: false } })); expect(wrapper.text()).toContain('이전 정보에 대한 분석 · 갱신 필요'); expect(wrapper.text()).toContain('인수 완료'); expect(wrapper.text()).not.toContain('새 업무 내용 · 인계 재확인 필요');
  });
  it('derives required waiting from actual requests and retains it despite a inconsistent summary flag', async () => {
    const wrapper = await render(detail({ waiting_for_input: false })); expect(wrapper.text()).toContain('필수 질문 · 담당자 답변 대기');
  });
  it('separates intake from failed AI and only owner can see retry', async () => {
    const data = detail({ allowed_commands: ['retry_job'] }); const failed = { ...job, status: 'FAILED', error_code: 'TOOL_ERROR', retryable: true };
    const wrapper = await render(data, reporter, failed); expect(wrapper.text()).toContain('AI 조사 실패 · 제보는 저장됨'); expect(wrapper.findAll('button').some(b => b.text() === 'AI 조사 재시도')).toBe(false);
    await wrapper.setProps({ me: supervisor }); expect(wrapper.findAll('button').some(b => b.text() === 'AI 조사 재시도')).toBe(true);
  });
  it('retains review_required and BLOCKED independently of a succeeded run', async () => {
    const wrapper = await render(detail({ review_required: true, review_reason: '승인 반려 사유', analysis: { ...detail().analysis!, decision: 'BLOCKED' } })); expect(wrapper.text()).toContain('후속 검토 필요'); expect(wrapper.text()).toContain('승인 반려 사유'); expect(wrapper.text()).toContain('조사 보류'); expect(wrapper.text()).toContain('AI 실행 완료');
  });
  it.each(['OPEN','ACTION_REQUIRED','IN_PROGRESS','PENDING_VERIFICATION','RESOLVED'])('shows authoritative %s separately from AI success', async status => {
    const wrapper = await render(detail({ status })); expect(wrapper.find('.state-stack').text()).toContain('사건 ·'); expect(wrapper.find('.state-stack').text()).toContain('AI 실행 완료');
  });
  it('does not render expanded diagnostics for non-owner even if response is malformed', async () => {
    const wrapper = await render(detail(), reporter, { ...job, run_summary: { selected_draft_id: 'private-summary-only' } }); expect(wrapper.text()).not.toContain('private-summary-only');
  });
  it('opens evidence using server evidence ID and displays immutable provenance', async () => {
    const wrapper = await render(); vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ ...detail().evidence[0], source_location: 'chapter1', equipment_id: 'eq-1', captured_at: '2026-10-09T02:01:00Z' }))); await wrapper.find('.plain-list button').trigger('click'); await flushPromises(); expect(wrapper.find('.evidence-detail').text()).toContain('chapter1'); expect(wrapper.find('.evidence-detail').text()).toContain('초기 점검 완료.');
  });
});
