import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils';
import IncidentList from '../src/features/intake/IncidentList.vue';
import { api } from '../src/lib/api';
import { detail, equipment, response } from './fixtures';

const polling = vi.hoisted(() => ({ refresh: undefined as undefined | (() => Promise<unknown>) }));
vi.mock('../src/lib/polling', () => ({ usePolling: (refresh: () => Promise<unknown>) => { polling.refresh = refresh; } }));

let wrapper: VueWrapper | undefined;
afterEach(() => { wrapper?.unmount(); wrapper = undefined; vi.unstubAllGlobals(); });
const incident = (id: string) => detail({ id, display_id: id });
const page = (ids: string[], next: string | null = null) => response({ items: ids.map(incident), next_cursor: next });
const render = async () => { wrapper = mount(IncidentList, { props: { equipment } }); await flushPromises(); return wrapper; };
const cards = () => wrapper!.findAll('.incident-list .identifier').map(card => card.text());
const loadMore = () => wrapper!.findAll('button').find(button => button.text() === '다음 사건 보기')!;
const query = (url: string) => new URL(url, 'http://localhost').searchParams;
const deferred = () => {
  let resolve!: (value: Response) => void;
  const promise = new Promise<Response>(done => { resolve = done; });
  return { promise, resolve };
};

describe('incident list polling with cursor pages', () => {
  it('refreshes the loaded window in current server order using fresh cursors', async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(page(['A', 'B'], 'old-page-2'))
      .mockResolvedValueOnce(page(['C', 'D'], 'old-page-3'))
      .mockResolvedValueOnce(page(['D', 'A'], 'new-page-2'))
      .mockResolvedValueOnce(page(['B', 'C'], 'new-page-3'))
      .mockResolvedValueOnce(page(['E']));
    vi.stubGlobal('fetch', fetcher);
    await render(); await loadMore().trigger('click'); await flushPromises();
    expect(cards()).toEqual(['A', 'B', 'C', 'D']);
    await polling.refresh!(); await flushPromises();
    expect(cards()).toEqual(['D', 'A', 'B', 'C']);
    expect(fetcher.mock.calls.map(([url]) => query(url).get('cursor'))).toEqual([null, 'old-page-2', null, 'new-page-2']);
    await loadMore().trigger('click'); await flushPromises();
    expect(query(fetcher.mock.calls[4][0]).get('cursor')).toBe('new-page-3');
    expect(cards()).toEqual(['D', 'A', 'B', 'C', 'E']);
  });

  it('keeps the entire prior window, cursor and freshness when a later refresh page fails', async () => {
    const secondRefreshPage = deferred();
    const fetcher = vi.fn()
      .mockResolvedValueOnce(page(['A'], 'old-page-2'))
      .mockResolvedValueOnce(page(['B'], 'old-page-3'))
      .mockResolvedValueOnce(page(['NEW'], 'new-page-2'))
      .mockReturnValueOnce(secondRefreshPage.promise)
      .mockResolvedValueOnce(page(['C']));
    vi.stubGlobal('fetch', fetcher);
    await render(); await loadMore().trigger('click'); await flushPromises();
    const freshness = wrapper!.find('.freshness').text();
    const refreshing = polling.refresh!(); await flushPromises();
    expect(cards()).toEqual(['A', 'B']);
    secondRefreshPage.resolve(new Response(JSON.stringify({ error: { code: 'SERVICE_UNAVAILABLE', message: '읽기 실패' } }), { status: 503 }));
    await refreshing; await flushPromises();
    expect(cards()).toEqual(['A', 'B']);
    expect(wrapper!.text()).toContain('이전 조회 내용을 표시');
    expect(wrapper!.find('.freshness').text()).toBe(freshness);
    await loadMore().trigger('click'); await flushPromises();
    expect(query(fetcher.mock.calls[4][0]).get('cursor')).toBe('old-page-3');
    expect(cards()).toEqual(['A', 'B', 'C']);
  });

  it('does not let polling and manual pagination discard or duplicate each other', async () => {
    const nextPage = deferred(); const firstRefreshPage = deferred();
    const fetcher = vi.fn()
      .mockResolvedValueOnce(page(['A'], 'old-page-2'))
      .mockReturnValueOnce(nextPage.promise)
      .mockReturnValueOnce(firstRefreshPage.promise)
      .mockResolvedValueOnce(page(['A'], 'new-page-3'));
    vi.stubGlobal('fetch', fetcher);
    await render(); await loadMore().trigger('click'); await loadMore().trigger('click');
    await polling.refresh!(); await flushPromises();
    expect(fetcher).toHaveBeenCalledTimes(2);
    nextPage.resolve(page(['B'], 'old-page-3')); await flushPromises();
    expect(cards()).toEqual(['A', 'B']);
    const refreshing = polling.refresh!(); await flushPromises();
    expect(loadMore().attributes('disabled')).toBeDefined();
    await loadMore().trigger('click'); await flushPromises();
    expect(fetcher).toHaveBeenCalledTimes(3);
    firstRefreshPage.resolve(page(['B'], 'new-page-2')); await refreshing; await flushPromises();
    expect(cards()).toEqual(['B', 'A']);
    expect(fetcher).toHaveBeenCalledTimes(4);
  });

  it('discards an obsolete multi-page refresh when filters change and resets the window', async () => {
    const stalePage = deferred();
    const fetcher = vi.fn()
      .mockResolvedValueOnce(page(['A'], 'old-page-2'))
      .mockResolvedValueOnce(page(['B'], 'old-page-3'))
      .mockResolvedValueOnce(page(['NEW'], 'new-page-2'))
      .mockReturnValueOnce(stalePage.promise)
      .mockResolvedValueOnce(page(['MINE'], 'mine-page-2'))
      .mockResolvedValueOnce(page(['MINE-UPDATED'], 'mine-page-2'));
    vi.stubGlobal('fetch', fetcher);
    await render(); await loadMore().trigger('click'); await flushPromises();
    const refreshing = polling.refresh!(); await flushPromises();
    await wrapper!.find('#scope-filter').setValue('mine'); await flushPromises();
    expect(cards()).toEqual(['MINE']);
    expect(query(fetcher.mock.calls[4][0]).get('scope')).toBe('mine');
    stalePage.resolve(page(['STALE'])); await refreshing; await flushPromises();
    expect(cards()).toEqual(['MINE']);
    await polling.refresh!(); await flushPromises();
    expect(cards()).toEqual(['MINE-UPDATED']);
    expect(fetcher).toHaveBeenCalledTimes(6);
    expect(query(fetcher.mock.calls[5][0]).get('cursor')).toBeNull();
  });

  it('never publishes a partial window or continues it after session invalidation', async () => {
    const stalePage = deferred();
    const fetcher = vi.fn()
      .mockResolvedValueOnce(page(['A'], 'old-page-2'))
      .mockResolvedValueOnce(page(['B'], 'old-page-3'))
      .mockResolvedValueOnce(page(['NEW'], 'new-page-2'))
      .mockReturnValueOnce(stalePage.promise);
    vi.stubGlobal('fetch', fetcher);
    await render(); await loadMore().trigger('click'); await flushPromises();
    const refreshing = polling.refresh!(); await flushPromises();
    api.invalidateSession(); stalePage.resolve(page(['STALE'], 'new-page-3'));
    await refreshing; await flushPromises();
    expect(cards()).toEqual(['A', 'B']);
    expect(fetcher).toHaveBeenCalledTimes(4);
    expect(wrapper!.find('[role="alert"]').exists()).toBe(false);
  });
});
