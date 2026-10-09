<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { session } from './core/session'
const { user, busy, error, revision } = session
const accounts = [ ['reporter', '작업자'], ['maintainer', '정비 담당자'], ['outgoing_supervisor', '출발 책임자'], ['incoming_supervisor', '수신 책임자'] ]
onMounted(() => session.load())
function change(event: Event) { const key = (event.target as HTMLSelectElement).value; if (key) void session.load(key) }
</script>
<template>
  <header class="topbar"><RouterLink to="/incidents" class="brand">ShiftLink</RouterLink><span class="tag">합성 데모 자료</span></header>
  <main>
    <section class="session-bar" aria-label="현재 계정" :aria-busy="busy">
      <div><strong>{{ user?.display_name ?? '계정을 선택해 주세요' }}</strong><p>{{ user?.site_name ?? '업무를 시작하려면 계정을 선택하세요.' }}</p></div>
      <label>데모 계정 <select :disabled="busy" @change="change"><option value="">선택</option><option v-for="[key,label] in accounts" :key="key" :value="key">{{ label }}</option></select></label>
    </section>
    <p v-if="error" role="alert">{{ error }} <button :disabled="busy" @click="session.load()">다시 확인</button></p>
    <template v-if="user"><nav><RouterLink to="/incidents">제보·미해결 사건</RouterLink><RouterLink to="/handovers">교대 인수</RouterLink></nav>
      <RouterView :key="`${user.user_id}:${revision}`" />
    </template>
    <p v-else-if="busy" role="status">세션을 확인하고 있습니다.</p>
  </main>
</template>
