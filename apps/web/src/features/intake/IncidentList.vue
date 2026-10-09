<script setup lang="ts">
import { IncidentStatusValues } from '../../lib/contracts';
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { api, Command, errorMessage, SessionChanged } from '../../lib/api';
import type { Equipment, Incident, IntakeResult, Page } from '../../lib/types';
import UiIcon from '../../components/UiIcon.vue';
import { label, personName, time } from '../../lib/presentation';
import { usePolling } from '../../lib/polling';
import CommandFeedback from '../../components/CommandFeedback.vue';
const props = defineProps<{ equipment: Equipment[]; initialStatus?: string; archive?: boolean }>();
const emit = defineEmits<{ open: [id: string, notice?: string] }>();
const equipmentId = ref('');
const text = ref('');
const command = reactive(new Command());
const scope = ref('all');
const status = ref(props.initialStatus ?? '');
const focusIntake = () => document.getElementById('intake-text')?.focus();
const filterEquipment = ref('');
const items = ref<Incident[] | null>(null);
const nextCursor = ref<string | null>(null);
const error = ref('');
const loading = ref(false);
const lastSuccess = ref<string | null>(null);
let readGeneration = 0;
let loadedPages = 1;
const canSubmit = computed(() => equipmentId.value !== '' && text.value.trim() !== '' && !command.busy && !command.hasPending);
watch(() => props.equipment, value => { if (!equipmentId.value && value.length) equipmentId.value = value[0].id; }, { immediate: true });
async function refresh(cursor?: string): Promise<boolean> {
  const current = ++readGeneration;
  const epoch = api.sessionEpoch;
  const pageLimit = cursor ? 1 : loadedPages;
  const query = new URLSearchParams({ scope: scope.value });
  if (status.value) query.set('status', status.value);
  if (filterEquipment.value) query.set('equipment_id', filterEquipment.value);
  loading.value = true;
  try {
    const refreshed: Incident[] = [];
    let next = cursor ?? null;
    let pagesRead = 0;
    // Follow fresh cursors across the loaded window, then publish it atomically.
    // A later-page failure must keep the previous items and their matching cursor.
    do {
      if (next) query.set('cursor', next); else query.delete('cursor');
      const { data } = await api.request<Page<Incident>>(`/incidents?${query}`);
      if (current !== readGeneration || epoch !== api.sessionEpoch) return false;
      refreshed.push(...data.items);
      next = data.next_cursor;
      pagesRead += 1;
    } while (next && pagesRead < pageLimit);
    const combined = cursor && items.value ? [...items.value, ...refreshed] : refreshed;
    const seen = new Set<string>();
    items.value = combined.filter(item => { if (seen.has(item.id)) return false; seen.add(item.id); return true; });
    nextCursor.value = next;
    loadedPages = cursor ? loadedPages + pagesRead : pagesRead;
    error.value = ''; lastSuccess.value = new Date().toISOString();
    return true;
  } catch (e) {
    if (!(e instanceof SessionChanged) && current === readGeneration) error.value = errorMessage(e);
    return false;
  }
  finally { if (current === readGeneration) loading.value = false; }
}
function loadMore() {
  if (!loading.value && nextCursor.value) void refresh(nextCursor.value);
}
watch([scope, status, filterEquipment], () => { items.value = null; nextCursor.value = null; lastSuccess.value = null; loadedPages = 1; void refresh(); });
onMounted(() => void refresh());
onUnmounted(() => { readGeneration += 1; });
usePolling(async () => { if (!loading.value) return refresh(); });
async function submit(retry = false) {
  try {
    const result = retry ? await command.send<IntakeResult>(api) : await command.send<IntakeResult>(api, '/incidents', { equipment_id: equipmentId.value, text: text.value, observed_at: null });
    if (!result) return;
    text.value = '';
    emit('open', result.incident_id, `제보 저장됨 · 조사 대기 · ${result.display_id} · ${result.incident_id}`);
  } catch { /* CommandFeedback retains the original request and explains recovery. */ }
}
async function review() {
  if (!command.canReview) return;
  const refreshed = await refresh();
  if (refreshed && command.canReview) command.reset();
}
</script>
<template>
  <div class="incident-workspace view-enter">
    <header class="page-heading"><div><p class="eyebrow">{{ archive ? 'ARCHIVE / 완료된 사건' : 'INCIDENTS / 현장 업무' }}</p><h1>{{ archive ? '해결 이력' : '사건 작업대' }}<span class="heading-dot">.</span></h1><p class="muted">{{ archive ? '사람의 최종 확인으로 마무리된 사건을 다시 확인하세요.' : '확인이 필요한 기록부터, 다음 교대에 이어질 업무까지.' }}</p></div><button v-if="!archive" class="primary new-incident" @click="focusIntake"><UiIcon name="plus" />새 제보 작성</button></header>
    <div class="list-layout" :class="{ 'archive-layout': archive }">
      <section aria-labelledby="list-heading" class="incidents-section">
        <div class="section-heading"><div class="list-section-title"><h2 id="list-heading">사건 목록</h2><span v-if="items !== null" class="result-count">{{ items.length }}{{ nextCursor ? '+' : '' }}</span></div><button class="text-button" :disabled="loading" @click="refresh()">새로고침</button></div>
        <div class="filters"><div><label for="scope-filter">내 확인 요청·업무</label><select id="scope-filter" v-model="scope"><option value="all">사업장 전체</option><option value="mine">나와 관련된 사건</option></select></div><div><label for="status-filter">사건 상태</label><select id="status-filter" v-model="status"><option value="">미해결 전체</option><option v-for="s in IncidentStatusValues" :key="s" :value="s">{{ label(s) }}</option></select></div><div><label for="equipment-filter">설비 필터</label><select id="equipment-filter" v-model="filterEquipment"><option value="">모든 설비</option><option v-for="item in equipment" :key="item.id" :value="item.id">{{ item.code }}</option></select></div></div>
        <p v-if="error" role="alert" class="notice error">{{ error }} {{ items !== null ? '이전 조회 내용을 표시하고 있습니다.' : '아직 목록을 확인하지 못했습니다.' }}</p>
        <div v-if="items === null && loading" class="loading-state" role="status"><span class="loading-line"></span>사건 조회 중…</div>
        <div v-if="items !== null && items.length === 0" class="empty-state"><div class="empty-drawing" aria-hidden="true"><UiIcon name="inbox" /><span class="empty-signal"></span></div><p class="section-number">NOTHING TO FOLLOW UP</p><h3>해당하는 사건이 없습니다.</h3><p>현재 필터로 조회한 결과입니다.</p><button v-if="!archive" class="text-button" @click="focusIntake">새로운 현장 기록 남기기 <span aria-hidden="true">↗</span></button></div>
        <div v-if="items?.length" class="list-columns" aria-hidden="true"><span>사건 / 설비</span><span>현재 상태</span><span>책임자</span></div>
        <ul v-if="items?.length" class="incident-list"><li v-for="item in items" :key="item.id"><a :href="`/incidents/${item.id}`" @click.prevent="emit('open', item.id)"><div class="incident-main"><div class="incident-card-top"><span class="identifier">{{ item.display_id }}</span><span class="equipment-code">{{ equipment.find(e => e.id === item.equipment_id)?.code ?? item.equipment_id }}</span></div><h3>{{ item.title ?? '제보 기록' }}</h3><p v-if="item.waiting_for_input" class="attention">담당자 답변 대기</p><p v-if="item.review_required" class="attention">후속 검토 필요</p><small v-if="item.open_request_count !== undefined || item.unfinished_action_count !== undefined">미응답 질문 {{ item.open_request_count ?? '미수집' }} · 미완료 작업 {{ item.unfinished_action_count ?? '미수집' }}</small></div><span class="badge" :data-status="item.status">{{ label(item.status) }}</span><div class="incident-owner"><span>{{ personName(item.owner_id) }}</span><small>{{ time(item.updated_at) }}</small><span class="row-arrow" aria-hidden="true">↗</span></div></a></li></ul>
        <div class="list-footer"><p class="freshness"><span class="freshness-dot" :class="{ loading }"></span>마지막 성공 조회: {{ time(lastSuccess) }}</p><button v-if="nextCursor" class="secondary" :disabled="loading" @click="loadMore">다음 사건 보기</button></div>
        <slot name="handover" />
      </section>
      <section v-if="!archive" class="panel intake-form" aria-labelledby="intake-heading"><div class="intake-heading"><span class="form-icon"><UiIcon name="note" /></span><span class="section-number">NEW REPORT</span></div><h2 id="intake-heading">현장의 변화를 남겨주세요.</h2><p class="muted">작은 기록에서 다음 확인이 시작됩니다.</p>
        <form @submit.prevent="submit()" :aria-busy="command.busy"><label for="intake-equipment">설비</label><select id="intake-equipment" v-model="equipmentId" required :disabled="command.busy || command.hasPending"><option disabled value="">설비 선택</option><option v-for="item in equipment" :key="item.id" :value="item.id">{{ item.code }} · {{ item.label ?? item.aliases.join(', ') }}</option></select><label for="intake-text">제보 원문</label><textarea id="intake-text" v-model="text" rows="6" required maxlength="10000" placeholder="무엇을 관찰하셨나요?
발생한 설비, 상황과 확인한 내용을 남겨주세요." :disabled="command.busy || command.hasPending" :aria-invalid="!!command.error" :aria-describedby="command.error ? 'intake-error' : 'intake-help'"></textarea><p id="intake-help" class="field-help">직접 관찰한 내용과 전해 들은 내용을 구분해 주세요.</p><CommandFeedback :command="command" error-id="intake-error" @retry="submit(true)" @review="review" /><button class="primary wide" type="submit" :disabled="!canSubmit">{{ command.busy ? '저장 중…' : '제보 저장' }}<span aria-hidden="true">↗</span></button></form><p class="form-footnote">원문은 그대로 보존됩니다.</p>
      </section>
    </div>
  </div>
</template>
