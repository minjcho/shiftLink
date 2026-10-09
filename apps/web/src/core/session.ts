import { readonly, ref } from 'vue'
import { api, ApiError } from './api'
import type { SessionView } from './contracts'
export function createSessionStore(client = api) {
  const user = ref<SessionView | null>(null)
  const busy = ref(false)
  const error = ref('')
  const revision = ref(0)
  async function load(accountKey?: string) {
    const current = ++revision.value
    // Unmount previous actor's panels before the server changes the cookie.
    user.value = null; busy.value = true; error.value = ''
    try {
      const value = accountKey ? await client.switchSession<SessionView>(accountKey) : await client.get<SessionView>('/me')
      if (current === revision.value) user.value = value
    } catch (failure) {
      if (current === revision.value) error.value = failure instanceof ApiError ? failure.message : '세션을 확인하지 못했습니다.'
    } finally { if (current === revision.value) busy.value = false }
  }
  return { user: readonly(user), busy: readonly(busy), error: readonly(error), revision: readonly(revision), load }
}
export const session = createSessionStore()
