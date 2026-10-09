<script setup lang="ts">
import { computed } from 'vue';
import { person, time } from '../../lib/presentation';
import type { HandoverSummaryData } from './types';
const props = defineProps<{ summary: HandoverSummaryData | null; ownerId?: string; assigneeId?: string | null; assigneeIds?: string[] }>();
const emit = defineEmits<{ open: [id: string] }>();
const handoverId = computed(() => props.summary?.handover_id ?? props.summary?.id);
const assignees = computed(() => props.assigneeIds ?? (props.assigneeId ? [props.assigneeId] : []));
const isResolved = computed(() => props.summary?.is_resolved === true);
const requiresReAck = computed(() => !!props.summary?.is_stale
  || (!!props.summary?.previously_acknowledged && props.summary.ack_status !== 'ACKNOWLEDGED'));
const statusText = computed(() => isResolved.value ? '해결된 사건 · 과거 인계'
  : requiresReAck.value ? '변경된 내용 · 추가 인수 필요'
  : props.summary?.ack_status === 'ACKNOWLEDGED' ? '인수 완료' : '인수 확인 대기');
</script>
<template>
  <section v-if="summary" class="panel" aria-label="교대 인수 요약">
    <h2>교대 인수 요약</h2>
    <p><span class="badge" :class="{ amber: !isResolved && (summary.is_stale || summary.ack_status !== 'ACKNOWLEDGED') }">{{ statusText }}</span> <span v-if="summary.added_since_cutoff" class="badge">최초 인계 이후 추가됨</span></p>
    <p v-if="ownerId">현재 사건 책임자 {{ person(ownerId) }}</p>
    <p v-for="id in assignees" :key="id">유지된 작업 담당자 {{ person(id) }}</p>
    <p>내용 revision {{ summary.revision ?? '미수집' }} · 확인한 사건 버전 {{ summary.snapshot_version ?? '미수집' }} · ACK 적용 버전 {{ summary.ack_applied_version ?? '미인수' }}</p>
    <p v-if="summary.cutoff_at">최초 인계 기준 {{ time(summary.cutoff_at) }}</p>
    <p v-if="isResolved" class="muted">해결된 사건의 당시 인계 기록입니다. 이력은 조회할 수 있으며 새 인수는 할 수 없습니다.</p>
    <p v-else class="muted">인수 완료는 사건 해결이 아닙니다. AI 분석의 최신성과 인수 확인 여부는 별도로 판단합니다.</p>
    <a v-if="handoverId" :href="`/handovers/${encodeURIComponent(handoverId)}`" @click.prevent="emit('open', handoverId)">인계 내용과 변경 이력 확인</a>
  </section>
</template>
