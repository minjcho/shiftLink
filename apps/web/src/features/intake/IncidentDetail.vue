<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { api, Command, errorMessage, SessionChanged, type CommandState } from '../../lib/api';
import type { Equipment, IncidentDetail, Job, Me, MessageResult, RequestItem } from '../../lib/types';
import { label, person, time } from '../../lib/presentation';
import { usePolling } from '../../lib/polling';
import CommandFeedback from '../../components/CommandFeedback.vue';
import EvidencePanel from '../../components/EvidencePanel.vue';
const props = defineProps<{ id: string; me: Me; equipment: Equipment[]; notice?: string }>();
const emit = defineEmits<{ back: [] }>();
const detail = ref<IncidentDetail | null>(null);
const job = ref<Job | null>(null);
const readError = ref('');
const jobError = ref('');
const lastSuccess = ref<string | null>(null);
const loading = ref(false);
const note = ref('');
const correctionOf = ref('');
const noteCommand = reactive(new Command());
const retryCommand = reactive(new Command());
const replies = reactive<Record<string, string>>({});
const replyCommands = reactive<Record<string, CommandState>>({});
const savedNotice = ref(props.notice ?? '');
let sequence = 0;
const requiredOpen = computed(() => detail.value?.requests.some(r => r.status === 'OPEN' && r.is_required) ?? false);
const stale = computed(() => !!detail.value?.analysis && detail.value.analysis.base_version !== detail.value.version);
const canRetryJob = computed(() => !!detail.value && props.me.role === 'supervisor' && props.me.user_id === detail.value.owner_id && detail.value.allowed_commands.includes('retry_job') && job.value?.status === 'FAILED' && job.value.retryable);
function replyCommand(id: string) { return replyCommands[id] ?? (replyCommands[id] = new Command()); }
function canAnswer(request: RequestItem) { return request.status === 'OPEN' && request.target_user_id === props.me.user_id && detail.value?.allowed_commands.includes('reply_request'); }
async function refresh(): Promise<boolean> {
  const current = ++sequence;
  loading.value = true;
  try {
    const { data } = await api.request<IncidentDetail>(`/incidents/${encodeURIComponent(props.id)}`);
    if (current !== sequence) return false;
    detail.value = data; readError.value = ''; lastSuccess.value = new Date().toISOString();
    if (data.latest_job) {
      try {
        const result = await api.request<Job>(`/jobs/${encodeURIComponent(data.latest_job.id)}`);
        if (current === sequence) { job.value = result.data; jobError.value = ''; }
      } catch (error) {
        if (current === sequence && !(error instanceof SessionChanged)) { job.value = data.latest_job; jobError.value = errorMessage(error); }
        return false;
      }
    } else { job.value = null; jobError.value = ''; }
    return current === sequence;
  } catch (error) {
    if (current === sequence && !(error instanceof SessionChanged)) readError.value = errorMessage(error);
    return false;
  }
  finally { if (current === sequence) loading.value = false; }
}
async function refreshSlot(): Promise<void> { await refresh(); }
onMounted(() => void refresh());
usePolling(refresh);
async function sendMessage(requestId?: string, retry = false) {
  if (!detail.value) return;
  const command = requestId ? replyCommand(requestId) : noteCommand;
  const body = { text: requestId ? replies[requestId] : note.value, expected_version: detail.value.version, reply_to_request_id: requestId ?? null, observed_at: null, correction_of: requestId ? null : correctionOf.value || null };
  try {
    const result = retry ? await command.send<MessageResult>(api) : await command.send<MessageResult>(api, `/incidents/${encodeURIComponent(props.id)}/messages`, body);
    if (!result) return;
    if (requestId) replies[requestId] = ''; else { note.value = ''; correctionOf.value = ''; }
    savedNotice.value = requestId ? `답변 저장됨 · ${result.message_id} · ${result.job_id ? '새 조사 대기' : '원문 기록됨'}` : `추가 원문 저장됨 · ${result.message_id}`;
    await refresh();
  } catch { /* Retain inputs and exact retry snapshot. */ }
}
async function review(command: CommandState) {
  if (!command.canReview) return;
  const refreshed = await refresh();
  if (refreshed && command.canReview) command.reset();
}
async function retryJob(retry = false) {
  if (!job.value) return;
  try {
    const result = retry ? await retryCommand.send<Job>(api) : await retryCommand.send<Job>(api, `/jobs/${job.value.id}/retry`, {});
    if (result) { savedNotice.value = '조사 재시도 요청을 저장했습니다.'; await refresh(); }
  } catch { /* Owner-only retry errors remain separate from intake success. */ }
}
</script>
<template>
  <a href="/incidents" class="back-link" @click.prevent="emit('back')">← 사건 목록</a>
  <p v-if="savedNotice" class="notice success" role="status">{{ savedNotice }}</p>
  <p v-if="readError" class="notice error" role="alert">{{ readError }} {{ detail ? '이전 조회 내용을 표시하고 있습니다.' : '사건을 확인하지 못했습니다.' }}</p>
  <p v-if="!detail && loading" role="status">사건 조회 중…</p>
  <button v-if="!detail && readError" @click="refresh()">다시 조회</button>
  <template v-if="detail">
    <header class="detail-heading"><div><p class="eyebrow">{{ detail.display_id }} · {{ equipment.find(e => e.id === detail?.equipment_id)?.code ?? detail.equipment_id }}</p><h1>{{ detail.title ?? '사건 기록' }}</h1><p class="identifier">Incident {{ detail.id }}</p></div><div class="state-stack"><span class="badge">사건 · {{ label(detail.status) }}</span><span v-if="requiredOpen" class="badge amber">필수 질문 · 담당자 답변 대기</span><span v-if="job" class="badge">{{ label(job.status) }}</span></div></header>
    <div class="detail-meta"><span>현재 책임자 {{ person(detail.owner_id) }}</span><span>업무 버전 {{ detail.version }}</span><span>마지막 성공 조회 {{ time(lastSuccess) }}</span><button class="link-button" :disabled="loading" @click="refresh()">새로고침</button></div>
    <p v-if="detail.review_required" class="notice error"><strong>후속 검토 필요</strong> · {{ detail.review_reason }}<br>원문과 이력은 보존됩니다. 추가 기록으로 승인·검증이 자동 재개되지 않습니다.</p>
    <div v-if="job?.status === 'FAILED'" class="notice error"><strong>AI 조사 실패 · 제보는 저장됨</strong><p>{{ job.error_code ?? '상세 실패 코드 미수집' }}</p><button v-if="canRetryJob" type="button" :disabled="retryCommand.busy || retryCommand.hasPending" @click="retryJob()">AI 조사 재시도</button><CommandFeedback :command="retryCommand" error-id="retry-error" @retry="retryJob(true)" @review="review(retryCommand)" /></div>
    <div class="detail-grid">
      <div class="column">
        <section class="panel" aria-labelledby="messages-heading"><span class="section-number">사람이 남긴 기록</span><h2 id="messages-heading">원문·추가 기록</h2><ol class="timeline"><li v-for="message in detail.messages" :key="message.id"><div class="record-meta"><strong>{{ message.kind }}</strong><span>{{ time(message.received_at) }}</span></div><p class="preserve-lines">{{ message.text }}</p><small>작성자 {{ person(message.author_id) }}</small><small class="identifier">Message {{ message.id }}</small><small v-if="message.reply_to_request_id">답변 질문 {{ message.reply_to_request_id }}</small><small v-if="message.correction_of">정정 대상 {{ message.correction_of }} · 이전 원문 유지</small></li></ol>
          <form v-if="detail.allowed_commands.includes('add_message')" class="separated" @submit.prevent="sendMessage()" :aria-busy="noteCommand.busy"><h3>추가 기록</h3><label for="correction">기록 종류</label><select id="correction" v-model="correctionOf" :disabled="noteCommand.busy || noteCommand.hasPending"><option value="">일반 추가 원문</option><option v-for="message in detail.messages" :key="message.id" :value="message.id">정정: {{ message.text.slice(0, 45) }} ({{ message.id }})</option></select><label for="note-text">추가 원문</label><textarea id="note-text" v-model="note" required rows="4" maxlength="10000" :disabled="noteCommand.busy || noteCommand.hasPending" :aria-invalid="!!noteCommand.error" :aria-describedby="noteCommand.error ? 'note-error' : undefined"></textarea><CommandFeedback :command="noteCommand" error-id="note-error" @retry="sendMessage(undefined, true)" @review="review(noteCommand)" /><button class="primary" :disabled="!note.trim() || noteCommand.busy || noteCommand.hasPending">추가 기록 저장</button></form>
          <p v-else-if="detail.status === 'RESOLVED'" class="notice">해결된 사건입니다. 새 정보는 새 사건으로 제보해 주세요.</p>
          <div v-if="!detail.allowed_commands.includes('add_message') && note" class="notice"><strong>작성 중이던 내용</strong><p class="preserve-lines">{{ note }}</p><p>권한 또는 사건 상태가 변경되어 전송하지 않았습니다. 새 제보에 복사할 수 있습니다.</p></div>
        </section>
        <section class="panel" aria-labelledby="questions-heading"><span class="section-number">담당자 확인</span><h2 id="questions-heading">확인 질문·답변</h2><p v-if="!detail.requests.length">{{ job?.status === 'RUNNING' || job?.status === 'QUEUED' ? '조사 결과를 기다리고 있습니다. 아직 저장된 질문은 없습니다.' : '저장된 확인 질문이 없습니다.' }}</p><article v-for="request in detail.requests" :key="request.id" class="question-card"><div class="record-meta"><strong>{{ request.purpose_code === 'VERIFY_SCOPE' ? '점검 범위 확인' : '점검 결과 확인' }}</strong><span class="badge" :class="{ amber: request.status === 'OPEN' }">{{ request.is_required ? '필수' : '선택' }} · {{ request.status === 'OPEN' ? '답변 대기' : '답변 완료' }}</span></div><h3>{{ request.question }}</h3><p>답변 대상 {{ person(request.target_user_id) }}</p><p class="identifier">Request {{ request.id }}</p><small>{{ time(request.created_at) }}</small><p class="muted">근거 {{ request.evidence_refs.join(', ') || '없음' }}</p><blockquote v-if="request.response_message_id">{{ detail.messages.find(m => m.id === request.response_message_id)?.text ?? '답변 원문은 기록에서 확인해 주세요.' }}</blockquote><form v-if="canAnswer(request)" @submit.prevent="sendMessage(request.id)" :aria-busy="replyCommand(request.id).busy"><label :for="`reply-${request.id}`">이 질문에 대한 답변</label><textarea :id="`reply-${request.id}`" v-model="replies[request.id]" rows="3" required maxlength="10000" :disabled="replyCommand(request.id).busy || replyCommand(request.id).hasPending" :aria-invalid="!!replyCommand(request.id).error" :aria-describedby="replyCommand(request.id).error ? `reply-error-${request.id}` : undefined"></textarea><CommandFeedback :command="replyCommand(request.id)" :error-id="`reply-error-${request.id}`" @retry="sendMessage(request.id, true)" @review="review(replyCommand(request.id))" /><button class="primary" :disabled="!replies[request.id]?.trim() || replyCommand(request.id).busy || replyCommand(request.id).hasPending">답변 저장</button></form><p v-else-if="request.status === 'OPEN'" class="muted">지정된 담당자만 답변할 수 있습니다.</p><p v-if="!canAnswer(request) && replies[request.id]" class="notice preserve-lines">미전송 답변: {{ replies[request.id] }}</p></article></section>
      </div>
      <div class="column">
        <section class="panel analysis-panel" aria-labelledby="analysis-heading"><span class="section-number">AI 조사 참고</span><h2 id="analysis-heading">사실과 미확인 내용</h2><p class="muted">AI 조사 결과는 사람의 승인이나 사건 해결을 대신하지 않습니다.</p><template v-if="detail.analysis"><p v-if="stale" class="notice amber">이전 정보에 대한 분석 · 갱신 필요<br>분석 기준 {{ detail.analysis.base_version }} / 현재 업무 {{ detail.version }}</p><p v-if="detail.analysis.decision === 'BLOCKED'" class="notice error">조사 보류 · 정상 또는 해결로 판단되지 않았습니다.</p><p>{{ detail.analysis.reason }}</p><h3>기록·사람 진술·시스템 상태</h3><ul class="facts"><li v-for="(fact, index) in detail.analysis.facts" :key="index"><span class="category">{{ ({ HUMAN_STATEMENT: '사람 진술', RECORD: '기록', SYSTEM_STATE: '시스템 상태' } as Record<string,string>)[fact.kind] ?? fact.kind }}</span><p>{{ fact.text }}</p><small>근거 {{ fact.source_refs.join(', ') || '없음' }}</small></li></ul><h3>가설 · 확인된 사실 아님</h3><ul><li v-for="(hypothesis,index) in detail.analysis.hypotheses" :key="index">{{ hypothesis }}</li></ul><p v-if="!detail.analysis.hypotheses.length" class="muted">기록된 가설 없음</p><h3>미확인 정보</h3><ul><li v-for="(missing,index) in detail.analysis.missing_information" :key="index">{{ missing }}</li></ul><p v-if="!detail.analysis.missing_information.length" class="muted">분석에 기록된 미확인 항목 없음</p></template><p v-else>아직 저장된 분석이 없습니다. 원문 접수 상태는 유지됩니다.</p></section>
        <slot name="actions" :detail="detail" :session="me" :refresh="refreshSlot">
        <section v-if="detail.actions.length" class="panel"><h2>연결된 작업</h2><article v-for="action in detail.actions" :key="action.id"><h3>{{ action.status }} · {{ action.id }}</h3><p>{{ action.scope }}</p><p>작업 담당자 {{ person(action.assignee_id) }}</p><p v-if="action.status === 'COMPLETED'">작업 결과 제출 완료 · 사건 상태는 별도로 확인합니다.</p></article></section>
        </slot>
        <slot name="resolution" :detail="detail" :session="me" :refresh="refreshSlot" />
        <section v-if="detail.handover" class="panel"><h2>교대 인수 요약</h2><p>{{ detail.handover.ack_status === 'ACKNOWLEDGED' ? '인수 완료' : '인수 확인 대기' }}</p><p v-if="detail.handover.is_stale">새 업무 내용 · 인계 재확인 필요</p><p class="muted">인수 상태와 AI 분석 최신성은 별개입니다.</p></section>
        <EvidencePanel :evidence="detail.evidence" />
      </div>
    </div>
    <slot name="history" :detail="detail" :session="me" :refresh="refreshSlot">
    <section class="panel"><h2>최근 업무 이력</h2><p v-if="!detail.recent_events.length">저장된 이력 없음</p><ul><li v-for="(event,index) in detail.recent_events" :key="event.id ?? index">{{ time(event.occurred_at) }} · {{ event.type }} · {{ event.id }} · {{ person(event.actor_id) }}</li></ul></section>
    </slot>
    <details class="panel diagnostics"><summary>실행 진단 · 실제 모드와 실행 기록</summary><p v-if="jobError" class="notice error">Job 조회 실패 · {{ jobError }}</p><dl v-if="job"><dt>Job / 상태</dt><dd>{{ job.id }} / {{ job.status }}</dd><dt>모드</dt><dd>{{ job.mode ?? 'UNKNOWN' }}</dd><dt>run / attempt</dt><dd>{{ job.latest_run_id ?? '미수집' }} / {{ job.attempt ?? '미수집' }}</dd><dt>run 상태</dt><dd>{{ job.latest_run_status ?? '미수집' }}</dd><dt>시작 / 종료</dt><dd>{{ time(job.started_at) }} / {{ time(job.finished_at) }}</dd><dt>오류</dt><dd>{{ job.error_code ?? '없음' }}</dd></dl><p v-else>저장된 Job 없음</p><template v-if="job?.run_summary && me.role === 'supervisor' && me.user_id === detail.owner_id"><h3>현재 책임자에게 제공된 실행 요약</h3><pre>{{ JSON.stringify(job.run_summary, null, 2) }}</pre></template></details>
  </template>
</template>
