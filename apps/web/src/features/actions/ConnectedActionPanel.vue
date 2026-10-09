<script setup lang="ts">
import { computed } from 'vue';
import { api, ApiError, SessionChanged, uncertain } from '../../lib/api';
import { normalizeApiBasePath } from '../../lib/api-base';
import type { IncidentDetail, Me } from '../../lib/types';
import ActionPanel from './ActionPanel.vue';
import { CommandFailure, validateActionData } from './client';
import type { ActionView, ApprovalView, SendCommand } from './types';

const props = defineProps<{ detail: IncidentDetail & { approvals?: ApprovalView[] }; session: Me; refresh: () => Promise<void> }>();
const action = computed(() => {
  const value = props.detail.actions[0] as Partial<ActionView> | undefined;
  if (!value || !Number.isInteger(value.version) || typeof value.scope !== 'string'
    || typeof value.due_at !== 'string' || !Number.isFinite(Date.parse(value.due_at))
    || !Array.isArray(value.completion_criteria) || !Array.isArray(value.evidence_refs)) return null;
  return value as ActionView;
});
const result = computed(() => {
  const message = props.detail.messages.find(m => m.id === action.value?.result_message_id);
  return message && message.author_id && message.received_at ? { ...message, author_id: message.author_id, received_at: message.received_at } : null;
});
const evidenceOptions = computed(() => props.detail.evidence.map(e => ({ id: e.id, label: `${e.source_type} · ${e.excerpt.slice(0, 80)}` })));
const send: SendCommand = async command => {
  try {
    const response = await api.request(`/actions/${encodeURIComponent(command.actionId)}/${command.kind}`, 'POST', JSON.parse(command.serializedBody), command.key);
    return validateActionData(response.data, command.actionId);
  } catch (error) {
    if (error instanceof SessionChanged || error instanceof CommandFailure) throw error;
    throw new CommandFailure(error instanceof ApiError ? error.message : '응답을 확인하지 못했습니다. 같은 요청으로 다시 확인해 주세요.',
      error instanceof ApiError ? error.code : 'NETWORK', uncertain(error));
  }
};
</script>
<template>
  <div class="connected-action">
    <p v-if="detail.actions.length && !action" class="notice error" role="alert">작업 상세를 확인하지 못했습니다. 최신 사건을 다시 조회해 주세요.</p>
    <ActionPanel :action="action" :incident="detail" :session="session" :approvals="detail.approvals ?? []" :result="result"
      :evidence-options="evidenceOptions" :evidence-base-url="normalizeApiBasePath()" :send="send" :refresh="refresh" />
  </div>
</template>
