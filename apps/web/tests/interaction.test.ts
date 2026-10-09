import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils';
import IncidentList from '../src/features/intake/IncidentList.vue';
import IncidentDetail from '../src/features/intake/IncidentDetail.vue';
import App from '../src/App.vue';
import CommandFeedback from '../src/components/CommandFeedback.vue';
import { detail, equipment, job, maintainer, reporter, response, failure } from './fixtures';
const wrappers: VueWrapper[] = [];
afterEach(() => { wrappers.forEach(w => w.unmount()); wrappers.length = 0; vi.unstubAllGlobals(); });
const listRender = async () => { const w = mount(IncidentList, { props: { equipment } }); wrappers.push(w); await flushPromises(); return w; };
const detailRender = async () => { const w = mount(IncidentDetail, { props: { id: 'incident-1', me: maintainer, equipment } }); wrappers.push(w); await flushPromises(); return w; };
const reviewScenes = [
  { name: 'intake', render: listRender, input: '#intake-text', form: '.intake-form form', feedback: 'intake-error' },
  { name: 'reply', render: detailRender, input: '#reply-request-1', form: '.question-card form', feedback: 'reply-error-request-1' },
];
const getData = (url: string) => url.includes('/jobs/') ? job : url.includes('/incidents?') ? { items: [], next_cursor: null } : detail();
describe('AC31 inputs and observed-read state', () => {
  for (const scene of reviewScenes) {
    it.each([false, true])(`${scene.name} preserves an uncertain command across manual reads and review events (read failure: %s)`, async readFails => {
      let uncertainWrite = false;
      const fetcher = vi.fn().mockImplementation((url: string, init: RequestInit) => {
        if (init.method === 'POST') {
          uncertainWrite = true;
          return Promise.reject(new TypeError('response lost'));
        }
        return uncertainWrite && readFails ? Promise.reject(new TypeError('read failed')) : Promise.resolve(response(getData(url)));
      });
      vi.stubGlobal('fetch', fetcher);
      const wrapper = await scene.render();
      await wrapper.find(scene.input).setValue('불확실한 원문 유지');
      await wrapper.find(scene.form).trigger('submit'); await flushPromises();
      const feedback = wrapper.findAllComponents(CommandFeedback).find(c => c.props('errorId') === scene.feedback)!;
      const command = feedback.props('command');
      await wrapper.findAll('button').find(b => b.text() === '새로고침')!.trigger('click'); await flushPromises();
      // A stale component event must be safe independently of whether its button is visible.
      feedback.vm.$emit('review'); await flushPromises();
      expect(command.hasPending).toBe(true);
      expect(command.canRetry).toBe(true);
      expect(feedback.findAll('button').some(b => b.text() === '최신 내용 조회 · 새 요청 준비')).toBe(false);
      expect((wrapper.find(scene.input).element as HTMLTextAreaElement).value).toBe('불확실한 원문 유지');
      expect(wrapper.find(scene.input).attributes()).toHaveProperty('disabled');
      const posts = () => fetcher.mock.calls.filter(call => call[1].method === 'POST');
      expect(posts()).toHaveLength(1);
      await feedback.findAll('button').find(b => b.text() === '같은 요청 결과 확인')!.trigger('click'); await flushPromises();
      expect(posts()).toHaveLength(2);
      expect(posts()[1][1].body).toBe(posts()[0][1].body);
      expect(posts()[1][1].headers['Idempotency-Key']).toBe(posts()[0][1].headers['Idempotency-Key']);
    });
    it(`${scene.name} retains a known rejected request until a current successful review read`, async () => {
      let readFails = false;
      const fetcher = vi.fn().mockImplementation((url: string, init: RequestInit) => init.method === 'POST'
        ? Promise.resolve(failure('VERSION_CONFLICT'))
        : readFails ? Promise.reject(new TypeError('read failed')) : Promise.resolve(response(getData(url))));
      vi.stubGlobal('fetch', fetcher);
      const wrapper = await scene.render();
      await wrapper.find(scene.input).setValue('거부된 원문 유지'); await wrapper.find(scene.form).trigger('submit'); await flushPromises();
      const feedback = wrapper.findAllComponents(CommandFeedback).find(c => c.props('errorId') === scene.feedback)!;
      const command = feedback.props('command');
      readFails = true; feedback.vm.$emit('review'); await flushPromises();
      expect(command.hasPending).toBe(true);
      expect(fetcher.mock.calls.filter(c => c[1].method === 'POST')).toHaveLength(1);
      readFails = false; feedback.vm.$emit('review'); await flushPromises();
      expect(command.hasPending).toBe(false);
      expect((wrapper.find(scene.input).element as HTMLTextAreaElement).value).toBe('거부된 원문 유지');
      await wrapper.find(scene.form).trigger('submit'); await flushPromises();
      const posts = fetcher.mock.calls.filter(call => call[1].method === 'POST');
      expect(posts).toHaveLength(2);
      expect(posts[1][1].headers['Idempotency-Key']).not.toBe(posts[0][1].headers['Idempotency-Key']);
    });
    it(`${scene.name} does not reset from a superseded successful read while a newer review is pending`, async () => {
      const pending: Array<(value: Response) => void> = [];
      let holdReads = false;
      const fetcher = vi.fn().mockImplementation((url: string, init: RequestInit) => {
        if (init.method === 'POST') return Promise.resolve(failure('VERSION_CONFLICT'));
        if (holdReads && !url.includes('/jobs/')) return new Promise<Response>(resolve => pending.push(resolve));
        return Promise.resolve(response(getData(url)));
      });
      vi.stubGlobal('fetch', fetcher);
      const wrapper = await scene.render();
      await wrapper.find(scene.input).setValue('두 조회 중 원문 유지'); await wrapper.find(scene.form).trigger('submit'); await flushPromises();
      const feedback = wrapper.findAllComponents(CommandFeedback).find(c => c.props('errorId') === scene.feedback)!;
      const command = feedback.props('command');
      holdReads = true;
      feedback.vm.$emit('review'); feedback.vm.$emit('review'); await flushPromises();
      expect(pending).toHaveLength(2);
      pending[0](response(scene.name === 'intake' ? { items: [], next_cursor: null } : detail({ version: 4 })));
      await flushPromises();
      expect(command.hasPending).toBe(true);
      pending[1](failure('SERVICE_UNAVAILABLE', 503)); await flushPromises();
      expect(command.hasPending).toBe(true);
      expect(fetcher.mock.calls.filter(c => c[1].method === 'POST')).toHaveLength(1);
    });
  }
  it('keeps a rejected detail command when the required Job refresh fails after the Incident read succeeds', async () => {
    let jobFails = false;
    const fetcher = vi.fn().mockImplementation((url: string, init: RequestInit) => {
      if (init.method === 'POST') return Promise.resolve(failure('VERSION_CONFLICT'));
      if (jobFails && url.includes('/jobs/')) return Promise.reject(new TypeError('job read failed'));
      return Promise.resolve(response(getData(url)));
    });
    vi.stubGlobal('fetch', fetcher);
    const wrapper = await detailRender();
    await wrapper.find('#reply-request-1').setValue('질문 답변 보존');
    await wrapper.find('.question-card form').trigger('submit'); await flushPromises();
    const feedback = wrapper.findAllComponents(CommandFeedback).find(c => c.props('errorId') === 'reply-error-request-1')!;
    jobFails = true; feedback.vm.$emit('review'); await flushPromises();
    expect(feedback.props('command').hasPending).toBe(true);
    expect(wrapper.text()).toContain('Job 조회 실패');
    jobFails = false; feedback.vm.$emit('review'); await flushPromises();
    expect(feedback.props('command').hasPending).toBe(false);
    expect(fetcher.mock.calls.filter(c => c[1].method === 'POST')).toHaveLength(1);
  });
  it('retains intake text across network uncertainty and retries original request manually', async () => {
    const fetcher = vi.fn().mockImplementation((url: string, init: RequestInit) => init.method === 'POST' ? Promise.reject(new TypeError('offline')) : Promise.resolve(response({ items: [], next_cursor: null }))); vi.stubGlobal('fetch', fetcher); const wrapper = await listRender(); await wrapper.find('#intake-text').setValue('원문은 잃지 않는다'); await wrapper.find('form').trigger('submit'); await flushPromises(); expect((wrapper.find('#intake-text').element as HTMLTextAreaElement).value).toBe('원문은 잃지 않는다'); expect(wrapper.text()).toContain('같은 요청 결과 확인'); expect(wrapper.find('#intake-text').attributes('aria-describedby')).toBe('intake-error'); expect(wrapper.emitted('open')).toBeUndefined();
    const posts = () => fetcher.mock.calls.filter(c => c[1].method === 'POST'); expect(posts()).toHaveLength(1); const button = wrapper.findAll('button').find(b => b.text() === '같은 요청 결과 확인')!; await button.trigger('click'); await flushPromises(); expect(posts()).toHaveLength(2); expect(posts()[0][1].body).toBe(posts()[1][1].body); expect(posts()[0][1].headers['Idempotency-Key']).toBe(posts()[1][1].headers['Idempotency-Key']);
  });
  it('only moves to actual returned Incident ID after 202 persisted intake', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((_url: string, init: RequestInit) => Promise.resolve(init.method === 'POST' ? response({ incident_id: 'actual-id', display_id: 'INC-REAL' }, 202) : response({ items: [], next_cursor: null })))); const wrapper = await listRender(); await wrapper.find('#intake-text').setValue('실제 응답 확인'); await wrapper.find('form').trigger('submit'); await flushPromises(); expect(wrapper.emitted('open')?.[0][0]).toBe('actual-id'); expect((wrapper.find('#intake-text').element as HTMLTextAreaElement).value).toBe('');
  });
  it('does not claim empty results when first read fails, keeps cache on later failure', async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError('offline')); vi.stubGlobal('fetch', fetcher); const wrapper = await listRender(); expect(wrapper.text()).not.toContain('해당하는 사건이 없습니다'); expect(wrapper.text()).toContain('아직 목록을 확인하지 못했습니다'); fetcher.mockImplementation(() => Promise.resolve(response({ items: [detail()], next_cursor: null }))); await wrapper.findAll('button').find(b => b.text() === '새로고침')!.trigger('click'); await flushPromises(); expect(wrapper.text()).toContain('INC-001'); fetcher.mockRejectedValue(new TypeError('offline')); await wrapper.findAll('button').find(b => b.text() === '새로고침')!.trigger('click'); await flushPromises(); expect(wrapper.text()).toContain('INC-001'); expect(wrapper.text()).toContain('이전 조회 내용을 표시');
  });
  it('keeps reply draft on 409, refreshes without resubmission, then uses a new key after explicit review', async () => {
    let version = 3; let conflict = true; const fetcher = vi.fn().mockImplementation((url: string, init: RequestInit) => Promise.resolve(init.method === 'POST' ? conflict ? failure('VERSION_CONFLICT') : response({ message_id: 'reply-id', incident_id: 'incident-1', incident_version: 5, job_id: 'job-2' }, 202) : response(url.includes('/jobs/') ? job : detail({ version })))); vi.stubGlobal('fetch', fetcher); const wrapper = mount(IncidentDetail, { props: { id: 'incident-1', me: maintainer, equipment } }); wrappers.push(wrapper); await flushPromises(); await wrapper.find('#reply-request-1').setValue('답변 보존'); await wrapper.find('.question-card form').trigger('submit'); await flushPromises(); expect((wrapper.find('#reply-request-1').element as HTMLTextAreaElement).value).toBe('답변 보존'); const posts = () => fetcher.mock.calls.filter(c => c[1].method === 'POST'); expect(posts()).toHaveLength(1); version = 4; await wrapper.findAll('button').find(b => b.text() === '최신 내용 조회 · 새 요청 준비')!.trigger('click'); await flushPromises(); expect(posts()).toHaveLength(1); conflict = false; await wrapper.find('.question-card form').trigger('submit'); await flushPromises(); expect(posts()).toHaveLength(2); expect(JSON.parse(posts()[1][1].body).expected_version).toBe(4); expect(posts()[0][1].headers['Idempotency-Key']).not.toBe(posts()[1][1].headers['Idempotency-Key']);
  });
  it('polling/manual refresh never overwrites in-progress additional text or answers', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => Promise.resolve(response(url.includes('/jobs/') ? job : detail())))); const wrapper = mount(IncidentDetail, { props: { id: 'incident-1', me: maintainer, equipment } }); wrappers.push(wrapper); await flushPromises(); await wrapper.find('#note-text').setValue('새 원문'); await wrapper.find('#reply-request-1').setValue('작성 중 답변'); await wrapper.findAll('button').find(b => b.text() === '새로고침')!.trigger('click'); await flushPromises(); expect((wrapper.find('#note-text').element as HTMLTextAreaElement).value).toBe('새 원문'); expect((wrapper.find('#reply-request-1').element as HTMLTextAreaElement).value).toBe('작성 중 답변');
  });
  it('session switch explicitly clears old pending write and never replays it', async () => {
    let currentMe = reporter; const fetcher = vi.fn().mockImplementation((url: string, init: RequestInit) => {
      if (url.endsWith('/demo/session')) { currentMe = maintainer; return Promise.resolve(response(currentMe)); }
      if (url.endsWith('/incidents') && init.method === 'POST') return Promise.reject(new TypeError('offline'));
      return Promise.resolve(response(url.endsWith('/me') ? currentMe : url.endsWith('/equipment') ? { items: equipment } : { items: [], next_cursor: null }));
    }); vi.stubGlobal('fetch', fetcher); vi.stubGlobal('scrollTo', vi.fn()); history.replaceState({}, '', '/incidents'); const wrapper = mount(App); wrappers.push(wrapper); await flushPromises(); await wrapper.find('#intake-text').setValue('이전 계정 원문'); await wrapper.find('.intake-form form').trigger('submit'); await flushPromises(); await wrapper.find('#account').setValue('maintainer'); await wrapper.find('.session-area form').trigger('submit'); await flushPromises(); expect(wrapper.text()).toContain('이전 계정의 재전송 대기를 정리'); expect((wrapper.find('#intake-text').element as HTMLTextAreaElement).value).toBe(''); expect(fetcher.mock.calls.filter(c => c[0].endsWith('/incidents') && c[1].method === 'POST')).toHaveLength(1); expect(wrapper.text()).not.toContain('같은 요청 결과 확인');
  });
});

