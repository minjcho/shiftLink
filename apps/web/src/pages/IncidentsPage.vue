<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { api } from '../core/api'
const equipment = ref<{id:string;code:string;label:string}[]>([])
const shifts = ref<{id:string;label:string}[]>([])
const state = ref<'loading'|'ready'|'error'>('loading')
const lastSuccess = ref('')
let active = true
onUnmounted(() => { active = false })
async function refresh() {
  state.value = 'loading'
  try {
    const [e,s] = await Promise.all([api.get<{items:typeof equipment.value}>('/equipment'), api.get<{items:typeof shifts.value}>('/shifts')])
    if (!active) return
    equipment.value = e.items; shifts.value = s.items; state.value = 'ready'; lastSuccess.value = new Date().toLocaleTimeString('ko-KR')
  } catch { if (active) state.value = 'error' }
}
onMounted(refresh)
</script>
<template><section class="panel"><h1>제보·미해결 사건</h1>
  <p v-if="state === 'loading'" role="status">기본 정보를 불러오고 있습니다.</p>
  <p v-if="state === 'error'" role="alert">최신 정보를 불러오지 못했습니다. <button @click="refresh">다시 불러오기</button></p>
  <p v-if="lastSuccess" class="muted">마지막 성공 조회 {{ lastSuccess }} <span v-if="state === 'error'">· 이전 조회 내용</span></p>
  <h2>등록 설비</h2><ul><li v-for="item in equipment" :key="item.id">{{ item.code }} · {{ item.label }}</li></ul>
  <p v-if="state === 'ready' && !equipment.length">등록된 설비가 없습니다.</p>
  <h2>등록 교대</h2><ul><li v-for="item in shifts" :key="item.id">{{ item.label }}</li></ul>
  <slot name="intake"><p class="notice">제보 접수와 사건 목록 기능을 준비 중입니다.</p></slot>
</section></template>
