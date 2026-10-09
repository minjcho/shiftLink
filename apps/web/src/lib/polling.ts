import { onMounted, onUnmounted } from 'vue';
/** Hidden documents produce no new polling requests. Resume uses a fresh read. */
export function startVisiblePolling(refresh: () => Promise<unknown>, interval: number, doc: Pick<Document, 'hidden' | 'addEventListener' | 'removeEventListener'> = document) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let stopped = false;
  let running = false;
  const schedule = () => { clearTimeout(timer); if (!stopped && !doc.hidden) timer = setTimeout(tick, interval); };
  const tick = async () => { if (stopped || doc.hidden || running) return; running = true; try { await refresh(); } finally { running = false; schedule(); } };
  const change = () => { clearTimeout(timer); if (!doc.hidden && !stopped) void tick(); };
  doc.addEventListener('visibilitychange', change);
  schedule();
  return () => { stopped = true; clearTimeout(timer); doc.removeEventListener('visibilitychange', change); };
}
export function usePolling(refresh: () => Promise<unknown>) {
  let stop: (() => void) | undefined;
  onMounted(() => { stop = startVisiblePolling(refresh, Math.max(500, Number(import.meta.env.VITE_POLL_INTERVAL_MS) || 2000)); });
  onUnmounted(() => stop?.());
}
