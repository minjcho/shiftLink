<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue';
import { api, Command, errorMessage, SessionChanged, type CommandState } from '../../lib/api';
import type { Me } from '../../lib/types';
import { label, person, time } from '../../lib/presentation';
import { usePolling } from '../../lib/polling';
import HandoverSnapshot from './HandoverSnapshot.vue';
import type { AckResult, Handover, HandoverItem } from './types';

const props = defineProps<{ id: string; me: Me }>();
const emit = defineEmits<{ back: []; openIncident: [id: string] }>();
const handover = ref<Handover | null>(null);
const shown = reactive<Record<string, HandoverItem>>({});
const confirmed = reactive<Record<string, boolean>>({});
const selections = reactive<Record<string, number>>({});
const commands = reactive<Record<string, CommandState>>({});
const notices = reactive<Record<string, string>>({});
const historyBusy = reactive<Record<string, boolean>>({});
const historyErrors = reactive<Record<string, string>>({});
const readError = ref('');
const lastSuccess = ref<string | null>(null);
const loading = ref(false);
const refreshCommand = reactive(new Command());
const refreshNotice = ref('');
let alive = true;
let sequence = 0;
const historySequences: Record<string, number> = {};
const canRegenerate = computed(() => props.me.role === 'supervisor' && handover.value?.from_shift?.supervisor_id === props.me.user_id);
function commandFor(id: string) { return commands[id] ?? (commands[id] = new Command()); }
function latest(id: string) { return handover.value?.items.find(item => item.id === id); }
function display(item: HandoverItem) { return shown[item.id] ?? item; }
function isCurrent(item: HandoverItem) {
  const selected = display(item);
  return selected.revision === item.latest_revision && selected.snapshot_token === item.snapshot_token;
}
function canAck(item: HandoverItem) {
  return props.me.role === 'supervisor' && props.me.user_id === handover.value?.receiver_id && item.can_ack && !item.is_resolved
    && isCurrent(item) && !readError.value && !loading.value && !historyBusy[item.id] && !historyErrors[item.id]
    && !commandFor(item.id).busy && !commandFor(item.id).hasPending;
}
function statusText(item: HandoverItem) {
  if (item.is_resolved) return '해결된 사건 · 과거 인계';
  if (!isCurrent(item)) return '새 내용 있음 · 최신 revision 확인 필요';
  if (item.ack_status === 'ACKNOWLEDGED' && !item.is_stale) return '인수 완료';
  if (item.previously_acknowledged || item.is_stale) return '변경된 내용 · 추가 인수 필요';
  return '인수 확인 대기';
}
function changes(item: HandoverItem) {
  const old = display(item).snapshot;
  const next = item.snapshot;
  const result: string[] = [];
  const sections = [['messages', '원문·답변·작업 결과'], ['requests', '질문과 답변 상태'], ['actions', '작업과 결과'], ['approvals', '승인 기록'], ['evidence', '근거']] as const;
  for (const [key, text] of sections) if (JSON.stringify(old[key]) !== JSON.stringify(next[key])) result.push(text);
  if (old.status !== next.status) result.push('사건 상태');
  if (old.review_required !== next.review_required || old.review_reason !== next.review_reason) result.push('후속 검토');
  if (old.owner_id !== next.owner_id) result.push('책임자');
  return result.length ? result.join(', ') : '업무 버전과 기록';
}
function useLatest(item: HandoverItem) {
  historySequences[item.id] = (historySequences[item.id] ?? 0) + 1;
  historyBusy[item.id] = false;
  shown[item.id] = item;
  selections[item.id] = item.revision;
  confirmed[item.id] = false;
  historyErrors[item.id] = '';
}
async function refresh() {
  const current = ++sequence;
  loading.value = true;
  try {
    const { data } = await api.request<Handover>(`/handovers/${encodeURIComponent(props.id)}`);
    if (!alive || current !== sequence) return;
    handover.value = data;
    for (const item of data.items) if (!shown[item.id]) useLatest(item);
    readError.value = ''; lastSuccess.value = new Date().toISOString();
  } catch (error) { if (alive && current === sequence && !(error instanceof SessionChanged)) readError.value = errorMessage(error); }
  finally { if (alive && current === sequence) loading.value = false; }
}
async function review(id: string) {
  if (commandFor(id).busy) return;
  await refresh();
  const item = latest(id);
  if (alive && !readError.value && item) { useLatest(item); commandFor(id).reset(); notices[id] = ''; }
}
async function viewHistory(id: string) {
  const revision = Number(selections[id]);
  const item = latest(id);
  if (!item || !Number.isInteger(revision) || revision < 1 || revision > item.latest_revision || commandFor(id).busy) return;
  const current = (historySequences[id] ?? 0) + 1;
  historySequences[id] = current;
  historyBusy[id] = true;
  confirmed[id] = false;
  try {
    const query = new URLSearchParams({ item_id: id, revision: String(revision) });
    const { data } = await api.request<Handover>(`/handovers/${encodeURIComponent(props.id)}?${query}`);
    if (!alive || current !== historySequences[id]) return;
    const historical = data.items.find(value => value.id === id);
    if (!historical) throw new Error('요청한 revision이 조회 응답에 없습니다.');
    shown[id] = historical; historyErrors[id] = ''; notices[id] = '';
  } catch (error) { if (alive && current === historySequences[id] && !(error instanceof SessionChanged)) historyErrors[id] = errorMessage(error); }
  finally { if (alive && current === historySequences[id]) historyBusy[id] = false; }
}
async function acknowledge(id: string, retry = false) {
  const item = latest(id);
  const command = commandFor(id);
  if (!item || readError.value || loading.value || command.busy || (!retry && (!canAck(item) || !confirmed[id]))) return;
  const selected = display(item);
  try {
    const result = retry ? await command.send<AckResult>(api) : await command.send<AckResult>(api,
      `/handovers/${encodeURIComponent(props.id)}/items/${encodeURIComponent(id)}/ack`,
      { revision: selected.revision, snapshot_token: selected.snapshot_token, expected_version: selected.snapshot_version });
    if (!alive || !result) return;
    confirmed[id] = false;
    notices[id] = `이 항목의 revision ${result.revision} 인수를 저장했습니다. 사건 책임자 ${person(result.owner_id)} · 작업 담당자 ${person(result.assignee_id)}. 다른 항목은 별도로 확인하세요.`;
    await refresh();
  } catch { /* Keep the displayed revision, confirmation and exact-key retry snapshot. */ }
}
async function regenerate(retry = false) {
  if (!handover.value || !canRegenerate.value || readError.value || loading.value) return;
  try {
    const result = retry ? await refreshCommand.send<Handover>(api) : await refreshCommand.send<Handover>(api, '/handovers', {
      from_shift_occurrence_id: handover.value.from_shift_occurrence_id,
      to_shift_occurrence_id: handover.value.to_shift_occurrence_id,
    });
    if (!alive || !result) return;
    refreshNotice.value = '새 대상의 snapshot을 저장했습니다. 최초 기준 시각과 추가 표시는 유지되며 항목별 인수가 필요합니다.';
    await refresh();
  } catch { /* Preserve the explicit generation command for retry. */ }
}
async function reviewRegeneration() { await refresh(); if (alive && !readError.value) refreshCommand.reset(); }
onMounted(() => void refresh());
usePolling(refresh);
onUnmounted(() => { alive = false; sequence += 1; });
</script>

