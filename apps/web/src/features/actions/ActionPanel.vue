<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { CommandFailure, prepareCommand } from './client'
import type { ActionView, ApprovalView, CommandKind, EvidenceOption, IncidentView,
  PendingCommand, ResultView, SendCommand, SessionView } from './types'

const props = defineProps<{
  action: ActionView | null
  incident: IncidentView
  session: SessionView
  approvals: ApprovalView[]
  result: ResultView | null
  evidenceOptions: EvidenceOption[]
  send: SendCommand
  refresh: () => Promise<void>
}>()
const reason = ref('')
const resultText = ref('')
const selectedEvidence = ref<string[]>([])
const busy = ref(false)
const pending = ref<PendingCommand | null>(null)
const error = ref('')
const notice = ref('')
const reviewRequired = ref(false)
const refreshRequired = ref(false)
const unmetRequirements = ref<string[]>([])
const requirementLabels: Record<string, string> = {
  REVIEW_REQUIRED: '책임자의 후속 검토 필요', REQUIRED_ACTION_MISSING: '필수 작업 없음',
  MULTIPLE_MAIN_ACTIONS: '주 작업 중복 확인 필요', ACTION_NOT_COMPLETED: '필수 작업 미완료',
  APPROVAL_INVALID: '승인 내용 확인 필요', EVIDENCE_INVALID: '작업 근거 확인 필요',
  RESULT_MISSING: '수행 결과 확인 필요', COMPLETION_EVIDENCE_INVALID: '결과 근거 확인 필요',
  REQUIRED_QUESTION_UNANSWERED: '필수 질문 답변 필요', INCIDENT_RESOLVED: '이미 해결된 사건',
}
let generation = 0
const statusLabels = { PROPOSED: '승인 대기', APPROVED: '승인됨', IN_PROGRESS: '진행 중',
  COMPLETED: '작업 결과 제출 완료', REJECTED: '반려됨' }
const blocked = computed(() => props.incident.review_required || props.incident.status === 'RESOLVED')
const canApprove = computed(() => props.action?.status === 'PROPOSED'
  && props.session.role === 'supervisor' && props.session.user_id === props.incident.owner_id && !blocked.value)
const canStart = computed(() => props.action?.status === 'APPROVED'
  && props.session.user_id === props.action.assignee_id && !blocked.value)
const canComplete = computed(() => props.action?.status === 'IN_PROGRESS'
  && props.session.user_id === props.action.assignee_id && !blocked.value)
const disabled = computed(() => busy.value || !!pending.value || reviewRequired.value || refreshRequired.value)
const actionApprovals = computed(() => props.approvals.filter(a => a.action_id === props.action?.id))
const displayedResult = computed(() => props.result?.id === props.action?.result_message_id ? props.result : null)

watch([() => props.incident.id, () => props.action?.id, () => props.session.user_id], () => {
  generation++ // Discard a previous actor/action's late response; never replay under a new actor.
  reason.value = ''; resultText.value = ''; selectedEvidence.value = []
  pending.value = null; error.value = ''; notice.value = ''; busy.value = false
  reviewRequired.value = false; refreshRequired.value = false
  unmetRequirements.value = []
}, { flush: 'sync' })
watch([() => props.incident.version, () => props.action?.version], () => {
  if (reason.value || resultText.value || pending.value) reviewRequired.value = true
}, { flush: 'sync' })

