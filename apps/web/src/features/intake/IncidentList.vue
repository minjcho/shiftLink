<script setup lang="ts">
import { IncidentStatusValues } from '../../lib/contracts';
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { api, Command, errorMessage, SessionChanged } from '../../lib/api';
import type { Equipment, Incident, IntakeResult, Page } from '../../lib/types';
import { label, person, time } from '../../lib/presentation';
import { usePolling } from '../../lib/polling';
import CommandFeedback from '../../components/CommandFeedback.vue';
const props = defineProps<{ equipment: Equipment[] }>();
const emit = defineEmits<{ open: [id: string, notice?: string] }>();
const equipmentId = ref('');
const text = ref('');
const command = reactive(new Command());
const scope = ref('all');
const status = ref('');
const filterEquipment = ref('');
const items = ref<Incident[] | null>(null);
const nextCursor = ref<string | null>(null);
const error = ref('');
const loading = ref(false);
const lastSuccess = ref<string | null>(null);
let readGeneration = 0;
const canSubmit = computed(() => equipmentId.value !== '' && text.value.trim() !== '' && !command.busy && !command.hasPending);
watch(() => props.equipment, value => { if (!equipmentId.value && value.length) equipmentId.value = value[0].id; }, { immediate: true });
async function refresh(cursor?: string) {
  const current = ++readGeneration;
  const query = new URLSearchParams({ scope: scope.value });
  if (status.value) query.set('status', status.value);
  if (filterEquipment.value) query.set('equipment_id', filterEquipment.value);
  if (cursor) query.set('cursor', cursor);
  loading.value = true;
  try {
    const { data } = await api.request<Page<Incident>>(`/incidents?${query}`);
    if (current !== readGeneration) return;
    items.value = cursor && items.value ? [...items.value, ...data.items] : data.items;
    nextCursor.value = data.next_cursor;
    error.value = ''; lastSuccess.value = new Date().toISOString();
  } catch (e) { if (!(e instanceof SessionChanged) && current === readGeneration) error.value = errorMessage(e); }
  finally { if (current === readGeneration) loading.value = false; }
}
watch([scope, status, filterEquipment], () => { items.value = null; nextCursor.value = null; lastSuccess.value = null; void refresh(); });
onMounted(() => void refresh());
usePolling(refresh);
async function submit(retry = false) {
  try {
    const result = retry ? await command.send<IntakeResult>(api) : await command.send<IntakeResult>(api, '/incidents', { equipment_id: equipmentId.value, text: text.value, observed_at: null });
    if (!result) return;
    text.value = '';
    emit('open', result.incident_id, `제보 저장됨 · 조사 대기 · ${result.display_id} · ${result.incident_id}`);
  } catch { /* CommandFeedback retains the original request and explains recovery. */ }
}
async function review() { await refresh(); command.reset(); }
</script>
<template>
  <div class="intro"><p class="eyebrow">01 / 접수와 확인</p><h1>현장의 기록을<br>다음 확인으로 연결합니다.</h1><p>관찰한 내용은 원문 그대로 남고, 확인이 필요한 내용은 담당자에게 전달됩니다.</p></div>
  <div class="list-layout">
    <section class="panel intake-form" aria-labelledby="intake-heading">
      <span class="section-number">새 기록</span><h2 id="intake-heading">이상 징후 제보</h2>
      <form @submit.prevent="submit()" :aria-busy="command.busy">
        <label for="intake-equipment">설비</label>
        <select id="intake-equipment" v-model="equipmentId" required :disabled="command.busy || command.hasPending"><option disabled value="">설비 선택</option><option v-for="item in equipment" :key="item.id" :value="item.id">{{ item.code }} · {{ item.label ?? item.aliases.join(', ') }}</option></select>
        <label for="intake-text">제보 원문</label>
        <textarea id="intake-text" v-model="text" rows="7" required maxlength="10000" placeholder="어떤 설비에서 무엇을 관찰했는지 적어 주세요." :disabled="command.busy || command.hasPending" :aria-invalid="!!command.error" :aria-describedby="command.error ? 'intake-error' : 'intake-help'"></textarea>
        <p id="intake-help" class="field-help">직접 관찰한 내용과 전해 들은 내용을 구분해 주세요.</p>
        <CommandFeedback :command="command" error-id="intake-error" @retry="submit(true)" @review="review" />
        <button class="primary wide" type="submit" :disabled="!canSubmit">{{ command.busy ? '저장 중…' : '제보 저장' }}</button>
      </form>
    </section>
    <section aria-labelledby="list-heading" class="incidents-section">
      <div class="section-heading"><div><span class="section-number">진행 상황</span><h2 id="list-heading">사건 목록</h2></div><button class="secondary" :disabled="loading" @click="refresh()">새로고침</button></div>
      <div class="filters"><div><label for="scope-filter">내 확인 요청·업무</label><select id="scope-filter" v-model="scope"><option value="all">사업장 전체</option><option value="mine">나와 관련된 사건</option></select></div><div><label for="status-filter">사건 상태</label><select id="status-filter" v-model="status"><option value="">미해결 전체</option><option v-for="s in IncidentStatusValues" :key="s" :value="s">{{ label(s) }}</option></select></div><div><label for="equipment-filter">설비 필터</label><select id="equipment-filter" v-model="filterEquipment"><option value="">모든 설비</option><option v-for="item in equipment" :key="item.id" :value="item.id">{{ item.code }}</option></select></div></div>
      <p class="freshness">마지막 성공 조회: {{ time(lastSuccess) }}</p>
      <p v-if="error" role="alert" class="notice error">{{ error }} {{ items !== null ? '이전 조회 내용을 표시하고 있습니다.' : '아직 목록을 확인하지 못했습니다.' }}</p>
      <p v-if="items === null && loading" role="status">사건 조회 중…</p>
      <div v-if="items !== null && items.length === 0" class="empty-state"><h3>해당하는 사건이 없습니다.</h3><p>현재 필터로 조회한 결과입니다.</p></div>
      <ul v-if="items?.length" class="incident-list"><li v-for="item in items" :key="item.id"><a :href="`/incidents/${item.id}`" @click.prevent="emit('open', item.id)"><div class="incident-card-top"><span class="identifier">{{ item.display_id }}</span><span class="badge">{{ label(item.status) }}</span></div><h3>{{ equipment.find(e => e.id === item.equipment_id)?.code ?? item.equipment_id }} · {{ item.title ?? '제보 기록' }}</h3><p v-if="item.waiting_for_input" class="attention">필수 질문 · 담당자 답변 대기</p><p v-if="item.review_required" class="attention">후속 검토 필요</p><p v-if="item.open_request_count !== undefined || item.unfinished_action_count !== undefined">미응답 질문 {{ item.open_request_count ?? '미수집' }} · 미완료 작업 {{ item.unfinished_action_count ?? '미수집' }}</p><p class="muted">현재 책임자: {{ person(item.owner_id) }}</p><small>최근 변경 {{ time(item.updated_at) }} · 업무 버전 {{ item.version }}</small></a></li></ul>
      <button v-if="nextCursor" class="secondary wide" :disabled="loading" @click="refresh(nextCursor)">다음 사건 보기</button>
    </section>
  </div>
</template>
