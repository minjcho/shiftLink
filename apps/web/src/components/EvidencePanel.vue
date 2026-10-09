<script setup lang="ts">
import { ref } from 'vue';
import { api, errorMessage } from '../lib/api';
import type { Evidence } from '../lib/types';
import { time } from '../lib/presentation';
defineProps<{ evidence: Evidence[] }>();
const selected = ref<Evidence | null>(null);
const error = ref('');
const loading = ref(false);
let generation = 0;
async function open(id: string) {
  const current = ++generation;
  loading.value = true; error.value = ''; selected.value = null;
  try { const { data } = await api.request<Evidence>(`/evidence/${encodeURIComponent(id)}`); if (current === generation) selected.value = data; }
  catch (e) { if (current === generation) error.value = errorMessage(e); }
  finally { if (current === generation) loading.value = false; }
}
</script>
<template>
  <section class="panel" aria-labelledby="evidence-heading">
    <h2 id="evidence-heading">근거 원문</h2>
    <p class="muted">합성 로그·절차·과거 사례입니다. 과거 사례는 현재 설비의 측정 결과가 아닙니다.</p>
    <p v-if="!evidence.length">저장된 근거가 없습니다.</p>
    <ul class="plain-list"><li v-for="item in evidence" :key="item.id"><button type="button" class="link-button" @click="open(item.id)">{{ item.source_type }} · {{ item.id }}</button><p>{{ item.excerpt }}</p></li></ul>
    <p v-if="loading" role="status">근거 조회 중…</p><p v-if="error" role="alert" class="notice error">{{ error }}</p>
    <div v-if="selected" class="evidence-detail" tabindex="0" aria-label="선택한 근거 원문">
      <h3>{{ selected.source_type }} · 출처 {{ selected.source_id }}</h3>
      <dl><dt>근거 ID</dt><dd>{{ selected.id }}</dd><dt>버전 / 위치</dt><dd>{{ selected.source_version }} / {{ selected.source_location ?? '미수집' }}</dd><dt>설비</dt><dd>{{ selected.equipment_id ?? '공통 적용 자료' }}</dd><dt>적용 범위</dt><dd>{{ selected.applicability ?? '미수집' }}</dd><dt>관측 / 조회 시각</dt><dd>{{ time(selected.observed_at) }} / {{ time(selected.captured_at) }}</dd></dl>
      <blockquote>{{ selected.excerpt }}</blockquote>
    </div>
  </section>
</template>
