<script setup lang="ts">
import { ApiError, errorMessage, type CommandState } from '../lib/api';
defineProps<{ command: CommandState; errorId: string }>();
defineEmits<{ retry: []; review: [] }>();
</script>
<template>
  <p v-if="command.busy" role="status">서버 응답을 기다리는 중입니다…</p>
  <div v-if="command.error" :id="errorId" class="notice error" role="alert">
    <strong>{{ errorMessage(command.error) }}</strong>
    <p v-if="command.canRetry">입력을 보존했습니다. 이전 요청의 같은 내용과 중복 방지 키로 결과를 확인할 수 있습니다.</p>
    <p v-else-if="command.error instanceof ApiError && command.error.code === 'INCIDENT_RESOLVED'">종료된 사건입니다. 입력을 복사해 새 사건으로 제보해 주세요.</p>
    <p v-else>입력을 보존했습니다. 최신 내용을 조회하고 검토한 뒤 새 명령을 제출해 주세요.</p>
    <div class="button-row">
      <button v-if="command.canRetry" type="button" :disabled="command.busy" @click="$emit('retry')">같은 요청 결과 확인</button>
      <button v-if="command.canReview" type="button" class="secondary" :disabled="command.busy" @click="$emit('review')">최신 내용 조회 · 새 요청 준비</button>
    </div>
  </div>
</template>
