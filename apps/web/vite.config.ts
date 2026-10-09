import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import { normalizeApiBasePath } from './src/lib/api-base';
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  const base = normalizeApiBasePath(process.env.VITE_API_BASE_URL ?? env.VITE_API_BASE_URL);
  const escapedBase = base.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return {
    plugins: [vue()],
    server: { port: 5173, proxy: { [`^${escapedBase}(?:/|\\?|$)`]: {
      target: process.env.SHIFTLINK_API_PROXY ?? 'http://127.0.0.1:8000',
      rewrite: path => `/api/v1${path.slice(base.length)}`,
    } } },
  };
});