describe('F0 session concurrency', () => {
  it('allows only one session POST until cookie and visible identity are refreshed', async () => {
    let finishSwitch!: (value: Response) => void;
    let currentMe = reporter;
    const fetcher = vi.fn().mockImplementation((url: string) => {
      if (url.endsWith('/demo/session')) return new Promise(resolve => { finishSwitch = resolve; });
      return Promise.resolve(response(url.endsWith('/me') ? currentMe : url.endsWith('/equipment') ? { items: equipment } : { items: [], next_cursor: null }));
    });
    vi.stubGlobal('fetch', fetcher);
    history.replaceState({}, '', '/incidents');
    const wrapper = mount(App); wrappers.push(wrapper); await flushPromises();
    await wrapper.find('#account').setValue('maintainer');
    await wrapper.find('.session-area form').trigger('submit');
    await wrapper.find('.session-area form').trigger('submit');
    expect(fetcher.mock.calls.filter(c => c[0].endsWith('/demo/session'))).toHaveLength(1);
    expect(wrapper.find('#account').attributes('disabled')).toBeDefined();
    expect(wrapper.find('.session-identity').exists()).toBe(false);
    currentMe = maintainer; finishSwitch(response(maintainer)); await flushPromises();
    expect(wrapper.find('.session-identity').text()).toContain('정비 담당자');
    expect(wrapper.find('#account').attributes('disabled')).toBeUndefined();
  });
});

describe('F0 feature panel boundary', () => {
  it('shares the authoritative detail and refresh with a feature slot', async () => {
    const { h } = await import('vue');
    let current = detail();
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => Promise.resolve(response(url.includes('/jobs/') ? job : current))));
    const wrapper = mount(IncidentDetail, {
      props: { id: current.id, me: reporter, equipment },
      slots: { actions: ({ detail: value, session, refresh }: { detail: ReturnType<typeof detail>; session: typeof reporter; refresh: () => Promise<void> }) => h('button', { id: 'feature-refresh', onClick: refresh }, `${value.version}:${session.user_id}`) },
    });
    wrappers.push(wrapper); await flushPromises();
    expect(wrapper.find('#feature-refresh').text()).toBe(`3:${reporter.user_id}`);
    current = detail({ version: 4 });
    await wrapper.find('#feature-refresh').trigger('click'); await flushPromises();
    expect(wrapper.find('#feature-refresh').text()).toBe(`4:${reporter.user_id}`);
    expect(wrapper.find('.detail-meta').text()).toContain('업무 버전 4');
  });
});