function date(value: string) {
  return new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', dateStyle: 'short', timeStyle: 'short' })
    .format(new Date(value))
}
async function reload() {
  const current = generation
  busy.value = true
  try {
    await props.refresh()
    if (current !== generation) return
    refreshRequired.value = false
    error.value = ''
  } catch {
    if (current === generation) {
      error.value = '최신 내용을 불러오지 못했습니다. 입력은 보존됩니다.'
      refreshRequired.value = true
    }
  } finally { if (current === generation) busy.value = false }
}
async function transmit(command: PendingCommand) {
  if (busy.value || command.actorId !== props.session.user_id || command.actionId !== props.action?.id) return
  const current = generation
  busy.value = true; error.value = ''; notice.value = ''
  let saved = false
  try {
    const data = await props.send(command)
    if (current !== generation) return
    saved = true; pending.value = null
    unmetRequirements.value = data.unmet_requirements ?? []
    reason.value = ''; resultText.value = ''; selectedEvidence.value = []
    notice.value = data.action_status === 'COMPLETED'
      ? (data.verification_ready ? '작업 결과가 저장됐습니다. 책임자의 최종 검증을 기다립니다.'
        : '작업 결과가 저장됐습니다. 아직 사건의 검증 조건이 충족되지 않았습니다.')
      : '처리가 저장됐습니다.'
    await props.refresh()
    if (current === generation) { reviewRequired.value = false; refreshRequired.value = false }
  } catch (failure) {
    if (current !== generation) return
    if (saved) {
      error.value = '저장은 완료됐지만 최신 조회에 실패했습니다. 내용을 다시 불러와 주세요.'
      refreshRequired.value = true
    } else {
      const known = failure instanceof CommandFailure
      const retry = !known || failure.retrySameRequest
      error.value = known ? failure.message : '응답을 확인하지 못했습니다. 같은 요청으로 다시 확인해 주세요.'
      pending.value = retry ? command : null
      if (!retry) { reviewRequired.value = true; refreshRequired.value = true }
    }
  } finally { if (current === generation) busy.value = false }
}
function submit(kind: CommandKind, decision?: 'APPROVE' | 'REJECT') {
  if (!props.action || disabled.value) return
  if (kind === 'approval-decisions' && (!canApprove.value || !reason.value.trim())) return
  if (kind === 'start' && !canStart.value) return
  if (kind === 'completion' && (!canComplete.value || !resultText.value.trim())) return
  const body = { expected_version: props.action.version, expected_incident_version: props.incident.version,
    ...(kind === 'approval-decisions' ? { decision, reason: reason.value } : {}),
    ...(kind === 'completion' ? { result: resultText.value, evidence_refs: [...selectedEvidence.value] } : {}) }
  const command = prepareCommand(props.action.id, props.session.user_id, kind, body)
  pending.value = command
  void transmit(command)
}
</script>

