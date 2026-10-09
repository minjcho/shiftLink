<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue';
import { api, Command, errorMessage, SessionChanged } from '../../lib/api';
import type { Me } from '../../lib/types';
import { time } from '../../lib/presentation';
import CommandFeedback from '../../components/CommandFeedback.vue';
import type { Handover, ShiftList, ShiftPair } from './types';

const props = defineProps<{ me: Me }>();
const emit = defineEmits<{ created: [id: string] }>();
const shifts = ref<ShiftList | null>(null);
const selected = ref('');
const readError = ref('');
const loading = ref(false);
const command = reactive(new Command());
let alive = true;
let sequence = 0;
const pairs = computed(() => shifts.value?.allowed_pairs.filter(pair => shifts.value?.items.find(shift => shift.id === pair.from_shift_occurrence_id)?.supervisor_id === props.me.user_id) ?? []);
function pairKey(pair: ShiftPair) { return `${pair.from_shift_occurrence_id}/${pair.to_shift_occurrence_id}`; }
function shiftName(id: string) {
  const shift = shifts.value?.items.find(value => value.id === id);
  return shift ? `${shift.label ?? shift.id} · ${time(shift.starts_at)}` : id;
}
async function refresh() {
  const current = ++sequence;
  loading.value = true;
  try {
    const result = await api.request<ShiftList>('/shifts');
    if (!alive || current !== sequence) return;
    shifts.value = result.data; readError.value = '';
    if (!pairs.value.some(pair => pairKey(pair) === selected.value)) selected.value = '';
  } catch (error) { if (alive && current === sequence && !(error instanceof SessionChanged)) readError.value = errorMessage(error); }
  finally { if (alive && current === sequence) loading.value = false; }
}
async function create(retry = false) {
  const pair = pairs.value.find(value => pairKey(value) === selected.value);
  if (!retry && (readError.value || loading.value || !pair)) return;
  try {
    const result = retry ? await command.send<Handover>(api) : await command.send<Handover>(api, '/handovers', pair);
    const id = result?.handover_id ?? result?.id;
    if (alive && id) emit('created', id);
  } catch { /* Command preserves the exact request and key for an explicit retry. */ }
}
async function review() { await refresh(); if (alive && !readError.value) command.reset(); }
onMounted(() => { if (props.me.role === 'supervisor') void refresh(); });
onUnmounted(() => { alive = false; sequence += 1; });
</script>

<template>
  <section v-if="me.role === 'supervisor'" class="panel" aria-labelledby="handover-create-heading">
    <span class="section-number">교대 책임 이전</span>
    <h2 id="handover-create-heading">미해결 사건 인계</h2>
    <p>서버가 지정한 다음 교대로 질문·작업·검증 대기 사건을 전달합니다. 사건별 인수는 수신 책임자가 확인합니다.</p>
    <p v-if="loading" role="status">허용된 교대를 조회하고 있습니다…</p>
    <p v-if="readError" id="handover-shifts-error" role="alert" class="notice error">{{ readError }}</p>
    <button v-if="readError" type="button" :disabled="loading" @click="refresh()">교대 다시 조회</button>
    <form v-if="pairs.length" @submit.prevent="create()" :aria-busy="command.busy">
      <label for="handover-shift-pair">인계할 교대</label>
      <select id="handover-shift-pair" v-model="selected" required :disabled="command.busy || command.hasPending || loading || !!readError" :aria-invalid="!!command.error" :aria-describedby="command.error ? 'handover-create-error' : readError ? 'handover-shifts-error' : undefined">
        <option value="" disabled>허용된 교대 쌍을 선택하세요</option>
        <option v-for="pair in pairs" :key="pairKey(pair)" :value="pairKey(pair)">{{ shiftName(pair.from_shift_occurrence_id) }} → {{ shiftName(pair.to_shift_occurrence_id) }}</option>
      </select>
      <CommandFeedback :command="command" error-id="handover-create-error" @retry="create(true)" @review="review()" />
      <button type="submit" class="primary" :disabled="!selected || command.busy || command.hasPending || loading || !!readError">{{ command.busy ? '인계 저장 중…' : '인계 생성 · 기존 인계 갱신' }}</button>
    </form>
    <p v-else-if="!loading && !readError">현재 계정에 지정된 출발 교대가 없습니다. 수신 책임자는 전달받은 인계에서 사건별로 인수할 수 있습니다.</p>
  </section>
</template>
