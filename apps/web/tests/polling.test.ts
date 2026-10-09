import { afterEach, expect, it, vi } from 'vitest';
import { startVisiblePolling } from '../src/lib/polling';
afterEach(() => vi.useRealTimers());
it('AC31 stops in hidden tabs, resumes once and cleans up after unmount', async () => {
  vi.useFakeTimers(); const events = new EventTarget(); const doc = { hidden: false, addEventListener: events.addEventListener.bind(events), removeEventListener: events.removeEventListener.bind(events) }; const read = vi.fn().mockResolvedValue(null);
  const stop = startVisiblePolling(read, 2000, doc); await vi.advanceTimersByTimeAsync(2000); expect(read).toHaveBeenCalledTimes(1);
  doc.hidden = true; events.dispatchEvent(new Event('visibilitychange')); await vi.advanceTimersByTimeAsync(10000); expect(read).toHaveBeenCalledTimes(1);
  doc.hidden = false; events.dispatchEvent(new Event('visibilitychange')); await vi.advanceTimersByTimeAsync(1); expect(read).toHaveBeenCalledTimes(2); stop(); await vi.advanceTimersByTimeAsync(10000); expect(read).toHaveBeenCalledTimes(2);
});
it('AC31 never overlaps refresh calls on rapid visibility changes', async () => {
  vi.useFakeTimers(); const events = new EventTarget(); const doc = { hidden: false, addEventListener: events.addEventListener.bind(events), removeEventListener: events.removeEventListener.bind(events) }; let resolve!: () => void; const read = vi.fn().mockReturnValue(new Promise<void>(r => resolve = r)); const stop = startVisiblePolling(read, 100, doc); await vi.advanceTimersByTimeAsync(100); doc.hidden = true; events.dispatchEvent(new Event('visibilitychange')); doc.hidden = false; events.dispatchEvent(new Event('visibilitychange')); expect(read).toHaveBeenCalledTimes(1); resolve(); await vi.advanceTimersByTimeAsync(1); stop();
});