<template>
  <a href="/incidents" class="back-link" @click.prevent="emit('back')">← 사건 목록</a>
  <p v-if="!handover && loading" role="status">인계 내용을 조회하고 있습니다…</p>
  <div v-if="readError" class="notice error" role="alert"><strong>{{ readError }}</strong><p>{{ handover ? '마지막 성공 조회 내용을 보존했습니다. 최신 조회가 성공할 때까지 인수할 수 없습니다.' : '인계 목록을 확인하지 못했습니다. 성공한 빈 목록이 아닙니다.' }}</p><p>마지막 성공 조회 {{ time(lastSuccess) }}</p><button type="button" :disabled="loading" @click="refresh()">다시 조회</button></div>
  <template v-if="handover">
    <header class="detail-heading"><div><p class="eyebrow">교대 인계·인수</p><h1>남은 업무를 함께 확인하세요</h1><p class="identifier">Handover {{ handover.handover_id ?? handover.id ?? id }}</p></div><span class="badge">사건별 확인</span></header>
    <section class="panel handover-overview" aria-label="인계 기준과 책임자">
      <dl><dt>출발 → 수신 교대</dt><dd>{{ handover.from_shift?.label ?? handover.from_shift_occurrence_id }} → {{ handover.to_shift?.label ?? handover.to_shift_occurrence_id }}</dd><dt>최초 인계 기준 시각</dt><dd>{{ time(handover.cutoff_at) }}</dd><dt>지정 수신 책임자</dt><dd>{{ handover.receiver?.display_name ?? person(handover.receiver_id) }}</dd><dt>마지막 성공 조회</dt><dd>{{ time(lastSuccess) }}</dd></dl>
      <div class="button-row"><button type="button" class="secondary" :disabled="loading" @click="refresh()">{{ loading ? '조회 중…' : '현재 상태 새로고침' }}</button><button v-if="canRegenerate" type="button" :disabled="loading || !!readError || refreshCommand.busy || refreshCommand.hasPending" @click="regenerate()">{{ refreshCommand.busy ? 'snapshot 저장 중…' : '추가 사건을 인계 snapshot에 포함' }}</button></div>
      <p class="muted">자동 조회는 확인 중인 원문을 바꾸지 않습니다. 변경 안내에서 최신 내용을 확인한 뒤 인수하세요. 최초 기준 이후 추가 표시는 인수 후에도 유지됩니다.</p>
      <p v-if="refreshNotice" class="notice success" role="status">{{ refreshNotice }}</p>
      <p v-if="refreshCommand.busy" role="status">인계 갱신 응답을 기다리고 있습니다…</p>
      <div v-if="refreshCommand.error" class="notice error" role="alert"><p>{{ errorMessage(refreshCommand.error) }}</p><button v-if="refreshCommand.canRetry" type="button" :disabled="!!readError || loading || refreshCommand.busy" @click="regenerate(true)">같은 인계 갱신 요청 결과 확인</button><button type="button" class="secondary" :disabled="refreshCommand.busy" @click="reviewRegeneration()">최신 목록 조회 · 새 요청 준비</button></div>
    </section>
    <section v-if="handover.pending_additions?.length" class="panel pending-additions" aria-labelledby="pending-additions-heading"><h2 id="pending-additions-heading">추가됨 · 아직 snapshot에 포함되지 않은 사건</h2><p>출발 책임자의 명시적 인계 갱신 후 항목별 내용을 확인해야 인수할 수 있습니다.</p><ul><li v-for="addition in handover.pending_additions" :key="addition.incident_id"><a :href="`/incidents/${encodeURIComponent(addition.incident_id)}`" @click.prevent="emit('openIncident', addition.incident_id)">{{ addition.display_id ?? addition.incident_id }} · {{ addition.title ?? '새 미해결 사건' }}</a><span v-if="addition.status"> · {{ label(addition.status) }}</span><span class="badge amber">추가됨 · 인수 전</span></li></ul></section>
    <p v-if="!handover.items.length && !handover.pending_additions?.length && !readError" class="panel" role="status">조회가 완료되었습니다. 이 교대 범위의 미해결 인계 항목이 없습니다.</p>
    <article v-for="item in handover.items" :key="item.id" class="panel handover-item" :data-item-id="item.id" :data-incident-id="item.incident_id" :data-testid="`handover-item-${item.id}`" :aria-labelledby="`item-heading-${item.id}`">
      <header class="item-heading"><div><p class="eyebrow">{{ display(item).snapshot.display_id ?? item.incident_id }} · {{ display(item).snapshot.equipment?.code ?? display(item).snapshot.equipment_id }}</p><h2 :id="`item-heading-${item.id}`">{{ display(item).snapshot.title ?? '인계 사건' }}</h2></div><div class="state-stack"><span class="badge" :class="{ amber: item.ack_status !== 'ACKNOWLEDGED' || !isCurrent(item) }">{{ statusText(item) }}</span><span v-if="item.added_since_cutoff" class="badge">최초 인계 이후 추가됨</span><span class="badge">현재 사건 · {{ label(item.current_incident_status) }}</span></div></header>
      <div class="detail-meta"><span>현재 책임자 {{ item.current_owner?.display_name ?? person(item.current_owner_id) }}</span><span>유지된 작업 담당자 {{ item.current_assignee?.display_name ?? person(item.current_assignee_id) }}</span><span>현재 사건 버전 {{ item.current_incident_version }}</span></div>
      <p v-if="item.current_analysis_is_stale" class="notice amber">AI 분석은 이전 업무 정보 기준입니다. 분석 기준 {{ item.current_analysis_base_version }} / 현재 사건 버전 {{ item.current_incident_version }}. 분석의 갱신 필요만으로 인수를 다시 요구하지 않습니다.</p>
      <p>표시 중인 revision {{ display(item).revision }} / 최신 {{ item.latest_revision }} · snapshot 사건 버전 {{ display(item).snapshot_version }} · ACK 적용 버전 {{ item.ack_applied_version ?? '미인수' }}</p>
      <p class="identifier">Item {{ item.id }} · Incident {{ item.incident_id }}</p>
      <a :href="`/incidents/${encodeURIComponent(item.incident_id)}`" @click.prevent="emit('openIncident', item.incident_id)">이 사건의 현재 상세와 업무 이력</a>
      <div v-if="!isCurrent(item)" class="notice amber" role="status"><strong>확인 중인 원문을 그대로 보존했습니다.</strong><p>새 revision의 변경 항목: {{ changes(item) }}. 과거 내용을 보고 있는 동안에는 인수할 수 없습니다.</p><button type="button" :disabled="loading || commandFor(item.id).busy" @click="review(item.id)">최신 내용 확인 · revision {{ item.latest_revision }}</button></div>
      <p v-if="item.is_resolved" class="notice">이 사건은 해결되었습니다. 당시 인계는 조회할 수 있지만 새 인수는 할 수 없습니다.</p>
      <form class="history-picker" @submit.prevent="viewHistory(item.id)"><label :for="`history-${item.id}`">조회할 내용 revision</label><input :id="`history-${item.id}`" v-model.number="selections[item.id]" type="number" min="1" :max="item.latest_revision" required :disabled="historyBusy[item.id] || commandFor(item.id).busy || commandFor(item.id).hasPending"><button type="submit" class="secondary" :disabled="historyBusy[item.id] || commandFor(item.id).busy || commandFor(item.id).hasPending">{{ historyBusy[item.id] ? '과거 내용 조회 중…' : '선택한 revision 조회' }}</button></form>
      <p v-if="historyErrors[item.id]" class="notice error" role="alert">{{ historyErrors[item.id] }} 이전 내용을 표시하고 있습니다.</p>
      <HandoverSnapshot :snapshot="display(item).snapshot" :prefix="`snapshot-${item.id}-${display(item).revision}`" />
      <div class="separated ack-controls" :aria-busy="commandFor(item.id).busy">
        <p class="muted">인수는 사건 책임을 이전합니다. 작업 담당자·질문 답변 대상·업무 상태는 유지됩니다.</p>
        <template v-if="me.user_id === handover.receiver_id && me.role === 'supervisor'">
          <label class="confirm-label" :for="`confirm-${item.id}`"><input :id="`confirm-${item.id}`" v-model="confirmed[item.id]" type="checkbox" :disabled="!canAck(item)" :aria-invalid="!!commandFor(item.id).error" :aria-describedby="commandFor(item.id).error ? `ack-error-${item.id}` : undefined"> 표시 중인 revision {{ display(item).revision }}의 원문·남은 질문·작업과 근거를 확인했습니다.</label>
          <button type="button" class="primary" :disabled="!canAck(item) || !confirmed[item.id]" @click="acknowledge(item.id)">{{ commandFor(item.id).busy ? '인수 저장 중…' : item.previously_acknowledged ? '변경된 이 내용을 다시 인수했습니다' : '이 내용을 인수했습니다' }}</button>
        </template>
        <p v-else>지정 수신 책임자만 이 항목을 인수할 수 있습니다.</p>
        <p v-if="commandFor(item.id).busy" role="status">이 항목의 인수 응답을 기다리고 있습니다…</p>
        <p v-if="notices[item.id]" class="notice success" role="status">{{ notices[item.id] }}</p>
        <div v-if="commandFor(item.id).error" :id="`ack-error-${item.id}`" class="notice error" role="alert"><strong>{{ errorMessage(commandFor(item.id).error) }}</strong><p>확인 중인 내용을 보존했습니다. 최신 내용을 다시 읽고 사람이 새 명령을 제출해야 합니다.</p><p v-if="commandFor(item.id).canRetry">응답을 확인하지 못했습니다. 아래 결과 확인은 처음 보낸 내용과 중복 방지 키를 그대로 사용합니다.</p><div class="button-row"><button v-if="commandFor(item.id).canRetry" type="button" :disabled="loading || !!readError || commandFor(item.id).busy" @click="acknowledge(item.id, true)">같은 인수 요청 결과 확인</button><button type="button" class="secondary" :disabled="commandFor(item.id).busy" @click="review(item.id)">최신 내용 조회 · 새 요청 준비</button></div></div>
      </div>
    </article>
  </template>
</template>

<style scoped>
.handover-item { margin: 1.6rem 0; }
.item-heading { display: flex; gap: 1.2rem; align-items: flex-start; justify-content: space-between; }
.history-picker { display: flex; align-items: end; flex-wrap: wrap; gap: .7rem; margin: 1.2rem 0; }
.history-picker label { flex-basis: 100%; }
.history-picker input { width: 6rem; }
.confirm-label { display: flex; align-items: flex-start; gap: .65rem; padding: .8rem 0; }
.confirm-label input { width: auto; margin-top: .3rem; }
.pending-additions li { margin: .9rem 0; }
.handover-overview dl { margin-top: 0; }
@media (max-width: 700px) { .item-heading { flex-direction: column; } }
</style>
