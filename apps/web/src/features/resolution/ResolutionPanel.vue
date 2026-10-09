<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { api, Command, errorMessage, SessionChanged } from '../../lib/api';
import type { IncidentDetail, Me } from '../../lib/types';
import { person, time } from '../../lib/presentation';
import CommandFeedback from '../../components/CommandFeedback.vue';
import type { Resolution, VerificationResult } from './types';
const props = defineProps<{ detail: IncidentDetail & { resolution?: Resolution }; session: Me; refresh: () => Promise<void> }>();
const notes = ref('');
const refs = ref<string[]>([]);
const reviewedVersion = ref(props.detail.version);
const command = ref(new Command());
const refreshing = ref(false);
const refreshError = ref('');
const savedNotice = ref('');
const needsRefresh = ref(false);
let generation = 0;
const resolution = computed(() => props.detail.resolution);
const stale = computed(() => reviewedVersion.value !== props.detail.version);
const locked = computed(() => command.value.busy || command.value.hasPending || refreshing.value || needsRefresh.value);
const currentOwner = computed(() => props.session.role === 'supervisor' && props.session.user_id === props.detail.owner_id);
const canReview = computed(() => props.detail.status === 'PENDING_VERIFICATION' && currentOwner.value);
const labels: Record<string, string> = {
  REVIEW_REQUIRED: '후속 검토 필요', INCIDENT_RESOLVED: '이미 해결된 사건', REQUIRED_ACTION_MISSING: '필수 작업 없음',
  MULTIPLE_MAIN_ACTIONS: '필수 작업 구성 확인 필요', ACTION_NOT_COMPLETED: '필수 작업 미완료',
  APPROVAL_INVALID: '유효한 작업 승인 필요', EVIDENCE_INVALID: '작업 근거 확인 필요', RESULT_MISSING: '완료 결과 확인 필요',
  COMPLETION_EVIDENCE_INVALID: '완료 보고 근거 확인 필요', REQUIRED_QUESTION_UNANSWERED: '필수 질문 답변 필요',
  READINESS_UNAVAILABLE: '검증 준비 조건 연결 대기', INVALID_RESOLUTION_INPUT: '저장된 업무 자료 확인 필요',
};
watch(() => [props.detail.id, props.session.user_id, props.session.shift_occurrence_id].join(':'), () => {
  generation++; command.value = new Command(); notes.value = ''; refs.value = [];
  reviewedVersion.value = props.detail.version; savedNotice.value = ''; refreshError.value = '';
  needsRefresh.value = false; refreshing.value = false;
});
watch(() => props.detail.version, value => {
  if (!notes.value && !refs.value.length && !command.value.hasPending && !command.value.busy) reviewedVersion.value = value;
});
onBeforeUnmount(() => { generation++; });
async function refreshReview() {
  if (refreshing.value || command.value.busy || command.value.canRetry) return;
  const current = generation;
  refreshing.value = true;
  try {
    await props.refresh();
    if (current !== generation) return;
    refreshError.value = ''; needsRefresh.value = false;
    if (command.value.canReview) command.value.reset();
    reviewedVersion.value = props.detail.version;
  } catch (error) { if (current === generation) refreshError.value = errorMessage(error); }
  finally { if (current === generation) refreshing.value = false; }
}
async function submit(decision?: 'RESOLVE' | 'RETURN') {
  if (decision && (locked.value || stale.value || !notes.value.trim() || !canReview.value ||
      (decision === 'RESOLVE' ? !resolution.value?.can_resolve : !resolution.value?.can_return))) return;
  const current = generation;
  try {
    const result = decision
      ? await command.value.send<VerificationResult>(api, `/incidents/${encodeURIComponent(props.detail.id)}/verification`,
          { decision, notes: notes.value, evidence_refs: [...refs.value], expected_version: reviewedVersion.value })
      : await command.value.send<VerificationResult>(api);
    if (!result || current !== generation) return;
    savedNotice.value = result.case_id ? '사람의 해결 확인과 해결 이력을 저장했습니다.' : '반려 사유를 저장했습니다. 완료 결과는 보존되며 후속 검토가 필요합니다.';
    notes.value = ''; refs.value = []; needsRefresh.value = true;
    await refreshReview();
  } catch (error) { if (error instanceof SessionChanged) return; /* Command retains exact request/key. */ }
}
</script>
<template>
  <section class="panel" aria-labelledby="resolution-heading">
    <span class="section-number">사람의 최종 확인</span><h2 id="resolution-heading">최종 검증·해결 이력</h2>
    <p v-if="savedNotice" class="notice success" role="status">{{ savedNotice }}</p>
    <p v-if="refreshError" class="notice error" role="alert">{{ refreshError }} 저장 성공 후에는 재조회만 수행합니다.</p>
    <button v-if="needsRefresh" type="button" :disabled="refreshing" @click="refreshReview">저장 결과 다시 조회</button>
    <template v-if="detail.status !== 'RESOLVED'">
      <p>작업 완료와 사건 해결은 별개입니다. 승인 내용·결과·근거를 확인한 현재 책임자가 최종 검토합니다.</p>
      <p v-if="!resolution" class="notice">검증 준비 조건을 확인하지 못했습니다.</p>
      <p v-else-if="resolution.ready" class="notice success">필수 업무 조건 충족 · 현재 책임자의 최종 확인이 필요합니다.</p>
      <ul v-else><li v-for="missing in resolution.unmet_requirements" :key="missing">{{ labels[missing] ?? missing }}</li></ul>
      <h3>완료 보고</h3>
      <p v-if="!detail.messages.some(m => m.kind === 'ACTION_RESULT')" class="muted">저장된 완료 결과가 없습니다.</p>
      <blockquote v-for="message in detail.messages.filter(m => m.kind === 'ACTION_RESULT')" :key="message.id">
        <p class="preserve-lines">{{ message.text }}</p><small>{{ person(message.author_id) }} · {{ time(message.received_at) }}</small>
      </blockquote>
      <p v-if="!currentOwner" class="muted">현재 책임자만 해결 확인·반려할 수 있습니다.</p>
      <p v-else-if="!canReview" class="muted">검증 대기 상태에서 최종 검토할 수 있습니다.</p>
      <form v-if="canReview" @submit.prevent="submit('RESOLVE')">
        <label for="verification-notes">검토 사유 (필수)</label>
        <textarea id="verification-notes" v-model="notes" rows="4" maxlength="20000" required :disabled="locked" />
        <label for="verification-evidence">추가 근거 (선택)</label>
        <select id="verification-evidence" v-model="refs" multiple :disabled="locked">
          <option v-for="evidence in detail.evidence" :key="evidence.id" :value="evidence.id">{{ evidence.source_type }} · {{ evidence.excerpt.slice(0, 70) }}</option>
        </select>
        <p class="muted">서버가 저장한 완료 보고는 기본 종료 근거로 포함됩니다.</p>
        <p v-if="stale" class="notice amber">작성 중 새 정보가 들어왔습니다. 최신 내용을 다시 확인해 주세요.</p>
        <button v-if="stale && !command.hasPending" type="button" :disabled="locked" @click="refreshReview">최신 내용 다시 확인</button>
        <div class="inline-control">
          <button class="primary" :disabled="locked || stale || !notes.trim() || !resolution?.can_resolve">해결 확인</button>
          <button type="button" :disabled="locked || stale || !notes.trim() || !resolution?.can_return" @click="submit('RETURN')">검증 반려</button>
        </div>
      </form>
      <p v-else-if="notes" class="notice preserve-lines">미전송 검토 사유: {{ notes }}</p>
    </template>
    <CommandFeedback :command="command" error-id="verification-error" @retry="submit()" @review="refreshReview" />
    <article v-if="resolution?.latest_verification" class="separated">
      <h3>{{ resolution.latest_verification.decision === 'RESOLVE' ? '해결 확인 기록' : '검증 반려 기록' }}</h3>
      <p class="preserve-lines">{{ resolution.latest_verification.notes }}</p>
      <p>{{ resolution.latest_verification.reviewer.display_name }} · {{ time(resolution.latest_verification.created_at) }}</p>
      <small>검토 버전 {{ resolution.latest_verification.checked_version }} → 반영 버전 {{ resolution.latest_verification.applied_version }}</small>
    </article>
    <details v-if="resolution?.case" class="separated">
      <summary>해결 당시 기록 보기</summary>
      <p>{{ resolution.case.reviewer?.display_name }} · {{ time(resolution.case.resolved_at) }}</p>
      <p class="identifier">Case {{ resolution.case.id }} · 해결 버전 {{ resolution.case.resolved_version }}</p>
      <p>해결 당시 보존된 원문이며 이후 변경되지 않습니다.</p>
      <blockquote v-for="message in resolution.case.snapshot_json.messages" :key="message.id"><small>{{ message.kind }}</small><p class="preserve-lines">{{ message.text }}</p></blockquote>
      <p>종료 근거 {{ resolution.case.evidence_refs.join(', ') }}</p>
    </details>
  </section>
</template>