<template>
  <section class="action-panel" aria-labelledby="action-title" :aria-busy="busy">
    <header><h2 id="action-title">작업 제안·승인·수행</h2>
      <span v-if="action" class="badge">{{ statusLabels[action.status] }}</span></header>
    <p v-if="!action">아직 확정된 작업이 없습니다.</p>
    <template v-else>
      <p class="muted">작업 {{ action.id }}</p>
      <dl><dt>수행 범위</dt><dd>{{ action.scope }}</dd>
        <dt>담당자</dt><dd>{{ action.assignee_id }}</dd>
        <dt>기한 (한국 시간)</dt><dd>{{ date(action.due_at) }}</dd>
        <dt>완료 기준</dt><dd><ul><li v-for="criterion in action.completion_criteria" :key="criterion">{{ criterion }}</li></ul></dd>
        <dt>제안 근거</dt><dd><ul><li v-for="id in action.evidence_refs" :key="id">
          <a :href="`/api/v1/evidence/${encodeURIComponent(id)}`" target="_blank" rel="noopener noreferrer">{{ evidenceOptions.find(e => e.id === id)?.label ?? id }}</a>
        </li></ul></dd></dl>
      <p v-if="incident.review_required" role="status">후속 검토 필요: {{ incident.review_reason }}</p>
      <p>사건 상태: {{ incident.status }}</p>
      <div v-for="approval in actionApprovals" :key="approval.id" class="record">
        <strong>{{ approval.decision === 'APPROVE' ? '승인' : '반려' }}</strong>
        <p>{{ approval.reason }}</p><p class="muted">{{ approval.actor_id }} · {{ date(approval.created_at) }}</p>
      </div>
      <template v-if="canApprove">
        <label for="action-reason">승인·반려 사유</label>
        <textarea id="action-reason" v-model="reason" :disabled="busy || !!pending" required />
        <div class="buttons"><button :disabled="disabled || !reason.trim()" @click="submit('approval-decisions', 'APPROVE')">작업 승인</button>
          <button :disabled="disabled || !reason.trim()" @click="submit('approval-decisions', 'REJECT')">작업 반려</button></div>
      </template>
      <button v-if="canStart" :disabled="disabled" @click="submit('start')">작업 착수</button>
      <template v-if="canComplete">
        <label for="action-result">수행 결과</label>
        <textarea id="action-result" v-model="resultText" :disabled="busy || !!pending" required />
        <fieldset v-if="evidenceOptions.length" :disabled="busy || !!pending"><legend>추가 근거 (선택)</legend>
          <label v-for="item in evidenceOptions" :key="item.id" class="evidence-choice">
            <input v-model="selectedEvidence" type="checkbox" :value="item.id">{{ item.label }}</label></fieldset>
        <button :disabled="disabled || !resultText.trim()" @click="submit('completion')">작업 결과 제출</button>
      </template>
      <p v-if="!canApprove && !canStart && !canComplete && !blocked && action.status !== 'COMPLETED' && action.status !== 'REJECTED'">
        현재 책임자 또는 지정 작업 담당자만 해당 단계를 처리할 수 있습니다.</p>
      <div v-if="displayedResult" class="record"><strong>제출된 결과</strong><p>{{ displayedResult.text }}</p>
        <p class="muted">{{ displayedResult.author_id }} · {{ date(displayedResult.received_at) }}</p></div>
      <p v-if="action.status === 'COMPLETED'">작업 결과 제출과 사건의 최종 해결은 별도입니다.</p>
    </template>
    <p v-if="notice" role="status">{{ notice }}</p>
    <ul v-if="unmetRequirements.length" aria-label="검증 준비에 부족한 항목">
      <li v-for="item in unmetRequirements" :key="item">{{ requirementLabels[item] ?? '추가 확인 필요' }}</li>
    </ul>
    <p v-if="error" role="alert">{{ error }}</p>
    <button v-if="pending && !busy" @click="transmit(pending)">같은 요청으로 다시 확인</button>
    <button v-if="refreshRequired" :disabled="busy || !!pending" @click="reload">최신 내용 불러오기</button>
    <div v-if="reviewRequired && !pending"><p>새 정보가 있습니다. 입력은 유지되며 최신 내용을 확인한 뒤 다시 제출할 수 있습니다.</p>
      <button :disabled="busy || refreshRequired" @click="reviewRequired = false">최신 내용을 확인했습니다</button></div>
  </section>
</template>

<style scoped>
.action-panel { padding: 1.25rem; border: 1px solid #cbd5e1; border-radius: .75rem; background: #fff; color: #172033; }
header, .buttons { display: flex; gap: .75rem; align-items: center; flex-wrap: wrap; }
h2 { font-size: 1.1rem; margin: 0; } .badge { background: #e2e8f0; padding: .25rem .5rem; border-radius: .25rem; }
dl { display: grid; grid-template-columns: 7rem 1fr; gap: .6rem; } dt { font-weight: 600; } dd { margin: 0; overflow-wrap: anywhere; }
ul { padding-left: 1.2rem; margin: 0; } p { white-space: pre-wrap; overflow-wrap: anywhere; }
label { display: block; margin: .75rem 0 .3rem; } textarea { box-sizing: border-box; width: 100%; min-height: 6rem; font: inherit; padding: .65rem; }
button { font: inherit; padding: .6rem .85rem; margin-top: .65rem; cursor: pointer; } button:disabled { cursor: not-allowed; opacity: .55; }
.muted { color: #526174; font-size: .85rem; } .record { border-left: 3px solid #64748b; padding-left: .8rem; margin: 1rem 0; }
.evidence-choice { display: flex; gap: .5rem; } [role="alert"] { color: #a21c25; }
@media (max-width: 480px) { dl { grid-template-columns: 1fr; } dd { margin-bottom: .5rem; } }
</style>
