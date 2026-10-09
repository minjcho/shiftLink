<script setup lang="ts">
import type { IncidentDetail, SessionView } from '../core/contracts'
defineProps<{id:string; detail?:IncidentDetail; session?:SessionView; refresh?:()=>Promise<void>}>()
</script>
<template><section class="panel"><h1>사건 상세</h1><p class="muted">사건 {{ id }}</p>
  <slot name="summary" :detail="detail"><p v-if="!detail">사건 조회 기능을 준비 중입니다.</p></slot>
  <section aria-label="원문·질문"><slot name="intake" :detail="detail" :session="session" :refresh="refresh" /></section>
  <section aria-label="작업 승인·수행"><slot name="actions" :detail="detail" :session="session" :refresh="refresh" /></section>
  <section aria-label="최종 검증"><slot name="resolution" :detail="detail" :session="session" :refresh="refresh" /></section>
  <section aria-label="근거·이력"><slot name="history" :detail="detail" /></section>
</section></template>
